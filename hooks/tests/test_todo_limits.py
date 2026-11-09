import importlib.util
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location('todo_limits', Path(__file__).resolve().parents[1] / 'mainframe-todo-limits.py')
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)
HEADINGS = ('Запланировано', 'На рассмотрении', 'Отложено', 'Отказались')
NOTE = '# Фильтры заказов\n\n## Суть\nЗапоминать выбор фильтров.\n\n## Ожидаемый результат\nВыбор сохраняется между посещениями.\n\n## Ограничения\nТолько список заказов.\n'


class TodoLimitsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / '.docs/todos').mkdir(parents=True)
        self.note = self.root / '.docs/todos/filters.md'
        self.note.write_text(NOTE)
        self.index = self.root / '.docs/todo'

    def index_text(self, summary='Сохранять фильтры списка заказов.', group=0, target='todos/filters.md'):
        return '# TODO\n\n' + '\n\n'.join('## ' + h + ('\n- ' + summary + ' [Подробнее](' + target + ')' if i == group else '') for i, h in enumerate(HEADINGS)) + '\n'

    def test_summary_boundary_counts_unicode_characters_without_link(self):
        self.assertIsNone(guard.check_write(str(self.root), str(self.index), self.index_text('я' * 500)))
        self.assertIn('500', guard.check_write(str(self.root), str(self.index), self.index_text('я' * 501)))

    def test_note_boundary_counts_all_content(self):
        exact = NOTE + 'я' * (5000 - len(NOTE))
        self.assertIsNone(guard.check_write(str(self.root), str(self.note), exact))
        self.assertIn('5000', guard.check_write(str(self.root), str(self.note), exact + 'я'))

    def test_note_structure_and_index_link_are_checked(self):
        self.assertIsNotNone(guard.check_write(str(self.root), str(self.index), '# TODO\n'))
        self.assertIsNotNone(guard.check_write(str(self.root), str(self.note), 'Как выше обсудили.'))
        self.assertIsNotNone(guard.check_write(str(self.root), str(self.index), self.index_text(target='todos/missing.md')))
        self.assertIsNotNone(guard.check_write(str(self.root), str(self.index), self.index_text(target='../outside.md')))

    def test_declined_entry_requires_decision_in_linked_note(self):
        self.assertIsNotNone(guard.check_write(str(self.root), str(self.index), self.index_text(group=3)))
        self.note.write_text(NOTE + '\n## Решение\nОтказались: существующий фильтр уже закрывает этот сценарий.\n')
        self.assertIsNone(guard.check_write(str(self.root), str(self.index), self.index_text(group=3)))

    def test_only_changed_rows_and_addressed_notes_are_validated(self):
        old = self.index_text('я' * 501)
        self.index.write_text(old)
        (self.root / '.docs/todos/unrelated.md').write_text('я' * 9000)
        self.assertIsNone(guard.check_write(str(self.root), str(self.index), old + '\n'))
        self.assertIsNone(guard.check_write(str(self.root), str(self.root / 'README.md'), 'x' * 9000))
        self.assertIsNone(guard.check_write(str(self.root), str(self.note), NOTE))

    def test_moving_a_row_into_declined_is_a_changed_entry(self):
        self.index.write_text(self.index_text())
        self.assertIsNotNone(guard.check_write(str(self.root), str(self.index), self.index_text(group=3)))

    def test_note_edit_cannot_remove_existing_decline_reason(self):
        self.index.write_text(self.index_text(group=3))
        self.note.write_text(NOTE + '\n## Решение\nОтказались из-за дублирования существующей функции.\n')
        self.assertIsNotNone(guard.check_write(str(self.root), str(self.note), NOTE))

    def test_large_complete_note_does_not_bypass_limit(self):
        self.assertIsNotNone(guard.check_write(str(self.root), str(self.note), NOTE + 'я' * 1_000_001))

    def test_write_edit_and_patch_reject_same_overlong_note(self):
        self.assertIsNotNone(guard.check_edit(str(self.root), str(self.note), 'Запоминать выбор фильтров.', 'я' * 5001))
        patch = '*** Begin Patch\n*** Update File: .docs/todos/filters.md\n@@\n-Запоминать выбор фильтров.\n+' + 'я' * 5001 + '\n*** End Patch\n'
        self.assertIsNotNone(guard.check_patch(str(self.root), patch))

    def test_patch_accepts_note_then_index_in_one_operation(self):
        patch = '*** Begin Patch\n*** Add File: .docs/todos/new.md\n' + ''.join('+' + s + '\n' for s in NOTE.splitlines())
        patch += '*** Add File: .docs/todo\n' + ''.join('+' + s + '\n' for s in self.index_text(target='todos/new.md').splitlines()) + '*** End Patch\n'
        self.assertIsNone(guard.check_patch(str(self.root), patch))

    def test_symlinks_and_unresolved_edits_are_neutral_and_never_write(self):
        outside = self.root / 'outside.md'
        outside.write_text('private synthetic material')
        link = self.root / '.docs/todos/link.md'
        link.symlink_to(outside)
        self.assertIsNone(guard.check_write(str(self.root), str(link), 'x' * 9000))
        self.assertIsNone(guard.check_edit(str(self.root), str(self.note), 'absent', 'x' * 9000))
        self.assertIsNone(guard.check_patch(None, 'not a patch'))
        self.assertEqual(outside.read_text(), 'private synthetic material')
        self.assertEqual(self.note.read_text(), NOTE)


if __name__ == '__main__':
    unittest.main()
