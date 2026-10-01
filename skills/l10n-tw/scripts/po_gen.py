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
import ast
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


def find_translator_file(start: Path) -> Path | None:
    """Walk up from start's directory looking for translator.txt (bounded, no disk-wide scan)."""
    d = start.resolve().parent
    for _ in range(4):
        f = d / "translator.txt"
        if f.is_file():
            return f
        if d.parent == d:
            break
        d = d.parent
    return None


def resolve_translator(cli_value: str | None, start: Path) -> str:
    """Resolve Last-Translator: CLI arg > L10N_TW_TRANSLATOR env > {project-dir}/translator.txt > placeholder."""
    value = cli_value or os.environ.get("L10N_TW_TRANSLATOR")
    if value:
        return value
    config_file = find_translator_file(start)
    if config_file:
        for line in config_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("L10N_TW_TRANSLATOR="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    print("⚠️  No translator specified (--translator / L10N_TW_TRANSLATOR / {project-dir}/translator.txt). Using placeholder.")
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


def normalize_eof(s: str) -> str:
    """Ensure the string ends with exactly one newline."""
    return s.rstrip('\n') + '\n'


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
    """Remove '#, fuzzy' flag while preserving other flags.

    Flags are a comma-separated list on the '#,' line (e.g. '#, fuzzy, c-format').
    The fuzzy flag may appear anywhere in the list, not just at the start.
    A line left with no flags after removal is deleted entirely.
    """
    def repl(m):
        flags = [f.strip() for f in m.group(1).split(',') if f.strip() != 'fuzzy']
        return '#, ' + ', '.join(flags) + '\n' if flags else ''
    return re.sub(r'^#, ([^\n]*\bfuzzy\b[^\n]*)\n?', repl, entry, flags=re.MULTILINE)


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
                team: str = LANGUAGE_TEAM) -> str:
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
        msgctxt = get_msgctxt(entry)
        lookup_key = (msgctxt + '\x04' + msgid) if msgctxt else msgid
        translation = translations.get(lookup_key, None)

        if translation is not None:
            stats['translated'] += 1
            stats['from_map'] += 1

            # Preserve the POT entry head (comments + msgctxt + msgid +
            # msgid_plural) verbatim: the msgid must match the upstream POT
            # byte-for-byte (including line wrapping), so copy the original
            # lines instead of re-assembling them. Only the msgstr is replaced.
            head_lines: list[str] = []
            for line in entry.split('\n'):
                if re.match(r'^msgstr(?:\[\d+\])?\s+', line):
                    break
                head_lines.append(line)

            # Format msgstr (handles plural forms if translation is a list/tuple)
            result = '\n'.join(head_lines) + '\n' + '\n'.join(format_msgstr(translation))

            # Remove fuzzy if present (preserving other flags)
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
        return load_translations_py(source)
    else:
        raise ValueError(f"Unsupported translations file: {source} (use .py or .json)")


def load_translations_py(path: str) -> dict[str, str]:
    """Load TRANSLATIONS from a translations.py WITHOUT executing it.

    Parses the file as an AST and only accepts dict-literal assignments
    (``TRANSLATIONS = {...}`` / ``T = {...}``, optionally annotated like
    ``TRANSLATIONS: dict = {...}``). Values are evaluated with
    ast.literal_eval, so arbitrary code is never executed.
    """
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
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
    parser.add_argument('--translator', default=None, help='Translator name (default: resolve from L10N_TW_TRANSLATOR env / {project-dir}/translator.txt)')
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

    translator = resolve_translator(args.translator, Path(args.pot))
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
        f.write(normalize_eof(po_content))

    print(f"\n✅ Written to: {output_path}")


if __name__ == '__main__':
    main()
