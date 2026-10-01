"""Checkpoint advice through the five maintained native output contracts."""
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from installer import codex_hook, zcode_hook, cline_hook, minimax_hook, antigravity_hook

ROOT = Path(__file__).resolve().parents[1]
NAME = 'mainframe-commit-checkpoint'
CONTENT = 'work\n' * 2100


class CheckpointAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mainframe-checkpoint-native-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.workspace = self.base / 'workspace'; self.workspace.mkdir()
        subprocess.run(['git', '-C', str(self.workspace), 'init', '-q'], check=True)
        self.file = self.workspace / 'work.txt'; self.file.write_text(CONTENT)
        self.support = self.base / 'support'; (self.support / 'detectors').mkdir(parents=True)
        shutil.copyfile(ROOT / 'hooks' / (NAME + '.py'), self.support / 'detectors' / (NAME + '.py'))
        self.state = self.base / 'state'; self.state.mkdir(mode=0o700)

    def native(self, bridge, payload):
        with patch.object(bridge, 'ROOT', self.support):
            return bridge.dispatch(NAME, self.state, io.BytesIO(json.dumps(payload).encode()))

    def codex_payload(self):
        return {'hook_event_name': 'PostToolUse', 'session_id': 'session', 'tool_use_id': 'edit',
                'cwd': str(self.workspace), 'tool_name': 'apply_patch', 'tool_response': {'ok': True},
                'tool_input': {'patch': '*** Begin Patch\n*** Add File: work.txt\n' + '+work\n' * 2100 + '*** End Patch\n'}}

    def zcode_payload(self):
        return {'hook_event_name': 'PostToolUse', 'session_id': 'session', 'tool_use_id': 'edit',
                'cwd': str(self.workspace), 'tool_name': 'Write', 'tool_response': {'ok': True},
                'tool_input': {'file_path': str(self.file), 'content': CONTENT}}

    def test_codex_success_advises_once_failed_and_stop_are_silent(self):
        payload = self.codex_payload()
        result = self.native(codex_hook, payload)
        self.assertIn('Commit checkpoint', result['hookSpecificOutput']['additionalContext'])
        self.assertNotIn('permissionDecision', result['hookSpecificOutput'])
        self.assertIsNone(self.native(codex_hook, payload))
        self.assertIsNone(self.native(codex_hook, {**payload, 'hook_event_name': 'Stop'}))
        self.assertIsNone(self.native(codex_hook, {**payload, 'tool_use_id': 'failed', 'tool_response': {'isError': True}}))

    def test_zcode_success_advises_once_failure_and_pre_are_silent(self):
        payload = self.zcode_payload()
        result = self.native(zcode_hook, payload)
        self.assertIn('Commit checkpoint', result['hookSpecificOutput']['additionalContext'])
        self.assertIsNone(self.native(zcode_hook, payload))
        self.assertIsNone(self.native(zcode_hook, {**payload, 'hook_event_name': 'PostToolUseFailure'}))
        self.assertIsNone(self.native(zcode_hook, {**payload, 'hook_event_name': 'PreToolUse'}))

    def test_disabled_codex_and_zcode_create_no_checkpoint_state(self):
        (self.support / ('.disabled-' + NAME)).write_text('')
        for bridge, payload in [(codex_hook, self.codex_payload()), (zcode_hook, self.zcode_payload())]:
            self.assertIsNone(self.native(bridge, payload))
        self.assertEqual(list(self.state.iterdir()), [])

    def test_cross_workspace_and_missing_identity_are_silent(self):
        payload = self.codex_payload()
        payload['tool_input']['patch'] = payload['tool_input']['patch'].replace('work.txt', str(self.base / 'outside.txt'))
        self.assertIsNone(self.native(codex_hook, payload))
        payload = self.zcode_payload(); del payload['tool_use_id']
        self.assertIsNone(self.native(zcode_hook, payload))
        self.assertEqual(list(self.state.iterdir()), [])

    def test_cline_native_patch_delivers_context_without_cancelling(self):
        payload = {'hookName': 'PostToolUse', 'taskId': 'task',
                   'workspaceRoots': [str(self.workspace)], 'workspaceInfo': {'rootPath': str(self.workspace)},
                   'tool_result': {'id': 'edit', 'name': 'apply_patch',
                                   'input': {'input': self.codex_payload()['tool_input']['patch']}},
                   'postToolUse': {'success': True}}
        with patch.object(cline_hook, 'HOOKS', self.support):
            result = cline_hook.post_tool(payload, self.state)
            self.assertIn('Commit checkpoint', result['contextModification'])
            self.assertFalse(result.get('cancel', False))
            self.assertIsNone(cline_hook.post_tool(payload, self.state))
            failed = {**payload, 'tool_result': {**payload['tool_result'], 'id': 'failed'}, 'postToolUse': {'success': False}}
            self.assertIsNone(cline_hook.post_tool(failed, self.state))
            (self.support / ('.disabled-' + NAME)).write_text('')
            next_payload = {**payload, 'tool_result': {**payload['tool_result'], 'id': 'next'}}
            self.assertIsNone(cline_hook.post_tool(next_payload, self.state))

    def test_minimax_context_and_disable_are_independent_of_quality(self):
        payload = {**self.zcode_payload(), 'tool_name': 'write'}
        with patch.object(minimax_hook, 'HOOKS', self.support), patch.object(minimax_hook, 'DETECTORS', self.support / 'detectors'):
            result = minimax_hook.post_tool(payload, self.state)
            self.assertIn('Commit checkpoint', result['hookSpecificOutput']['additionalContext'])
            self.assertNotIn('permissionDecision', result['hookSpecificOutput'])
            self.assertIsNone(minimax_hook.post_tool(payload, self.state))
            self.assertIsNone(minimax_hook.post_tool({**payload, 'tool_use_id': 'failed', 'tool_response': {'isError': True}}, self.state))
            (self.support / ('.disabled-' + NAME)).write_text('')
            self.assertIsNone(minimax_hook.post_tool({**payload, 'tool_use_id': 'next'}, self.state))

    def test_antigravity_large_edit_uses_post_context_not_stop_continuation(self):
        transcript = self.base / 'antigravity/brain/session/.system_generated/logs/transcript.jsonl'
        transcript.parent.mkdir(parents=True)
        transcript.write_text(json.dumps({'step_index': 1, 'created_at': '2026-10-01T12:00:00Z',
            'tool_calls': [{'name': 'write_to_file', 'args': {'TargetFile': str(self.file), 'CodeContent': CONTENT, 'Overwrite': False}}]}) + '\n')
        payload = {'conversationId': 'session', 'workspacePaths': [str(self.workspace)],
                   'transcriptPath': str(transcript), 'invocationNum': 1, 'executionNum': 1}
        with patch.object(antigravity_hook, 'ROOT', self.support):
            result = antigravity_hook.post_invocation(payload, self.state)
            self.assertIn('Commit checkpoint', result['injectSteps'][0]['ephemeralMessage'])
            self.assertEqual(antigravity_hook.post_invocation(payload, self.state), {})
            self.assertEqual(antigravity_hook.stop(payload, self.state), {'decision': 'stop'})
            (self.support / ('.disabled-' + NAME)).write_text('')
            self.assertEqual(antigravity_hook.post_invocation(payload, self.state), {})


if __name__ == '__main__': unittest.main()
