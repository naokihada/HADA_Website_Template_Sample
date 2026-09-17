"""Hash-bound reviewed file plans with immutable backups; never operates on Git."""
import hashlib
import json
from pathlib import Path
from path_policy import ensure_path

def safe(root, rel):
    root = ensure_path(root, label='root')
    parts = rel.replace('\\', '/').split('/')
    if any(x in ('', '.', '..') or ':' in x for x in parts) or parts[0].lower() == '.git':
        raise ValueError('Unsafe relative path')
    p = root
    for node in [root, *root.parents]:
        if node.is_symlink() or (hasattr(node, 'is_junction') and node.is_junction()):
            raise ValueError('Linked root')
    for part in parts:
        p = p / part
        ensure_path(p, label='target')
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('Linked path')
    if not p.resolve().is_relative_to(root.resolve()):
        raise ValueError('Escaped root')
    return p

def digest(path):
    if path.exists() and not path.is_file():
        raise ValueError('Expected a file')
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def entry(root, rel, data):
    return {'path': rel, 'before': digest(safe(root, rel)),
        'after': hashlib.sha256(data).hexdigest() if data is not None else None,
        'content_hex': data.hex() if data is not None else None}

def apply(root, entries, backup):
    """Reject stale plans before any write; repeat already-applied plans as no-ops."""
    pending = []
    for e in entries:
        p = safe(root, e['path'])
        now = digest(p)
        data = bytes.fromhex(e['content_hex']) if e['content_hex'] is not None else None
        expected = hashlib.sha256(data).hexdigest() if data is not None else None
        if expected != e['after']:
            raise ValueError('Plan content hash mismatch')
        if now == e['after']:
            continue
        if now != e['before']:
            raise ValueError('REVIEW_REQUIRED changed since planning: ' + e['path'])
        pending.append((e, p, data))
    if not pending:
        return []
    backup = Path(backup)
    backup.mkdir(parents=True, exist_ok=False)
    for e, p, data in pending:
        if p.is_file():
            dest = safe(backup, e['path'])
            dest.parent.mkdir(parents=True, exist_ok=True)
            original = p.read_bytes()
            if hashlib.sha256(original).hexdigest() != e['before']:
                raise ValueError('Changed while backing up')
            dest.write_bytes(original)
    (backup / 'BACKUP.json').write_text(json.dumps(entries, indent=2), encoding='utf-8')
    for e, p, data in pending:
        if digest(p) != e['before']:
            raise ValueError('Changed while applying: ' + e['path'])
        if data is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
    return [e['path'] for e, _, _ in pending]
