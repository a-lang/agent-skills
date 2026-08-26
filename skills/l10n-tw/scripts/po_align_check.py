#!/usr/bin/env python3
"""
po_align_check.py — Verify CLI help text alignment between msgid and msgstr.

CLI help blocks (Translation Project style) pad each option to a fixed display
column so all descriptions start at the same position. CJK characters are
double-width, so after translation the number of padding spaces must be
recalculated from DISPLAY width — counting characters instead silently
misjudges every line containing CJK.

For each entry, every physical line of the msgid is compared with the
corresponding line of the msgstr:

- Option lines: msgid line has >= 2 leading spaces AND a run of >= 2 spaces
  separating the option from the description. The description's display
  column in the msgstr must equal the msgid's column. If the translated
  option is wider than the original column, exact alignment is impossible
  and a human must decide (shorten the option or move the whole block).
- Continuation lines: msgid line has a pure indent >= 10 columns (wrapped
  description text aligned to the description column). The msgstr indent
  column must equal the msgid's.

Skipped: lines containing tabs (tab-aligned output is guaranteed by the tab
itself), empty msgstr lines, msgstr lines without an msgid counterpart.

Exit codes:
  0 = no issues (including "no CLI help lines found")
  1 = alignment issues found (offsets must be fixed; oversized options need
      a human decision — both are actionable, the report says which)

Usage:
    uv run python3 skills/l10n-tw/scripts/po_align_check.py <pot> <po>
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from po_verify import parse_entries, get_msgstr


def dwidth(s: str) -> int:
    """Display width: CJK wide/fullwidth chars (east_asian_width W/F) = 2, else 1."""
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)


SEPARATOR_RE = re.compile(r' {2,}(\S)')


def desc_col(line: str) -> tuple[int | None, int | None]:
    """Return (desc_start_col, option_width) for an option line.

    desc_start_col: display column (1-based) where the description begins.
    option_width:   display width of the option part (up to the padding).
    Returns (None, None) when the line has no 2+ space separator.
    """
    body = line.lstrip(' ')
    m = SEPARATOR_RE.search(body)
    if not m:
        return None, None
    lead = len(line) - len(body)
    return dwidth(line[: lead + m.end() - 1]), dwidth(line[: lead + m.start()])


def check_po(pot_path: Path, po_path: Path) -> int:
    """Check alignment; returns 0 = clean, 1 = issues."""
    pot_entries = parse_entries(pot_path.read_text(encoding='utf-8'))
    po_entries = parse_entries(po_path.read_text(encoding='utf-8'))
    po_by_id = {e[0]: e[1] for e in po_entries}

    issues: list[str] = []
    checked = 0

    for msgid, entry in pot_entries:
        if not msgid:
            continue
        po_entry = po_by_id.get(msgid)
        if po_entry is None:
            continue
        msgstr = get_msgstr(po_entry)
        if not msgstr:
            continue
        m_lines = msgid.replace('\\n', '\n').split('\n')
        s_lines = msgstr.replace('\\n', '\n').split('\n')

        for i, m in enumerate(m_lines):
            if '\t' in m:
                continue
            s = s_lines[i] if i < len(s_lines) else ''
            if not s.strip():
                continue

            m_indent = len(m) - len(m.lstrip(' '))
            m_col, _m_opt = desc_col(m)
            s_indent = len(s) - len(s.lstrip(' '))
            s_col, s_opt = desc_col(s)

            if m_col is not None and m_indent >= 2:
                # msgid 選項行：譯文說明欄位必須與原文一致。
                if s_col is None:
                    if s_indent >= 10:
                        # 譯文換行結構不同（此處是續行）— 無法按索引比對，跳過
                        continue
                    checked += 1
                    issues.append(
                        f'L{i}: 原文說明欄 {m_col}，譯文選項與說明間無 2+ 空格分隔: {s[:60]!r}')
                    continue
                checked += 1
                if s_opt is not None and s_opt > m_col:
                    issues.append(
                        f'L{i}: 譯文選項寬 {s_opt} 超過原文說明欄 {m_col}，'
                        f'無法對齊（需人工決定）: {s[:60]!r}')
                elif s_col != m_col:
                    issues.append(
                        f'L{i}: 對齊欄譯文={s_col} 應為 {m_col}: {s[:60]!r}')
            elif m_indent >= 10:
                # msgid 續行：譯文縮排欄位必須與原文一致。
                if s_col is not None:
                    # 譯文換行結構不同（此處是選項行）— 無法按索引比對，跳過
                    continue
                checked += 1
                if dwidth(s[:s_indent]) != dwidth(m[:m_indent]):
                    issues.append(
                        f'L{i}: 續行縮排譯文={dwidth(s[:s_indent])} 應為 '
                        f'{dwidth(m[:m_indent])}: {s[:60]!r}')

    if checked == 0:
        print('✅ 無 CLI 求助對齊行（無需檢查）')
        return 0

    if issues:
        print(f'❌ CLI 求助文字對齊問題 ({len(issues)} 條)：')
        for issue in issues:
            print(f'   - {issue}')
        print()
        print('修正原則：依顯示寬度（CJK=2 欄）調整補空格數，使說明欄位與原文一致；')
        print('「需人工決定」者縮短譯文選項或整體平移欄位。')
        return 1

    print(f'✅ CLI 求助文字對齊檢查通過（{checked} 行檢查）')
    return 0


def self_check() -> bool:
    """Sanity-check the column math against known cases."""
    cases = [
        # (line, expected_desc_col, expected_option_width)
        ('  --host=hostname              set the server', 31, 17),
        ('  --rmqs=主機|@網域|#佇列      傳送 Remote Message Queue 請求', 31, 25),
        ('  --proxy-host=[IP|主機名稱]   設定/取消設定代理伺服器', 31, 28),
        ('                               do not use any configuration file data', None, None),
        ('  --set-from-header[=(auto|on|off)] set From header handling', None, None),
    ]
    ok = True
    for line, want_col, want_opt in cases:
        col, opt = desc_col(line)
        if col != want_col or opt != want_opt:
            ok = False
            print(f'  ❌ desc_col({line!r}) = ({col}, {opt}), expected ({want_col}, {want_opt})')
    for s, want in [('主機名稱', 8), ('abc', 3), ('--rmqs=', 7)]:
        got = dwidth(s)
        if got != want:
            ok = False
            print(f'  ❌ dwidth({s!r}) = {got}, expected {want}')
    if ok:
        print('  ✅ po_align_check self-check passed')
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Verify CLI help text alignment between POT and PO (display-width aware)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('pot', nargs='?', help='Path to .pot template file')
    parser.add_argument('po', nargs='?', help='Path to .po translation file')
    parser.add_argument('--self-check', action='store_true',
                        help='Run internal sanity checks and exit')
    args = parser.parse_args()

    if args.self_check:
        sys.exit(0 if self_check() else 1)

    if not args.pot or not args.po:
        parser.error('pot and po are required unless --self-check is used')
    if not Path(args.pot).exists() or not Path(args.po).exists():
        print('❌ POT or PO file not found', file=sys.stderr)
        sys.exit(1)

    sys.exit(check_po(Path(args.pot), Path(args.po)))


if __name__ == '__main__':
    main()