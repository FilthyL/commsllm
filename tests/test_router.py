from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from scripts import router

CONFIG = dict(paused='false', trusted_actors=['FilthyL', 'github-actions[bot]', 'chatgpt-codex-connector[bot]'],
              owner='FilthyL', codex_runner='cloud', claude_runner='session', sla_minutes='30', max_pings='2')


def header(kind='task', **fields):
    return dict(type=kind, **{'from': 'claude'}, to='codex', task='cl-004', next='codex', **fields)


def message(minute, kind='task', author='FilthyL', **fields):
    h = header(kind, **fields)
    return dict(time=f'2026-11-06T00:{minute:02d}:00Z', author=author,
                body='COMMS/1 ' + ' '.join(f'{k}={v}' for k, v in h.items()))


class RouterTests(unittest.TestCase):
    def test_mapping(self):
        for kind, verdict, state in [('task', '', 'building'), ('ready', '', 'review'), ('fixed', '', 'review'),
                                     ('review', 'changes', 'changes'), ('review', 'approve', 'approved'), ('blocked', '', 'blocked')]:
            with self.subTest(kind=kind, verdict=verdict):
                actions = router.route(header(kind, verdict=verdict), CONFIG, 'FilthyL', ['next:claude', 'state:review', 'task'])
                self.assertEqual(actions[0], ('labels', ['next:claude', 'state:review'], ['next:codex', 'state:' + state]))
        self.assertEqual(router.route(header('done'), CONFIG, 'FilthyL', ['state:review', 'next:codex'])[0],
                         ('labels', ['state:review', 'next:codex'], []))

    def test_skips_owner_and_dispatch(self):
        self.assertEqual(router.route(header(), dict(CONFIG, paused='true'), 'FilthyL'), [])
        self.assertEqual(router.route(header(), CONFIG, 'stranger'), [])
        self.assertEqual(router.route({}, CONFIG, 'FilthyL'), [])
        h = dict(header(), next='owner')
        self.assertIn(('owner', 'FilthyL'), router.route(h, CONFIG, 'FilthyL'))
        for actor in ('codex', 'claude'):
            self.assertIn(('dispatch', actor + '-agent.yml'), router.route(dict(h, to=actor), dict(CONFIG, **{actor + '_runner': 'action'}), 'FilthyL'))

    def test_last_trusted_header_and_native_reviews(self):
        items = [message(0), message(10, 'done', author='stranger')]
        self.assertEqual(router.last_header(items, CONFIG, 'cl-004')[0]['type'], 'task')
        native = dict(time='2026-11-06T00:20:00Z', author='chatgpt-codex-connector[bot]', body='![P1 Badge] finding')
        self.assertEqual(router.last_header(items + [native], CONFIG, 'cl-004')[0]['verdict'], 'changes')
        self.assertEqual(router.last_header([dict(native, body='', content='+1')], CONFIG, 'cl-004')[0]['verdict'], 'approve')
        self.assertEqual(router.last_header([dict(native, body='P2 suggestion')], CONFIG, 'cl-004')[0], {})

    def test_watchdog_ping_escalation_and_activity(self):
        items = [message(0)]
        def check(hour, minute=0, activity=(), config=CONFIG):
            return router.watchdog(items, activity, config, 'cl-004', datetime(2026, 11, 6, hour, minute, tzinfo=timezone.utc))[2]
        self.assertEqual(check(0, 29), [])
        first = check(0, 30)
        self.assertIn('@codex\nCOMMS/1 type=ping', first[0][1])
        items.append(dict(time='2026-11-06T00:30:00Z', author='github-actions[bot]', body=first[0][1]))
        self.assertEqual(check(0, 45), [])
        second = check(1)
        items.append(dict(time='2026-11-06T01:00:00Z', author='github-actions[bot]', body=second[0][1]))
        self.assertIn('type=blocked', check(1, 30)[0][1])
        self.assertIn(('owner', 'FilthyL'), check(1, 30))
        self.assertEqual(check(1, 30, config=dict(CONFIG, paused='true')), [])
        for author in ('FilthyL', 'chatgpt-codex-connector[bot]'):
            self.assertEqual(check(1, 30, [dict(author=author, time='2026-11-06T01:20:00Z')]), [])
        items.append(dict(time='2026-11-06T01:10:00Z', author='FilthyL', body='Resuming'))
        self.assertIn('type=ping', check(2)[0][1])
        self.assertNotIn('type=blocked', check(2)[0][1])

    @patch.object(router, 'gh')
    @patch.object(router, 'api', return_value={'workflows': []})
    def test_missing_runner_continues(self, api, gh):
        router.apply([('dispatch', 'codex-agent.yml'), ('owner', 'FilthyL')], 'FilthyL/commsllm', 6)
        self.assertEqual(gh.call_args.args[:3], ('issue', 'edit', 6))


class AdapterTests(unittest.TestCase):
    @patch.object(router, 'gh', return_value='[{"id": 1}]\n[{"id": 2}]')
    def test_pagination(self, gh):
        self.assertEqual(router.api('items'), [{'id': 1}, {'id': 2}])
        gh.return_value = '{"workflows": [{"path": "first"}]}\n{"workflows": [{"path": "last"}]}'
        self.assertEqual(len(router.api('workflows')['workflows']), 2)

    @patch.object(router, 'api')
    def test_pushes_and_reactions(self, api):
        api.side_effect = [[dict(id=1, user={'login': 'FilthyL'}, created_at='comment-time', body='working')],
                           [dict(user={'login': 'FilthyL'}, created_at='reaction-time')], [], [], [],
                           {'head': {'ref': 'task/cl-004-router'}},
                           [dict(activity_type='push', actor={'login': 'FilthyL'}, timestamp='push-time')]]
        messages, activity = router.snapshot('FilthyL/commsllm', 6)
        self.assertEqual(messages[0]['body'], 'working')
        self.assertEqual([a['time'] for a in activity], ['reaction-time', 'push-time'])
        self.assertIn('ref=refs%2Fheads%2Ftask%2Fcl-004-router', api.call_args.args[0])

    @patch.object(router, 'gh')
    @patch.object(router, 'api', return_value={'workflows': [{'path': '.github/workflows/codex-agent.yml'}]})
    def test_dispatch_and_safe_arguments(self, api, gh):
        self.assertTrue(router.apply([('dispatch', 'codex-agent.yml')], 'FilthyL/commsllm', 6))
        self.assertEqual(gh.call_args.args, ('workflow', 'run', 'codex-agent.yml', '--repo', 'FilthyL/commsllm', '-f', 'pr=6'))
        body = '$(touch /tmp/unwanted) `false` "quote"\ntext'
        router.apply([('comment', body)], 'FilthyL/commsllm', 6)
        self.assertEqual(gh.call_args.args[-1], body)
