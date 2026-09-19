import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/core'))
import manifest_schema

class ManifestSchemaTests(unittest.TestCase):
    def valid(self):
        return {'manifest_version': '1.0', 'schema_version': '0.1',
                'template': {'id': 'hada-website-template', 'name': 'HADA',
                             'version': '0.2.0', 'release': 'v0.2.0'},
                'compatibility': {'schema_version': '0.1', 'data_format_version': '0.1'},
                'files': {'template_base': 'TEMPLATE_BASE.md'}}

    def test_accepts_common_manifest(self):
        manifest = self.valid()
        self.assertIs(manifest_schema.validate(manifest), manifest)

    def test_rejects_missing_required_field(self):
        manifest = self.valid()
        del manifest['files']
        with self.assertRaises(ValueError):
            manifest_schema.validate(manifest)

    def test_rejects_release_mismatch(self):
        manifest = self.valid()
        manifest['template']['release'] = 'v0.1.3'
        with self.assertRaises(ValueError):
            manifest_schema.validate(manifest)

if __name__ == '__main__':
    unittest.main()
