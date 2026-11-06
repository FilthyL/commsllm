#!/usr/bin/env python3
"""Stdlib COMMS/1 tools. Run from the repository root."""
import argparse
import json
from pathlib import Path
import re
import sys

ACTORS = ['claude', 'codex', 'owner', 'router']
TYPES = 'task ready review fixed question answer blocked status propose stop done ping pong notify'.split()
TASK_ENUMS = {'status': 'draft ready active done dropped'.split(), 'owner': ACTORS[:2],
              'reviewer': ACTORS[:2], 'size': ['S', 'M', 'L'], 'priority': ['P0', 'P1', 'P2']}
CONFIG_ENUMS = {'protocol': ['COMMS/1'], 'phase': ['0', '1', '2', '3'],
                'paused': ['true', 'false'], 'lead': ['claude'], 'builder': ['codex'],
                'claude_runner': ['session', 'action'], 'codex_runner': ['cloud', 'action'],
                'merge_policy': ['owner', 'lead']}
CONFIG_KEYS = set(CONFIG_ENUMS) | set('owner bus_pr max_review_rounds max_wip_per_agent max_diff_lines fix_forward_max_lines sla_minutes max_pings trusted_actors'.split())
TASK_KEYS = set('id title status owner reviewer goal size priority depends_on scope'.split())
TOKEN = r'[A-Za-z0-9_.#-]+'
HEADER = re.compile(r'^COMMS/1(?: +[A-Za-z_]+=' + TOKEN + r')+ *$', re.M)


def scalar(text):
    text = text.strip()
    if not text:
        return ''
    if text[0:1] in ('"', "'"):
        if text[-1:] != text[0]:
            raise ValueError('unterminated quoted scalar')
        return json.loads(text) if text[0] == '"' else text[1:-1]
    if ':' in text or text.startswith(('{', '|', '>')):
        raise ValueError('nested maps and multiline values are unsupported')
    return text


def yaml_subset(text):
    """Parse flat scalars/lists, preserving key line numbers for diagnostics."""
    values, lines, current = {}, {}, None
    for number, raw in enumerate(text.splitlines(), 1):
        # Comments are recognized outside quoted strings only.
        quote, end = None, len(raw)
        for index, char in enumerate(raw):
            if char in ('"', "'"):
                quote = None if quote == char else (char if quote is None else quote)
            elif char == '#' and quote is None:
                end = index
                break
        line = raw[:end].rstrip()
        if not line.strip():
            continue
        item = re.fullmatch(r'  - (.+)', line)
        if item:
            if current is None or not isinstance(values[current], list):
                raise ValueError(f'{number}: list item without a list key')
            values[current].append(scalar(item[1]))
            continue
        match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*):(?: +(.*))?', line)
        if not match:
            raise ValueError(f'{number}: nested maps or invalid YAML are unsupported')
        key, value = match[1], match[2] or ''
        if key in values:
            raise ValueError(f'{number}: duplicate key {key}')
        lines[key], current = number, key
        if value.startswith('['):
            if not value.endswith(']'):
                raise ValueError(f'{number}: unterminated inline list')
            values[key] = [scalar(x) for x in value[1:-1].split(',')] if value[1:-1].strip() else []
        else:
            values[key] = scalar(value) if value else []
    return values, lines


def read_yaml(path, task=False):
    text = path.read_text()
    if task:
        parts = text.split('---', 2)
        if len(parts) != 3 or parts[0].strip():
            raise ValueError('1: missing front matter')
        values, lines = yaml_subset(parts[1].lstrip('\n'))
        return values, {k: v + 1 for k, v in lines.items()}, parts[2]
    values, lines = yaml_subset(text)
    return values, lines, text


def parse_header(text):
    headers = list(HEADER.finditer(text))
    return dict(pair.split('=', 1) for pair in headers[-1][0].split()[1:]) if headers else {}


def lint():
    errors = []
    paths = sorted(p for p in Path('comms/tasks').glob('*.md') if p.name != '_TEMPLATE.md')
    ids = {p.stem for p in paths}
    for path in [Path('comms/config.yml')] + paths:
        task = path.suffix == '.md'
        try:
            data, lines, body = read_yaml(path, task)
        except (ValueError, OSError) as exc:
            errors.append(f'{path}:{exc}')
            continue
        def error(key, message):
            errors.append(f'{path}:{lines.get(key, 1)}: {message}')
        for key in (TASK_KEYS if task else CONFIG_KEYS):
            if key not in data:
                error(key, f'missing {key}')
            elif key not in ['scope', 'depends_on', 'trusted_actors'] and not isinstance(data[key], str):
                error(key, f'{key} must be a non-empty scalar')
        for key, allowed in (TASK_ENUMS if task else CONFIG_ENUMS).items():
            if key in data and data[key] not in allowed:
                error(key, f'invalid {key}: {data[key]}')
        if task:
            if data.get('id') != path.stem:
                error('id', 'id must match filename')
            if not re.fullmatch(r'(cl|cx)-[0-9]+', str(data.get('id', ''))):
                error('id', 'invalid task id')
            if not isinstance(data.get('scope'), list) or not data['scope'] or not all(data['scope']):
                error('scope', 'scope must be a non-empty list')
            deps = data.get('depends_on')
            if not isinstance(deps, list):
                error('depends_on', 'depends_on must be a list')
            elif any(dep not in ids for dep in deps):
                error('depends_on', 'unknown dependency')
            for section in ['Goal', 'Acceptance criteria', 'Verify']:
                if not re.search(r'^## ' + section + r'\s*$', body, re.M):
                    error('id', f'missing section {section}')
        else:
            for key in ['bus_pr', 'max_review_rounds', 'max_wip_per_agent', 'max_diff_lines', 'fix_forward_max_lines', 'sla_minutes', 'max_pings']:
                if not str(data.get(key, '')).isdigit():
                    error(key, f'{key} must be a nonnegative integer')
            if not isinstance(data.get('trusted_actors'), list) or not data['trusted_actors']:
                error('trusted_actors', 'trusted_actors must be a non-empty list')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'OK ({len(paths)} task files)')
    return 0


def input_text(path):
    return sys.stdin.read() if path == '-' else Path(path).read_text()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    msg = sub.add_parser('msg', epilog='Example: comms.py msg --type ready --from codex --to claude --task cl-003 --next claude')
    for key, choices in [('type', TYPES), ('from', ACTORS), ('to', ACTORS[:3] + ['all']), ('next', ACTORS[:3] + ['none'])]:
        msg.add_argument('--' + key, choices=choices, required=True)
    msg.add_argument('--task', required=True)
    msg.add_argument('--round', type=int)
    msg.add_argument('--verdict', choices=['approve', 'changes'])
    msg.add_argument('--re')
    msg.add_argument('--body-file')
    parse = sub.add_parser('parse', epilog='Example: comms.py parse comment.md')
    parse.add_argument('path', nargs='?', default='-')
    sub.add_parser('lint', epilog='Example: comms.py lint')
    new = sub.add_parser('new', epilog='Example: comms.py new --title "Add router" --prefix cx')
    new.add_argument('--title', required=True)
    new.add_argument('--owner', choices=ACTORS[:2], default='codex')
    new.add_argument('--prefix', choices=['cl', 'cx'], default='cl')
    sub.add_parser('board', epilog='Example: comms.py board')
    args = parser.parse_args(argv)
    try:
        if args.cmd == 'parse':
            header = parse_header(input_text(args.path))
            print(json.dumps(header))
            return 0 if header else 1
        if args.cmd == 'lint':
            return lint()
        if args.cmd == 'msg':
            fields = {k: str(v) for k, v in vars(args).items() if k not in ['cmd', 'body_file'] and v is not None}
            if not re.fullmatch(r'(cl-[0-9]+|cx-[0-9]+|goal-[0-9]+|bus)', args.task):
                parser.error('invalid task id')
            if any(not re.fullmatch(TOKEN, v) for v in fields.values()) or (args.round is not None and args.round < 0):
                parser.error('invalid header value')
            config, _, _ = read_yaml(Path('comms/config.yml'))
            if args.to == 'codex' and config.get('codex_runner') == 'cloud':
                print('@codex')
            if args.to == 'claude' and config.get('claude_runner') == 'action':
                print('@claude')
            print('COMMS/1 ' + ' '.join(f'{k}={v}' for k, v in fields.items()))
            if args.body_file:
                print(input_text(args.body_file).rstrip())
        if args.cmd == 'new':
            if '\n' in args.title or '\r' in args.title or not args.title.strip():
                parser.error('title must be a non-empty single line')
            directory = Path('comms/tasks')
            numbers = [int(p.stem.split('-')[1]) for p in directory.glob(args.prefix + '-*.md') if re.fullmatch(args.prefix + r'-[0-9]+', p.stem)]
            task_id = f'{args.prefix}-{max(numbers, default=0) + 1:03d}'
            template = (directory / '_TEMPLATE.md').read_text()
            for key, value in {'id': task_id, 'title': json.dumps(args.title), 'status': 'draft', 'owner': args.owner}.items():
                template = re.sub(r'^' + key + r':.*$', f'{key}: {value}', template, flags=re.M)
            path = directory / (task_id + '.md')
            with path.open('x') as stream:
                stream.write(template)
            print(path)
        if args.cmd == 'board':
            print('| id | title | status | owner | size | depends_on |\n|---|---|---|---|---|---|')
            tasks = [read_yaml(p, True)[0] for p in Path('comms/tasks').glob('*.md') if p.name != '_TEMPLATE.md']
            order = TASK_ENUMS['status']
            for task in sorted(tasks, key=lambda t: (order.index(t['status']), t['id'])):
                cells = [', '.join(task[k]) if isinstance(task[k], list) else task[k] for k in ['id', 'title', 'status', 'owner', 'size', 'depends_on']]
                print('| ' + ' | '.join(str(c).replace('|', '\\|').replace('\n', ' ') for c in cells) + ' |')
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    sys.exit(main())
