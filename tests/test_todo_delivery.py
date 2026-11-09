"""Real CLI routing and canonical guard integration in disposable homes."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from installer.codex import Codex
from installer.zcode import ZCode
from installer.core import encode_json, transact

ROOT = Path(__file__).resolve().parents[1]


class TodoDeliveryTests(unittest.TestCase):
    def exercise(self, product):
        with tempfile.TemporaryDirectory(prefix='mainframe-todo-entrypoint-') as tmp:
            base = Path(tmp).resolve()
            source, home = base / 'source', base / 'home'
            source.mkdir(); home.mkdir()
            for name in ('instructions', 'skills', 'agents', 'commands', 'hooks', 'plugins', 'installer'):
                shutil.copytree(ROOT / name, source / name, ignore=shutil.ignore_patterns('__pycache__'))
            for name in ('ADAPTATION.example.json', '.gitignore', 'install.py'):
                shutil.copy2(ROOT / name, source / name)
            credentials = source / 'shared/credentials'; credentials.mkdir(parents=True)
            for name in ('mainframe-secret', 'credentials-index.template.md'):
                shutil.copy2(ROOT / 'shared/credentials' / name, credentials / name)
            adapter = (Codex(source, home, version='0.153.4', surface='desktop') if product == 'codex'
                       else ZCode(source, home, version='3.11.2.6792', surface='desktop'))
            self.addCleanup(adapter.clean_event_state)
            changes, _ = adapter.plan(instructions_reviewed=True)
            transact(changes, adapter.journal, adapter.allowed)
            receipt = adapter.receipt()
            for name, record in list(receipt['files'].items()):
                if record['component'] in ('commands.todo', 'hooks.mainframe-todo-limits'):
                    Path(name).unlink()
                    del receipt['files'][name]
            if product == 'codex':
                registration = adapter.codex / 'hooks.json'
            else:
                registration = adapter.config
            config = json.loads(registration.read_bytes())
            groups = config['hooks'] if product == 'codex' else config['hooks']['events']
            groups['PreToolUse'] = [g for g in groups['PreToolUse'] if 'mainframe-todo-limits' not in json.dumps(g)]
            receipt['hook_groups']['PreToolUse'] = [g for g in receipt['hook_groups']['PreToolUse'] if 'mainframe-todo-limits' not in json.dumps(g)]
            registration.write_bytes(encode_json(config))
            adapter.receipt_path.write_bytes(encode_json(receipt))
            version = '0.165.0-alpha.1.2' if product == 'codex' else '3.17.1.9553'
            command = [sys.executable, '-B', str(source / 'install.py'), product]
            options = ['--surface', 'desktop', '--home', str(home), '--runtime-version', version, '--todo']
            for action in ('plan', 'apply', 'verify'):
                result = subprocess.run(command + [action] + options, cwd=source, text=True, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertNotIn('runtime_support', report)
            self.assertTrue(report['scoped_update_matches'])
            self.assertEqual(report['file_change_count'], 0)
            note = source / '.docs/todos/example.md'; note.parent.mkdir(parents=True)
            note.write_text('# Existing\n')
            if product == 'codex':
                inputs = {'command': '*** Begin Patch\n*** Update File: .docs/todos/example.md\n@@\n-# Existing\n+# ' + 'я' * 5001 + '\n*** End Patch\n'}
                tool = 'apply_patch'
            else:
                inputs = {'file_path': str(note), 'content': '# ' + 'я' * 5001}
                tool = 'Write'
            payload = {'hook_event_name': 'PreToolUse', 'tool_name': tool, 'tool_input': inputs,
                       'cwd': str(source), 'session_id': 'isolated-protocol', 'tool_use_id': 'edit-1'}
            result = subprocess.run([sys.executable, '-B', str(adapter.hooks / 'bridge.py'), 'mainframe-todo-limits', str(adapter.event_state)],
                                    input=json.dumps(payload), text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')
            self.assertEqual(note.read_text(), '# Existing\n')

    def test_codex_cli_and_canonical_guard(self):
        self.exercise('codex')

    def test_zcode_cli_and_canonical_guard(self):
        self.exercise('zcode')

    def test_unsupported_cli_selectors_fail_before_writes(self):
        for product, action, extra in [('codex', 'disable', []), ('minimax', 'plan', []),
                                       ('codex', 'plan', ['--skill', 'mainframe-sentry']),
                                       ('zcode', 'plan', ['--adopt-existing'])]:
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'install.py'), product, action,
                                     '--surface', 'desktop', '--todo', *extra], text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn('--todo requires', result.stderr)


if __name__ == '__main__':
    unittest.main()
