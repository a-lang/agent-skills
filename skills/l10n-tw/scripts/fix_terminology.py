#!/usr/bin/env python3
"""
fix_terminology.py — Apply zh_TW terminology fixes from terminology.md to translations.py.

Scans terminology.md for "不翻「XX」" notes, extracts the disallowed CN terms,
then replaces them with the documented TW equivalents inside translations.py values.

Usage:
    uv run python3 skills/l10n-tw/scripts/fix_terminology.py \
        <translations.py> [--terms terminology.md]
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path


DEFAULT_TERMS_PATH = Path(__file__).resolve().parents[1] / "terminology.md"


def load_replacements(terms_path: Path) -> list[tuple[str, str]]:
    """Parse terminology.md and return (old_CN, new_TW) pairs.

    Looks for lines like:
        | default | 預設 | 不翻「默認」 |
    """
    text = terms_path.read_text(encoding='utf-8')
    replacements: list[tuple[str, str]] = []
    seen: set[str] = set()

    for line in text.split('\n'):
        # Find a table cell containing 不翻「...」
        m = re.search(r'不翻「([^」]+)」', line)
        if not m:
            continue
        old_terms = [t.strip() for t in m.group(1).split('/')]
        # Find the TW equivalent: the cell before the 不翻 note.
        cells = [c.strip() for c in line.split('|')]
        if len(cells) >= 4:
            tw_term = cells[-3]  # tw term is the cell before the 不翻 note cell
        else:
            continue
        for old in old_terms:
            if old and old not in seen:
                replacements.append((old, tw_term))
                seen.add(old)

    return replacements


def load_translations(path: Path) -> dict:
    """Load a translations.py file as a module and return TRANSLATIONS."""
    spec = importlib.util.spec_from_file_location("translations_mod", str(path))
    if not spec or not spec.loader:
        raise ValueError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    # Don't add to sys.modules to avoid conflicts
    spec.loader.exec_module(mod)
    if hasattr(mod, 'TRANSLATIONS'):
        return mod.TRANSLATIONS
    if hasattr(mod, 'T'):
        return mod.T
    raise ValueError(f"TRANSLATIONS dict not found in {path}")


def fix_value(val: str | list[str], replacements: list[tuple[str, str]]) -> str | list[str]:
    """Apply replacements to a single value or list of plural forms."""
    if isinstance(val, list):
        return [fix_value(v, replacements) for v in val]

    for old, new in replacements:
        val = val.replace(old, new)
    return val


def write_translations_py(translations: dict, path: Path):
    """Write a translations.py file with proper escaping."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write('TRANSLATIONS = {\n')
        for key, val in translations.items():
            py_key = key.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
            if isinstance(val, list):
                py_vals = [
                    v.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
                    for v in val
                ]
                f.write("    '{}': [{}],\n".format(py_key, ", ".join("'" + v + "'" for v in py_vals)))
            else:
                py_val = val.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
                f.write(f"    '{py_key}': '{py_val}',\n")
        f.write('}\n')


def main():
    parser = argparse.ArgumentParser(
        description="Apply terminology fixes from terminology.md to translations.py"
    )
    parser.add_argument('translations', type=Path, help='Path to translations.py')
    parser.add_argument(
        '--terms',
        type=Path,
        default=DEFAULT_TERMS_PATH,
        help=f'Path to terminology.md (default: {DEFAULT_TERMS_PATH})',
    )
    args = parser.parse_args()

    if not args.translations.exists():
        print(f"❌ File not found: {args.translations}", file=sys.stderr)
        sys.exit(1)
    if not args.terms.exists():
        print(f"❌ Terms file not found: {args.terms}", file=sys.stderr)
        sys.exit(1)

    replacements = load_replacements(args.terms)
    print(f"Loaded {len(replacements)} terminology replacements from {args.terms}")

    translations = load_translations(args.translations)
    fixed = 0
    remaining: dict[str, int] = {}

    for key, val in translations.items():
        new_val = fix_value(val, replacements)
        if new_val != val:
            translations[key] = new_val
            fixed += 1

    write_translations_py(translations, args.translations)
    print(f"✅ Fixed {fixed} entries in {args.translations}")

    # Final check
    for old, _ in replacements:
        count = sum(
            1
            for val in translations.values()
            for s in (val if isinstance(val, list) else [val])
            if old in s
        )
        if count:
            remaining[old] = count

    if remaining:
        print("⚠️  Remaining terms:")
        for term, count in sorted(remaining.items()):
            print(f'  "{term}" x{count}')
    else:
        print("✅ All target terms cleaned")


if __name__ == '__main__':
    main()
