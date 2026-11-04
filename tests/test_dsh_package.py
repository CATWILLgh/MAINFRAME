"""Standalone native tarball packaging, with synthetic runtimes and no profile IO."""
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
        self.runtime = self.base / 'python'
        (self.runtime / 'bin').mkdir(parents=True)
        (self.runtime / 'lib').mkdir()
        (self.runtime / 'bin/python3.12').write_bytes(b'#!/bin/sh\nexit 0\n')
        (self.runtime / 'bin/python3.12').chmod(0o755)
        (self.runtime / 'bin/python3').symlink_to('python3.12')
        (self.runtime / 'lib/libpython.dylib').write_bytes(b'synthetic shared library')
        (self.runtime / 'LICENSE').write_text('Synthetic upstream license fixture\n')
        (self.runtime / 'mainframe-runtime.json').write_text(json.dumps({
            'schema': 1, 'target': 'aarch64-apple-darwin', 'python': '3.12.12',
            'sqlcipher3': '0.6.4', 'cipher': 'synthetic fixture',
            'provider': 'uv/python-build-standalone', 'binary_wheel_only': True}))
        self.output = self.base / 'packages'

    def build(self, output=None):
        return build_packages(self.root, output or self.output, self.runtime)

    def test_runtime_payload_and_native_handoff_are_self_contained(self):
        report = self.build()
        self.assertFalse(report['profile_verified'])
        self.assertEqual(set(report['bundles']), {'activity-analytics', 'message-time', 'secrets-vault'})
        for name, item in report['bundles'].items():
            archive = Path(item['archive'])
            self.assertTrue(archive.is_absolute())
            self.assertIn(item['version'], archive.name)
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), item['sha256'])
            self.assertEqual(item['handoff']['target'], str(archive))
            self.assertEqual(item['handoff']['tool'], 'plugin_manager')
            with tarfile.open(archive) as packed:
                members = packed.getmembers()
                self.assertTrue(all(member.isfile() for member in members))
                self.assertTrue(all(member.name.startswith('package/') for member in members))
                self.assertFalse(any('.test.' in member.name or member.name.endswith('/test.mjs')
                                     or 'client.template' in member.name for member in members))
                manifest = json.load(packed.extractfile('package/package.json'))
                self.assertEqual(manifest['name'], '@mainframe/' + name)
                self.assertFalse(manifest.get('scripts'))
                if name == 'secrets-vault':
                    python = packed.getmember('package/runtime/bin/python3')
                    self.assertEqual(python.mode, 0o755)
                    self.assertEqual(packed.getmember('package/ssh-askpass').mode, 0o755)
                    self.assertIn('runtime', manifest['files'])
                    self.assertEqual(manifest['os'], ['darwin'])
                    self.assertEqual(manifest['cpu'], ['arm64'])
                    self.assertIn('-darwin-arm64.tgz', archive.name)
                    self.assertEqual(packed.extractfile(python).read(), (self.runtime / 'bin/python3.12').read_bytes())
                    self.assertIn('package/runtime/LICENSE', packed.getnames())
                else:
                    self.assertFalse(any('/runtime/' in member.name for member in members))
        # Neither a checkout link nor a Python symlink survives in installed payload.
        shutil.rmtree(self.root)
        shutil.rmtree(self.runtime)
        self.assertTrue(all(Path(row['archive']).is_file() for row in report['bundles'].values()))

    def test_archives_are_reproducible_independent_of_mtime(self):
        first = self.build()
        os.utime(self.runtime / 'LICENSE', (1700000000, 1700000000))
        second = self.build(self.base / 'second')
        for name in first['bundles']:
            self.assertEqual(first['bundles'][name]['sha256'], second['bundles'][name]['sha256'])
        archive = Path(first['bundles']['message-time']['archive'])
        self.assertEqual(archive.read_bytes()[4:8], b'\x00\x00\x00\x00')

    def test_rejects_external_broken_and_cyclic_runtime_links_without_output(self):
        outside = self.base / 'outside'
        outside.write_bytes(b'must not copy')
        for target in (str(outside), 'missing', '.'):
            link = self.runtime / 'bad'
            link.symlink_to(target)
            try:
                with self.subTest(target=target), self.assertRaises(Conflict):
                    self.build()
                self.assertFalse(self.output.exists())
            finally:
                link.unlink()

    def test_rejects_private_runtime_and_virtualenv_without_output(self):
        for relative in ('vault.db', '.env', 'private.pem', 'pyvenv.cfg', 'credentials.json'):
            private = self.runtime / relative
            private.write_bytes(b'synthetic private or environment fixture')
            try:
                with self.subTest(relative=relative), self.assertRaises(Conflict):
                    self.build()
                self.assertFalse(self.output.exists())
            finally:
                private.unlink()

    def test_requires_executable_python_and_upstream_license(self):
        (self.runtime / 'bin/python3.12').chmod(0o644)
        with self.assertRaises(Conflict):
            self.build()
        (self.runtime / 'bin/python3.12').chmod(0o755)
        (self.runtime / 'LICENSE').unlink()
        with self.assertRaises(Conflict):
            self.build()
        self.assertFalse(self.output.exists())

    def test_excludes_runtime_caches(self):
        cache = self.runtime / 'lib/__pycache__'
        cache.mkdir()
        (cache / 'cached.pyc').write_bytes(b'cache')
        report = self.build()
        with tarfile.open(report['bundles']['secrets-vault']['archive']) as packed:
            self.assertFalse(any('__pycache__' in name for name in packed.getnames()))

    def test_rejects_nonempty_output_source_overlap_and_aliases(self):
        self.output.mkdir()
        marker = self.output / 'keep'
        marker.write_text('untouched')
        with self.assertRaises(Conflict):
            self.build()
        self.assertEqual(marker.read_text(), 'untouched')
        with self.assertRaises(Conflict):
            self.build(self.root / 'build')
        alias = self.base / 'alias'
        alias.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(Conflict):
            self.build(alias / 'new')
        with self.assertRaises(Conflict):
            build_packages(self.root, self.base / 'new', alias / 'python')

    def test_requires_supported_pinned_runtime_receipt(self):
        receipt = self.runtime / 'mainframe-runtime.json'
        original = json.loads(receipt.read_text())
        for changes in ({'schema': 2}, {'target': 'unknown'}, {'python': '3.13.0'},
                        {'sqlcipher3': '9'}, {'binary_wheel_only': False}):
            receipt.write_text(json.dumps({**original, **changes}))
            with self.subTest(changes=changes), self.assertRaises(Conflict):
                self.build()
            self.assertFalse(self.output.exists())
        receipt.unlink()
        with self.assertRaises(Conflict):
            self.build()

    def test_requires_exact_worker_python_version(self):
        (self.runtime / 'bin/python3').unlink()
        (self.runtime / 'bin/python3.12').rename(self.runtime / 'bin/python3')
        with self.assertRaises(Conflict):
            self.build()
        self.assertFalse(self.output.exists())

    def test_rejects_home_and_profile_output_without_inspecting_them(self):
        for key in ('DSH_HOME', 'DSH_PROFILE_DIR'):
            with self.subTest(key=key), patch.dict(os.environ, {key: str(self.base / 'protected')}):
                with self.assertRaises(Conflict):
                    self.build(self.base / 'protected' / 'packages')
        with patch('installer.dsh_package.Path.home', return_value=self.base / 'home'):
            with self.assertRaises(Conflict):
                self.build(self.base / 'home' / '.dsh' / 'packages')

    def test_omits_packaging_tools_and_stdlib_tests_but_keeps_sqlcipher_license(self):
        site = self.runtime / 'lib/python3.12/site-packages'
        for relative in ('pip/_vendor/certifi/cacert.pem', 'pip-26.dist-info/licenses/LICENSE',
                         '../test/certdata/private.pem', 'sqlcipher3-0.6.4.dist-info/licenses/LICENSE'):
            path = site / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic fixture')
        report = self.build()
        with tarfile.open(report['bundles']['secrets-vault']['archive']) as packed:
            names = packed.getnames()
            self.assertFalse(any('/pip/' in name or '/test/' in name for name in names))
            self.assertIn('package/runtime/lib/python3.12/site-packages/sqlcipher3-0.6.4.dist-info/licenses/LICENSE', names)

    def test_reuses_exact_source_boundary(self):
        (self.root / 'plugins/dsh/message-time/local.db').write_bytes(b'synthetic private fixture')
        with self.assertRaises(Conflict):
            self.build()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
