"""Windows-safe path length policy for repository and evidence operations."""
from pathlib import Path

MAX_ABSOLUTE_PATH = 240

def ensure_path(path, *, label='path'):
    value = Path(path).absolute()
    if len(str(value)) > MAX_ABSOLUTE_PATH:
        raise ValueError(f'{label} exceeds {MAX_ABSOLUTE_PATH} characters: {value}')
    return value

def scan_tree(root, *, limit=MAX_ABSOLUTE_PATH):
    root = ensure_path(root, label='root')
    records = []
    for item in root.rglob('*'):
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            continue
        length = len(str(item.absolute()))
        if length > limit:
            records.append({'length': length, 'path': str(item.absolute())})
    return sorted(records, key=lambda row: (-row['length'], row['path']))
