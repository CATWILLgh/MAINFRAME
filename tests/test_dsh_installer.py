"""Read-only DSH source planning, never a profile installation claim."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import install as entrypoint

from installer.core import Conflict
from installer.dsh import DSH
from installer.shared import DSH_PLUGINS, unsupported_dsh_plugins

ROOT = Path(__file__).resolve().parents[1]


class DSHTests(unittest.TestCase):
    def collaboration_fixture(self, root):
        source = 'plugins/dsh/session-collaboration'
        package = root / source
        runtime = ['index.js', 'core.js', 'selftest.js', 'tasks.js', 'storage.js',
                   'wait-many.js', 'lifecycle-management.js', 'lifecycle-reads.js', 'model-selection.js', 'tool-surface.js',
                   'cordis.patch.yml', 'README.md', 'icon.svg',
                   'locale/en.json', 'locale/ru.json']
        for relative in [*runtime, 'core.test.js', 'tasks.test.js', 'wait-many.test.js',
                         'index.test.js', 'lifecycle-management.test.js', 'model-selection.test.js', 'tool-surface.test.js', 'title-creation.test.js']:
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}' if relative.endswith('.json') else 'synthetic source')
        manifest = {'name': '@mainframe/session-collaboration', 'version': '0.5.1',
                    'dsh': {'bundle': {'patch': './cordis.patch.yml'}}, 'files': runtime}
        (package / 'package.json').write_text(json.dumps(manifest))
        return source, package, manifest

    def test_collaboration_inventory_is_pending_and_dsh_only(self):
        source = json.loads((ROOT / 'ADAPTATION.example.json').read_text())
        row = source['components']['plugins'].get('session-collaboration')
        self.assertEqual(row, {'source': 'plugins/dsh/session-collaboration',
                               'delivery': 'pending', 'verification': 'pending'})
        self.assertEqual(DSH_PLUGINS['session-collaboration'], row['source'])
        self.assertIn(('plugins', 'session-collaboration'), unsupported_dsh_plugins(source))

    def test_collaboration_source_handoff_needs_no_profile_or_extra_runtime(self):
        self.assertIn('session-collaboration', DSH_PLUGINS)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, package, _ = self.collaboration_fixture(root)
            home = root / 'never-created-profile'
            bundle = DSH(root, home)._bundle('session-collaboration', source)
            self.assertEqual(bundle['package'], '@mainframe/session-collaboration')
            self.assertEqual(bundle['version'], '0.5.1')
            self.assertEqual(bundle['requirements'], [])
            self.assertIsNone(bundle['install_target'])
            self.assertIsNone(bundle['handoff']['target'])
            self.assertEqual(bundle['handoff']['tool'], 'plugin_manager')
            self.assertEqual(set(bundle['source_files']),
                             {p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file()})
            self.assertFalse(home.exists())

    def test_collaboration_rejects_private_source_and_omitted_runtime(self):
        self.assertIn('session-collaboration', DSH_PLUGINS)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, package, manifest = self.collaboration_fixture(root)
            adapter = DSH(root, root / 'unused-home')
            for runtime in ('core.js', 'tasks.js', 'storage.js', 'wait-many.js',
                            'lifecycle-management.js', 'lifecycle-reads.js', 'model-selection.js', 'tool-surface.js'):
                with self.subTest(runtime=runtime):
                    manifest['files'].remove(runtime)
                    (package / 'package.json').write_text(json.dumps(manifest))
                    with self.assertRaisesRegex(Conflict, 'Incomplete DSH runtime payload'):
                        adapter._bundle('session-collaboration', source)
                    manifest['files'].append(runtime)
            (package / 'package.json').write_text(json.dumps(manifest))
            (package / 'private.json').write_text('{}')
            with self.assertRaisesRegex(Conflict, 'Unexpected DSH source'):
                adapter._bundle('session-collaboration', source)

    def test_plan_reuses_inventory_without_claiming_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / '.dsh/profiles/desktop'
            profile.mkdir(parents=True)
            foreign = profile / 'foreign.txt'
            foreign.write_text('untouched')
            before = {p.relative_to(home): p.read_bytes() for p in home.rglob('*') if p.is_file()}
            changes, report = DSH(ROOT, home).plan()
            self.assertEqual(changes, [])
            self.assertFalse(report['profile_verified'])
            self.assertTrue(report['source_verified'])
            self.assertEqual(set(report['bundles']), set(DSH_PLUGINS))
            for name, row in report['state']['components']['plugins'].items():
                self.assertIn(name, DSH_PLUGINS)
                self.assertEqual(row['delivery'], 'pending')
                self.assertEqual(row['verification'], 'pending')
                self.assertIn('plugin_manager', row['next_action'])
            self.assertFalse(any(row['delivery'] == 'installed'
                                 for group in report['state']['components'].values()
                                 for row in group.values()))
            self.assertEqual(before, {p.relative_to(home): p.read_bytes() for p in home.rglob('*') if p.is_file()})

    def test_mainframe_namespace_matches_manifests_patches_and_client_modules(self):
        _, report = DSH(ROOT, ROOT / 'unused-home').plan()
        for name in DSH_PLUGINS:
            package = ROOT / DSH_PLUGINS[name]
            expected = f'@mainframe/{name}'
            with self.subTest(package=name):
                self.assertEqual(report['bundles'][name]['package'], expected)
                self.assertEqual(json.loads((package / 'package.json').read_text())['name'], expected)
                self.assertIn(f"name: '{expected}'", (package / 'cordis.patch.yml').read_text())
                for client in ('client.js', 'client.template.js'):
                    if (package / client).exists():
                        self.assertRegex((package / client).read_text(), rf"id:\s*'{expected}'")

    def test_source_validation_rejects_private_material_and_missing_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('plugins', 'skills', 'instructions', 'agents', 'commands', 'hooks'):
                shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns('__pycache__'))
            credentials = root / 'shared/credentials'
            credentials.mkdir(parents=True)
            shutil.copy2(ROOT / 'shared/credentials/mainframe-secret', credentials)
            for name in ('ADAPTATION.example.json', '.gitignore'):
                shutil.copy2(ROOT / name, root / name)
            package = root / 'plugins/dsh/message-time'
            private = package / 'vault.db'
            private.write_bytes(b'synthetic private fixture')
            with self.assertRaisesRegex(Conflict, 'Unexpected DSH source'):
                DSH(root, root / 'home').plan()
            private.unlink()
            (package / 'index.js').unlink()
            with self.assertRaisesRegex(Conflict, 'Missing DSH payload'):
                DSH(root, root / 'home').plan()

    def test_invalid_manifest_is_an_actionable_source_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'plugins/dsh/message-time'
            shutil.copytree(ROOT / 'plugins/dsh/message-time', package)
            for value in ([], {'name': '@mainframe/message-time', 'version': '1.1.0', 'dsh': []}):
                (package / 'package.json').write_text(json.dumps(value))
                with self.subTest(manifest=value), self.assertRaises(Conflict):
                    DSH(root, root / 'home')._bundle('message-time', 'plugins/dsh/message-time')

    def test_manifest_cannot_omit_required_runtime_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'plugins/dsh/message-time'
            shutil.copytree(ROOT / 'plugins/dsh/message-time', package)
            path = package / 'package.json'
            manifest = json.loads(path.read_text())
            manifest['files'] = ['cordis.patch.yml']
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(Conflict, 'Incomplete DSH runtime payload'):
                DSH(root, root / 'home')._bundle('message-time', 'plugins/dsh/message-time')

    def test_source_report_requires_packed_user_install_instead_of_links(self):
        _, report = DSH(ROOT, ROOT / 'unused-home').plan()
        for bundle in report['bundles'].values():
            self.assertIsNone(bundle['install_target'])
            self.assertIsNone(bundle['handoff']['target'])
            self.assertIn('.tgz', bundle['packaging'])

    def test_cli_package_never_provisions_a_runtime(self):
        shared_runtime = entrypoint.provision_runtime
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / 'packages'
            with patch('installer.dsh_package.build_packages', return_value={'mode': 'fixture'}) as build, \
                    patch('subprocess.run') as spawn, patch('install.show'):
                self.assertEqual(entrypoint.main(['dsh', 'package', '--surface', 'desktop', '--output', str(output)]), 0)
                build.assert_called_once_with(ROOT, output)
                spawn.assert_not_called()
                self.assertIs(entrypoint.provision_runtime, shared_runtime)
            forbidden = ROOT / 'never-create-package-output'
            with self.assertRaises(Conflict):
                entrypoint.main(['dsh', 'package', '--surface', 'desktop', '--output', str(forbidden)])
            self.assertFalse(forbidden.exists())
        with self.assertRaises(SystemExit):
            entrypoint.main(['dsh', 'package', '--surface', 'desktop', '--vault-runtime', '/not-used'])

    def test_cli_routes_and_rejects_mutation_and_foreign_options(self):
        for action in ('plan', 'verify'):
            result = subprocess.run([sys.executable, '-B', 'install.py', 'dsh', action,
                                     '--surface', 'desktop'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['verification_scope'], 'repository-source-only')
            self.assertFalse(report['profile_verified'])
        for extra in (['apply'], ['uninstall'], ['plan', '--native'],
                      ['plan', '--codex-home', '/tmp/not-used'], ['plan', '--hook', 'anything']):
            result = subprocess.run([sys.executable, '-B', 'install.py', 'dsh', *extra,
                                     '--surface', 'desktop'], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('DSH', result.stderr)
