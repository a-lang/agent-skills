#!/usr/bin/env python3
"""
po_verify.py — Verify PO matches POT format and report translation coverage.

Usage:
    python3 po_verify.py <pot_path> <po_path>

Reports:
  - Entry count match (no missing/extra msgids)
  - Translation coverage percentage
  - Comment preservation check (optional)
  - Listing of untranslated entries (if any)

Exit code: 0 = all good, 1 = issues found
"""

import re
import sys
import argparse

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

def parse_entries(text: str) -> list[tuple[str, str]]:
    """Return list of (msgid, full_entry_text).
    Header entry has msgid=''.
    """
    entries = re.split(r'\n{2,}', text.strip())
    result: list[tuple[str, str]] = []
    for e in entries:
        if not e.strip():
            continue
        msgid = ''
        parts: list[str] = []
        in_msgid = False
        for line in e.split('\n'):
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

        msgid = ''.join(parts)
        result.append((msgid, e.strip()))
    return result


def get_msgstr(entry: str) -> str:
    """Extract decoded msgstr from entry."""
    parts: list[str] = []
    in_msgstr = False
    for line in entry.split('\n'):
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


def is_empty_msgstr(entry: str) -> bool:
    """Check if msgstr is truly empty (no content after PO decoding)."""
    return not get_msgstr(entry)


def has_fuzzy(entry: str) -> bool:
    return bool(re.search(r'^#, fuzzy\b', entry, re.MULTILINE))


def get_comment_lines(text: str) -> list[str]:
    """Get all non-obsolete comment lines from a PO/POT file."""
    return [l for l in text.split('\n')
            if l.startswith('#') and not l.startswith('#~')]


# ── Main verification ────────────────────────────────────────────────────

def verify(pot_path: str, po_path: str, check_comments: bool = False) -> int:
    """Verify PO vs POT. Returns 0 on success, 1 on issues."""
    issues = 0

    with open(pot_path, 'r', encoding='utf-8') as f:
        pot_text = f.read()
    with open(po_path, 'r', encoding='utf-8') as f:
        po_text = f.read()

    pot_entries = parse_entries(pot_text)
    po_entries = parse_entries(po_text)

    pot_msgids: dict[str, str] = {e[0]: e[1] for e in pot_entries}
    po_msgids: dict[str, str] = {e[0]: e[1] for e in po_entries}

    pot_count = len(pot_msgids)  # includes header
    po_count = len(po_msgids)

    missing = set(pot_msgids.keys()) - set(po_msgids.keys())
    extra = set(po_msgids.keys()) - set(pot_msgids.keys())

    print(f"POT entries: {pot_count} (1 header + {pot_count - 1} translatable)")
    print(f"PO entries:  {po_count}")
    print()

    if missing:
        n = len(missing) - (1 if '' in missing else 0)  # exclude header
        if n > 0:
            issues += 1
            print(f"❌ {n} MISSING in PO:")
            for m in sorted(missing):
                if m:
                    print(f'  - "{m[:80]}"')
    if extra:
        n = len(extra) - (1 if '' in extra else 0)
        if n > 0:
            issues += 1
            print(f"⚠️  {n} EXTRA in PO:")
            for e in sorted(extra):
                if e:
                    print(f'  - "{e[:80]}"')

    if not missing and not extra:
        print("✅ Entry count matches — no missing or extra entries")

    # Translation coverage
    print()
    translated = 0
    total_msgids = 0
    untranslated_list = []
    fuzzy_list = []

    for msgid, entry in po_entries:
        if not msgid:
            continue  # header
        total_msgids += 1
        if not is_empty_msgstr(entry):
            translated += 1
        else:
            untranslated_list.append(msgid)
        if has_fuzzy(entry):
            fuzzy_list.append(msgid)

    if untranslated_list:
        issues += 1
    coverage = translated / total_msgids * 100 if total_msgids > 0 else 100
    print(f"Coverage: {translated}/{total_msgids} ({coverage:.0f}%)")

    if untranslated_list:
        print(f"\n⚠️  Untranslated entries ({len(untranslated_list)}):")
        for m in untranslated_list[:10]:
            print(f'  - "{m[:80]}"')
        if len(untranslated_list) > 10:
            print(f"  ... and {len(untranslated_list) - 10} more")

    if fuzzy_list:
        print(f"\n⚠️  Fuzzy entries ({len(fuzzy_list)}):")
        for m in fuzzy_list[:5]:
            print(f'  - "{m[:80]}"')
        if len(fuzzy_list) > 5:
            print(f"  ... and {len(fuzzy_list) - 5} more")

    if not untranslated_list and not fuzzy_list:
        print("✅ All entries translated and no fuzzy markers")

    # Comment structure check
    if check_comments:
        print()
        pot_comments = get_comment_lines(pot_text)
        po_comments = get_comment_lines(po_text)
        print(f"Comment lines: POT={len(pot_comments)}, PO={len(po_comments)}")

        # Check if any meaningful comments (#. for metadata, #: for source refs) were dropped
        pot_refs = {l for l in pot_comments if l.startswith('#:') or l.startswith('#.')}
        po_refs = {l for l in po_comments if l.startswith('#:') or l.startswith('#.')}
        dropped = pot_refs - po_refs
        if dropped:
            print(f"⚠️  {len(dropped)} source/comment references dropped from POT")
            for d in list(dropped)[:5]:
                print(f'  - {d}')
        else:
            print("✅ All source references preserved")

    # Print metadata
    for entry in po_entries:
        if not entry[0]:  # header
            text = entry[1]
            for line in text.split('\n'):
                if 'Last-Translator:' in line:
                    lt = re.search(r'Last-Translator: (.+?)(?:\\\\n|$)', line)
                    if lt:
                        print(f"\n👤 Last-Translator: {lt.group(1)}")
                elif 'Language: ' in line and '\\n' in line:
                    lang = re.search(r'Language: ([a-z_]+[A-Za-z]*)', line)
                    if lang:
                        print(f"🌐 Language: {lang.group(1)}")
            break

    return 0 if issues == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="Verify PO file matches POT and report coverage",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('pot', help='Path to .pot template file')
    parser.add_argument('po', help='Path to .po translation file')
    parser.add_argument('--comments', action='store_true',
                        help='Also check comment structure preservation')

    args = parser.parse_args()

    exit_code = verify(args.pot, args.po, check_comments=args.comments)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
