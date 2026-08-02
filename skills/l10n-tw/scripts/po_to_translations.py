#!/usr/bin/env python3
"""
po_to_translations.py — Extract existing translations from a PO file into translations.py.

Usage:
    uv run python3 skills/l10n-tw/scripts/po_to_translations.py \
        <input.po> -o <translations.py>

By default, only entries with a non-empty msgstr are written. Use --all to
include every msgid (with empty msgstr for untranslated entries).

Handles msgctxt, msgid_plural, and multi-line msgstr.
"""

import argparse
import re
import sys
from pathlib import Path

from po_gen import decode_po, get_msgctxt, get_msgid, get_msgid_plural, parse_po_entries


def get_msgstr(entry: str, has_plural: bool) -> str | list[str] | None:
    """Extract decoded msgstr from a PO entry.

    Args:
        has_plural: True if the entry has msgid_plural (must return a list).

    Returns:
        - None if no msgstr found
        - str for singular entries
        - list[str] for plural entries (msgstr[0], msgstr[1], ...)
    """
    lines = entry.split('\n')
    plural_forms: dict[int, list[str]] = {}
    current_index: int | None = None
    in_msgstr = False

    for line in lines:
        m = re.match(r'^msgstr(?:\[(\d+)\])?\s+"(.*)"$', line)
        if m:
            in_msgstr = True
            index_str, text = m.groups()
            current_index = int(index_str) if index_str else 0
            plural_forms.setdefault(current_index, []).append(text)
        elif in_msgstr and line.startswith('"'):
            m2 = re.match(r'^"(.*)"$', line)
            if m2 and current_index is not None:
                plural_forms[current_index].append(m2.group(1))
        elif in_msgstr and not line.startswith('"'):
            in_msgstr = False
            current_index = None

    if not plural_forms:
        return None

    sorted_indices = sorted(plural_forms.keys())
    decoded_forms = [decode_po(''.join(plural_forms[i])) for i in sorted_indices]

    # If the entry has msgid_plural, always return a list so po_gen.py emits
    # msgstr[0] ... correctly. Languages like zh_TW use only one plural form
    # (nplurals=1; plural=0) but still need the msgstr[0] syntax.
    if has_plural:
        return decoded_forms

    return decoded_forms[0]


def py_string_literal(s: str) -> str:
    """Escape a string for writing as a single-quoted Python string literal."""
    return (s
            .replace('\\', '\\\\')
            .replace("'", "\\'")
            .replace('\n', '\\n')
            .replace('\t', '\\t'))


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
        description="Extract msgstr from a PO file into translations.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python3 po_to_translations.py old-zh_TW.po -o translations.py
  uv run python3 po_to_translations.py old-zh_TW.po -o translations.py --all
        """,
    )
    parser.add_argument('po', type=Path, help='Path to input PO file')
    parser.add_argument('-o', '--output', type=Path, required=True,
                        help='Output translations.py path')
    parser.add_argument('--all', action='store_true',
                        help='Include all msgids, even untranslated ones')
    args = parser.parse_args()

    if not args.po.exists():
        print(f"❌ File not found: {args.po}", file=sys.stderr)
        sys.exit(1)

    text = args.po.read_text(encoding='utf-8')
    entries = parse_po_entries(text)

    translations: dict[str, str | list[str]] = {}
    skipped = 0

    for entry in entries:
        msgid = get_msgid(entry)
        if not msgid:
            continue  # skip header

        msgctxt = get_msgctxt(entry)
        key = (msgctxt + '\x04' + msgid) if msgctxt else msgid

        has_plural = get_msgid_plural(entry) is not None
        msgstr = get_msgstr(entry, has_plural)
        if msgstr is None:
            continue

        if isinstance(msgstr, list):
            is_empty = all(not s.strip() for s in msgstr)
        else:
            is_empty = not msgstr.strip()

        if is_empty and not args.all:
            skipped += 1
            continue

        translations[key] = msgstr

    write_translations_py(translations, args.output)

    print(f"✅ translations.py: {args.output}")
    print(f"   Written {len(translations)} entries")
    if skipped:
        print(f"   Skipped {skipped} empty entries (use --all to include)")


if __name__ == '__main__':
    main()
