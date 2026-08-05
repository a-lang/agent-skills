#!/usr/bin/env python3
"""
fix_terminology.py — Apply zh_TW terminology fixes from terminology.md to translations.py.

Scans terminology.md for "不翻「XX」" notes, extracts the disallowed CN terms,
then replaces them with the documented TW equivalents inside translations.py values.

Usage:
    uv run python3 skills/l10n-tw/scripts/fix_terminology.py \
        <translations.py> [--terms references/terminology.md]
"""

import argparse
import ast
import re
import sys
from pathlib import Path


DEFAULT_TERMS_PATH = Path(__file__).resolve().parents[1] / "references" / "terminology.md"


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
    """Load TRANSLATIONS from translations.py WITHOUT executing it.

    Parses the file as an AST and only accepts dict-literal assignments
    (``TRANSLATIONS = {...}`` / ``T = {...}``, optionally annotated like
    ``TRANSLATIONS: dict = {...}``). Values are evaluated with
    ast.literal_eval, so arbitrary code is never executed.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    # Pass 1: every top-level statement must be a docstring or an assignment
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            continue
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            raise ValueError(
                f"refusing to load {path}: non-assignment statement "
                f"({type(node).__name__}) — translations.py must be a pure dict literal")
    # Pass 2: find the TRANSLATIONS / T dict literal
    translations = None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        elif isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                raise ValueError(
                    f"refusing to load {path}: unsupported multi-target assignment")
            target = node.targets[0]
            value = node.value
        else:
            continue  # docstring
        if not (isinstance(target, ast.Name) and target.id in ("TRANSLATIONS", "T")):
            continue
        if value is None:
            raise ValueError(f"{target.id} must be assigned a dict literal in {path}")
        if not isinstance(value, ast.Dict):
            raise ValueError(f"{target.id} must be a dict literal in {path}")
        try:
            translations = ast.literal_eval(value)
        except ValueError as e:
            raise ValueError(
                f"{target.id} in {path} contains non-literal values ({e})") from None
        break
    if translations is None:
        raise ValueError(f"TRANSLATIONS dict not found in {path}")
    return translations


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
