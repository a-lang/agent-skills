#!/usr/bin/env python3
"""
po_preflight.py — Pre-flight check of a source POT/PO file before translation.

Verifies that the source file is well-formed enough for downstream steps
(po_gen.py / po_verify.py / po_to_pot.py / po_to_translations.py) to succeed.
Run this in Phase 1 *before* building translations.py.

Checks:
  Encoding & BOM       UTF-8, no BOM, charset declaration matches
  Header entry         First entry is the msgid "" header
  Header fields        Required header keys present (Content-Type, Plural-Forms, ...)
  Format legality     `msgfmt --statistics -cv` exits 0 (no c-format / syntax errors)
  Fuzzy flags          Header-level `#, fuzzy` breaks output; entry-level counted
  Duplicate entries    Same (msgctxt, msgid) twice → po_gen collision
  Obsolete entries     `#~` leftovers counted
  Line endings         CRLF reported (info only; legit for GNOME projects)

Exit code: 0 = clean (no errors, no warnings); 1 = issues found.
Issues are reported (soft-stop): the caller presents them to the user, who
decides whether to fix or proceed — this script does not abort the workflow.

Usage:
    python3 po_preflight.py <path/to/source.pot|source.po>
    python3 po_preflight.py <source.po> --no-msgfmt   # skip msgfmt check
"""

import re
import sys
import shutil
import argparse

from po_verify import check_eof_canonicality


# ── PO string helpers (mirroring po_verify.py / po_gen.py) ────────────────

def decode_po(s: str) -> str:
    return (s
            .replace('\\"', '\x00Q')
            .replace('\\\\', '\x00B')
            .replace('\\n', '\n')
            .replace('\\t', '\t')
            .replace('\x00Q', '"')
            .replace('\x00B', '\\'))


def _continuations(lines, start, prefix_re):
    """Collect quoted continuation lines following a directive line."""
    parts = []
    for line in lines[start + 1:]:
        if not line.startswith('"'):
            break
        m = re.match(r'^"(.*)"$', line)
        if m:
            parts.append(m.group(1))
        else:
            break
    return parts


def parse_entries(text: str) -> list[dict]:
    """Parse a POT/PO into a list of entry dicts with keys:
    msgctxt, msgid, msgstr, flags (set), is_header, is_obsolete, raw.
    """
    entries = re.split(r'\n{2,}', text.strip())
    result = []
    for e in entries:
        if not e.strip():
            continue
        lines = e.split('\n')
        is_obsolete = any(l.lstrip().startswith('#~') for l in lines)

        msgctxt = ''
        msgid_parts = []
        msgstr_parts = []
        flags = set()

        for i, line in enumerate(lines):
            # flags
            m = re.match(r'^#,\s*(.+)$', line)
            if m:
                flags.update(f.strip() for f in m.group(1).split(','))
                continue
            mc = re.match(r'^msgctxt\s+"(.*)"$', line)
            if mc:
                msgctxt = mc.group(1) + ''.join(_continuations(lines, i, None))
                continue
            mi = re.match(r'^msgid\s+"(.*)"$', line)
            if mi:
                msgid_parts.append(mi.group(1))
                msgid_parts.extend(_continuations(lines, i, None))
                continue
            ms = re.match(r'^msgstr(?:\[\d+])?\s+"(.*)"$', line)
            if ms:
                msgstr_parts.append(ms.group(1))
                msgstr_parts.extend(_continuations(lines, i, None))
                continue

        result.append({
            'msgctxt': decode_po(msgctxt),
            'msgid': decode_po(''.join(msgid_parts)),
            'msgstr': decode_po(''.join(msgstr_parts)),
            'flags': flags,
            'is_header': ('' not in flags) and not msgctxt and ''.join(msgid_parts) == '',
            'is_obsolete': is_obsolete,
            'raw': e.strip(),
        })
    return result


def parse_header_fields(header_msgstr: str) -> dict[str, str]:
    """Header msgstr (already decoded) → {Key: value}."""
    out = {}
    for line in header_msgstr.split('\n'):
        if ':' in line:
            k, _, v = line.partition(':')
            out[k.strip()] = v.strip()
    return out


# ── Checks ────────────────────────────────────────────────────────────────

def check_msgfmt(path: str) -> tuple[int, str]:
    """Run msgfmt --statistics -cv. Return (exit_code, stderr_text)."""
    if not shutil.which('msgfmt'):
        return -1, 'msgfmt not found on PATH (skipped)'
    import subprocess
    r = subprocess.run(
        ['msgfmt', '--statistics', '-cv', path, '-o', '/dev/null'],
        capture_output=True, text=True,
    )
    return r.returncode, r.stderr.strip()


def preflight(path: str, use_msgfmt: bool = True) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    is_po = path.lower().endswith('.po')

    # 1. Encoding & BOM
    with open(path, 'rb') as f:
        raw = f.read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    if bom:
        warnings.append('UTF-8 BOM detected — strip it to avoid downstream parse issues')
        body = raw[3:]
    else:
        body = raw
    try:
        text = body.decode('utf-8')
    except UnicodeDecodeError as ex:
        errors.append(f'File is not valid UTF-8: {ex}')
        print('❌ Encoding: file is not valid UTF-8 — aborting further checks')
        print(f'\nISSUES FOUND (1 error, {len(warnings)} warnings)')
        return 1

    print('Encoding & BOM')
    print(f'  UTF-8 decode: ✅ OK')
    print(f'  BOM:          {"⚠️  present" if bom else "✅ none"}')
    print()

    # 1b. EOF / trailing-whitespace canonicality
    format_issues = check_eof_canonicality(body)
    print('File format (EOF / trailing whitespace)')
    if format_issues:
        errors.extend(format_issues)
        for fi in format_issues:
            print(f'  ❌ {fi}')
    else:
        print('  ✅ Exactly one trailing newline, no trailing whitespace')
    print()

    # 2. Line endings
    crlf = b'\r\n' in body
    print('Line endings')
    if crlf:
        infos.append('CRLF line endings detected (common for GNOME; ensure consistency)')
        print('  ⚠️  CRLF detected (info only — not flagged as issue)')
    else:
        print('  ✅ LF')
    print()

    # 3. Parse entries
    entries = parse_entries(text)
    print(f'Entries parsed: {len(entries)}')
    print()

    # 4. Header entry
    if not entries:
        errors.append('No entries found — file appears empty')
    elif not entries[0]['is_header']:
        errors.append('First entry is not the msgid "" header')
        print('❌ Header: missing leading msgid "" header entry')
    else:
        print('Header entry')
        print('  ✅ Present (msgid "")')
    print()

    # 5. Header fields
    if entries and entries[0]['is_header']:
        fields = parse_header_fields(entries[0]['msgstr'])
        print('Header fields')

        ctype = fields.get('Content-Type', '')
        if not ctype:
            errors.append('Header missing Content-Type')
            print('  ❌ Content-Type: missing')
        elif 'utf-8' not in ctype.lower():
            errors.append(f'Content-Type charset is not UTF-8: {ctype!r}')
            print(f'  ❌ Content-Type: {ctype} (charset not UTF-8)')
        else:
            print(f'  ✅ Content-Type: {ctype}')

        for key in ('MIME-Version', 'Project-Id-Version', 'Plural-Forms'):
            if key not in fields:
                warnings.append(f'Header missing {key}')
                print(f'  ⚠️  {key}: missing')
            else:
                print(f'  ✅ {key}: {fields[key]}')

        if is_po:
            for key in ('Language', 'Last-Translator'):
                if key not in fields:
                    warnings.append(f'Header missing {key} (PO source)')
                    print(f'  ⚠️  {key}: missing')
                else:
                    print(f'  ✅ {key}: {fields[key]}')
        else:
            print('  ℹ️  POT source — Language/Last-Translator not required')
        print()

    # 6. Fuzzy flags
    header_fuzzy = entries and entries[0]['is_header'] and 'fuzzy' in entries[0]['flags']
    entry_fuzzy = [e for e in entries if not e['is_header'] and 'fuzzy' in e['flags']]

    print('Fuzzy flags')
    if header_fuzzy:
        errors.append('Header carries `#, fuzzy` — it will propagate to output PO')
        print('  ❌ Header has `#, fuzzy` (must be removed before po_gen)')
    else:
        print('  ✅ Header has no `#, fuzzy`')
    if entry_fuzzy:
        warnings.append(f'{len(entry_fuzzy)} entry-level fuzzy flags — review before po_gen')
        print(f'  ⚠️  {len(entry_fuzzy)} entry-level fuzzy flags')
    else:
        print('  ✅ No entry-level fuzzy flags')
    print()

    # 7. Duplicate (msgctxt, msgid)
    seen: dict[tuple[str, str], int] = {}
    dups = []
    for e in entries:
        if e['is_header']:
            continue
        key = (e['msgctxt'], e['msgid'])
        if key in seen:
            dups.append(key)
        else:
            seen[key] = 1
    print('Duplicate entries')
    if dups:
        errors.append(f'{len(dups)} duplicate (msgctxt, msgid) pairs — po_gen will collide')
        print(f'  ❌ {len(dups)} duplicate (msgctxt, msgid) pairs:')
        for k in dups[:5]:
            label = f'{k[0]} | ' if k[0] else ''
            print(f'    - {label}"{k[1][:70]}"')
    else:
        print('  ✅ No duplicates')
    print()

    # 8. Obsolete entries
    obsolete = [e for e in entries if e['is_obsolete']]
    print('Obsolete entries')
    if obsolete:
        warnings.append(f'{len(obsolete)} obsolete (`#~`) entries — po_gen ignores them')
        print(f'  ⚠️  {len(obsolete)} obsolete (`#~`) entries')
    else:
        print('  ✅ None')
    print()

    # 9. msgfmt format check
    if use_msgfmt:
        print('msgfmt --statistics -cv')
        code, stderr = check_msgfmt(path)
        if code == -1:
            warnings.append('msgfmt not found on PATH — format check skipped')
            print('  ⚠️  msgfmt not found — skipped')
        elif code == 0:
            print('  ✅ OK (exit 0)')
            if stderr:
                print(f'     {stderr.splitlines()[-1] if stderr.splitlines() else stderr}')
        else:
            errors.append(f'msgfmt reported format errors (exit {code})')
            print(f'  ❌ msgfmt exit {code}')
            for line in stderr.splitlines():
                print(f'     {line}')
        print()

    # Summary
    total = len(errors) + len(warnings)
    print('=' * 70)
    if total == 0:
        print(f'PASS — no errors, no warnings ({len(infos)} info)' if infos else 'PASS — no errors, no warnings')
    else:
        print(f'ISSUES FOUND ({len(errors)} error(s), {len(warnings)} warning(s))')
    return 1 if total else 0


def main():
    parser = argparse.ArgumentParser(
        description='Pre-flight check of a source POT/PO file before translation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('source', help='Path to source .pot or .po file')
    parser.add_argument('--no-msgfmt', action='store_true',
                        help='Skip the msgfmt --statistics -cv format check')
    args = parser.parse_args()
    sys.exit(preflight(args.source, use_msgfmt=not args.no_msgfmt))


if __name__ == '__main__':
    main()