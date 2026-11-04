"""Portable Vault runtime provisioning uses only isolated build directories."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from installer.core import Conflict
from installer.dsh_runtime import provision_runtime, runtime_target, validate_build_output


class RuntimeTests(unittest.TestCase):
    def test_known_targets_and_unsupported_platform_fail_closed(self):
        self.assertEqual(runtime_target('Darwin', 'arm64'), 'aarch64-apple-darwin')
        self.assertEqual(runtime_target('Linux', 'x86_64'), 'x86_64-unknown-linux-gnu')
        with self.assertRaisesRegex(Conflict, 'Unsupported'):
            runtime_target('Windows', 'AMD64')

    def test_provision_downloads_pinned_standalone_not_venv_then_checks_sqlcipher(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp).resolve() / 'runtime-build'
            commands = []
            environments = []
            def run(command, **kwargs):
                commands.append(command)
                self.assertEqual(kwargs['cwd'], destination)
                environments.append(kwargs['env'])
                if 'install' in command and 'python' in command:
                    runtime = destination / 'python' / 'cpython-test'
                    (runtime / 'bin').mkdir(parents=True)
                    (runtime / 'bin/python3.12').write_text('synthetic executable')
                    (runtime / 'lib/python3.12/site-packages').mkdir(parents=True)
                class Result:
                    stdout = json.dumps({'python': '3.12.12', 'sqlcipher3': '0.6.4', 'cipher': '4.19.0'})
                return Result()
            injected = {'UV_INDEX_URL': 'https://invalid.example', 'PIP_CONFIG_FILE': '/bad',
                        'PYTHONPATH': '/bad', 'LD_PRELOAD': '/bad', 'LD_LIBRARY_PATH': '/bad',
                        'DYLD_INSERT_LIBRARIES': '/bad', 'DYLD_LIBRARY_PATH': '/bad',
                        'SSLKEYLOGFILE': '/bad', 'MAINFRAME_BUILD_MARKER': 'kept'}
            with patch('installer.dsh_runtime.subprocess.run', side_effect=run), patch('installer.dsh_runtime.shutil.which', return_value='/tools/uv'), patch.dict(os.environ, injected):
                result = provision_runtime(destination)
            for environment in environments:
                for name in injected:
                    if name != 'MAINFRAME_BUILD_MARKER':
                        self.assertNotIn(name, environment)
                self.assertEqual(environment['MAINFRAME_BUILD_MARKER'], 'kept')
            self.assertEqual(result.name, 'cpython-test')
            self.assertIn('3.12.12', commands[0])
            self.assertIn('--no-bin', commands[0])
            self.assertIn('sqlcipher3==0.6.4', commands[1])
            self.assertIn('--only-binary', commands[1])
            self.assertIn('-I', commands[2])
            self.assertIn('-B', commands[2])
            self.assertTrue((result / 'mainframe-runtime.json').is_file())

    def test_preflight_rejects_relative_aliases_existing_and_missing_parents(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            self.assertEqual(validate_build_output(base / 'new'), base / 'new')
            alias = base / 'alias'
            alias.symlink_to(base, target_is_directory=True)
            candidates = [Path('relative-build'), base, base / 'absent' / 'nested',
                          alias / 'new', base / '..' / base.name / 'new']
            with patch('installer.dsh_runtime.subprocess.run') as run:
                for candidate in candidates:
                    with self.subTest(candidate=candidate), self.assertRaises(Conflict):
                        provision_runtime(candidate)
                run.assert_not_called()
            self.assertFalse((base / 'new').exists())

    def test_preflight_protects_dsh_home_profile_and_source_both_directions(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            home = base / 'home'
            home.mkdir()
            source = base / 'source'
            source.mkdir()
            protected = base / 'protected'
            protected.mkdir()
            with patch('installer.dsh_runtime.Path.home', return_value=home), patch.dict(os.environ, {
                    'DSH_HOME': str(protected / 'dsh'), 'DSH_PROFILE_DIR': str(protected / 'profile')}):
                cases = [home / '.dsh', protected / 'dsh', protected / 'profile',
                         protected / 'dsh' / 'build', source / 'build']
                for candidate in cases:
                    with self.subTest(candidate=candidate), self.assertRaises(Conflict):
                        validate_build_output(candidate, source_root=source)
                # Nonexistent ancestors must also be forbidden: a producer must
                # not allocate a future source or profile parent as a build tree.
                with patch.dict(os.environ, {'DSH_HOME': str(base / 'future' / 'dsh')}):
                    with self.assertRaises(Conflict):
                        validate_build_output(base / 'future')
                with self.assertRaises(Conflict):
                    validate_build_output(base / 'ancestor', source_root=base / 'ancestor' / 'checkout')
                with patch('installer.dsh_runtime.subprocess.run') as run:
                    with self.assertRaises(Conflict):
                        provision_runtime(protected / 'profile')
                    run.assert_not_called()
            self.assertFalse((home / '.dsh').exists())
            self.assertFalse((source / 'build').exists())

    def test_existing_output_and_missing_uv_do_not_download(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('installer.dsh_runtime.subprocess.run') as run:
                with self.assertRaises(Conflict):
                    provision_runtime(Path(temp).resolve())
                run.assert_not_called()
            with patch('installer.dsh_runtime.shutil.which', return_value=None):
                with self.assertRaisesRegex(Conflict, 'uv'):
                    provision_runtime(Path(temp).resolve() / 'missing')
