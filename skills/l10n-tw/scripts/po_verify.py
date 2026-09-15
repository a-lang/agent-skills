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


def has_format_flag(entry: str) -> bool:
    """Check if an entry carries a positive format flag (c-format / php-format / ...).

    Entries marked `no-c-format` / `no-format` (literal percents that gettext is
    told to ignore, e.g. "93% of") are excluded from placeholder checking.
    """
    for line in entry.split('\n'):
        m = re.match(r'^#,\s*(.*)$', line)
        if m:
            flags = m.group(1)
            if re.search(r'\bno-(?:c-)?format\b', flags):
                return False
            return bool(re.search(r'\b[\w-]*format\b', flags))
    return False


def get_comment_lines(text: str) -> list[str]:
    """Get all non-obsolete comment lines from a PO/POT file."""
    return [l for l in text.split('\n')
            if l.startswith('#') and not l.startswith('#~')]


# ── Format placeholder checking ─────────────────────────────────────────

# Conversion letters for printf-style formats (c-format / php-format / ...)
_FORMAT_CONV = r'[diouxXeEfFgGaAcsp]'

# Matches a single format specifier: optional flags/width/precision/position/length, then a conversion.
# Captures optional positional index (N$), length modifier, and the conversion letter.
_FORMAT_RE = re.compile(
    r'%'                          # literal percent
    r'(?:(?P<pos>\d+)\$)?'        # positional index N$ (optional)
    r'[-+ #0]*'                   # flags (note: a space is a flag, e.g. "% d")
    r'(?:\d+|\*)?'                # width
    r'(?:\.(?:\d+|\*))?'          # precision
    r'(?P<length>hh|h|ll|l|L|j|z|t)?'  # length modifier (e.g. "%jd", "%td")
    r'(?P<conv>' + _FORMAT_CONV + r')'
)


def scan_format_specifiers(text: str) -> tuple[list[tuple[int | None, str]], bool]:
    """Scan a format string.

    Returns (specs, advanced) where:
      - specs = [(positional_index_or_None, conversion_letter), ...]
      - advanced = True if the string contains a construct this checker cannot
        reliably verify (gnulib `%<PRIuMAX>`, a length modifier such as `%ju`
        or `%jd`, or a `%` it could not consume). Advanced strings are left for
        `msgfmt` to judge, which is the authoritative check.
    Escaped '%%' is skipped. Positional index is 1-based when present (N$).
    """
    out: list[tuple[int | None, str]] = []
    advanced = False
    i = 0
    n = len(text)
    while i < n:
        if text[i] != '%':
            i += 1
            continue
        if i + 1 < n and text[i + 1] == '%':
            i += 2
            continue
        if i + 1 < n and text[i + 1] == '<':
            advanced = True  # gnulib abstract placeholder e.g. %<PRIuMAX>
            i += 1
            continue
        m = _FORMAT_RE.match(text, i)
        if not m:
            advanced = True  # unconsumable '%' (e.g. %m, or a literal we can't parse)
            i += 1
            continue
        pos = int(m.group('pos')) if m.group('pos') else None
        if m.group('length'):
            advanced = True  # length-modified specifier — defer to msgfmt
        out.append((pos, m.group('conv')))
        i = m.end()
    return out, advanced


def parse_format_specifiers(text: str) -> list[tuple[int | None, str]]:
    """Return [(positional_index_or_None, conversion_letter), ...] (ignores advanced flag)."""
    return scan_format_specifiers(text)[0]


def _is_positional(specs: list[tuple[int | None, str]]) -> bool:
    """True if any specifier carries a positional index (N$)."""
    return any(p is not None for p, _ in specs)


def check_placeholders(msgid: str, msgstr: str) -> list[str]:
    """Compare msgid vs msgstr format specifiers. Returns a list of issues.

    Rules:
      - Equal specifier count.
      - Within a single string, positional and non-positional must not mix.
      - msgid non-positional + msgstr positional: each %N$letter must match
        the conversion of the Nth msgid specifier (index refers to msgid args).
      - msgid positional: msgstr must be positional too, with matching index
        and conversion per position.
      - msgid non-positional + msgstr non-positional: conversions must match
        position-by-position (same order).
    """
    issues: list[str] = []
    id_specs, id_advanced = scan_format_specifiers(msgid)
    str_specs, str_advanced = scan_format_specifiers(msgstr)

    # Constructs we can't reliably verify (length modifiers, gnulib %<...>, or
    # unconsumable '%') are left to msgfmt — the authoritative check. Skipping
    # them avoids false positives on valid PO files.
    if id_advanced or str_advanced:
        return []

    if len(id_specs) != len(str_specs):
        issues.append(
            f"佔位符數量不一致：msgid {len(id_specs)} 個，msgstr {len(str_specs)} 個")

    if _is_positional(id_specs) and any(p is None for p, _ in id_specs):
        issues.append("msgid 混用位置式與非位置式佔位符")
    if _is_positional(str_specs) and any(p is None for p, _ in str_specs):
        issues.append("msgstr 混用位置式與非位置式佔位符")

    if not id_specs and not str_specs:
        return issues

    if _is_positional(id_specs):
        # msgid positional → msgstr must be positional with matching idx+type.
        if not _is_positional(str_specs):
            issues.append("msgid 使用位置式但 msgstr 未使用位置式")
        else:
            for i, ((ip, ic), (sp, sc)) in enumerate(zip(id_specs, str_specs), start=1):
                if ip != sp:
                    issues.append(f"位置式索引第 {i} 個不一致：msgid %{ip}$ 對 msgstr %{sp}$")
                elif ic != sc:
                    issues.append(f"位置式型別第 {i} 個不一致：msgid %{ip}${ic} 對 msgstr %{sp}${sc}")
    elif _is_positional(str_specs):
        # msgid non-positional, msgstr positional: %N$letter refers to the
        # Nth msgid specifier → conversion must match that argument.
        for i, (sp, sc) in enumerate(str_specs, start=1):
            if sp is None:
                continue
            if sp < 1 or sp > len(id_specs):
                issues.append(f"msgstr 位置式索引 %{sp}$ 超出 msgid 參數範圍")
                continue
            ic = id_specs[sp - 1][1]
            if ic != sc:
                issues.append(
                    f"位置式型別不一致：msgstr %{sp}${sc} 對應 msgid 第 {sp} 個參數為 %{ic}")
    else:
        # Both non-positional: conversions must match position-by-position.
        for i, ((_, ic), (_, sc)) in enumerate(zip(id_specs, str_specs), start=1):
            if ic != sc:
                issues.append(
                    f"非位置式型別第 {i} 個不一致：msgid %{ic} 對 msgstr %{sc}")

    return issues


def check_eof_canonicality(data: bytes) -> list[str]:
    """Check byte-level PO file format canonicality.

    Returns a list of issues (empty = pass). data is the file's raw bytes.
    Checks: exactly one trailing newline; no trailing whitespace on any line.
    """
    issues: list[str] = []

    trailing = len(data) - len(data.rstrip(b'\n'))
    if trailing != 1:
        issues.append(f"EOF: 檔案應以恰好一個換行結尾（現有 {trailing} 個）")

    lines = data.split(b'\n')
    for i, line in enumerate(lines[:-1], start=1):
        if line.rstrip(b' \t') != line:
            issues.append(f"L{i}: 行尾有多餘空白")

    return issues


# ── Main verification ────────────────────────────────────────────────────

def verify(pot_path: str, po_path: str, check_comments: bool = False) -> int:
    """Verify PO vs POT. Returns 0 on success, 1 on issues."""
    issues = 0

    with open(pot_path, 'r', encoding='utf-8') as f:
        pot_text = f.read()
    with open(po_path, 'r', encoding='utf-8') as f:
        po_text = f.read()
    with open(po_path, 'rb') as f:
        po_raw = f.read()

    # Byte-level file format canonicality (before entry-level parsing)
    format_issues = check_eof_canonicality(po_raw)
    if format_issues:
        issues += 1
        print("❌ PO file format issues:")
        for fi in format_issues:
            print(f"   - {fi}")
        print()

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

    # Format placeholder check (only entries carrying a format flag)
    print()
    placeholder_issues: list[tuple[str, str]] = []
    for msgid, entry in po_entries:
        if not msgid:
            continue
        if not has_format_flag(entry):
            continue
        msgstr = get_msgstr(entry)
        if not msgstr:
            continue
        for issue in check_placeholders(msgid, msgstr):
            placeholder_issues.append((issue, msgid))

    if placeholder_issues:
        issues += 1
        print(f"❌ Format placeholder issues ({len(placeholder_issues)}):")
        for issue, msgid in placeholder_issues[:10]:
            print(f'  - {issue}\n    "{msgid[:100]}"')
        if len(placeholder_issues) > 10:
            print(f"  ... and {len(placeholder_issues) - 10} more")
    else:
        print("✅ Format placeholders match between msgid and msgstr")

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
