#!/usr/bin/env python3
"""
po_gen.py — Generate PO file from POT + translation map.

Usage:
    python3 po_gen.py <pot_path> [translations.py] [-o output.po]

If translations.py is omitted, looks for 'translations.py' in the same directory.
The translations.py should export a dict TRANSLATIONS = {msgid: msgstr, ...}.

Alternatively, pass -j translations.json for a JSON map.

Features:
  - Preserves POT comments (#:, #., #: lines)
  - Handles multi-line msgid and msgstr (real newlines and PO escape sequences)
  - Removes '#, fuzzy' from translated entries
  - Generates proper header with Last-Translator
  - Reports coverage stats
"""

import re
import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# ── Default translations (can be overridden via -t/--translations) ──────────
# Projects should create their own translations.py and import from there.
# This dict serves as a fallback / demo.
TRANSLATIONS: dict[str, str] = {}
TRANSLATOR = "Translator Name <translator@example.org>"
LANGUAGE = "zh_TW"
LANGUAGE_TEAM = "Chinese (Traditional)"
X_GENERATOR = "Hermes Agent + po_gen.py"


def resolve_translator(cli_value: str | None) -> str:
    """Resolve Last-Translator: CLI arg > L10N_TW_TRANSLATOR env > skill .env > placeholder."""
    value = cli_value or os.environ.get("L10N_TW_TRANSLATOR")
    if value:
        return value
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("L10N_TW_TRANSLATOR="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    print("⚠️  No translator specified (--translator / L10N_TW_TRANSLATOR / skills/l10n-tw/.env). Using placeholder.")
    return TRANSLATOR


# ── PO string encoding / decoding ─────────────────────────────────────────

def decode_po(s: str) -> str:
    """Decode PO escape sequences: \\n -> newline, \\" -> quote, \\\\ -> backslash."""
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
    """Check if a string NEEDS multi-line PO format (>70 chars or contains newline)."""
    return '\n' in s or len(s) > 70


# ── POT/Parsing helpers ──────────────────────────────────────────────────

def parse_po_entries(text: str) -> list[str]:
    """Split PO/POT text into individual entry strings (blank-line separated)."""
    entries = re.split(r'\n{2,}', text.strip())
    return [e for e in entries if e.strip()]


def get_msgid(entry: str) -> str | None:
    """Extract full decoded msgid from a PO entry (handles multi-line)."""
    lines = entry.split('\n')
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


def get_msgctxt(entry: str) -> str | None:
    """Extract decoded msgctxt from a PO entry, or None."""
    m = re.search(r'^msgctxt\s+"(.*)"$', entry, re.MULTILINE)
    if m:
        return decode_po(m.group(1))
    return None


def get_msgid_plural(entry: str) -> str | None:
    """Extract decoded msgid_plural from a PO entry, or None."""
    m = re.search(r'^msgid_plural\s+"(.*)"$', entry, re.MULTILINE)
    if m:
        return decode_po(m.group(1))
    return None


def get_msgstr_raw(entry: str) -> str:
    """Extract full decoded msgstr from a PO entry (handles singular and plural)."""
    lines = entry.split('\n')
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


def is_empty_msgstr(entry: str) -> bool:
    """Check if msgstr is empty ("" or msgstr[0] "")."""
    return bool(re.search(r'^msgstr(?:\[\d+\])?\s+""$', entry, re.MULTILINE))


def has_fuzzy(entry: str) -> bool:
    """Check if entry has #, fuzzy marker."""
    return bool(re.search(r'^#, fuzzy\b', entry, re.MULTILINE))


def remove_fuzzy(entry: str) -> str:
    """Remove '#, fuzzy' lines from entry."""
    return re.sub(r'^#, fuzzy\s*\n?', '', entry, flags=re.MULTILINE)


def get_comments(entry: str) -> list[str]:
    """Extract all comment lines (#:, #., #|, #) from entry, preserving order."""
    result = []
    for line in entry.split('\n'):
        if re.match(r'^#[^ ]|^# ', line) or line.startswith('#:') or line.startswith('#.') or line.startswith('#|') or line.startswith('#'):
            result.append(line)
        else:
            break
    return result


# ── PO generation ─────────────────────────────────────────────────────────

def format_msgstr(text: str | list[str] | tuple[str, ...]) -> list[str]:
    """Format a translation string or list of plural forms as PO msgstr lines."""
    # Plural forms: list/tuple of translations -> msgstr[0], msgstr[1], ...
    if isinstance(text, (list, tuple)):
        if not text:
            return ['msgstr[0] ""']
        lines: list[str] = []
        for i, form in enumerate(text):
            encoded = encode_po(form)
            if '\n' in form or is_multiline_po(form):
                lines.append(f'msgstr[{i}] ""')
                parts = form.split('\n')
                for j, part in enumerate(parts):
                    if j < len(parts) - 1:
                        part = part + '\n'
                    lines.append(f'"{encode_po(part)}"')
            else:
                lines.append(f'msgstr[{i}] "{encoded}"')
        return lines

    if not text:
        return ['msgstr ""']

    if '\n' in text:
        # Real newlines — split into multi-line format with \n escapes
        lines = ['msgstr ""']
        parts = text.split('\n')
        for i, part in enumerate(parts):
            encoded = encode_po(part + '\n') if i < len(parts) - 1 else encode_po(part)
            lines.append(f'"{encoded}"')
        return lines

    encoded = encode_po(text)
    if is_multiline_po(text):
        return ['msgstr ""', f'"{encoded}"']
    else:
        return [f'msgstr "{encoded}"']


def generate_po(pot_path: str, translations: dict[str, str],
                language: str = LANGUAGE,
                translator: str = TRANSLATOR,
                team: str = LANGUAGE_TEAM,
                generator: str = X_GENERATOR) -> str:
    """Generate a complete PO file from a POT and translation map."""
    with open(pot_path, 'r', encoding='utf-8') as f:
        pot_content = f.read()

    pot_entries = parse_po_entries(pot_content)

    now_po = datetime.now().strftime('%Y-%m-%d %H:%M+0800')

    output_entries: list[str] = []
    stats = {'total': 0, 'translated': 0, 'from_map': 0, 'untranslated': 0, 'missing': []}

    for entry in pot_entries:
        msgid = get_msgid(entry)

        if not msgid:
            # Header entry — preserve POT header, override our fields
            # Extract the original msgstr lines from POT header
            pot_lines = entry.split('\n')
            comments = [l for l in pot_lines if l.startswith('#') and not l.startswith('#,')]
            msgstr_lines = []
            in_msgstr = False
            for line in pot_lines:
                if line.startswith('msgstr'):
                    in_msgstr = True
                    continue
                if in_msgstr and line.startswith('"'):
                    msgstr_lines.append(line)
                elif in_msgstr and not line.startswith('"'):
                    break

            # Build new msgstr: replace fields we override, keep the rest
            override_fields = {
                'PO-Revision-Date': f'PO-Revision-Date: {now_po}',
                'Last-Translator': f'Last-Translator: {translator}',
                'Language-Team': f'Language-Team: {team}',
                'Language': f'Language: {language}',
                'X-Generator': f'X-Generator: {generator}',
            }
            new_msgstr = []
            seen_keys = set()
            for line in msgstr_lines:
                raw = re.match(r'^"(.*)"$', line)
                if raw:
                    decoded = decode_po(raw.group(1))
                    replaced = False
                    for key, val in override_fields.items():
                        if decoded.startswith(f'{key}:'):
                            new_msgstr.append(f'"{val}\\n"')
                            seen_keys.add(key)
                            replaced = True
                            break
                    if not replaced:
                        new_msgstr.append(line)

            # Fix Content-Type charset (POT has charset=CHARSET)
            new_msgstr = [
                line.replace('charset=CHARSET', f'charset=UTF-8')
                if 'Content-Type' in line else line
                for line in new_msgstr
            ]

            # Fix Plural-Forms placeholder (POT has nplurals=INTEGER; plural=EXPRESSION)
            new_msgstr = [
                re.sub(r'Plural-Forms:[^"\\]*', 'Plural-Forms: nplurals=1; plural=0;', line)
                if 'Plural-Forms' in line else line
                for line in new_msgstr
            ]

            # Add any override fields not found in original header
            for key, val in override_fields.items():
                if key not in seen_keys:
                    new_msgstr.append(f'"{val}\\n"')

            # Add Plural-Forms after Content-Transfer-Encoding
            plural_added = any('Plural-Forms' in line for line in new_msgstr)
            if not plural_added:
                for i, line in enumerate(new_msgstr):
                    if 'Content-Transfer-Encoding' in line:
                        new_msgstr.insert(i + 1, '"Plural-Forms: nplurals=1; plural=0;\\n"')
                        break

            header_parts = list(comments)
            header_parts.append('msgid ""')
            header_parts.append('msgstr ""')
            header_parts.extend(new_msgstr)
            output_entries.append('\n'.join(header_parts))
            continue

        stats['total'] += 1
        comments = get_comments(entry)
        msgctxt = get_msgctxt(entry)
        msgid_plural = get_msgid_plural(entry)
        lookup_key = (msgctxt + '\x04' + msgid) if msgctxt else msgid
        translation = translations.get(lookup_key, None)

        if translation is not None:
            stats['translated'] += 1
            stats['from_map'] += 1

            # Build entry: comments + msgctxt + msgid + msgid_plural + msgstr
            entry_lines = list(comments)
            if msgctxt:
                raw_ctxt = encode_po(msgctxt)
                if '\n' in msgctxt:
                    entry_lines.append(f'msgctxt ""')
                    for part in msgctxt.split('\n'):
                        entry_lines.append(f'"{encode_po(part + "\n")}"')
                else:
                    entry_lines.append(f'msgctxt "{raw_ctxt}"')

            # Format msgid (preserve multi-line from source)
            msgid_lines = []
            decoded_msgid = decode_po(msgid)  # We already have decoded
            # Re-encode for output
            raw_msgid = encode_po(decoded_msgid)
            if is_multiline_po(decoded_msgid) or '\n' in decoded_msgid:
                msgid_lines.append('msgid ""')
                # Split on newline, then add trailing \n back to all but the
                # last segment — PO multi-line format keeps a trailing \n on
                # every line except the last (matches xgettext output).
                parts = decoded_msgid.split('\n')
                for i, part in enumerate(parts):
                    if i < len(parts) - 1:
                        part = part + '\n'
                    msgid_lines.append(f'"{encode_po(part)}"')
            else:
                msgid_lines.append(f'msgid "{raw_msgid}"')

            # Format msgid_plural if present
            if msgid_plural:
                decoded_plural = decode_po(msgid_plural)
                raw_plural = encode_po(decoded_plural)
                if is_multiline_po(decoded_plural) or '\n' in decoded_plural:
                    msgid_lines.append('msgid_plural ""')
                    parts = decoded_plural.split('\n')
                    for i, part in enumerate(parts):
                        if i < len(parts) - 1:
                            part = part + '\n'
                        msgid_lines.append(f'"{encode_po(part)}"')
                else:
                    msgid_lines.append(f'msgid_plural "{raw_plural}"')

            entry_lines.extend(msgid_lines)

            # Format msgstr (handles plural forms if translation is a list/tuple)
            entry_lines.extend(format_msgstr(translation))

            # Remove fuzzy if present
            result = '\n'.join(entry_lines)
            if has_fuzzy(result):
                result = remove_fuzzy(result)
            output_entries.append(result)
        else:
            stats['untranslated'] += 1
            stats['missing'].append(msgid[:80])
            # Keep original POT entry (empty msgstr)
            # Ensure msgstr is empty
            if is_empty_msgstr(entry):
                output_entries.append(entry)
            else:
                # Replace msgstr with empty
                entry = re.sub(r'^msgstr\s+".*"(\s*)$', 'msgstr ""', entry, flags=re.MULTILINE)
                output_entries.append(entry)

    result = '\n\n'.join(output_entries) + '\n'

    # Print stats
    print(f"POT entries:   {stats['total']}")
    print(f"Translated:    {stats['translated']}/{stats['total']} ({stats['translated']/max(stats['total'],1)*100:.0f}%)")
    if stats['missing']:
        print(f"\n⚠️  Untranslated ({len(stats['missing'])}):")
        for m in stats['missing']:
            print(f"  - \"{m}\"")
    else:
        print("✅ All entries translated!")

    return result


# ── Load translations from .py or .json ──────────────────────────────────

def load_translations(source: str) -> dict[str, str]:
    """Load translation map from a .py or .json file."""
    if source.endswith('.json'):
        with open(source, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif source.endswith('.py'):
        # Import the file as a module
        import importlib.util
        spec = importlib.util.spec_from_file_location("translations_mod", source)
        mod = importlib.util.module_from_spec(spec)
        # Don't add to sys.modules to avoid conflicts
        spec.loader.exec_module(mod)
        if hasattr(mod, 'TRANSLATIONS'):
            return mod.TRANSLATIONS
        # Also check for upper-case T dict
        if hasattr(mod, 'T'):
            return mod.T
        raise ValueError(f"TRANSLATIONS dict not found in {source}")
    else:
        raise ValueError(f"Unsupported translations file: {source} (use .py or .json)")


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate PO file from POT + translation map",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 po_gen.py template.pot -t translations.py -o zh_TW.po
  python3 po_gen.py template.pot -j translations.json -l zh_CN
  python3 po_gen.py template.pot          # uses embedded TRANSLATIONS dict
        """)
    parser.add_argument('pot', help='Path to .pot template file')
    parser.add_argument('-t', '--translations', help='Path to translations.py (exports TRANSLATIONS dict)')
    parser.add_argument('-j', '--json', help='Path to translations.json')
    parser.add_argument('-o', '--output', help='Output PO file path (default: auto-derived from pot name)')
    parser.add_argument('-l', '--language', default=LANGUAGE, help=f'Language code (default: {LANGUAGE})')
    parser.add_argument('--translator', default=None, help='Translator name (default: resolve from L10N_TW_TRANSLATOR env / skill .env)')
    parser.add_argument('--team', default=LANGUAGE_TEAM, help=f'Language team (default: {LANGUAGE_TEAM})')

    args = parser.parse_args()

    # Resolve translations
    if args.json:
        translations = load_translations(args.json)
    elif args.translations:
        translations = load_translations(args.translations)
    else:
        translations = TRANSLATIONS
        if not translations:
            print("⚠️  No translations provided. Use -t translations.py or define TRANSLATIONS in this script.")
            print("   Generating empty PO for reference.\n")

    # Derive output path (default: same directory as the POT file)
    if args.output:
        output_path = args.output
    else:
        pot_dir = os.path.dirname(os.path.abspath(args.pot))
        base = os.path.splitext(os.path.basename(args.pot))[0]
        # Remove @ from extension names for cleaner filename
        base = base.replace('@', '-')
        output_path = os.path.join(pot_dir, f"{base}.{args.language}.po")

    translator = resolve_translator(args.translator)
    print(f"Generating: {args.pot} → {output_path}")
    print(f"Language:   {args.language}")
    print(f"Translator: {translator}")
    print()

    po_content = generate_po(
        args.pot,
        translations,
        language=args.language,
        translator=translator,
        team=args.team,
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(po_content)

    print(f"\n✅ Written to: {output_path}")


if __name__ == '__main__':
    main()
