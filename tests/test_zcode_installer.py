import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from installer.zcode import (ZCode, HOOK_NAMES, SHELL_HOOK_NAMES,
    _is_validated_hook_config_update, _legacy_hook_registration,
    role_body, command_body)
from installer.core import Conflict, transact, restore
from installer.runtime import runtime_bin

ROOT = Path(__file__).resolve().parents[1]


class ZCodeInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mainframe-zcode-install-test-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.source = base / "source"
        self.source.mkdir()
        for name in ('instructions', 'skills', 'agents', 'commands', 'hooks', 'installer'):
            shutil.copytree(ROOT / name, self.source / name, ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('ADAPTATION.example.json', '.gitignore', 'install.py'):
            shutil.copyfile(ROOT / name, self.source / name)
        credentials = self.source / 'shared/credentials'
        credentials.mkdir(parents=True)
        for name in ('mainframe-secret', 'credentials-index.template.md'):
            shutil.copyfile(ROOT / 'shared/credentials' / name, credentials / name)
        self.home = base / "home with 'quotes'"
        self.home.mkdir()
        self.adapter = ZCode(self.source, self.home, version='3.11.2.6792')
        self.addCleanup(self.adapter.clean_event_state)

    def apply(self, reviewed=False):
        changes, report = self.adapter.plan(reviewed)
        self.assertIsNone(report['instruction_review'])
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.adapter.clean_directories(self.adapter.receipt())
        return report

    def test_fresh_delivery_converges_without_native_calls(self):
        _, report = self.adapter.plan()
        self.assertTrue(report['changes'])
        self.assertFalse(self.adapter.zcode.exists())
        self.apply()
        _, second = self.adapter.plan()
        self.assertEqual(second['changes'], [])
        state = json.loads(self.adapter.state_path.read_text())
        self.assertEqual(state['components']['commands']['mainframe-project-skill']['delivery'], 'installed')
        self.assertEqual(state['components']['commands']['mainframe-project-skill']['verification'], 'pending')
        self.assertEqual(state['components']['hooks']['mainframe-code-quality']['delivery'], 'unsupported')
        self.assertNotIn('status', state['components']['commands']['mainframe-project-skill'])
        self.assertFalse((self.adapter.commands / 'mainframe-init.md').read_text().find('MAINFRAME OPTIONAL BLOCK') >= 0)
        self.assertIn('disallowedTools:', (self.adapter.agents / 'mainframe-researcher.md').read_text())
        automation_skill = self.adapter.skills / 'mainframe-tickets-find/SKILL.md'
        self.assertTrue(automation_skill.is_file())
        self.assertIn('explicitly request /mainframe-tickets-find', automation_skill.read_text())
        self.assertFalse((self.adapter.skills / 'mainframe-tickets-implement').exists())
        self.assertFalse((self.home / '.agents').exists())
        self.assertEqual(
            self.adapter.plan()[1]['next_actions'],
            ['In ZCode Settings, refresh Skills once, then open a new Desktop session to load the delivered registrations.'],
        )

    def test_native_role_settings_and_command_newline_normalization_are_preserved(self):
        self.apply()
        name = 'mainframe-typescript-backend-engineer'
        role = self.adapter.agents / (name + '.md')
        source = (self.source / 'agents' / (name + '.md')).read_text()
        settings = {
            'color': 'yellow',
            'model': 'account:zai-individual-coding-plan/GLM-5.3-Flash',
            'thoughtLevel': 'low',
            'injectAgentsMd': False,
        }
        role.write_bytes(role_body(source, name, settings))
        command = self.adapter.commands / 'mainframe-tickets-find.md'
        command.write_bytes(command.read_bytes().rstrip(b'\n'))

        self.apply()
        body = role.read_text()
        self.assertIn('model: "account:zai-individual-coding-plan/GLM-5.3-Flash"', body)
        self.assertIn('thoughtLevel: low', body)
        self.assertIn('injectAgentsMd: false', body)
        self.assertFalse(command.read_bytes().endswith(b'\n'))
        self.assertEqual(self.adapter.plan()[1]['changes'], [])

        role.write_text(body + '\nChanged role body.\n')
        with self.assertRaisesRegex(Conflict, 'was edited'):
            self.adapter.plan()

    def test_shell_guards_and_quality_lifecycle_are_registered_with_explicit_limits(self):
        report = self.apply()
        cfg = json.loads(self.adapter.config.read_text())
        events = cfg['hooks']['events']
        self.assertEqual(set(events), {
            'PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'Stop', 'SessionStart'
        })
        self.assertEqual(len(events['PreToolUse'][0]['hooks']), 1)
        self.assertEqual(events['PreToolUse'][0]['hooks'][0]['args'][-2], 'mainframe-pre-shell')
        self.assertEqual(events['PreToolUse'][0]['hooks'][0]['args'][-3], str(runtime_bin(self.home)))
        self.assertEqual(events['PreToolUse'][1]['matcher'], 'Write|Edit')
        self.assertEqual(events['PreToolUse'][1]['hooks'][0]['args'][-2], 'mainframe-code-quality')
        self.assertEqual(events['PostToolUse'][0]['matcher'], 'Write|Edit')
        self.assertEqual(events['PostToolUse'][0]['hooks'][0]['args'][-2], 'mainframe-code-quality')
        self.assertEqual(events['PostToolUse'][0]['hooks'][0]['args'][-3], str(runtime_bin(self.home)))
        self.assertEqual(events['PostToolUseFailure'][0]['matcher'], 'Write|Edit')
        self.assertEqual(events['PostToolUseFailure'][0]['hooks'][0]['args'][-2], 'mainframe-code-quality')
        self.assertNotIn('matcher', events['Stop'][0])
        self.assertEqual(events['Stop'][0]['hooks'][0]['args'][-2], 'mainframe-code-quality')
        start = events['SessionStart'][0]
        self.assertEqual(start['matcher'], 'startup|clear|compact|resume')
        self.assertEqual(start['hooks'][0]['args'][-2], 'mainframe-destructive-operations')
        self.assertIn('subagent', report['hook_scope'])
        state = json.loads(self.adapter.state_path.read_text())
        self.assertEqual(state['components']['hooks']['mainframe-commit-secrets']['delivery'], 'installed')
        self.assertEqual(state['components']['hooks']['mainframe-destructive-operations']['delivery'], 'installed')
        for name in ('mainframe-code-quality', 'mainframe-fallow-quality'):
            row = state['components']['hooks'][name]
            self.assertEqual(row['delivery'], 'unsupported')
            self.assertIn('Stop', row['reason'])
            self.assertNotIn('verification', row)

    def test_bounded_update_accepts_only_the_exact_runtime_path_upgrade(self):
        self.apply()
        after = json.loads(self.adapter.config.read_text())
        before = json.loads(self.adapter.config.read_text())
        for groups in before['hooks']['events'].values():
            for group in groups:
                for index, callback in enumerate(group['hooks']):
                    name = callback['args'][-2]
                    group['hooks'][index] = _legacy_hook_registration(
                        self.adapter.hooks, name, self.adapter.event_state,
                        callback['timeoutMs'],
                    )
        self.assertTrue(_is_validated_hook_config_update(
            (json.dumps(before) + '\n').encode(),
            (json.dumps(after) + '\n').encode(),
            self.adapter.hooks, self.adapter.event_state, runtime_bin(self.home),
        ))
        after['unrelated'] = True
        self.assertFalse(_is_validated_hook_config_update(
            (json.dumps(before) + '\n').encode(),
            (json.dumps(after) + '\n').encode(),
            self.adapter.hooks, self.adapter.event_state, runtime_bin(self.home),
        ))

    def test_native_evidence_survives_non_rendering_adapter_change_and_clears_reload_handoff(self):
        self.apply()
        state = json.loads(self.adapter.state_path.read_text())
        for name in SHELL_HOOK_NAMES:
            state['components']['hooks'][name]['verification'] = 'passed'
        self.adapter.state_path.write_text(json.dumps(state))
        receipt = json.loads(self.adapter.receipt_path.read_text())
        receipt['fingerprint'] = 'historical-adapter-fingerprint'
        self.adapter.receipt_path.write_text(json.dumps(receipt))

        changes, report = self.adapter.plan()
        self.assertNotIn(
            'Open a new ZCode Desktop session to load the delivered registrations.',
            report['next_actions'],
        )
        self.assertEqual(report['planned_verification']['passed'], len(SHELL_HOOK_NAMES))
        resulting_state = next(
            change.after for change in changes if change.path == self.adapter.state_path
        )
        reconciled = json.loads(resulting_state)
        self.assertTrue(all(
            reconciled['components']['hooks'][name]['verification'] == 'passed'
            for name in SHELL_HOOK_NAMES
        ))

    def test_entrypoint_hook_selection_reflects_shared_shell_support(self):
        self.apply()
        result = subprocess.run([
            sys.executable, '-B', str(self.source / 'install.py'), 'zcode', 'enable',
            '--home', str(self.home), '--hook', 'mainframe-commit-secrets',
        ], cwd=self.source, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['hooks'], ['mainframe-commit-secrets'])
        result = subprocess.run([
            sys.executable, '-B', str(self.source / 'install.py'), 'codex', 'enable',
            '--home', str(self.home), '--hook', 'mainframe-commit-secrets',
        ], cwd=self.source, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        # Codex now recognizes the safe context-free subset of this identity;
        # this separate fixture home simply has no Codex installation to control.
        self.assertIn('No installer-owned hooks', result.stderr)

    def test_instruction_review_and_unrelated_config_preservation(self):
        self.adapter.zcode.mkdir()
        instruction = self.adapter.zcode / 'AGENTS.md'
        instruction.write_text('User instruction.\n')
        self.adapter.config.parent.mkdir()
        before = {'plugins': {'sample': True}, 'hooks': {'enabled': False, 'events': {'Stop': [{'hooks': [{'type': 'process', 'command': 'true'}]}]}}}
        self.adapter.config.write_text(json.dumps(before))
        _, report = self.adapter.plan()
        self.assertIsNotNone(report['instruction_review'])
        self.assertEqual(instruction.read_text(), 'User instruction.\n')
        self.apply(reviewed=True)
        cfg = json.loads(self.adapter.config.read_text())
        self.assertEqual(cfg['plugins'], before['plugins'])
        report = self.adapter.plan()[1]
        self.assertFalse(report['hooks_globally_enabled'])
        self.assertTrue(any('deliberately disabled' in action for action in report['next_actions']))
        self.assertFalse(cfg['hooks']['enabled'])
        self.assertEqual(cfg['hooks']['events']['Stop'][0], before['hooks']['events']['Stop'][0])
        self.assertEqual(len(cfg['hooks']['events']['Stop']), 2)
        self.assertTrue(instruction.read_text().startswith('User instruction.\n'))
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(instruction.read_text(), 'User instruction.\n')
        self.assertEqual(json.loads(self.adapter.config.read_text()), before)

    def test_update_and_user_edits_are_preserved(self):
        self.apply()
        body = self.source / 'skills/mainframe-research/SKILL.md'
        body.write_text(body.read_text() + '\nUpdated canonical guidance.\n')
        self.apply()
        target = self.adapter.skills / 'mainframe-research/SKILL.md'
        self.assertTrue(target.read_text().endswith('Updated canonical guidance.\n'))
        target.write_text(target.read_text() + '\nUser change.\n')
        receipt = self.adapter.receipt_path.read_bytes()
        with self.assertRaisesRegex(Conflict, 'was edited'):
            self.apply()
        self.assertEqual(self.adapter.receipt_path.read_bytes(), receipt)

    def test_shared_command_override_is_scoped_and_restored(self):
        shared = self.home / '.agents/skills/mainframe-project-skill/SKILL.md'
        shared.parent.mkdir(parents=True)
        shared.write_text('Foreign Codex command; do not edit.')
        self.adapter.config.parent.mkdir(parents=True)
        self.adapter.config.write_text(json.dumps({'skills': {'unrelated': {'enable': False}}}))
        self.apply()
        cfg = json.loads(self.adapter.config.read_text())
        self.assertEqual(cfg['skills'][str(shared)], {'enable': False})
        self.assertEqual(shared.read_text(), 'Foreign Codex command; do not edit.')
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(json.loads(self.adapter.config.read_text()), {'skills': {'unrelated': {'enable': False}}})

    def test_disable_enable_and_cached_callback_after_uninstall(self):
        self.apply()
        cfg = json.loads(self.adapter.config.read_text())
        callback = cfg['hooks']['events']['PreToolUse'][0]['hooks'][0]
        payload = json.dumps({'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': 'mainframe-secret get TEST_FIXTURE'}, 'session_id': 'fixture', 'tool_use_id': 'fixture1'})
        def invoke():
            return subprocess.run([callback['command'], *callback['args']], input=payload, text=True, capture_output=True, timeout=5)
        self.assertIn('deny', invoke().stdout)
        state = json.loads(self.adapter.state_path.read_text())
        state['components']['hooks']['mainframe-secret-access']['verification'] = 'passed'
        state['components']['skills']['mainframe-research']['verification'] = 'passed'
        self.adapter.state_path.write_text(json.dumps(state))
        transact(self.adapter.control(False), self.adapter.journal, self.adapter.allowed)
        self.assertEqual(invoke().stdout, '')
        state = json.loads(self.adapter.state_path.read_text())
        self.assertEqual(state['components']['hooks']['mainframe-secret-access']['delivery'], 'installed')
        self.assertEqual(state['components']['hooks']['mainframe-secret-access']['verification'], 'pending')
        self.assertEqual(state['components']['skills']['mainframe-research']['verification'], 'passed')
        self.assertEqual(self.adapter.plan()[1]['changes'], [])
        transact(self.adapter.control(True), self.adapter.journal, self.adapter.allowed)
        self.assertIn('deny', invoke().stdout)
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        result = invoke()
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))

    def test_interrupted_write_rolls_back_and_foreign_file_survives(self):
        foreign = self.adapter.skills / 'mainframe-research/SKILL.md'
        foreign.parent.mkdir(parents=True)
        foreign.write_bytes((self.source / 'skills/mainframe-research/SKILL.md').read_bytes())
        before = foreign.read_bytes()
        changes, _ = self.adapter.plan()
        from installer import core
        real = core.atomic_write
        writes = 0
        def fail_once(path, data, mode=0o600):
            nonlocal writes
            writes += 1
            if writes == 4: raise OSError('fixture interrupted write')
            return real(path, data, mode)
        with patch.object(core, 'atomic_write', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'fixture interrupted'):
                transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(foreign.read_bytes(), before)
        self.assertFalse(self.adapter.receipt_path.exists())
        self.assertFalse(self.adapter.journal.exists())
        self.apply()
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(foreign.read_bytes(), before)

    def test_adopt_recognized_manual_components_and_reject_changed_copy(self):
        source = json.loads((self.source / 'ADAPTATION.example.json').read_text())
        artifacts = self.adapter.artifacts(source)
        for path, (data, mode, component, retain) in artifacts.items():
            if component.startswith(('skills.', 'agents.', 'commands.')):
                path.parent.mkdir(parents=True, exist_ok=True)
                if path == self.adapter.commands / 'mainframe-init.md':
                    data = command_body((self.source / 'commands/mainframe-init.md').read_text(), legacy=True)
                path.write_bytes(data);path.chmod(mode)
        (self.adapter.zcode / 'AGENTS.md').write_bytes((self.source / 'instructions/global.md').read_bytes())
        self.adapter.state_path.write_text(json.dumps({'target': {'product_id': 'zcode'}}))
        self.adapter.adopt_existing = True
        self.apply()
        self.assertTrue(self.adapter.receipt()['adopted_legacy'])
        self.assertNotIn('MAINFRAME OPTIONAL BLOCK', (self.adapter.commands / 'mainframe-init.md').read_text())
        self.assertEqual(self.adapter.plan()[1]['changes'], [])

    def test_legacy_hook_adoption_keeps_cached_entrypoint_inert(self):
        from installer import zcode
        legacy = self.adapter.legacy
        (legacy / 'detectors').mkdir(parents=True)
        bridge = legacy / 'zcode_hook.py'
        bridge.write_text("import pathlib,sys\nif not (pathlib.Path(__file__).parent / ('.disabled-' + sys.argv[1])).exists(): print('legacy active')\n")
        for name in zcode.LEGACY_HOOKS:
            shutil.copyfile(self.source / 'hooks' / (name + '.py'), legacy / 'detectors' / (name + '.py'))
        callback = {'type': 'process', 'command': '/usr/local/bin/python3', 'args': [str(bridge), 'mainframe-secret-access'], 'enabled': True, 'timeoutMs': 10000}
        cfg = {'plugins': {'unrelated': True}, 'hooks': {'enabled': True, 'events': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [callback]}]}}}
        self.adapter.config.parent.mkdir(parents=True)
        self.adapter.config.write_text(json.dumps(cfg))
        self.adapter.state_path.write_text(json.dumps({'target': {'product_id': 'zcode'}}))
        with self.assertRaisesRegex(Conflict, 'adoption'):
            self.adapter.plan()
        self.adapter.adopt_existing = True
        with patch.object(zcode, 'LEGACY_BRIDGE_SHA256', zcode.digest(bridge.read_bytes())):
            self.apply()
        result = subprocess.run([sys.executable, str(bridge), 'mainframe-secret-access'], capture_output=True, text=True)
        self.assertEqual(result.stdout, '')
        self.assertTrue(bridge.exists())
        self.assertEqual(self.adapter.plan()[1]['changes'], [])
        (legacy / '.disabled-mainframe-secret-access').unlink()
        self.apply()
        result = subprocess.run([sys.executable, str(bridge), 'mainframe-secret-access'], capture_output=True, text=True)
        self.assertEqual(result.stdout, '')
        self.apply()
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertTrue(bridge.exists())
        self.assertTrue((legacy / '.disabled-mainframe-secret-access').exists())
        self.assertEqual(json.loads(self.adapter.config.read_text())['plugins'], {'unrelated': True})

    def test_adoption_rejects_changed_manual_component_before_writes(self):
        self.adapter.state_path.write_text(json.dumps({'target': {'product_id': 'zcode'}}))
        p = self.adapter.commands / 'mainframe-project-skill.md'
        p.parent.mkdir(parents=True)
        p.write_text('User replacement; must survive.')
        self.adapter.adopt_existing = True
        with self.assertRaisesRegex(Conflict, 'differs from the known adaptation'):
            self.adapter.plan()
        self.assertEqual(p.read_text(), 'User replacement; must survive.')
        self.assertFalse(self.adapter.receipt_path.exists())

    def test_edited_owned_disable_marker_is_not_removed(self):
        self.apply()
        transact(self.adapter.control(False), self.adapter.journal, self.adapter.allowed)
        marker = self.adapter.hooks / '.disabled-mainframe-secret-access'
        marker.write_text('User annotation; preserve it.')
        with self.assertRaisesRegex(Conflict, 'was edited'):
            self.adapter.control(True)
        with self.assertRaisesRegex(Conflict, 'was edited'):
            self.adapter.plan(remove=True)
        self.assertEqual(marker.read_text(), 'User annotation; preserve it.')
        marker.write_bytes(b'')

    def test_update_preserves_disabled_state_across_hook_prefix_migration(self):
        self.apply()
        transact(
            self.adapter.control(False, 'mainframe-secret-access'),
            self.adapter.journal,
            self.adapter.allowed,
        )
        current = self.adapter.hooks / '.disabled-mainframe-secret-access'
        legacy = self.adapter.hooks / '.disabled-secret-access'
        current.rename(legacy)
        receipt = json.loads(self.adapter.receipt_path.read_text())
        receipt['disabled_markers'] = {'secret-access': True}
        self.adapter.receipt_path.write_text(json.dumps(receipt))

        self.apply()
        self.assertFalse(legacy.exists())
        self.assertTrue(current.exists())
        self.assertEqual(
            self.adapter.receipt()['disabled_markers'],
            {'mainframe-secret-access': True},
        )

    def test_cleanup_refuses_nonprivate_state_directory(self):
        p = self.adapter.event_state
        p.mkdir(mode=0o755)
        (p / 'events.sqlite3').write_text('foreign state')
        try:
            with self.assertRaisesRegex(Conflict, 'not a private directory'):
                self.adapter.clean_event_state()
            self.assertEqual((p / 'events.sqlite3').read_text(), 'foreign state')
        finally:
            (p / 'events.sqlite3').unlink();p.rmdir()

    def test_duplicate_owned_registration_is_not_silently_claimed(self):
        self.apply()
        cfg = json.loads(self.adapter.config.read_text())
        group = cfg['hooks']['events']['PreToolUse'][0]
        cfg['hooks']['events']['PreToolUse'].append(group)
        self.adapter.config.write_text(json.dumps(cfg))
        with self.assertRaisesRegex(Conflict, 'duplicated'):
            self.adapter.plan()

    def test_split_foreign_registration_is_not_duplicated(self):
        from installer.zcode import hook_registration
        callback = hook_registration(self.adapter.hooks, HOOK_NAMES[0], self.adapter.event_state)
        self.adapter.config.parent.mkdir(parents=True)
        cfg = {'hooks': {'events': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [callback]}]}}}
        self.adapter.config.write_text(json.dumps(cfg))
        with self.assertRaisesRegex(Conflict, 'split or duplicated'):
            self.adapter.plan()
        self.assertEqual(json.loads(self.adapter.config.read_text()), cfg)

    def test_owned_shared_helper_updates_but_survives_removal(self):
        self.apply()
        source = self.source / 'shared/credentials/mainframe-secret'
        source.write_bytes(source.read_bytes() + b'\n# Canonical fixture update\n')
        self.apply()
        helper = self.home / '.local/bin/mainframe-secret'
        self.assertEqual(helper.read_bytes(), source.read_bytes())
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(helper.read_bytes(), source.read_bytes())

    def test_entrypoint_delivery_stops_after_file_verification(self):
        reports = []
        for action in ('plan', 'apply', 'verify'):
            result = subprocess.run([
                sys.executable, '-B', str(self.source / 'install.py'), 'zcode', action,
                '--surface', 'desktop', '--home', str(self.home), '--runtime-version', '3.11.2.6792',
            ], cwd=self.source, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            reports.append(json.loads(result.stdout))
        self.assertTrue(reports[1]['applied'])
        self.assertTrue(reports[2]['structure_matches'])
        self.assertEqual(reports[2]['file_change_count'], 0)
        self.assertEqual(reports[2]['planned_delivery'], {'installed': 34, 'pending': 0, 'unsupported': 2})
        self.assertEqual(reports[2]['planned_verification'], {'passed': 0, 'pending': 34})
        self.assertEqual(len(reports[2]['next_actions']), 1)
        state = json.loads(self.adapter.state_path.read_text())
        self.assertFalse(any(row.get('verification') == 'passed' for group in state['components'].values() for row in group.values()))

    def test_current_build_allows_only_bounded_existing_skill_updates(self):
        self.apply()
        skill_source = self.source / 'skills/mainframe-research/SKILL.md'
        skill_source.write_bytes(skill_source.read_bytes() + b'\nFixture content update.\n')
        options = ['--surface', 'desktop', '--home', str(self.home), '--runtime-version', '3.14.3.7762']
        result = subprocess.run([
            sys.executable, '-B', str(self.source / 'install.py'), 'zcode', 'apply', *options,
        ], cwd=self.source, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('bounded update', json.loads(result.stdout)['delivery_mode'])

        role_source = self.source / 'agents/mainframe-researcher.md'
        role_source.write_bytes(role_source.read_bytes() + b'\nFixture role change.\n')
        result = subprocess.run([
            sys.executable, '-B', str(self.source / 'install.py'), 'zcode', 'plan', *options,
        ], cwd=self.source, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn('cannot change native packaging', result.stderr)

    def test_unknown_build_is_rejected_before_plan_or_writes(self):
        other_home = self.home.parent / 'unknown-build-home'
        other_home.mkdir()
        result = subprocess.run([
            sys.executable, '-B', str(self.source / 'install.py'), 'zcode', 'plan',
            '--surface', 'desktop', '--home', str(other_home), '--runtime-version', '9.9.9',
        ], cwd=self.source, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Revalidate the maintained ZCode mapping', result.stderr)
        self.assertFalse((other_home / '.zcode').exists())

    def test_cli_product_rejects_wrong_surface(self):
        result = subprocess.run([sys.executable, '-B', str(self.source / 'install.py'), 'zcode', 'plan', '--surface', 'cli'], cwd=self.source, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Desktop only', result.stderr)


if __name__ == '__main__': unittest.main()
