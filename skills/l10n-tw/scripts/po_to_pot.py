#!/usr/bin/env python3
"""
po_to_pot.py — Extract a POT template from any existing PO file.

This strips the translations from a source PO, producing a .pot template with
empty msgstr/msgstr[0] lines. Useful when you only have a translated PO file and
need to bootstrap a new localization from it.

Usage:
    uv run python3 skills/l10n-tw/scripts/po_to_pot.py \
        <input.po> -o <output.pot>
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# Re-use PO helpers from po_gen.py (same package)
from po_gen import decode_po, encode_po, get_comments, get_msgctxt, get_msgid, get_msgid_plural, parse_po_entries


def strip_translation(entry: str) -> str:
    """Return a POT entry with the same msgid/msgid_plural but empty msgstr."""
    lines = entry.split('\n')
    result: list[str] = []
    in_msgstr = False
    for line in lines:
        if line.startswith('msgstr'):
            in_msgstr = True
            continue
        if in_msgstr:
            if line.startswith('"'):
                continue
            in_msgstr = False
        result.append(line)

    # Ensure msgid_plural entries get a msgstr[0] line
    has_plural = get_msgid_plural(entry) is not None
    if has_plural:
        result.append('msgstr[0] ""')
    else:
        result.append('msgstr ""')

    return '\n'.join(result)


def build_pot_header() -> str:
    """Return a minimal POT header."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M+0800')
    return f'''# SOME DESCRIPTIVE TITLE.
# Copyright (C) {datetime.now().year} PACKAGE COPYRIGHT HOLDER
# This file is distributed under the same license as the PACKAGE package.
# FIRST AUTHOR <EMAIL@ADDRESS>, {datetime.now().year}.
#
#, fuzzy
msgid ""
msgstr ""
"Project-Id-Version: PACKAGE VERSION\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: {now}\\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"
"Language-Team: LANGUAGE <LL@li.org>\\n"
"Language: \\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
'''


def main():
    parser = argparse.ArgumentParser(
        description="Extract a POT template from a translated PO file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python3 po_to_pot.py ../lutris/zh_CN.po -o ../lutris/lutris.pot
        """,
    )
    parser.add_argument('po', type=Path, help='Path to input PO file')
    parser.add_argument('-o', '--output', type=Path, required=True, help='Output POT path')
    args = parser.parse_args()

    if not args.po.exists():
        print(f"❌ File not found: {args.po}", file=sys.stderr)
        sys.exit(1)

    text = args.po.read_text(encoding='utf-8')
    entries = parse_po_entries(text)

    pot_entries: list[str] = []
    for entry in entries:
        msgid = get_msgid(entry)
        if msgid == '' or msgid is None:
            # Header entry — skip original, use our own
            continue
        pot_entries.append(strip_translation(entry))

    pot_content = build_pot_header().strip() + '\n\n' + '\n\n'.join(pot_entries) + '\n'
    args.output.write_text(pot_content, encoding='utf-8')
    print(f"✅ POT: {args.output} ({len(pot_entries)} entries)")


if __name__ == '__main__':
    main()
