#!/usr/bin/env python3
"""
extract_batch.py — Extract a batch of entries from a PO/POT file into a JSON map.

Usage:
    python3 extract_batch.py <input.po|input.pot> <out.json> <start_line> <end_line>

Extracts entries whose first line falls within the 1-based inclusive line
range [start_line, end_line] and writes them to <out.json> as
{"msgid": "translation"} for translation.

Source type detection:
  - .pot  → every entry in the range is extracted with an empty msgstr
  - .po   → prompts for which entries to extract (untranslated only, or all).
            Use --untranslated / --all to skip the prompt. Existing msgstr
            values are preserved so apply_translations.py never overwrites
            finished translations with empty strings.

Features:
  - Handles multi-line msgid and msgstr (PO escape sequences)
  - Excludes the header entry (empty msgid)
  - Reports batch stats (entry count, line range)
"""

import argparse
import json
import re
import sys


# ── PO string helpers ────────────────────────────────────────────────────

def decode_po(s: str) -> str:
    return (s
            .replace('\\"', '\x00Q')
            .replace('\\\\', '\x00B')
            .replace('\\n', '\n')
            .replace('\\t', '\t')
            .replace('\x00Q', '"')
            .replace('\x00B', '\\'))


# ── Parsing ──────────────────────────────────────────────────────────────

def parse_entries_with_lines(text: str) -> list[tuple[str, int, str]]:
    """Return list of (msgid, start_line, entry_text).

    Entries are blank-line separated; start_line is 1-based.
    The header entry has msgid=''.
    """
    entries: list[tuple[str, int, str]] = []
    buf: list[str] = []
    start: int | None = None

    for i, line in enumerate(text.split('\n')):
        if not line.strip():
            if buf:
                entries.append((get_msgid(buf) or '', start or 1, '\n'.join(buf)))
                buf = []
                start = None
            continue
        if start is None:
            start = i + 1
        buf.append(line)
    if buf:
        entries.append((get_msgid(buf) or '', start or 1, '\n'.join(buf)))
    return entries


def get_msgid(lines: list[str]) -> str | None:
    """Extract full decoded msgid from an entry's lines (handles multi-line)."""
    parts: list[str] = []
    in_msgid = False
    for line in lines:
        m = re.match(r'^msgid\s+"(.*)"$', line)
        if m:
            parts.append(m.group(1))
            in_msgid = True
        elif in_msgid and line.startswith('"'):
            m2 = re.match(r'^"(.*)"$', line)
            if m2:
                parts.append(m2.group(1))
        elif in_msgid and not line.startswith('"'):
            break
    if not parts:
        return None
    return decode_po(''.join(parts))


def get_msgstr(lines: list[str]) -> str:
    """Extract decoded msgstr from an entry's lines (handles multi-line)."""
    parts: list[str] = []
    in_msgstr = False
    for line in lines:
        m = re.match(r'^msgstr(?:\[\d+\])?\s+"(.*)"$', line)
        if m:
            parts.append(m.group(1))
            in_msgstr = True
        elif in_msgstr and line.startswith('"'):
            m2 = re.match(r'^"(.*)"$', line)
            if m2:
                parts.append(m2.group(1))
        elif in_msgstr and not line.startswith('"'):
            break
    return decode_po(''.join(parts))


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract a batch of entries from PO/POT into a JSON map",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Source type detection:\n"
            "  .pot  -> every entry in the range, empty msgstr\n"
            "  .po   -> prompt: untranslated only, or all (existing msgstr\n"
            "           preserved). Use --untranslated / --all to skip prompt."
        ))
    parser.add_argument('input', help='Path to .pot or .po source file')
    parser.add_argument('out', help='Path to output JSON file')
    parser.add_argument('start_line', type=int,
                        help='First line of range (1-based, inclusive)')
    parser.add_argument('end_line', type=int,
                        help='Last line of range (1-based, inclusive)')
    parser.add_argument('--untranslated', action='store_true',
                        help='For .po input: only untranslated entries (no prompt)')
    parser.add_argument('--all', action='store_true',
                        help='For .po input: all entries (no prompt)')
    parser.add_argument('--verify-total', type=int, default=None, metavar='N',
                        help='Assert the source holds exactly N translatable entries '
                             '(header excluded). Exits non-zero if the source count '
                             'differs, so you catch a wrong stated total before '
                             'slicing. For cross-batch coverage use '
                             'merge_batches.py --expected-total.')
    args = parser.parse_args()

    if args.start_line < 1 or args.end_line < args.start_line:
        print(f"❌ Invalid line range: [{args.start_line}, {args.end_line}]",
              file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            text = f.read()
    except OSError as ex:
        print(f"❌ Cannot read {args.input}: {ex}", file=sys.stderr)
        sys.exit(1)

    is_po = args.input.lower().endswith('.po')

    if not is_po:
        untranslated_only = False
        keep_msgstr = False
    elif args.untranslated:
        untranslated_only = True
        keep_msgstr = False
    elif args.all:
        untranslated_only = False
        keep_msgstr = True
    else:
        print("Input is a .po file. Which entries should be extracted?")
        print("  1) Untranslated only (empty msgstr) — recommended")
        print("  2) All entries (existing msgstr preserved)")
        try:
            choice = input("Choice [1/2]: ").strip()
        except EOFError:
            choice = '1'
        untranslated_only = choice != '2'
        keep_msgstr = not untranslated_only

    entries = parse_entries_with_lines(text)
    batch: dict[str, str] = {}
    matched = 0

    for msgid, start_line, entry in entries:
        if not msgid:
            continue  # header
        if not (args.start_line <= start_line <= args.end_line):
            continue
        if untranslated_only and get_msgstr(entry.split('\n')):
            continue
        batch[msgid] = get_msgstr(entry.split('\n')) if keep_msgstr else ''
        matched += 1

    if not batch:
        print(f"⚠️  No entries found in line range "
              f"[{args.start_line}, {args.end_line}]")
        sys.exit(0)

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(batch, f, ensure_ascii=False, indent=2)
        f.write('\n')

    mode = "untranslated" if untranslated_only else "all"
    print(f"✅ Extracted {matched} entries (mode={mode}) from {args.input}")
    print(f"   Line range: [{args.start_line}, {args.end_line}] -> {args.out}")

    if args.verify_total is not None:
        total = sum(1 for msgid, _, _ in entries if msgid)
        if total != args.verify_total:
            print(f"❌ --verify-total mismatch: source holds {total} translatable "
                  f"entries, expected {args.verify_total}.", file=sys.stderr)
            sys.exit(1)
        print(f"   verify-total: source confirmed {total} translatable entries")


if __name__ == '__main__':
    main()
