#!/usr/bin/env python3
"""
fix_terminology.py — Apply zh_TW terminology fixes from terminology.md.

Two marker styles in terminology.md:
- 不翻「XX」 — hard ban: terms are auto-replaced with the TW equivalent.
- 留意「XX」 — soft note: terms are only reported (scan-only), never replaced,
  because the term may be legitimate in other contexts (e.g. 文件 as document).

English-anchored variant (new): prefix markers with 對應「anchor」, one 對應
marker per anchor word (multiple anchors accumulate, OR semantics). An anchored
marker only fires when the msgid contains any anchor word (word-bounded,
case-insensitive):

- 對應「line」「lines」留意「行」  → scan-only when msgid contains line/lines
                                     and msgstr uses 行
- 對應「keyring」「key ring」不翻「金鑰環」 → auto-replace when msgid contains
                                     keyring/key ring

Markers before the first 對應 marker in a cell are global (as before); markers
after it are anchored by the accumulated anchors. This keeps the existing
130+ unanchored rows fully backward compatible.

Auto-replace also guards against substring traps: if the banned term is a
substring of the TW equivalent (e.g. 應用 → 應用程式), the replacement would
corrupt existing translations (應用程式 → 應用程式程式), so such entries are
downgraded to scan-only.

Two input modes:
- translations.py (default): replaces terms inside the dict values; anchored
  rules are matched against the dict key (the msgid).
- .po file: replaces terms inside every msgstr (including msgstr[n]); anchored
  rules are matched against the entry's msgid (msgid_plural included).

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

from po_gen import normalize_eof
from po_verify import parse_entries

DEFAULT_TERMS_PATH = Path(__file__).resolve().parents[1] / "references" / "terminology.md"

REPLACE_RE = re.compile(r'不翻「([^」]+)」')
SCAN_RE = re.compile(r'留意「([^」]+)」')
ANCHOR_RE = re.compile(r'對應「([^」]+)」')
MARKER_RE = re.compile(
    r'對應((?:「[^」]+」)+)|不翻「([^」]+)」|留意「([^」]+)」'
)


def anchor_regex(anchors: list[str]) -> re.Pattern:
    """Build a word-bounded, case-insensitive regex from anchor words.

    Word boundaries are emulated with lookarounds so that words inside
    larger identifiers (recvline, headline) never match, while line in
    command-line or "key ring" with a space still do.
    """
    alts = "|".join(re.escape(a) for a in anchors)
    return re.compile(rf'(?<![A-Za-z0-9_])(?:{alts})(?![A-Za-z0-9_])', re.IGNORECASE)


def load_replacements(terms_path: Path) -> tuple[
    list[tuple[str, str]],           # auto: (old, new) — global
    list[tuple[str, str]],           # scan: (old, new) — global
    list[tuple[re.Pattern, str, str]],  # anchor auto: (pattern, old, new)
    list[tuple[re.Pattern, str, str]],  # anchor scan: (pattern, old, new)
]:
    """Parse terminology.md and return (auto, scan, anchor_auto, anchor_scan).

    Looks for lines like:
        | default | 預設 | 不翻「默認」 |        → auto-replace 默認 → 預設
        | File | 檔案 | 留意「文件」 |           → scan-only, never replaced
        | Keyring | 鑰匙圈 | 對應「keyring」「key ring」不翻「金鑰環」 |
            → anchored auto-replace when msgid contains keyring/key ring
        | Line | 列 | 對應「line」「lines」留意「行」 |
            → anchored scan-only when msgid contains line/lines

    A banned term that equals or is a substring of the TW equivalent is
    downgraded to scan-only (would corrupt existing translations, e.g.
    應用 → 應用程式 would turn 應用程式 into 應用程式程式).
    """
    text = terms_path.read_text(encoding='utf-8')
    auto: list[tuple[str, str]] = []
    scan: list[tuple[str, str]] = []
    anchor_auto: list[tuple[re.Pattern, str, str]] = []
    anchor_scan: list[tuple[re.Pattern, str, str]] = []
    auto_seen: set[str] = set()
    scan_seen: set[str] = set()

    for line in text.split('\n'):
        # Find the TW equivalent: the cell before the note cell.
        cells = [c.strip() for c in line.split('|')]
        if len(cells) < 4:
            continue
        tw_term = cells[-3]
        note = cells[-2] if len(cells) >= 5 else ''

        # Walk the note cell left to right; anchors accumulate and apply to
        # markers appearing after them.
        anchors: list[str] = []
        local_auto: list[str] = []
        local_scan: list[str] = []
        local_a_auto: list[tuple[list[str], str]] = []
        local_a_scan: list[tuple[list[str], str]] = []
        for m in MARKER_RE.finditer(note):
            if m.group(1) is not None:
                # One 對應 marker may carry multiple 「anchor」 groups.
                anchors.extend(re.findall(r'「([^」]+)」', m.group(1)))
            elif m.group(2) is not None:
                if anchors:
                    local_a_auto.append((list(anchors), m.group(2)))
                else:
                    local_auto.append(m.group(2))
            elif m.group(3) is not None:
                if anchors:
                    local_a_scan.append((list(anchors), m.group(3)))
                else:
                    local_scan.append(m.group(3))

        def add(terms: list[str], auto_replace: bool):
            for old in terms:
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

        def add_anchored(rules: list[tuple[list[str], str]], auto_replace: bool):
            for anchors, old in rules:
                old = old.strip()
                if not old:
                    continue
                trap = auto_replace and (old == tw_term or old in tw_term)
                pat = anchor_regex(anchors)
                if auto_replace and not trap:
                    anchor_auto.append((pat, old, tw_term))
                else:
                    anchor_scan.append((pat, old, tw_term))

        add(local_auto, auto_replace=True)
        add(local_scan, auto_replace=False)
        add_anchored(local_a_auto, auto_replace=True)
        add_anchored(local_a_scan, auto_replace=False)

    return auto, scan, anchor_auto, anchor_scan


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


def entry_msgid(entry: str) -> str:
    """Extract the raw msgid of a single PO entry, msgid_plural included.

    Reuses po_verify.parse_entries, which handles multi-line msgids correctly
    (a hand-rolled single-line regex silently drops wrapped msgids), then
    appends the msgid_plural forms so anchored rules fire when the plural
    contains the anchor word but the singular does not.
    """
    pairs = parse_entries(entry)
    msgid = pairs[0][0] if pairs else ''
    lines = entry.split('\n')
    for j, line in enumerate(lines):
        m = re.match(r'^msgid_plural\s+"(.*)"$', line)
        if not m:
            continue
        parts = [m.group(1)]
        for k in range(j + 1, len(lines)):
            if not lines[k].startswith('"'):
                break
            mm = re.match(r'^"(.*)"$', lines[k])
            if mm:
                parts.append(mm.group(1))
        msgid += ''.join(parts)
    return msgid


def fix_po_file(path: Path, auto: list[tuple[str, str]],
                anchor_auto: list[tuple[re.Pattern, str, str]]) -> int:
    """Apply replacements to every msgstr of a PO file, in place.

    Global replacements apply to every entry; anchored replacements only to
    entries whose msgid matches the anchor. Operates at the text level so
    comments, msgid and multi-line formatting are preserved verbatim; only the
    msgstr content is rewritten.
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
        msgid = entry_msgid(entry)
        anchored = [(old, new) for pat, old, new in anchor_auto if pat.search(msgid)]
        replacements = auto + anchored
        if not replacements:
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
        f.write(normalize_eof(content))
    return fixed


def iter_po_contents(path: Path) -> list[str]:
    """Return every decoded msgstr content of a PO file."""
    text = path.read_text(encoding='utf-8')
    contents: list[str] = []
    for entry in text.split('\n\n'):
        for block in msgstr_blocks(entry):
            contents.append(block_content(block))
    return contents


def iter_po_anchored_hits(path: Path,
                          anchor_scan: list[tuple[re.Pattern, str, str]]) -> list[tuple[str, str, str]]:
    """Return (msgid, term, msgstr) hits for anchored scan rules in a PO file."""
    text = path.read_text(encoding='utf-8')
    hits: list[tuple[str, str, str]] = []
    for entry in text.split('\n\n'):
        if not entry.strip():
            continue
        msgid = entry_msgid(entry)
        for pat, old, _new in anchor_scan:
            if pat.search(msgid):
                for block in msgstr_blocks(entry):
                    content = block_content(block)
                    if old in content:
                        hits.append((msgid, old, content))
    return hits


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


def report_anchored_scan(hits: list[tuple[str, str, str]]):
    """Print anchored scan hits with msgid context (deduplicated by msgid)."""
    if not hits:
        return
    print("👀 錨定掃描命中（msgid 含英文錨定詞，msgstr 含疑慮詞）— 逐條人工判定語境後修正或保留：")
    seen: set[str] = set()
    for msgid, term, msgstr in hits:
        if msgid in seen:
            continue
        seen.add(msgid)
        print(f'  msgid:  {msgid[:70]!r}')
        print(f'  msgstr: {msgstr[:70]!r}   (含「{term}」)')


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

    auto, scan, anchor_auto, anchor_scan = load_replacements(args.terms)
    print(f"Loaded {len(auto)} auto-replace + {len(scan)} scan-only + "
          f"{len(anchor_auto)} anchored auto + {len(anchor_scan)} anchored scan "
          f"terms from {args.terms}")

    if args.target.suffix == '.po':
        fixed = fix_po_file(args.target, auto, anchor_auto)
        print(f"✅ Fixed {fixed} entries in {args.target}")
        contents = iter_po_contents(args.target)
        report_remaining(count_remaining(contents, auto),
                         count_remaining(contents, scan))
        report_anchored_scan(iter_po_anchored_hits(args.target, anchor_scan))
        return

    translations = load_translations(args.target)
    fixed = 0

    for key, val in translations.items():
        new_val = fix_value(val, auto)
        for pat, old, new in anchor_auto:
            if pat.search(key):
                new_val = fix_value(new_val, [(old, new)])
        if new_val != val:
            translations[key] = new_val
            fixed += 1

    write_translations_py(translations, args.target)
    print(f"✅ Fixed {fixed} entries in {args.target}")

    items = [s for val in translations.values()
             for s in (val if isinstance(val, list) else [val])]
    report_remaining(count_remaining(items, auto), count_remaining(items, scan))

    hits: list[tuple[str, str, str]] = []
    for key, val in translations.items():
        for pat, old, _new in anchor_scan:
            if pat.search(key):
                for s in (val if isinstance(val, list) else [val]):
                    if old in s:
                        hits.append((key, old, s))
    report_anchored_scan(hits)


if __name__ == '__main__':
    main()