import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/core'))
import migrate_legacy_workspace as migration

class LegacyTests(unittest.TestCase):
    def test_task_conflict_preserves_legacy(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'Cursor/tasks').mkdir(parents=True)
            (root / 'Cursor/tasks/CURRENT.md').write_text('old active task')
            (root / 'AI/tasks').mkdir(parents=True)
            (root / 'AI/tasks/CURRENT.md').write_text('new active task')
            plan = [{'path': p, 'sha256': h, 'classification': 'active-task', 'reason': 'active',
                'destination': 'AI/tasks/CURRENT.md'} for p, h in migration.inventory(root).items()]
            with self.assertRaises(ValueError): migration.migrate(root, plan)
            self.assertTrue((root / 'Cursor/tasks/CURRENT.md').exists())

    def test_hidden_history_preserved_dry_run_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / '.cursor').mkdir()
            (root / '.cursor/.hidden').write_bytes(b'evidence')
            plan = [{'path': p, 'sha256': h, 'classification': 'history', 'reason': 'retain'}
                for p, h in migration.inventory(root).items()]
            migration.migrate(root, plan, True)
            self.assertFalse((root / 'AI').exists())
            migration.migrate(root, plan)
            self.assertFalse((root / '.cursor').exists())
            self.assertEqual(migration.migrate(root, plan), [])
            self.assertTrue(any(p.read_bytes() == b'evidence' for p in (root / 'AI/history').rglob('.hidden')))

    def test_empty_legacy_roots_are_removed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / '.cursor').mkdir()
            (root / 'Cursor').mkdir()
            migration.migrate(root, [])
            self.assertFalse((root / '.cursor').exists())
            self.assertFalse((root / 'Cursor').exists())

if __name__ == '__main__': unittest.main()
