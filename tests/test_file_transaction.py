import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/core'))
import file_transaction as tx

class TransactionTests(unittest.TestCase):
    def test_conflict_before_any_write(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root / 'a'; p.write_bytes(b'old')
            entries = [tx.entry(root, 'new', b'new'), tx.entry(root, 'a', b'update')]
            p.write_bytes(b'user')
            with self.assertRaises(ValueError): tx.apply(root, entries, root / 'backup')
            self.assertFalse((root / 'new').exists())
            self.assertEqual(p.read_bytes(), b'user')

    def test_idempotent_with_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root / 'a'; p.write_bytes(b'old')
            entries = [tx.entry(root, 'a', b'new')]
            self.assertEqual(tx.apply(root, entries, root / 'backup'), ['a'])
            self.assertEqual(tx.apply(root, entries, root / 'backup'), [])
            self.assertEqual((root / 'backup/a').read_bytes(), b'old')

    def test_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for rel in ('../x', '/x', 'C:/x', '.git/config', 'x/../../z'):
                with self.assertRaises(ValueError): tx.safe(Path(d), rel)

if __name__ == '__main__': unittest.main()
