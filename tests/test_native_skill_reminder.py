import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from installer import zcode_hook

ROOT = Path(__file__).resolve().parents[1]


class NativeSkillReminderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.project = self.home / 'project'
        (self.project / '.git').mkdir(parents=True)
        self.state = self.home / 'state'
        self.payload = {'cwd': str(self.project), 'session_id': 'one', 'tool_use_id': 'read',
                        'hook_event_name': 'PostToolUse', 'tool_name': 'Read', 'tool_input': {}}

    def prepare(self, base, skills):
        (base / 'detectors').mkdir(parents=True)
        for target, source in [('skill_reminder.py', 'codex_skill_reminder.py'),
                               ('native_skill_reminder.py', 'native_skill_reminder.py'),
                               ('skill_profiles.py', 'skill_profiles.py')]:
            shutil.copyfile(ROOT / 'installer' / source, base / target)
        shutil.copyfile(ROOT / 'hooks/mainframe-skill-reminder.py', base / 'detectors/mainframe-skill-reminder.py')
        skill = skills / 'mainframe-testing/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: mainframe-testing\ndescription: testing\n---\n')
        (self.project / 'test_example.py').write_text('def test_sample(): pass\n')
        return skill

    def test_zcode_wire_dedup_awareness_disable(self):
        base = self.home / '.zcode/mainframe/hooks'
        skill = self.prepare(base, self.home / '.zcode/skills')
        data = dict(self.payload, tool_input={'file_path': str(self.project / 'test_example.py')})
        with patch.object(zcode_hook, 'ROOT', base):
            def call():
                return zcode_hook.dispatch('mainframe-skill-reminder', self.state, io.BytesIO(json.dumps(data).encode()))
            self.assertIn('mainframe-testing', call()['hookSpecificOutput']['additionalContext'])
            self.assertIsNone(call())
            data['session_id'] = 'two'; data['tool_input'] = {'file_path': str(skill)}
            self.assertIsNone(call())
            data['tool_input'] = {'file_path': str(self.project / 'test_example.py')}
            self.assertIsNone(call())
            (base / '.disabled-mainframe-skill-reminder').touch(); data['session_id'] = 'three'
            self.assertIsNone(call())

    def test_zcode_failed_read_does_not_send_or_consume_budget(self):
        base = self.home / '.zcode/mainframe/hooks'
        self.prepare(base, self.home / '.zcode/skills')
        data = dict(self.payload,
                    tool_input={'file_path': str(self.project / 'test_example.py')},
                    tool_response={'isError': True})
        with patch.object(zcode_hook, 'ROOT', base):
            def call():
                return zcode_hook.dispatch('mainframe-skill-reminder', self.state, io.BytesIO(json.dumps(data).encode()))

            self.assertIsNone(call())
            data['tool_response'] = {'isError': False}
            self.assertIn('mainframe-testing', call()['hookSpecificOutput']['additionalContext'])
