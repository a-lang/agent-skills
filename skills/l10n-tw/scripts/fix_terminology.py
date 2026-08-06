#!/usr/bin/env python3
"""
fix_terminology.py — Apply zh_TW terminology fixes from terminology.md.

Two marker styles in terminology.md:
- 不翻「XX」 — hard ban: terms are auto-replaced with the TW equivalent.
- 留意「XX」 — soft note: terms are only reported (scan-only), never replaced,
  because the term may be legitimate in other contexts (e.g. 文件 as document).

Auto-replace also guards against substring traps: if the banned term is a
substring of the TW equivalent (e.g. 應用 → 應用程式), the replacement would
corrupt existing translations (應用程式 → 應用程式程式), so such entries are
downgraded to scan-only.

Two input modes:
- translations.py (default): replaces terms inside the dict values.
- .po file: replaces terms inside every msgstr (including msgstr[n]).

Usage:
    uv run python3 skills/l10n-tw/scripts/fix_terminology.py \
        <translations.py> [--terms references/terminology.md]
    uv run python3 skills/l10n-tw/scripts/fix_terminology.py \
        <translations.po> [--terms references/terminology.md]
"""

import argparse
import ast
import re
import sys
from pathlib import Path


DEFAULT_TERMS_PATH = Path(__file__).resolve().parents[1] / "references" / "terminology.md"

REPLACE_RE = re.compile(r'不翻「([^」]+)」')
SCAN_RE = re.compile(r'留意「([^」]+)」')


def load_replacements(terms_path: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Parse terminology.md and return (auto_replace, scan_only) pairs.

    Looks for lines like:
        | default | 預設 | 不翻「默認」 |        → auto-replace 默認 → 預設
        | File | 檔案 | 留意「文件」 |           → scan-only, never replaced

    A banned term that equals or is a substring of the TW equivalent is
    downgraded to scan-only (would corrupt existing translations, e.g.
    應用 → 應用程式 would turn 應用程式 into 應用程式程式).
    """
    text = terms_path.read_text(encoding='utf-8')
    auto: list[tuple[str, str]] = []
    scan: list[tuple[str, str]] = []
    auto_seen: set[str] = set()
    scan_seen: set[str] = set()

    for line in text.split('\n'):
        # Find the TW equivalent: the cell before the note cell.
        cells = [c.strip() for c in line.split('|')]
        if len(cells) < 4:
            continue
        tw_term = cells[-3]

        def add(terms: str, auto_replace: bool):
            for old in terms.split('/'):
                old = old.strip()
                if not old:
                    continue
                # Substring trap: replacing 應用 with 應用程式 would corrupt
                # existing 應用程式 → downgrade this term to scan-only.
                trap = auto_replace and (old == tw_term or old in tw_term)
                if auto_replace and not trap:
                    if old not in auto_seen:
                        auto.append((old, tw_term))
                        auto_seen.add(old)
                elif old not in scan_seen:
                    scan.append((old, tw_term))
                    scan_seen.add(old)

        for m in REPLACE_RE.finditer(line):
            add(m.group(1), auto_replace=True)
        for m in SCAN_RE.finditer(line):
            add(m.group(1), auto_replace=False)

    return auto, scan


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


# ── PO mode ──────────────────────────────────────────────────────────────

def decode_po(s: str) -> str:
    return (s
            .replace('\\"', '\x00Q')
            .replace('\\\\', '\x00B')
            .replace('\\n', '\n')
            .replace('\\t', '\t')
            .replace('\x00Q', '"')
            .replace('\x00B', '\\'))


def encode_po(s: str) -> str:
    return (s
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\t', '\\t'))


MSGSTR_RE = re.compile(r'^msgstr(?:\[\d+\])?\s+"(.*)"$')


def msgstr_blocks(entry: str) -> list[list[str]]:
    """Split an entry into [msgstr-block lines] segments (header line + continuations)."""
    lines = entry.split('\n')
    blocks: list[list[str]] = []
    i = 0
    while i < len(lines):
        if MSGSTR_RE.match(lines[i]):
            block = [lines[i]]
            j = i + 1
            while j < len(lines) and lines[j].startswith('"'):
                block.append(lines[j])
                j += 1
            blocks.append(block)
            i = j
        else:
            i += 1
    return blocks


def block_content(block: list[str]) -> str:
    """Decode a msgstr block into its raw string."""
    parts = [MSGSTR_RE.match(block[0]).group(1)]
    for ln in block[1:]:
        m = re.match(r'^"(.*)"$', ln)
        if m:
            parts.append(m.group(1))
    return decode_po(''.join(parts))


def fix_po_file(path: Path, replacements: list[tuple[str, str]]) -> int:
    """Apply replacements to every msgstr of a PO file, in place.

    Operates at the text level so comments, msgid and multi-line formatting
    are preserved verbatim; only the msgstr content is rewritten.
    """
    text = path.read_text(encoding='utf-8')
    entries = text.split('\n\n')
    fixed = 0

    for i, entry in enumerate(entries):
        if not entry.strip():
            continue
        blocks = msgstr_blocks(entry)
        if not blocks:
            continue
        changed = False
        lines = entry.split('\n')
        out: list[str] = []
        pos = 0
        for block in blocks:
            start = next(k for k in range(pos, len(lines)) if lines[k] == block[0])
            out.extend(lines[pos:start])
            content = block_content(block)
            new_content = fix_value(content, replacements)
            if new_content != content:
                changed = True
                header = re.match(r'^(msgstr(?:\[\d+\])?\s+)', block[0]).group(1)
                encoded = encode_po(new_content)
                if len(block) == 1:
                    out.append(f'{header}"{encoded}"')
                else:
                    out.append(block[0])
                    out.append(f'"{encoded}"')
            else:
                out.extend(block)
            pos = start + len(block)
        out.extend(lines[pos:])
        if changed:
            entries[i] = '\n'.join(out)
            fixed += 1

    content = '\n\n'.join(entries)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
        if not content.endswith('\n'):
            f.write('\n')
    return fixed


def iter_po_contents(path: Path) -> list[str]:
    """Return every decoded msgstr content of a PO file."""
    text = path.read_text(encoding='utf-8')
    contents: list[str] = []
    for entry in text.split('\n\n'):
        for block in msgstr_blocks(entry):
            contents.append(block_content(block))
    return contents


def count_remaining(items: list[str], pairs: list[tuple[str, str]]) -> dict[str, int]:
    """Count occurrences of terms across items."""
    remaining: dict[str, int] = {}
    for s in items:
        for old, _ in pairs:
            if old in s:
                remaining[old] = remaining.get(old, 0) + 1
    return remaining


def report_remaining(auto_remaining: dict[str, int], scan_remaining: dict[str, int]):
    """Print remaining-term report."""
    if auto_remaining:
        print("⚠️  Remaining banned terms (should be fixed):")
        for term, count in sorted(auto_remaining.items()):
            print(f'  "{term}" x{count}')
    if scan_remaining:
        print("👀 Scan-only terms present — not auto-replaced (may be legitimate, verify manually):")
        for term, count in sorted(scan_remaining.items()):
            print(f'  "{term}" x{count}')
    if not auto_remaining and not scan_remaining:
        print("✅ All target terms cleaned")


def main():
    parser = argparse.ArgumentParser(
        description="Apply terminology fixes from terminology.md to translations.py or a .po file"
    )
    parser.add_argument('target', type=Path, help='Path to translations.py or a .po file')
    parser.add_argument(
        '--terms',
        type=Path,
        default=DEFAULT_TERMS_PATH,
        help=f'Path to terminology.md (default: {DEFAULT_TERMS_PATH})',
    )
    args = parser.parse_args()

    if not args.target.exists():
        print(f"❌ File not found: {args.target}", file=sys.stderr)
        sys.exit(1)
    if not args.terms.exists():
        print(f"❌ Terms file not found: {args.terms}", file=sys.stderr)
        sys.exit(1)

    auto, scan = load_replacements(args.terms)
    print(f"Loaded {len(auto)} auto-replace + {len(scan)} scan-only terms from {args.terms}")

    if args.target.suffix == '.po':
        fixed = fix_po_file(args.target, auto)
        print(f"✅ Fixed {fixed} entries in {args.target}")
        contents = iter_po_contents(args.target)
        report_remaining(count_remaining(contents, auto),
                         count_remaining(contents, scan))
        return

    translations = load_translations(args.target)
    fixed = 0

    for key, val in translations.items():
        new_val = fix_value(val, auto)
        if new_val != val:
            translations[key] = new_val
            fixed += 1

    write_translations_py(translations, args.target)
    print(f"✅ Fixed {fixed} entries in {args.target}")

    items = [s for val in translations.values()
             for s in (val if isinstance(val, list) else [val])]
    report_remaining(count_remaining(items, auto), count_remaining(items, scan))


if __name__ == '__main__':
    main()
