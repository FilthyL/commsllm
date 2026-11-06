import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('comms', ROOT / 'scripts/comms.py')
comms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comms)


class CommsTests(unittest.TestCase):
    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = comms.main(list(args))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def setUp(self):
        self.cwd = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        os.chdir(self.temp.name)
        shutil.copytree(ROOT / 'comms', 'comms')

    def tearDown(self):
        os.chdir(self.cwd)
        self.temp.cleanup()

    def message(self, recipient='claude'):
        return self.call('msg', '--type', 'ready', '--from', 'codex', '--to', recipient,
                         '--task', 'cl-003', '--next', 'claude', '--round', '1')

    def test_round_trip(self):
        code, output, _ = self.message()
        self.assertEqual(code, 0)
        Path('comment').write_text(output)
        code, output, _ = self.call('parse', 'comment')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)['type'], 'ready')

    def test_last_header_unknown_keys(self):
        text = 'COMMS/1 type=task next=codex\nCOMMS/1 type=ready next=claude future=yes\n'
        self.assertEqual(comms.parse_header(text), {'type': 'ready', 'next': 'claude', 'future': 'yes'})
        self.assertEqual(comms.parse_header('no header'), {})
        Path('empty').write_text('no header')
        self.assertEqual(self.call('parse', 'empty')[:2], (1, '{}\n'))

    def test_invalid_enums(self):
        for flag in ['--type', '--from', '--to', '--next', '--verdict']:
            args = ['msg', '--type', 'ready', '--from', 'codex', '--to', 'claude', '--next', 'claude', '--task', 'cl-003']
            if flag in args:
                args[args.index(flag) + 1] = 'invalid'
            else:
                args += [flag, 'invalid']
            self.assertEqual(self.call(*args)[0], 2)

    def test_mention_rules(self):
        self.assertTrue(self.message('codex')[1].startswith('@codex\n'))
        self.assertFalse(self.message()[1].startswith('@'))
        config = Path('comms/config.yml')
        config.write_text(config.read_text().replace('claude_runner: session', 'claude_runner: action').replace('codex_runner: cloud', 'codex_runner: action'))
        self.assertTrue(self.message()[1].startswith('@claude\n'))
        self.assertFalse(self.message('codex')[1].startswith('@'))

    def test_real_lint(self):
        self.assertEqual(self.call('lint')[0], 0)

    def test_bad_task_fixtures(self):
        original = Path('comms/tasks/cl-001.md').read_text()
        for old, new, diagnostic in [('id: cl-001', 'id: cl-999', 'id must match'),
                                      ('scope:', 'missing_scope:', 'missing scope'),
                                      ('depends_on: []', 'depends_on: [cl-999]', 'unknown dependency')]:
            with self.subTest(diagnostic=diagnostic):
                Path('comms/tasks/cl-001.md').write_text(original.replace(old, new))
                code, _, err = self.call('lint')
                self.assertEqual(code, 1)
                self.assertIn(diagnostic, err)
                self.assertRegex(err, r'comms/tasks/cl-001.md:\d+:')

    def test_yaml_subset(self):
        values, _ = comms.yaml_subset('name: "a # title" # comment\nitems: [a, b]\nother:\n  - c\n  - d # comment\n')
        self.assertEqual(values, {'name': 'a # title', 'items': ['a', 'b'], 'other': ['c', 'd']})
        for text in ['nested:\n  key: value', 'nested: {key: value}']:
            with self.assertRaisesRegex(ValueError, 'nested maps'):
                comms.yaml_subset(text)

    def test_new_and_board(self):
        code, path, _ = self.call('new', '--title', 'Useful task', '--prefix', 'cl')
        self.assertEqual(code, 0)
        self.assertEqual(path.strip(), 'comms/tasks/cl-007.md')
        data, _, _ = comms.read_yaml(Path(path.strip()), True)
        self.assertEqual((data['status'], data['title']), ('draft', 'Useful task'))
        self.assertIn('cl-008', self.call('new', '--title', 'Next')[1])
        code, output, _ = self.call('board')
        self.assertEqual(code, 0)
        self.assertIn('| cl-001 |', output)
        self.assertIn('| cl-006 |', output)

    def test_literal_title_and_missing_config(self):
        title = r'Windows: C:\new\test'
        code, path, _ = self.call('new', '--title', title)
        self.assertEqual(code, 0)
        self.assertEqual(comms.read_yaml(Path(path.strip()), True)[0]['title'], title)
        Path('comms/config.yml').unlink()
        code, _, error = self.call('lint')
        self.assertEqual(code, 1)
        self.assertIn('comms/config.yml:1:', error)

    def test_help_examples(self):
        for command in ['msg', 'parse', 'lint', 'new', 'board']:
            code, output, _ = self.call(command, '--help')
            self.assertEqual(code, 0)
            self.assertIn('Example:', output)


if __name__ == '__main__':
    unittest.main()
