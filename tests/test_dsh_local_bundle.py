"""Disposable filesystem tests; never consult a real DSH profile or runtime."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from installer import dsh_local_bundle as bundle


class LocalBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / 'repository'
        self.repo.mkdir()
        self.profile = self.root / 'profile'
        self.profile.mkdir()
        self.home = self.root / 'dsh-home'
        self.home.mkdir()
        self.output = self.root / 'deployment'
        self.addCleanup(patch.stopall)
        patch.object(bundle, 'REPOSITORY_ROOT', self.repo).start()
        patch.dict(os.environ, {'DSH_HOME': str(self.home)}).start()

    def generate(self, **kwargs):
        return bundle.generate_bundle(**{
            'output': self.output,
            'profile_directory': self.profile,
            **kwargs,
        })

    def reject(self, **kwargs):
        with self.assertRaises(bundle.LocalBundleError) as caught:
            self.generate(**kwargs)
        self.assertNotIn(str(self.root), str(caught.exception))
        return caught.exception

    def test_payload_is_private_config_only_with_display_exports(self):
        self.assertEqual(self.generate(), self.output)
        manifest = json.loads((self.output / 'package.json').read_text())
        self.assertEqual(manifest['name'], '@mainframe/local-deployment')
        self.assertIs(manifest['private'], True)
        for key in ('dependencies', 'devDependencies', 'scripts'):
            self.assertNotIn(key, manifest)
        self.assertNotIn('.', manifest['exports'])
        self.assertEqual(manifest['exports']['./icon'], './icon.svg')
        self.assertEqual(manifest['exports']['./locale/*.json'], './locale/*.json')
        self.assertEqual(set(manifest['files']), {'cordis.patch.yml', 'locale/*.json', 'icon.svg'})
        self.assertEqual(manifest['dsh']['bundle']['patch'], './cordis.patch.yml')
        rows = json.loads((self.output / 'cordis.patch.yml').read_text())[0]['insert']
        self.assertEqual(rows, [
            {'id': 'activity-analytics', 'name': '@mainframe/activity-analytics',
             'config': {'profileDirectory': str(self.profile)}},
            {'id': 'secrets-vault', 'name': '@mainframe/secrets-vault',
             'config': {'profileDirectory': str(self.profile)}},
        ])
        for language in ('en', 'ru'):
            meta = json.loads((self.output / 'locale' / f'{language}.json').read_text())['meta']
            self.assertTrue(meta['title'])
            self.assertTrue(meta['description'])
        self.assertEqual(ET.parse(self.output / 'icon.svg').getroot().tag,
                         '{http://www.w3.org/2000/svg}svg')
        self.assertEqual({p.relative_to(self.output).as_posix()
                          for p in self.output.rglob('*') if p.is_file()},
                         {'package.json', 'cordis.patch.yml', 'locale/en.json',
                          'locale/ru.json', 'icon.svg'})

    def test_profile_and_repository_are_not_read_or_written(self):
        marker = self.profile / 'do-not-open.db'
        marker.write_bytes(b'opaque fixture')
        original = Path.open
        def guarded_open(path, *args, **kwargs):
            if path == self.profile or self.profile in path.parents:
                self.fail('Generator opened a profile file')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded_open):
            self.generate()
        self.assertEqual(marker.read_bytes(), b'opaque fixture')
        self.assertEqual(list(self.profile.iterdir()), [marker])
        self.assertEqual(list(self.repo.iterdir()), [])

    @unittest.skipUnless(os.name == 'posix', 'POSIX permission bits')
    def test_owner_only_permissions_even_with_permissive_umask(self):
        old = os.umask(0)
        try:
            self.generate()
        finally:
            os.umask(old)
        for item in [self.output, *self.output.rglob('*')]:
            self.assertEqual(stat.S_IMODE(item.stat().st_mode),
                             0o700 if item.is_dir() else 0o600)

    @unittest.skipUnless(os.name == 'posix', 'POSIX permission bits')
    def test_restrictive_umask_still_produces_exact_owner_modes(self):
        old = os.umask(0o777)
        try:
            self.generate()
        finally:
            os.umask(old)
        self.assertEqual(stat.S_IMODE((self.output / 'locale').stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.output / 'package.json').stat().st_mode), 0o600)

    def test_rejects_output_ancestor_of_protected_tree(self):
        self.reject(output=self.root)
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_rejects_output_inside_repository_including_resolved_parent(self):
        self.reject(output=self.repo / 'private')
        self.reject(output=self.repo / 'missing' / '..' / 'private')
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_rejects_output_inside_profile_or_dsh_home(self):
        for target in (self.profile, self.profile / 'private', self.home, self.home / 'private'):
            with self.subTest(target=target.name):
                self.reject(output=target)
        self.assertEqual(list(self.profile.iterdir()), [])
        self.assertEqual(list(self.home.iterdir()), [])

    def test_default_dsh_home_boundary_uses_disposable_home(self):
        with patch.dict(os.environ, {'DSH_HOME': ''}), patch.object(Path, 'home', return_value=self.root):
            self.reject(output=self.root / '.dsh' / 'deployment')

    def test_dsh_home_resolves_symlink_for_boundary(self):
        alias = self.root / 'home-alias'
        alias.symlink_to(self.home, target_is_directory=True)
        with patch.dict(os.environ, {'DSH_HOME': str(alias)}):
            self.reject(output=self.home / 'private')

    def test_absolute_paths_are_required(self):
        for key in ('output', 'profile_directory'):
            with self.subTest(key=key):
                self.reject(**{key: Path('relative-path')})
        self.assertFalse(self.output.exists())

    def test_nonempty_output_is_preserved(self):
        self.output.mkdir()
        marker = self.output / 'foreign'
        marker.write_text('preserve')
        self.reject()
        self.assertEqual(marker.read_text(), 'preserve')
        self.assertEqual(list(self.output.iterdir()), [marker])

    def test_existing_empty_output_can_be_atomically_replaced(self):
        self.output.mkdir(mode=0o755)
        self.generate()
        self.assertTrue((self.output / 'package.json').is_file())
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)

    def test_file_output_and_missing_parent_are_rejected_without_creation(self):
        self.output.write_text('preserve')
        self.reject()
        self.assertEqual(self.output.read_text(), 'preserve')
        self.reject(output=self.root / 'missing-parent' / 'deployment')
        self.assertFalse((self.root / 'missing-parent').exists())

    def test_symlink_output_and_ancestors_are_rejected(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        self.reject(output=alias / 'deployment')
        self.output.symlink_to(self.root / 'missing')
        self.reject()
        self.assertTrue(self.output.is_symlink())
        self.assertFalse((self.root / 'missing').exists())

    def test_symlink_cannot_be_hidden_before_parent_traversal(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.profile, target_is_directory=True)
        self.reject(output=alias / '..' / 'deployment')
        self.assertFalse(self.output.exists())

    def test_conflict_created_during_staging_is_preserved(self):
        original = bundle._payload
        def introduce_conflict(profile):
            self.output.mkdir()
            (self.output / 'foreign').write_text('preserve')
            return original(profile)
        with patch.object(bundle, '_payload', side_effect=introduce_conflict):
            self.reject()
        self.assertEqual((self.output / 'foreign').read_text(), 'preserve')
        self.assertFalse(any(self.root.glob('.mainframe-deployment-*')))

    def test_symlink_profile_argument_is_rejected(self):
        alias = self.root / 'profile-alias'
        alias.symlink_to(self.profile, target_is_directory=True)
        self.reject(profile_directory=alias)
        self.assertFalse(self.output.exists())

    def test_paths_with_yaml_metacharacters_round_trip(self):
        profile = self.root / 'profile: # "quoted"'
        self.generate(profile_directory=profile)
        rows = json.loads((self.output / 'cordis.patch.yml').read_text())[0]['insert']
        self.assertEqual(rows[1]['config'], {'profileDirectory': str(profile)})
        self.assertFalse(profile.exists())

    def test_failed_publication_cleans_only_owned_staging_files(self):
        sentinel = self.root / '.foreign-stage'
        sentinel.mkdir()
        with patch.object(bundle.os, 'replace', side_effect=OSError('private path ' + str(self.root))):
            self.reject()
        self.assertTrue(sentinel.is_dir())
        self.assertFalse(self.output.exists())
        self.assertEqual(set(self.root.iterdir()), {self.repo, self.profile, self.home, sentinel})

    def test_failure_preserves_preexisting_empty_output(self):
        self.output.mkdir()
        with patch.object(bundle.os, 'replace', side_effect=OSError('private path')):
            self.reject()
        self.assertTrue(self.output.is_dir())
        self.assertEqual(list(self.output.iterdir()), [])

    def test_cli_success_does_not_print_private_paths(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = bundle.main(['--output', str(self.output), '--profile-directory', str(self.profile)])
        self.assertEqual(status, 0)
        self.assertNotIn(str(self.root), stdout.getvalue() + stderr.getvalue())

    def test_obsolete_python_option_is_rejected_without_echo(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit):
            bundle.main(['--output', str(self.output), '--profile-directory', str(self.profile),
                         '--vault-python', str(self.root / 'private-python')])
        self.assertNotIn(str(self.root), stderr.getvalue())
        self.assertFalse(self.output.exists())

    def test_cli_failure_hides_exception_paths(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = bundle.main(['--output', str(self.repo / 'private'),
                                  '--profile-directory', str(self.profile)])
        self.assertNotEqual(status, 0)
        self.assertNotIn(str(self.root), stdout.getvalue() + stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
