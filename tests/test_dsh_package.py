"""Node-native tarball packaging with synthetic source and no profile IO."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from installer.core import Conflict
from installer.dsh_package import build_packages

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'source'
        shutil.copytree(ROOT / 'plugins', self.root / 'plugins')
        self.output = self.base / 'packages'

    def build(self, output=None):
        return build_packages(self.root, output or self.output)

    def test_node_payload_and_native_handoff_are_self_contained(self):
        with patch('subprocess.run') as spawn:
            report = self.build()
            spawn.assert_not_called()
        self.assertFalse(report['profile_verified'])
        self.assertFalse(report['runtime_verified'])
        self.assertEqual(set(report['bundles']), {'activity-analytics', 'message-time', 'secrets-vault',
                                                'session-collaboration'})
        for name, item in report['bundles'].items():
            archive = Path(item['archive'])
            self.assertTrue(archive.is_absolute())
            self.assertEqual(archive.name, f'mainframe-{name}-{item["version"]}.tgz')
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), item['sha256'])
            self.assertEqual(item['handoff']['target'], str(archive))
            self.assertEqual(item['handoff']['tool'], 'plugin_manager')
            with tarfile.open(archive) as packed:
                members = packed.getmembers()
                self.assertTrue(all(member.isfile() and member.name.startswith('package/') for member in members))
                self.assertFalse(any('.test.' in member.name or member.name.endswith('/test.mjs')
                                     or 'client.template' in member.name for member in members))
                self.assertFalse(any('/runtime/' in member.name or member.name.endswith('.py') for member in members))
                manifest = json.load(packed.extractfile('package/package.json'))
                self.assertEqual(manifest['name'], '@mainframe/' + name)
                self.assertFalse(manifest.get('scripts'))
                if name in {'activity-analytics', 'message-time', 'secrets-vault'}:
                    self.assertEqual(manifest['engines']['dsh'], '0.2.2-rc.1')
                    self.assertNotIn('package/README.md', packed.getnames())
                    self.assertNotIn('package/schema-fixture.mjs', packed.getnames())
                    self.assertNotIn('package/discovery-benchmark.mjs', packed.getnames())
                if name == 'message-time':
                    self.assertEqual(manifest['dependencies']['@deepseek-ai/schemastery'], '~3.19.0')
                if name == 'session-collaboration':
                    self.assertEqual(item['version'], '0.5.1')
                    self.assertEqual(manifest['version'], '0.5.1')
                    for runtime in ('core.js', 'selftest.js', 'wait-many.js', 'tasks.js',
                                    'storage.js', 'lifecycle-management.js', 'lifecycle-reads.js', 'model-selection.js', 'tool-surface.js'):
                        self.assertIn('package/' + runtime, packed.getnames())
                    self.assertFalse(any(member.endswith('.test.js') for member in packed.getnames()))
                    self.assertFalse(manifest.get('dependencies'))
                    self.assertEqual(manifest['peerDependencies']['@deepseek-ai/dsh-storage-domain'], '0.2.2-rc.1')
                    self.assertEqual(manifest['peerDependencies']['@deepseek-ai/dsh-session-title'], '0.2.2-rc.1')
                    self.assertEqual(manifest['peerDependencies']['zod'], '4.4.3')
                if name == 'secrets-vault':
                    self.assertEqual(packed.getmember('package/ssh-askpass').mode, 0o755)
                    self.assertIn('package/core/index.js', packed.getnames())
                    self.assertNotIn('package/legacy-guard.test.mjs', packed.getnames())
                    self.assertNotIn('package/lifecycle.test.mjs', packed.getnames())
                    self.assertNotIn('package/test-effects.mjs', packed.getnames())
                    self.assertEqual(manifest['exports']['./core'], './core/index.js')
                    self.assertNotIn('runtime', manifest['files'])
                    self.assertNotIn('os', manifest)
                    self.assertNotIn('cpu', manifest)
        # A packed install survives checkout removal; never a link to the source.
        self.assertTrue(self.root.resolve() == self.root and self.root.parent == self.base)
        shutil.rmtree(self.root)
        self.assertTrue(all(Path(row['archive']).is_file() for row in report['bundles'].values()))

    def test_archives_are_reproducible_independent_of_mtime(self):
        first = self.build()
        os.utime(self.root / 'plugins/dsh/secrets-vault/core/index.js', (1700000000, 1700000000))
        second = self.build(self.base / 'second')
        for name in first['bundles']:
            self.assertEqual(first['bundles'][name]['sha256'], second['bundles'][name]['sha256'])
        archive = Path(first['bundles']['message-time']['archive'])
        self.assertEqual(archive.read_bytes()[4:8], b'\x00\x00\x00\x00')

    def test_rejects_nonempty_output_source_overlap_and_aliases(self):
        self.output.mkdir()
        marker = self.output / 'keep'
        marker.write_text('untouched')
        with self.assertRaises(Conflict):
            self.build()
        self.assertEqual(marker.read_text(), 'untouched')
        for output in (self.root / 'build', self.root, self.base, self.base / 'missing' / 'nested', Path('relative')):
            with self.subTest(output=output), self.assertRaises(Conflict):
                self.build(output)
        alias = self.base / 'alias'
        alias.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(Conflict):
            self.build(alias / 'new')
        with self.assertRaises(Conflict):
            self.build(self.base / '..' / self.base.name / 'new')

    def test_rejects_home_and_profile_output_without_inspecting_them(self):
        for key in ('DSH_HOME', 'DSH_PROFILE_DIR'):
            with self.subTest(key=key), patch.dict(os.environ, {key: str(self.base / 'protected')}):
                for output in (self.base / 'protected' / 'packages', self.base):
                    with self.assertRaises(Conflict):
                        self.build(output)
        with patch('installer.dsh_package.Path.home', return_value=self.base / 'home'):
            with self.assertRaises(Conflict):
                self.build(self.base / 'home' / '.dsh' / 'packages')

    def test_reuses_exact_source_boundary_including_nested_core(self):
        package = self.root / 'plugins/dsh/secrets-vault'
        for relative in ('local.db', 'vault.db.recovery.json', 'vault.v2.json', 'core/private.json', 'vault.py'):
            extra = package / relative
            extra.write_bytes(b'synthetic private or obsolete fixture')
            try:
                with self.subTest(relative=relative), self.assertRaises(Conflict):
                    self.build()
                self.assertFalse(self.output.exists())
            finally:
                extra.unlink()

    def test_rejects_install_scripts_before_output(self):
        manifest_file = self.root / 'plugins/dsh/message-time/package.json'
        manifest = json.loads(manifest_file.read_text())
        manifest['scripts'] = {'postinstall': 'not executed'}
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(Conflict, 'installation scripts'):
            self.build()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
