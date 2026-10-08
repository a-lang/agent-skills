# AGENTS.md — bookstack

Development rules and commands for the bookstack skill.

## What this is

The entry point is `SKILL.md` (CLI usage and SOP). The single-file CLI is at `scripts/bookstack-api-cli.py`,
black-box tests are in `tests/`, and contract documents are in `references/`.

## Commands

Run from the skill directory (`skills/bookstack/`):

```bash
# Full test suite (stdlib unittest, zero dependencies; must run after changing the script)
uv run python3 -m unittest discover -s tests -p "test_*.py"

# Single module
uv run python3 -m unittest test_exit_codes

# CLI smoke test
uv run python3 scripts/bookstack-api-cli.py --help
uv run python3 scripts/bookstack-api-cli.py -auth status
```

- Tests are driven by `tests/cli_harness.py`: the only seam is the module-level `transport(request)`.
  Tests replace it with `RecordingTransport` and then black-box assert on request (method/path/query/
  headers/body), stdout bytes, stderr bytes, and exit codes.
- No new dependencies: tests always use the stdlib `unittest`; the CLI always uses the stdlib (`urllib`/`json`/`ssl`, etc.).

## Development rules

- **Table-driven extension**: the `ACTIONS` table (along with `RESOURCE_ORDER`) is the single source of truth,
  driving argv parsing, argument validation, `--help` text generation, and the HTTP method/path mapping.
  New endpoints change only the table and tests; do not scatter branches through the parser.
- **Single seam**: the transport boundary (`transport()`). Do not add another mock seam above it;
  tests must not touch the real network or a real instance.
- **Contract consistency**: stdout passes through unchanged, non-2xx error JSON goes to stderr unchanged,
  and exit codes match `--help`/`references/cli.md`. When changing the contract, update all three places in sync.
- **Zero local state**: no cache or credential files; credentials are read only from env; the Token Secret must
  never appear in argv, files, or logs. Tests and docs always use fake values.
- **TDD**: add a failing test first for new behavior, implement to green, then run the full suite.
- **Version**: `USER_AGENT` is currently hardcoded as `bookstack-api-cli/1.0`; its alignment strategy with the
  SKILL `metadata.version` is undecided (noted in a script comment).
