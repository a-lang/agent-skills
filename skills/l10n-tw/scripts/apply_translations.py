#!/usr/bin/env python3
"""
apply_translations.py — Apply a batch of translations from JSON to a PO file.

Usage:
    python3 apply_translations.py <batch.json> -o <target.po>

Reads {"msgid": "translation"} from <batch.json> and writes each translation
into the matching entry of <target.po>. Entries not present in the JSON are
left untouched; entries with an empty value in the JSON are skipped.

Operates at the text level (no polib round-trip) so the original comment
formatting (#:, #. multi-line references) is preserved verbatim.

Features:
  - Handles multi-line msgid and msgstr (PO escape sequences)
  - Removes '#, fuzzy' from updated entries
  - Updates header (PO-Revision-Date, Last-Translator, X-Generator)
  - Reports applied / skipped / missing stats
  - Exit code 0 even with missing keys (warn only); 1 on IO errors
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

TRANSLATOR = "Alang Hsu <alang.hsu@gmail.com>"
LANGUAGE = "zh_TW"
X_GENERATOR = "Hermes Agent + apply_translations.py"


# ── PO string helpers ────────────────────────────────────────────────────

def decode_po(s: str) -> str:
    return (s
            .replace('\\"', '\x00Q')
            .replace('\\\\', '\x00B')
            .replace('\\n', '\n')
            .replace('\\t', '\t')
            .replace('\x00Q', '"')
            .replace('\x00B', '\\'))


def encode_po(s: str) -> str:
    """Encode string for PO msgstr: backslash first, then quote, then newline."""
    return (s
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\t', '\\t'))


def is_multiline_po(s: str) -> bool:
    """Check if a string NEEDS multi-line PO format (>70 chars or newline)."""
    return '\n' in s or len(s) > 70


# ── Entry manipulation ───────────────────────────────────────────────────

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


def replace_msgstr(entry: str, new_msgstr: str) -> str:
    """Return the entry with its msgstr replaced, comments/msgid untouched.

    The '#, fuzzy' marker is removed; '#:'/'#.' comment lines and the msgid
    (including multi-line continuation) are preserved verbatim.
    """
    lines = entry.split('\n')
    out: list[str] = []
    for line in lines:
        if re.match(r'^msgstr(?:\[\d+\])?\s+', line):
            break
        out.append(line)
    out = [l for l in out if not re.match(r'^#, fuzzy\b', l)]

    if not new_msgstr:
        return '\n'.join(out) + '\nmsgstr ""'

    encoded = encode_po(new_msgstr)
    if is_multiline_po(new_msgstr):
        out.append('msgstr ""')
        out.append(f'"{encoded}"')
    else:
        out.append(f'msgstr "{encoded}"')
    return '\n'.join(out)


def update_header(entry: str) -> str:
    """Override date/translator fields in the header entry, keep the rest."""
    now_po = datetime.now().strftime('%Y-%m-%d %H:%M+0800')
    override = {
        'PO-Revision-Date': f'PO-Revision-Date: {now_po}',
        'Last-Translator': f'Last-Translator: {TRANSLATOR}',
        'Language': f'Language: {LANGUAGE}',
        'X-Generator': f'X-Generator: {X_GENERATOR}',
    }
    lines = entry.split('\n')
    out: list[str] = []
    for line in lines:
        m = re.match(r'^"(([^:]+): (.*?))\\n"$', line)
        if m and m.group(2) in override:
            out.append(f'"{override[m.group(2)]}\\n"')
        else:
            out.append(line)
    return '\n'.join(out)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Apply batch translations (JSON) to a PO file")
    parser.add_argument('batch', help='Path to batch JSON ({"msgid": "msgstr"})')
    parser.add_argument('-o', '--output', required=True,
                        help='Path to target PO file (modified in place)')
    parser.add_argument('--translator', default=TRANSLATOR,
                        help=f'Last-Translator value (default: {TRANSLATOR})')
    args = parser.parse_args()

    try:
        with open(args.batch, 'r', encoding='utf-8') as f:
            translations = json.load(f)
    except OSError as ex:
        print(f"❌ Cannot read {args.batch}: {ex}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as ex:
        print(f"❌ Invalid JSON in {args.batch}: {ex}", file=sys.stderr)
        sys.exit(1)

    po_path = Path(args.output)
    try:
        with open(po_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except OSError as ex:
        print(f"❌ Cannot read {po_path}: {ex}", file=sys.stderr)
        sys.exit(1)

    # Split into entries, keeping blank-line separation intact
    entries = text.split('\n\n')
    applied = 0
    skipped = 0
    updated = False
    po_msgids: set[str] = set()

    for i, entry in enumerate(entries):
        if not entry.strip():
            continue
        lines = entry.split('\n')
        msgid = get_msgid(lines)
        if msgid is None:
            continue
        if not msgid:
            # Header entry
            if i == 0:
                entries[i] = update_header(entry)
                updated = True
            continue

        po_msgids.add(msgid)
        if msgid not in translations:
            continue
        value = translations[msgid]
        if not value:
            skipped += 1
            continue
        entries[i] = replace_msgstr(entry, value)
        applied += 1
        updated = True

    missing = [k for k in translations if k and k not in po_msgids]

    if not updated:
        print("⚠️  No entries updated — batch keys do not match the PO?")
        if missing:
            print(f"   Missing keys in batch JSON: {len(missing)}")
        sys.exit(0)

    with open(po_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(entries))
        if not text.endswith('\n\n'):
            f.write('\n')
    print(f"✅ Applied {applied} translations to {po_path}")
    print(f"   Skipped {skipped} entries with empty translation in batch")
    if missing:
        print(f"⚠️  MISSING {len(missing)} keys not found in PO:")
        for k in missing[:5]:
            print(f'   - "{k[:80]}"')


if __name__ == '__main__':
    main()
