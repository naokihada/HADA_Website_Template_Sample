import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/core'))
import path_policy

class PathPolicyTests(unittest.TestCase):
    def test_current_repository_paths_are_within_limit(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(path_policy.scan_tree(root), [])

    def test_rejects_overlong_path(self):
        with tempfile.TemporaryDirectory(prefix='hada-path-') as temp:
            path = Path(temp) / ('x' * path_policy.MAX_ABSOLUTE_PATH)
            with self.assertRaises(ValueError):
                path_policy.ensure_path(path)

if __name__ == '__main__':
    unittest.main()
