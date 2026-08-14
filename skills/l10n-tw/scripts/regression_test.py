#!/usr/bin/env python3
"""Regression test for translation projects.

Discovers project directories automatically by scanning for .pot files and
their matching translations script. Each project is a (POT, translations.py)
pair; for each pair, re-runs po_gen.py with the project's POT and translations
script, then compares the new PO's translations against the existing committed
PO.

Matching rules (per directory):
- `<potstem>-translations.py` always pairs with `<potstem>.pot`
- `translations.py` (default name) pairs with the sole .pot in the directory

Also runs po_verify.py on each (POT, generated PO) pair.

Usage:
    uv run python3 skills/l10n-tw/scripts/regression_test.py
    uv run python3 skills/l10n-tw/scripts/regression_test.py --root ./some-dir
"""
import argparse
import subprocess
import sys
from pathlib import Path

from po_verify import check_eof_canonicality

# Directory containing this script
SCRIPTS = Path(__file__).resolve().parent


def discover_projects(root: Path) -> list[tuple[Path, Path, Path]]:
    """Find (project_dir, pot_file, translations_py) project pairs."""
    projects: list[tuple[Path, Path, Path]] = []
    dirs: dict[Path, list[Path]] = {}
    for pot in root.rglob("*.pot"):
        dirs.setdefault(pot.parent, []).append(pot)
    for project_dir, pot_files in sorted(dirs.items()):
        pot_files = sorted(pot_files)
        default = project_dir / "translations.py"
        pairs: list[tuple[Path, Path, Path]] = []
        for pot_file in pot_files:
            tr_py = project_dir / f"{pot_file.stem}-translations.py"
            if tr_py.exists():
                pairs.append((project_dir, pot_file, tr_py))
        if default.exists():
            paired = {pot_file for _, pot_file, _ in pairs}
            unpaired = [p for p in pot_files if p not in paired]
            if len(unpaired) == 1:
                pairs.append((project_dir, unpaired[0], default))
            elif len(unpaired) > 1:
                print(
                    f"⚠️  Skipping {project_dir}: multiple .pot files with default "
                    "translations.py (use <potstem>-translations.py instead)"
                )
        projects.extend(pairs)
    return sorted(projects, key=lambda p: str(p[0]))


def find_committed_po(project_dir: Path, pot_file: Path, language: str) -> Path | None:
    """Find the committed PO file in the project directory."""
    base = pot_file.stem
    candidates = [
        project_dir / f"{base}-{language}.po",
        project_dir / f"{base}.{language}.po",
        project_dir / f"{language}.po",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def parse_po_translations(po_path: Path):
    """Parse a PO file and return {decoded_msgid: decoded_msgstr} dict,
    skipping the header (empty msgid)."""
    import polib

    po = polib.pofile(str(po_path))
    out = {}
    for e in po:
        if e.obsolete:
            continue
        if not e.msgid:
            continue  # header
        out[e.msgid] = e.msgstr
    return out


def self_check_eof_checker() -> bool:
    """Sanity-check check_eof_canonicality itself against known samples."""
    cases = [
        (b'x\n', []),
        (b'msgid ""\nmsgstr ""\n', []),
        (b'x\n\n', ['EOF']),
        (b'x', ['EOF']),
        (b'x \n', ['L1']),
        (b'x\t\n', ['L1']),
        (b'', ['EOF']),
        (b'x\n\n\n', ['EOF']),
    ]
    ok = True
    for data, expected in cases:
        issues = check_eof_canonicality(data)
        if expected:
            got = any(any(p in i for p in expected) for i in issues)
        else:
            got = not issues
        if not got:
            ok = False
            print(f"  ❌ self-check failed for {data!r}: {issues}")
    return ok


def run(cmd, **kw):
    print(f"$ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("STDOUT:", r.stdout[-2000:])
        print("STDERR:", r.stderr[-2000:])
    return r


def main():
    parser = argparse.ArgumentParser(
        description="Regression test for l10n-tw translation projects"
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Root directory to scan for projects (required — never scans cwd implicitly)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt before loading translations.py files",
    )
    parser.add_argument(
        "--language",
        default="zh_TW",
        help="Language code for generated PO files (default: zh_TW)",
    )
    args = parser.parse_args()

    if not self_check_eof_checker():
        print("❌ check_eof_canonicality self-check failed — aborting regression run")
        return 1

    root = args.root.resolve()
    out_dir = Path("/tmp/po-regress")
    out_dir.mkdir(exist_ok=True)

    projects = discover_projects(root)
    if not projects:
        print(f"⚠️  No projects found under {root}")
        return 0

    print(f"Will load {len(projects)} translations.py file(s):")
    for _, pot_file, tr_py in projects:
        print(f"  - {tr_py}")
    if not args.yes:
        try:
            input("Press Enter to continue, Ctrl-C to abort… ")
        except (EOFError, KeyboardInterrupt):
            print("Aborted.")
            return 1

    results = []
    for project_dir, pot_file, tr_py in projects:
        committed = find_committed_po(project_dir, pot_file, args.language)

        print(f"\n{'='*70}")
        print(f"  {project_dir.name}")
        print('='*70)

        if committed is None:
            print(f"  ⚠️  committed PO not found in {project_dir}")
            results.append((project_dir.name, "SKIP", "committed PO missing"))
            continue

        gen_po = out_dir / f"{committed.stem}.regen.po"

        # Regenerate
        r = run(
            [
                sys.executable,
                str(SCRIPTS / "po_gen.py"),
                str(pot_file),
                "-t",
                str(tr_py),
                "-o",
                str(gen_po),
                "-l",
                args.language,
            ]
        )
        if r.returncode != 0:
            results.append((project_dir.name, "FAIL", "po_gen.py failed"))
            continue

        # Byte-level format check on the regenerated PO
        gen_raw = gen_po.read_bytes()
        format_issues = check_eof_canonicality(gen_raw)
        if format_issues:
            print(f"  ❌ regenerated PO format issues: {format_issues[0]}")
            results.append((project_dir.name, "FAIL", "EOF/trailing-whitespace format issue"))
            continue

        # Verify structure
        r = run(
            [
                sys.executable,
                str(SCRIPTS / "po_verify.py"),
                str(pot_file),
                str(gen_po),
                "--comments",
            ]
        )
        if r.returncode != 0:
            print(r.stdout[-1500:])
            results.append((project_dir.name, "FAIL", "po_verify.py reported mismatch"))
            continue

        # Compare msgstr content
        try:
            committed_trans = parse_po_translations(committed)
            gen_trans = parse_po_translations(gen_po)
        except Exception as ex:
            print(f"  ⚠️  polib parse failed: {ex}")
            results.append((project_dir.name, "FAIL", f"polib parse error: {ex}"))
            continue

        missing_in_gen = {k: v for k, v in committed_trans.items() if k not in gen_trans}
        diff_msgstr = {
            k: (committed_trans[k], gen_trans[k])
            for k in committed_trans
            if k in gen_trans and committed_trans[k] != gen_trans[k]
        }
        extra_in_gen = {k: v for k, v in gen_trans.items() if k not in committed_trans}

        print(f"  committed: {len(committed_trans)} translations")
        print(f"  generated: {len(gen_trans)} translations")
        if missing_in_gen:
            print(f"  ❌ {len(missing_in_gen)} msgids in committed PO missing from regenerated PO")
        if diff_msgstr:
            print(f"  ❌ {len(diff_msgstr)} msgstrs differ")
            for k, (a, b) in list(diff_msgstr.items())[:3]:
                print(f"    committed: {a!r}")
                print(f"    generated: {b!r}")
        if extra_in_gen:
            print(f"  ⚠️  {len(extra_in_gen)} extra msgids in regenerated PO (not in committed)")

        if missing_in_gen or diff_msgstr:
            results.append(
                (project_dir.name, "FAIL", f"{len(missing_in_gen)} missing, {len(diff_msgstr)} diff")
            )
        else:
            results.append((project_dir.name, "OK", f"{len(committed_trans)} msgstrs preserved"))

    # Summary
    print(f"\n{'='*70}")
    print("  REGRESSION TEST SUMMARY")
    print('='*70)
    for name, status, detail in results:
        icon = "✅" if status == "OK" else "❌" if status == "FAIL" else "⚠️ "
        print(f"  {icon} [{status}] {name}: {detail}")
    return 0 if all(r[1] in ("OK", "SKIP") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
