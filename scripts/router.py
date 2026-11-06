#!/usr/bin/env python3
"""Pure COMMS decisions plus a gh-only GitHub adapter; run route or watchdog."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote

try:
    from . import comms
except ImportError:
    import comms


def valid(header):
    return ({'type', 'from', 'to', 'task', 'next'} <= header.keys() and
            header['type'] in comms.TYPES and header['from'] in comms.ACTORS and
            header['to'] in ('codex', 'claude', 'owner', 'all') and
            header['next'] in ('codex', 'claude', 'owner', 'none'))


def route(header, config, author, labels=()):
    """Return argv actions without I/O or mutating the supplied state."""
    if config['paused'] == 'true' or author not in config['trusted_actors']:
        return []
    if not valid(header):
        return []
    kind, target = header['type'], header['next']
    state = {'task': 'building', 'ready': 'review', 'fixed': 'review',
             'blocked': 'blocked'}.get(kind)
    if kind == 'review':
        state = {'changes': 'changes', 'approve': 'approved'}.get(header.get('verdict'))
    remove = [x for x in labels if x.startswith('next:') or
              (x.startswith('state:') and (state or kind == 'done'))]
    add = [] if kind == 'done' else ['next:' + target] if target != 'none' else []
    if state:
        add.append('state:' + state)
    actions = [('labels', remove, add)]
    if target == 'owner' and kind != 'done':
        actions += [('owner', config['owner'])]
    recipient = header['to']
    if kind != 'done' and recipient in ('codex', 'claude') and config[recipient + '_runner'] == 'action':
        actions += [('dispatch', recipient + '-agent.yml')]
    return actions


def last_header(messages, config, task):
    """Chronological trusted envelopes, including native Codex review signals."""
    result, stamp = {}, ''
    for item in sorted(messages, key=lambda m: m['time']):
        if item['author'] not in config['trusted_actors']:
            continue
        header = comms.parse_header(item.get('body') or '')
        if not header and item['author'] == 'chatgpt-codex-connector[bot]':
            verdict = 'changes' if re.search(r'\bP[01]\b', item.get('body') or '') else 'approve' if item.get('content') == '+1' else None
            if verdict:
                header = dict(type='review', **{'from': 'codex'}, to='claude', task=task,
                              next='claude', verdict=verdict)
        if valid(header):
            result, stamp = header, item['time']
    return result, stamp


def watchdog(messages, activity, config, task, now):
    """Return (header, age minutes, actions); router pings do not count as replies."""
    header, stamp = last_header(messages, config, task)
    if not header:
        return header, 0, []
    target = header['next']
    # Shared owner login may represent either agent; semantic headers disambiguate it.
    logins = {config['owner']} | ({'chatgpt-codex-connector[bot]'} if target == 'codex' else {'claude[bot]'} if target == 'claude' else set())
    replies = [m['time'] for m in messages if m['author'] in logins and
               comms.parse_header(m.get('body') or '').get('from', target) == target]
    _, anchor = last_header([m for m in messages if
                             comms.parse_header(m.get('body') or '').get('from') != 'router'], config, task)
    active = max([anchor or stamp] + replies + [a['time'] for a in activity if a['author'] in logins])
    last_nudge = max([active] + [m['time'] for m in messages if m['author'] in config['trusted_actors'] and
                      comms.parse_header(m.get('body') or '').get('from') == 'router'])
    age = max(0, (now - datetime.fromisoformat(active.replace('Z', '+00:00'))).total_seconds() / 60)
    if config['paused'] == 'true' or target in ('none', 'owner') or header['type'] in ('done', 'stop', 'blocked') or (now - datetime.fromisoformat(last_nudge.replace('Z', '+00:00'))).total_seconds() < int(config['sla_minutes']) * 60:
        return header, age, []
    pings = 0
    for m in sorted(messages, key=lambda m: m['time'], reverse=True):
        h = comms.parse_header(m.get('body') or '')
        if m['time'] < active or m['author'] not in config['trusted_actors']:
            continue
        if h.get('type') == 'ping' and h.get('from') == 'router' and h.get('next') == target:
            pings += 1
        elif h:
            break
    blocked = pings >= int(config['max_pings'])
    recipient = 'owner' if blocked else target
    wake = '@codex\n' if recipient == 'codex' and config['codex_runner'] == 'cloud' else '@claude\n' if recipient == 'claude' and config['claude_runner'] == 'action' else ''
    body = wake + f'COMMS/1 type={"blocked" if blocked else "ping"} from=router to={recipient} task={task} next={recipient}\n'
    body += '## Blocker\nUnanswered watchdog pings.\n## Need\nOwner intervention.\n## Workaround tried\nSLA wake attempts.' if blocked else 'SLA expired; please resume this lane.'
    actions = [('comment', body)]
    if blocked:
        actions += [('owner', config['owner'])]
    elif config[target + '_runner'] == 'action':
        actions += [('dispatch', target + '-agent.yml')]
    return header, age, actions


def gh(*args):
    return subprocess.check_output(['gh', *map(str, args)], text=True)


def api(path):
    stream, pages = gh('api', '--paginate', path).strip(), []
    while stream:
        page, end = json.JSONDecoder().raw_decode(stream)
        pages.append(page)
        stream = stream[end:].lstrip()
    if pages and isinstance(pages[0], dict) and 'workflows' in pages[0]:
        return {'workflows': [w for page in pages for w in page['workflows']]}
    return [item for page in pages for item in page] if pages and isinstance(pages[0], list) else pages[0]


def snapshot(repo, number, is_pr=True):
    messages, activity = [], []
    endpoints = [f'issues/{number}/comments', f'issues/{number}/reactions']
    for endpoint in endpoints + ([f'pulls/{number}/reviews', f'pulls/{number}/comments'] if is_pr else []):
        for item in api(f'repos/{repo}/{endpoint}?per_page=100'):
            stamp = item.get('submitted_at') or item.get('created_at')
            if not stamp or not item.get('user'):
                continue
            entry = dict(author=item['user']['login'], time=stamp, body=item.get('body') or '', content=item.get('content'))
            messages.append(entry)
            if endpoint.endswith('/comments'):
                resource = 'pulls/comments' if endpoint.startswith('pulls/') else 'issues/comments'
                for reaction in api(f'repos/{repo}/{resource}/{item["id"]}/reactions?per_page=100'):
                    activity.append(dict(author=reaction['user']['login'], time=reaction['created_at']))
    activity += [m for m in messages if m.get('content')]
    if is_pr:
        branch = api(f'repos/{repo}/pulls/{number}')['head']['ref']
        for push in api(f'repos/{repo}/activity?ref={quote("refs/heads/" + branch, safe="")}&per_page=100'):
            if push['activity_type'] in ('push', 'force_push') and push.get('actor'):
                activity.append(dict(author=push['actor']['login'], time=push['timestamp']))
    return messages, activity


def apply(actions, repo, number):
    dispatched = False
    for action in actions:
        kind, *args = action
        if kind == 'labels':
            remove, add = args
            flags = [v for label in remove if label not in add for v in ('--remove-label', label)]
            flags += [v for label in add for v in ('--add-label', label)]
            if flags:
                gh('issue', 'edit', number, '--repo', repo, *flags)
        elif kind == 'owner':
            gh('issue', 'edit', number, '--repo', repo, '--add-label', 'needs:owner', '--add-assignee', args[0])
        elif kind == 'comment':
            gh('pr', 'comment', number, '--repo', repo, '--body', args[0])
        elif kind == 'dispatch':
            workflows = api(f'repos/{repo}/actions/workflows?per_page=100')
            if any(w['path'].endswith('/' + args[0]) for w in workflows['workflows']):
                gh('workflow', 'run', args[0], '--repo', repo, '-f', f'pr={number}')
                dispatched = True
            else:
                print(f'Workflow {args[0]} missing; continuing.')
    return dispatched


def main():
    config = comms.read_yaml(Path('comms/config.yml'))[0]
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    if config['paused'] == 'true' or (sys.argv[1] == 'route' and event['sender']['login'] not in config['trusted_actors']):
        return
    repo = os.environ['GITHUB_REPOSITORY']
    bus = int(config['bus_pr'])
    if bus and 'comms:pause' in [x['name'] for x in api(f'repos/{repo}/issues/{bus}')['labels']]:
        return
    if sys.argv[1] == 'route':
        number = (event.get('issue') or event['pull_request'])['number']
        prs = [api(f'repos/{repo}/issues/{number}')]
    else:
        prs = [p for p in api(f'repos/{repo}/pulls?state=open&per_page=100') if re.match(r'^\[(cl|cx)-', p['title'])]
    rows = []
    for pr in prs:
        number = pr['number']
        lane_config = dict(config, paused='true') if 'comms:pause' in [x['name'] for x in pr['labels']] else config
        if sys.argv[1] == 'route' and lane_config['paused'] == 'true':
            continue
        match = re.match(r'^\[((?:cl|cx)-\d+)\]', pr['title'])
        task = match[1] if match else 'bus'
        messages, activity = snapshot(repo, number, sys.argv[1] != 'route' or 'pull_request' in pr)
        header, stamp = last_header(messages, config, task)
        if sys.argv[1] == 'route':
            # An older event must never re-dispatch the current message.
            source = event.get('comment') or event.get('review') or {}
            seen = any(m['author'] in config['trusted_actors'] and
                       (h := comms.parse_header(m.get('body') or '')).get('from') == 'router' and
                       h.get('re') == str(source.get('id')) for m in messages)
            current = (source.get('submitted_at') or source.get('created_at')) == stamp and not seen
            actions = route(header, config, event['sender']['login'], [x['name'] for x in pr['labels']])
            if apply([a for a in actions if a[0] != 'dispatch' or current], repo, number):
                receipt = f'COMMS/1 type=status from=router to=all task={header["task"]} next={header["next"]} re={source["id"]}\nRunner dispatched.'
                gh('issue', 'comment', number, '--repo', repo, '--body', receipt)
        else:
            apply([a for a in route(header, lane_config, 'github-actions[bot]', [x['name'] for x in pr['labels']]) if a[0] != 'dispatch'], repo, number)
            header, age, actions = watchdog(messages, activity, lane_config, task, datetime.now(timezone.utc))
            apply(actions, repo, number)
            if actions and actions[0][0] == 'comment':
                header = comms.parse_header(actions[0][1])
                apply(route(header, lane_config, 'github-actions[bot]', [x['name'] for x in pr['labels']])[:1], repo, number)
            rows.append(f'| #{number} | {task} | {header.get("next", "none")} | {int(age)} min |')
    if sys.argv[1] == 'watchdog' and bus:
        board = subprocess.check_output([sys.executable, 'scripts/comms.py', 'board'], text=True)
        gh('pr', 'edit', bus, '--repo', repo, '--body', board + '\n| PR | task | next | last activity age |\n|---|---|---|---|\n' + '\n'.join(rows))


if __name__ == '__main__':
    main()
