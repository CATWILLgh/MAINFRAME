import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from installer import codex_skill_reminder as reminder

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('skill_detector',ROOT/'hooks/mainframe-skill-reminder.py')
detector=importlib.util.module_from_spec(spec);spec.loader.exec_module(detector)

class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.home=self.base/'.codex';self.project=self.base/'project'
        (self.home/'sessions').mkdir(parents=True);(self.project/'.git').mkdir(parents=True)
        self.state=self.base/'state';self.hooks=self.home/'mainframe/hooks'
        self.skill=self.home/'skills/mainframe-python-backend/SKILL.md'
        self.skill.parent.mkdir(parents=True);self.skill.write_text('---\nname: mainframe-python-backend\ndescription: Backend\n---\n')
        self.data={'session_id':'parent','tool_use_id':'nested','cwd':str(self.project),
                   'tool_input':{'command':'cat server/app.py'},'tool_response':{'exit_code':0}}
        self.transcript=self.home/'sessions/test.jsonl';self.data['transcript_path']=str(self.transcript)
        self.write_call({'cmd':'cat server/app.py','workdir':str(self.project)})

    def write_call(self,values,extra=''):
        record={'timestamp':datetime.now(timezone.utc).isoformat(),'type':'response_item',
                'payload':{'type':'function_call','name':'exec','call_id':'outer','arguments':'await tools.exec_command('+json.dumps(values)+')'+extra}}
        self.transcript.write_text(json.dumps(record)+'\n')

    def invoke(self):
        return reminder.advisory(self.data,self.state,self.hooks,detector)

    def test_relative_read_and_recipient_dedup(self):
        self.assertIn('mainframe-python-backend',self.invoke())
        self.assertIsNone(self.invoke())
        self.data['agent_id']='child'
        self.assertIn('mainframe-python-backend',self.invoke())

    def test_workdir_conflict_and_dynamic_are_unknown(self):
        self.write_call({'cmd':'cat server/app.py','workdir':str(self.project)}, '; await tools.exec_command({cmd:"cat server/app.py",workdir:"/other"})')
        self.assertIsNone(self.invoke());self.assertFalse(self.state.exists())
        self.transcript.write_text('')
        self.assertIsNone(self.invoke())
        self.assertEqual(reminder.literal_calls('tools.exec_command({cmd:"cat x",workdir: variable})'),[])
        self.assertEqual(reminder.literal_calls('tools.exec_command({...args,cmd:"cat x"})'),[])

    def test_literal_plus_dynamic_matching_call_rejects_hint(self):
        self.write_call({'cmd':'cat server/app.py','workdir':str(self.project)}, '; tools.exec_command({cmd:"cat server/app.py",workdir:other})')
        self.assertIsNone(self.invoke())
        self.assertFalse(self.state.exists())

    def test_no_default_cwd_guess(self):
        self.write_call({'cmd':'cat server/app.py'})
        self.assertIsNone(self.invoke());self.assertFalse(self.state.exists())

    def test_failure_and_native_disabled_skill(self):
        self.data['tool_response']={'exit_code':1,'output':'Process exited with code 0'}
        self.assertIsNone(self.invoke())
        self.data['tool_response']={'exit_code':0}
        (self.home/'config.toml').write_text('[[skills.config]]\npath = '+json.dumps(str(self.skill))+'\nenabled = false\n')
        self.assertIsNone(self.invoke());self.assertFalse(self.state.exists())

    def test_project_method_precedence_and_user_only(self):
        skill=self.project/'.agents/skills/demo-engineering/SKILL.md';skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: demo-engineering\ndescription: project\n---\n')
        (self.project/'AGENTS.md').write_text('Use demo-engineering for substantive project work.')
        self.assertIn('demo-engineering',self.invoke())
        self.assertIn('mainframe-python-backend',self.invoke())
        self.assertIsNone(self.invoke())

    def test_absolute_read_without_transcript(self):
        self.data.pop('transcript_path')
        self.data['tool_input']['command']='cat '+str(self.project/'server/app.py')
        self.assertIn('mainframe-python-backend',self.invoke())

    def test_foreign_path_and_catalog_absence(self):
        self.write_call({'cmd':'cat server/app.py','workdir':'/foreign'})
        self.assertIsNone(self.invoke());self.assertFalse(self.state.exists())
        self.write_call({'cmd':'cat server/app.py','workdir':str(self.project)})
        self.skill.unlink();self.assertIsNone(self.invoke())

    def test_project_disable_and_unreadable_config(self):
        config=self.project/'.codex/config.toml';config.parent.mkdir()
        config.write_text('[[skills.config]]\npath = '+json.dumps(str(self.skill))+'\nenabled = false\n')
        self.assertIsNone(self.invoke());self.assertFalse(self.state.exists())
        config.unlink()
        config.symlink_to(self.base/'missing')
        self.assertIsNone(self.invoke());self.assertFalse(self.state.exists())

    def test_indirect_call_invalidates_literal_source(self):
        self.write_call({'cmd':'cat server/app.py','workdir':str(self.project)}, '; tools.exec_command(args)')
        self.assertIsNone(self.invoke());self.assertFalse(self.state.exists())
        self.assertEqual(reminder.literal_calls('tools.exec_command({cmd:"cat x",workdir:"/p"});'*33),[])

    def test_budget_expiry_and_observed_skill_read(self):
        from unittest.mock import patch
        self.assertFalse(reminder.reserve(self.state, 'scope', 'already-read', seen=True))
        self.assertFalse(reminder.reserve(self.state, 'scope', 'already-read'))
        for name in ('first', 'second', 'third'):
            self.assertTrue(reminder.reserve(self.state, 'scope', name))
        self.assertFalse(reminder.reserve(self.state, 'scope', 'fourth'))
        self.assertTrue(reminder.reserve(self.state, 'other-recipient', 'fourth'))
        with patch.object(reminder.time, 'time', return_value=reminder.time.time()+reminder.TTL+1):
            self.assertTrue(reminder.reserve(self.state, 'scope', 'first'))
        self.assertEqual((self.state/'skill-reminders.sqlite3').stat().st_mode & 0o777, 0o600)

    def test_reading_skill_suppresses_later_suggestion(self):
        self.data['tool_input']['command']='cat '+str(self.skill)
        self.assertIsNone(self.invoke())
        self.data['tool_input']['command']='cat server/app.py'
        self.assertIsNone(self.invoke())

    def test_native_raw_output_is_not_a_status_envelope(self):
        self.data['tool_response']='ordinary file content'
        self.assertIn('mainframe-python-backend', self.invoke())

    def test_raw_skill_output_does_not_prove_successful_read(self):
        self.data['tool_response']='Process exited with code 0\nOutput:\nnot a native status'
        self.data['tool_input']['command']='cat '+str(self.skill)
        self.assertIsNone(self.invoke())
        self.data['tool_input']['command']='cat server/app.py'
        self.assertIn('mainframe-python-backend', self.invoke())
