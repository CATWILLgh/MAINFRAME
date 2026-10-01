from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'mainframe-commit-checkpoint.py'
SPEC = importlib.util.spec_from_file_location('checkpoint', SOURCE)
HOOK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOOK)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mainframe-checkpoint-test-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.state = self.base / 'state'
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'work.txt').write_text('work in progress\n')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout

    def observe(self, event, lines=0, scope='session'):
        return HOOK.observe(scope, str(self.repo), event, lines, state_root=self.state)

    def test_small_work_is_silent_until_edit_threshold_then_deduplicates(self):
        for i in range(HOOK.EDIT_THRESHOLD - 1):
            self.assertIsNone(self.observe(str(i)))
        self.assertIn('Conventional', self.observe('crossing'))
        self.assertIsNone(self.observe('crossing', HOOK.LINE_THRESHOLD))

    def test_large_single_edit_reminds_even_before_first_commit(self):
        self.assertIn('Commit checkpoint', self.observe('large', HOOK.LINE_THRESHOLD))
        self.assertIsNone(self.observe('next', HOOK.LINE_THRESHOLD))

    def test_cooldown_requires_new_accumulation_not_just_elapsed_time(self):
        with patch.object(HOOK.time, 'time', return_value=1000):
            self.assertIsNotNone(self.observe('first', HOOK.LINE_THRESHOLD))
            self.assertIsNone(self.observe('during', 1))
        with patch.object(HOOK.time, 'time', return_value=1601):
            self.assertIsNone(self.observe('later', 1))
            self.assertIsNotNone(self.observe('more', HOOK.LINE_THRESHOLD))

    def test_new_head_resets_accumulation_and_real_commit_is_not_performed_by_hook(self):
        for i in range(HOOK.EDIT_THRESHOLD - 1): self.observe(str(i))
        self.git('commit', '--allow-empty', '-qm', 'chore: fixture checkpoint')
        head = self.git('rev-parse', 'HEAD')
        self.assertIsNone(self.observe('after-commit'))
        self.assertEqual(head, self.git('rev-parse', 'HEAD'))
        self.assertIn('work.txt', self.git('status', '--porcelain'))

    def test_clean_worktree_does_not_remind_even_after_large_edit_activity(self):
        self.git('add', 'work.txt')
        self.git('commit', '-qm', 'chore: fixture baseline')
        self.assertIsNone(self.observe('net-zero', HOOK.LINE_THRESHOLD))

    def test_scope_and_repository_are_isolated(self):
        self.assertIsNotNone(self.observe('large', HOOK.LINE_THRESHOLD))
        self.assertIsNotNone(self.observe('large', HOOK.LINE_THRESHOLD, scope='other'))
        other = self.base / 'other'; other.mkdir()
        subprocess.run(['git', '-C', str(other), 'init', '-q'], check=True)
        (other / 'work.txt').write_text('dirty\n')
        self.assertIsNotNone(HOOK.observe('session', str(other), 'large', HOOK.LINE_THRESHOLD, state_root=self.state))

    def test_concurrent_duplicate_delivery_counts_once(self):
        self.observe('initialize')
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.observe('duplicate', HOOK.LINE_THRESHOLD), range(16)))
        self.assertEqual(sum(value is not None for value in results), 1)
        with sqlite3.connect(self.state / 'commit-checkpoint.sqlite3') as con:
            self.assertEqual(con.execute('SELECT count(*) FROM events').fetchone()[0], 2)

    def test_non_git_missing_identity_and_unsafe_storage_fail_silently(self):
        self.assertIsNone(HOOK.observe('', str(self.repo), 'event', state_root=self.state))
        self.assertIsNone(HOOK.observe('session', str(self.base), 'event', 10000, state_root=self.state))
        self.assertFalse(self.state.exists())
        self.state.mkdir(mode=0o755)
        self.assertIsNone(self.observe('event', 10000))
        self.assertFalse((self.state / 'commit-checkpoint.sqlite3').exists())

    def test_symlink_and_hardlinked_database_are_rejected(self):
        target = self.base / 'target'; target.write_text('preserve')
        self.state.mkdir(mode=0o700)
        db = self.state / 'commit-checkpoint.sqlite3'
        db.symlink_to(target)
        self.assertIsNone(self.observe('symlink', 10000))
        self.assertEqual(target.read_text(), 'preserve')
        db.unlink(); db.hardlink_to(target)
        self.assertIsNone(self.observe('hardlink', 10000))
        self.assertEqual(target.read_text(), 'preserve')

    def test_bounded_capacity_and_expiration(self):
        with patch.object(HOOK, 'MAX_EVENTS', 1), patch.object(HOOK.time, 'time', return_value=1000):
            self.assertIsNotNone(self.observe('one', HOOK.LINE_THRESHOLD))
            self.assertIsNone(self.observe('two', HOOK.LINE_THRESHOLD))
        with patch.object(HOOK.time, 'time', return_value=1000 + HOOK.TTL_SECONDS + 1):
            self.assertIsNotNone(self.observe('two', HOOK.LINE_THRESHOLD))

    def test_retained_state_has_no_source_paths_payloads_or_raw_native_identity(self):
        self.observe('native-sensitive-id', HOOK.LINE_THRESHOLD, scope='native-sensitive-scope')
        raw = (self.state / 'commit-checkpoint.sqlite3').read_bytes()
        for value in (str(self.repo), 'native-sensitive-id', 'native-sensitive-scope', 'unborn:'):
            self.assertNotIn(value.encode(), raw)

    def test_no_source_text_reads_or_git_mutations_are_needed(self):
        secret = self.repo / '.env'; secret.write_text('do not read')
        before = self.git('status', '--porcelain')
        self.assertIsNotNone(self.observe('editing', HOOK.LINE_THRESHOLD))
        self.assertEqual(before, self.git('status', '--porcelain'))
        self.assertFalse((self.repo / '.git/index').exists())


if __name__ == '__main__': unittest.main()
