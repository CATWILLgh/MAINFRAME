import tempfile
import unittest
from pathlib import Path

from experiments.skill_reminder import codex


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workspace = self.root / 'project'
        self.workspace.mkdir()
        self.skills = {}
        for name in ('mainframe-testing', 'mainframe-python-backend', 'mainframe-go-backend',
                     'mainframe-typescript-backend', 'mainframe-frontend'):
            path = self.root / 'skills' / name / 'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text('fixture')
            self.skills[name] = str(path)
        self.config = {'workspace': str(self.workspace), 'skills': self.skills}
        self.state = self.root / 'state'

    def event(self, path='server/app.py', scope='parent'):
        p = self.workspace / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        return {'hook_event_name': 'PostToolUse', 'tool_name': 'Bash',
                'session_id': scope, 'tool_use_id': 'call',
                'tool_input': {'command': 'cat ' + str(p)},
                'tool_response': {'exit_code': 0}}

    def run_hook(self, data):
        return codex.respond(data, self.config, self.state)

    def test_route_and_native_nonblocking_shape(self):
        result = self.run_hook(self.event())
        self.assertEqual(set(result), {'hookSpecificOutput'})
        out = result['hookSpecificOutput']
        self.assertEqual(out['hookEventName'], 'PostToolUse')
        self.assertIn('mainframe-python-backend', out['additionalContext'])
        self.assertLess(len(out['additionalContext']), 350)

    def test_repeat_and_independent_recipient(self):
        self.assertIsNotNone(self.run_hook(self.event()))
        self.assertIsNone(self.run_hook(self.event('server/other.py')))
        self.assertIsNotNone(self.run_hook(self.event(scope='child')))

    def test_testing_precedes_language_and_no_audit(self):
        result = self.run_hook(self.event('server/tests/test_api.py'))
        self.assertIn('mainframe-testing', str(result))
        self.assertNotIn('test-audit', str(result))

    def test_ambiguous_generated_and_foreign_paths_are_silent(self):
        for path in ('script.py', 'src/utils.ts', 'node_modules/server/app.py', 'dist/server/app.py'):
            with self.subTest(path=path):
                self.assertIsNone(self.run_hook(self.event(path)))
        data = self.event()
        data['tool_input']['command'] = 'cat /some/other/server/app.py'
        self.assertIsNone(self.run_hook(data))
        self.assertFalse(self.state.exists())

    def test_shell_grammar_is_conservative(self):
        path = str(self.workspace / 'server/app.py')
        for command in ('cat server/app.py', 'echo '+path, 'cat '+path+'; pwd',
                        'cat '+path+' | head', 'cat "$(pwd)/server/app.py"',
                        'python3 -c "print(1)"', 'sed -i x '+path):
            self.assertEqual(codex.read_paths(command), [], command)
        self.assertEqual(codex.read_paths("sed -n '1,80p' '"+path+"'"), [path])
        self.assertEqual(codex.read_paths('head -n 30 '+path), [path])

    def test_missing_failed_unknown_disabled_no_state(self):
        for response in ({'exit_code': 1}, {}, 'unknown', {'exit_code': 0, 'isError': True}):
            data = self.event(); data['tool_response'] = response
            self.assertIsNone(self.run_hook(data))
        self.config['disabled'] = True
        self.assertIsNone(self.run_hook(self.event()))
        self.assertFalse(self.state.exists())

    def test_unavailable_skill_and_missing_identity(self):
        data = self.event(); del data['session_id']
        self.assertIsNone(self.run_hook(data))
        Path(self.skills['mainframe-python-backend']).unlink()
        self.assertIsNone(self.run_hook(self.event()))
        self.assertFalse(self.state.exists())

    def test_session_budget(self):
        self.assertIsNotNone(self.run_hook(self.event()))
        self.assertIsNotNone(self.run_hook(self.event('tests/test_api.py')))
        self.assertIsNone(self.run_hook(self.event('server/app.go')))

    def test_skill_read_suppresses_reminder_without_claiming_application(self):
        data = self.event()
        data['tool_input']['command'] = 'cat '+self.skills['mainframe-python-backend']
        self.assertIsNone(self.run_hook(data))
        self.assertIsNone(self.run_hook(self.event()))

    def test_symlink_escape_and_state_are_silent(self):
        outside = self.root / 'outside.py'; outside.touch()
        (self.workspace / 'server').mkdir()
        (self.workspace / 'server/app.py').symlink_to(outside)
        self.assertIsNone(self.run_hook(self.event()))
        self.state.symlink_to(self.root, target_is_directory=True)
        self.assertIsNone(self.run_hook(self.event('tests/test_api.py')))

    def test_react_requires_verified_profile(self):
        data = self.event('src/components/Card.tsx')
        self.assertIsNone(self.run_hook(data))
        self.config['react'] = True
        self.assertIn('mainframe-frontend', str(self.run_hook(data)))

    def test_mixed_domains_and_unknown_configuration_are_silent(self):
        a = self.event(); b = self.event('server/app.go')
        a['tool_input']['command'] += ' ' + b['tool_input']['command'][4:]
        self.assertIsNone(self.run_hook(a))
        self.assertIsNone(codex.respond(self.event(), {}, self.state))
        self.assertFalse(self.state.exists())

    def test_native_text_response_and_failure(self):
        data = self.event()
        data['tool_response'] = 'Wall time: 0.1 seconds\nProcess exited with code 1\nOutput:\nProcess exited with code 0'
        self.assertIsNone(self.run_hook(data))
        data['tool_response'] = 'Wall time: 0.1 seconds\nProcess exited with code 0\nOutput:\ntext'
        self.assertIsNotNone(self.run_hook(data))

    def test_concurrent_claims_and_expiry(self):
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import patch
        data = self.event()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.run_hook(data), range(8)))
        self.assertEqual(sum(x is not None for x in results), 1)
        with patch.object(codex.time, 'time', return_value=codex.time.time() + codex.TTL + 1):
            self.assertIsNotNone(self.run_hook(data))

    def test_process_protocol_missing_config_and_disabled(self):
        import json
        import subprocess
        import sys
        config = self.root / 'config.json'
        command = [sys.executable, '-B', str(Path(codex.__file__).resolve()), str(config), str(self.state)]
        payload = json.dumps(self.event())
        result = subprocess.run(command, input=payload, text=True, capture_output=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        config.write_text(json.dumps(self.config))
        result = subprocess.run(command, input=payload, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('additionalContext', json.loads(result.stdout)['hookSpecificOutput'])
        config.write_text(json.dumps({**self.config, 'disabled': True}))
        result = subprocess.run(command, input=payload, text=True, capture_output=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
