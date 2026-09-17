"""Regression checks for adoption safety and publication boundaries (synthetic only)."""
import sys
import tempfile
import unittest
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/core'))
import template_base as tb
import upgrade_from_release as up
import validate_framework as vf
import build_site as build

class BaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        self.manifest = {'template': {'id': 'hada-website-template', 'name': 'HADA Website Operations Framework',
            'version': '0.1.3', 'release_repository': 'naokihada/HADA_Website_Template'}}
        (self.root / 'config/template.manifest.yaml').write_text(yaml.safe_dump(self.manifest))

    def test_legacy_absence_detects_manifest(self):
        self.assertIsNone(tb.check(self.root))
        self.assertEqual(up.detect_version(self.root), ('detected', '0.1.3'))

    def test_generation_roundtrip_no_commit(self):
        text = tb.render(tb.from_manifest(self.manifest))
        self.assertNotIn('commit', text.lower())
        self.assertEqual(tb.parse(text)['Release'], 'v0.1.3')

    def test_mismatch_blocks_even_assumed(self):
        values = tb.from_manifest(self.manifest)
        values.update(Version='0.2.0', Release='v0.2.0')
        (self.root / 'TEMPLATE_BASE.md').write_text(tb.render(values))
        self.assertEqual(up.detect_version(self.root, '0.1.3'), ('unknown', None))

    def test_unknown_and_duplicate_rejected(self):
        for text in ('# Template Base\nVersion: UNKNOWN\n', tb.render(tb.from_manifest(self.manifest)) + 'Version: 0.1.3\n'):
            with self.assertRaises(ValueError):
                tb.parse(text)

    def test_existing_new_path_collision_requires_review(self):
        self.assertEqual(up.three_way_action(None, b'user', b'template'), up.Action.REVIEW)

    def test_ai_publication_forbidden_case_insensitive(self):
        for value in ('AI', 'AI/reports', 'ai', 'Cursor', '.cursor'):
            self.assertIsNotNone(vf.forbidden_segment(value))

    def test_custom_publication_root(self):
        (self.root / 'config/term_dictionary.yaml').write_text('entries: []\n')
        (self.root / 'config/project.yaml').write_text('paths:\n  publication_root: custom-web\n')
        for locale in ('jp', 'en'):
            (self.root / 'content' / locale).mkdir(parents=True)
        (self.root / 'content/jp/index.md').write_text('# Example\n')
        build.build_site(self.root)
        self.assertTrue((self.root / 'custom-web/jp/index.html').exists())
        self.assertFalse((self.root / 'site').exists())

    def test_failed_upgrade_keeps_metadata(self):
        (self.root / 'AGENTS.md').write_text('# Test')
        path = self.root / 'TEMPLATE_BASE.md'
        path.write_text(tb.render(tb.from_manifest(self.manifest)))
        before = path.read_bytes()
        result = up.run_upgrade(self.root, network_check=lambda _: (False, 'fixture offline'))
        self.assertEqual(result.status, 'BLOCKED')
        self.assertEqual(path.read_bytes(), before)

if __name__ == '__main__':
    unittest.main()
