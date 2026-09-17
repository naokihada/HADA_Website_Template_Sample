"""Current Template adoption metadata; no execution history or commit identifiers."""
from pathlib import Path
import re
import yaml

FIELDS = ('Template ID', 'Template Name', 'Version', 'Release', 'Repository')

def parse(text):
    values = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        key, sep, value = line.partition(':')
        if not sep or key not in FIELDS or key in values:
            raise ValueError('Invalid or duplicate Template Base field')
        values[key] = value.strip()
    if set(values) != set(FIELDS) or any(not v or v == 'UNKNOWN' for v in values.values()):
        raise ValueError('Template Base is incomplete or unknown')
    if not re.fullmatch(r'\d+\.\d+\.\d+', values['Version']):
        raise ValueError('Invalid Template Base version')
    if values['Release'] != 'v' + values['Version']:
        raise ValueError('Template Base release/version mismatch')
    return values

def from_manifest(manifest):
    t = manifest['template']
    values = dict(zip(FIELDS, (t['id'], t['name'], t['version'], 'v' + t['version'], t['release_repository'])))
    parse(render(values))
    return values

def render(values):
    return '# Template Base\n\n' + '\n'.join(f'{key}: {values[key]}' for key in FIELDS) + '\n'

def check(root):
    """Absence supports legacy projects; an existing contradictory base is an error."""
    root = Path(root)
    base = root / 'TEMPLATE_BASE.md'
    if not base.exists():
        return None
    values = parse(base.read_text(encoding='utf-8-sig'))
    manifest = root / 'config/template.manifest.yaml'
    if not manifest.is_file():
        raise ValueError('Template Base exists without release manifest')
    expected = from_manifest(yaml.safe_load(manifest.read_text(encoding='utf-8-sig')))
    if values != expected:
        raise ValueError('Template Base does not match release manifest')
    return values
