"""Inventory retired workspaces, then apply an explicitly classified migration plan."""
import argparse
import json
import sys
import uuid
from pathlib import Path
import file_transaction as tx

def inventory(root):
    entries = {}
    for name in ('.cursor', 'Cursor'):
        parent = tx.safe(root, name)
        if not parent.exists(): continue
        for p in parent.rglob('*'):
            rel = p.relative_to(root).as_posix()
            p = tx.safe(root, rel)
            if p.is_file(): entries[rel] = tx.digest(p)
    return entries

def migrate(root, plan, dry_run=False):
    current = inventory(root)
    legacy_roots = [tx.safe(root, name) for name in ('.cursor', 'Cursor')]
    if not current:
        if dry_run:
            return [{'path': name, 'after': None, 'reason': 'empty legacy directory'}
                    for name, parent in zip(('.cursor', 'Cursor'), legacy_roots) if parent.exists()]
        for parent in legacy_roots:
            if parent.exists():
                if any(parent.iterdir()):
                    raise ValueError('REVIEW_REQUIRED legacy directory changed during migration')
                parent.rmdir()
        return []
    if {e['path']: e['sha256'] for e in plan} != current:
        raise ValueError('REVIEW_REQUIRED inventory changed or classification incomplete')
    run = 'AI/history/legacy-' + uuid.uuid4().hex
    operations = []
    destinations = set()
    for item in plan:
        kind = item.get('classification')
        if kind not in ('history', 'active-task', 'project-rule', 'obsolete-adapter') or not item.get('reason'):
            raise ValueError('REVIEW_REQUIRED unknown legacy meaning')
        source = tx.safe(root, item['path'])
        data = source.read_bytes()
        operations.append(tx.entry(root, run + '/original/' + item['path'], data))
        if kind in ('active-task', 'project-rule'):
            rel = item.get('destination', '')
            valid = rel.startswith('AI/tasks/') if kind == 'active-task' else rel in ('AGENTS.md', 'SPEC.md')
            if not valid or rel in destinations: raise ValueError('REVIEW_REQUIRED ambiguous destination')
            destinations.add(rel)
            dest = tx.safe(root, rel)
            # Rules must have been semantically incorporated before approving removal.
            if kind == 'project-rule':
                if not dest.is_file() or tx.digest(dest) != item.get('destination_sha256'):
                    raise ValueError('REVIEW_REQUIRED incorporated rule evidence missing')
            elif dest.exists() and dest.read_bytes() != data:
                raise ValueError('REVIEW_REQUIRED active task conflict')
            else:
                operations.append(tx.entry(root, rel, data))
        operations.append(tx.entry(root, item['path'], None))
    # Preserve plan before any deletion; copies are ordered before all removals.
    operations.insert(0, tx.entry(root, run + '/PLAN.json', json.dumps(plan, indent=2).encode()))
    operations.sort(key=lambda e: e['after'] is None)
    if dry_run: return operations
    result = tx.apply(root, operations, tx.safe(root, run + '/backup'))
    for name in ('.cursor', 'Cursor'):
        parent = tx.safe(root, name)
        if not parent.exists(): continue
        for p in sorted(parent.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            p = tx.safe(root, p.relative_to(root).as_posix())
            if p.is_dir(): p.rmdir()
        parent.rmdir()
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--apply', type=Path)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    try:
        root = args.root.absolute()
        result = migrate(root, json.loads(args.apply.read_text()), args.dry_run) if args.apply else inventory(root)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print('REVIEW_REQUIRED: ' + str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__': sys.exit(main())
