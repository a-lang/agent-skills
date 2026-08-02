#!/usr/bin/env python3
"""
merge_batches.py — Merge multiple batch JSON files into translations.py.

Usage:
    uv run python3 skills/l10n-tw/scripts/merge_batches.py \
        batch1.json batch2.json ... -o translations.py

Empty values are skipped. Conflicting keys with different non-empty values
raise an error unless --override is used.
"""

import argparse
import json
import sys
from pathlib import Path


def py_string_literal(s: str) -> str:
    """Escape a string for writing as a single-quoted Python string literal."""
    return (s
            .replace('\\', '\\\\')
            .replace("'", "\\'")
            .replace('\n', '\\n')
            .replace('\t', '\\t'))


def is_empty_value(val):
    """Check if a batch value is empty (empty string or list of empty strings)."""
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip()
    if isinstance(val, list):
        return all(not (isinstance(v, str) and v.strip()) for v in val)
    return False


def write_translations_py(translations: dict[str, str | list[str]], path: Path) -> None:
    """Write a translations.py file with proper escaping."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write('TRANSLATIONS = {\n')
        for key, val in translations.items():
            key_lit = py_string_literal(key)
            if isinstance(val, list):
                vals_lit = ', '.join(f"'{py_string_literal(v)}'" for v in val)
                f.write(f"    '{key_lit}': [{vals_lit}],\n")
            else:
                val_lit = py_string_literal(val)
                f.write(f"    '{key_lit}': '{val_lit}',\n")
        f.write('}\n')


def main():
    parser = argparse.ArgumentParser(
        description="Merge batch JSON files into translations.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python3 merge_batches.py batch1.json batch2.json -o translations.py
  uv run python3 merge_batches.py batch*.json -o translations.py --override
        """,
    )
    parser.add_argument('batches', nargs='+', type=Path,
                        help='Batch JSON files to merge')
    parser.add_argument('-o', '--output', type=Path, required=True,
                        help='Output translations.py path')
    parser.add_argument('--override', action='store_true',
                        help='Allow later batch to override earlier non-empty value')
    args = parser.parse_args()

    translations: dict[str, str | list[str]] = {}
    conflicts: list[tuple[str, Path, str | list, Path, str | list]] = []
    total_files = 0
    total_entries = 0

    for batch_path in args.batches:
        if not batch_path.exists():
            print(f"❌ File not found: {batch_path}", file=sys.stderr)
            sys.exit(1)

        try:
            with open(batch_path, 'r', encoding='utf-8') as f:
                batch = json.load(f)
        except json.JSONDecodeError as ex:
            print(f"❌ Invalid JSON in {batch_path}: {ex}", file=sys.stderr)
            sys.exit(1)

        total_files += 1
        for key, val in batch.items():
            total_entries += 1
            if is_empty_value(val):
                continue

            if key in translations:
                existing = translations[key]
                if existing != val:
                    if args.override:
                        translations[key] = val
                    else:
                        conflicts.append((key, batch_path, val, Path('<previous>'), existing))
                continue

            translations[key] = val

    if conflicts:
        print(f"❌ {len(conflicts)} conflicting key(s):", file=sys.stderr)
        for key, path_a, val_a, path_b, val_b in conflicts[:5]:
            print(f"  - {key!r}", file=sys.stderr)
            print(f"    {path_a}: {val_a!r}", file=sys.stderr)
            print(f"    {path_b}: {val_b!r}", file=sys.stderr)
        sys.exit(1)

    write_translations_py(translations, args.output)

    print(f"✅ translations.py: {args.output}")
    print(f"   Merged {total_entries} entries from {total_files} files")
    print(f"   Written {len(translations)} non-empty entries")


if __name__ == '__main__':
    main()
