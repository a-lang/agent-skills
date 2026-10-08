# bookstack-api-cli.py CLI Contract

> Script: `scripts/bookstack-api-cli.py`; zero dependencies (Python standard library); runs with
> `uv run python3` or bare `python3`. For API facts see [`api.md`](api.md).

## Positioning

- **Thin REST wrapper**: each subcommand = one HTTP call; the shared layer handles only authentication,
  multipart, 429 retries, and error mapping.
- **agent-first**: opencode/pi/hermes call it via bash; output is programmatically parseable (`jq`/pipelines).
- **Does not do**: automatic pagination, content rendering, caching, dry-run, interactive prompts.

## argv grammar

```
bookstack-api-cli.py <resource> <action> [args] [flags]
bookstack-api-cli.py --help
```

- Positional `<resource>`/`<action>` map to REST resources and actions; all `--xxx` double-dash flags are
  reserved for REST parameters.
- `auth` is a local (non-REST) resource with `status` (offline env check) and `check`
  (live `GET /api/system` validation); it follows the same `<resource> <action>` grammar.
- `--help` (including per resource/action) prints to stdout and exits 0; unknown resource/action or argument
  errors go to stderr and exit 2. Help text is generated from the command spec table and never diverges from actual parsing.

## Resource and action mapping

Resource names use REST path plurals. Standard mappings:

| Action | HTTP | Command form |
|---|---|---|
| list | GET `/api/<resource>` | `<resource> list [--count N] [--offset N] [--sort ±field] [--filter k[op]=v]` |
| read | GET `/api/<resource>/{id}` | `<resource> read <id>` |
| create | POST `/api/<resource>` | `<resource> create --json @file\|- [field flags]` |
| update | PUT `/api/<resource>/{id}` | `<resource> update <id> --json @file\|- [field flags]` |
| delete | DELETE `/api/<resource>/{id}` | `<resource> delete <id>` |
| export | GET `/api/<resource>/{id}/export/<fmt>` | `<resource> export <id> --format html\|pdf\|plaintext\|markdown\|zip` |

Non-CRUD exceptions (nesting flattened into flags):

- `search all <query>`/`search book <id> <query>`/`search chapter <id> <query>`
- `system` (no action; reads `GET /api/system`)
- `tags names`/`tags values <name>`
- `recycle-bin list`/`recycle-bin restore <deletionId>`/`recycle-bin destroy <deletionId> --yes`
- `imports upload <zip>`/`imports run <id> --json @file|-`
- `docs` (defaults to `/api/docs.json`; `docs --html` switches to `/api/docs`)
- `image-gallery data <id>`/`image-gallery url-data --url URL` (streaming)
- `content-permissions read <type> <id>`/`content-permissions update <type> <id> --json @file|-`

The full actions of the 16 resources are in `SKILL.md`'s "Resources and actions" table.

## Request body and file arguments

- `--json @file`: full JSON body; `--json -` reads from stdin.
- Top-level field flags (such as `--name`, `--book-id`, `--chapter-id`, `--markdown`) override the same-named
  top-level keys in `--json`; no deep merge.
- Content-type flags support `@file` to read a file (such as `--markdown @doc.md`); otherwise the value is literal.
- File upload flags (`--image @cover.png`, `--file @x.zip`) automatically switch to multipart/form-data;
  all other requests use JSON.
- IDs are positional; list queries use `--count`/`--offset`/`--sort`/`--filter`
  (`--filter` is repeatable, format `k=v` or `k:like=%x%`).
- Conflicting body sources (`--json` clashing with field flags) or a missing required body exits 2.

## Authentication (env-only)

- Only source: `BOOKSTACK_URL`, `BOOKSTACK_TOKEN_ID`, `BOOKSTACK_TOKEN_SECRET`;
  no credential flags, nothing written to disk.
- The request header is always `Authorization: Token <token_id>:<token_secret>`;
  no session cookie or Basic.
- `auth check`: missing env or `GET /api/system` failure → stderr error JSON, exit 3;
  success → stdout system JSON, exit 0.
- `auth status`: purely offline check; stdout `{"ready": bool, "missing": [...]}`; exit 0/3.
- The CLI keeps no local state: there is no session and no logout; unset the
  variables to log out. `auth --help` documents both actions.

## stdout/stderr/exit codes

- 2xx: stdout = the API response bytes unchanged (byte-for-byte, no re-serialization), trailing newline guaranteed;
  204 → no stdout output.
- Streaming endpoints (`export`, `image-gallery`'s `data`/`url-data`): raw bytes go to stdout by default;
  with `-o FILE` they are written to the file and stdout prints `{"saved_to": "<path>"}`. Never base64-wrapped.
- Non-2xx (including 429 retries exhausted): stdout stays empty; stderr prints the API error JSON unchanged;
  retry warnings also go to stderr.
- `--help` → stdout, exit 0; usage errors → stderr, exit 2.
- Timeout defaults to 30 seconds per request; TLS certificate verification is always on (no flag to disable).
- Diagnostics and retry warnings go only to stderr; stdout always contains only results.

| Exit code | Meaning |
|---|---|
| 0 | Success (2xx, including 204) |
| 2 | Usage/argument error (unknown resource/action, missing `--yes`, conflicting body sources) |
| 3 | Auth/permission (401, 403, missing env vars, or validation failure) |
| 4 | Not found (404) |
| 5 | Client error (422 validation failure; other unnamed 4xx such as 400, 409) |
| 6 | Rate-limit retries exhausted (429) |
| 7 | Network/timeout/TLS |
| 8 | Server error (5xx) |

## Retries and pagination

- Only 429 is retried: with `Retry-After`, use its seconds; otherwise 1s/2s/4s backoff; at most 3 retries,
  then exit 6.
- All other errors fail fast (no retries, no automatic compensation); 5xx is not retried.
- No automatic pagination: `list` is one call, one request; `--count`/`--offset`/`--sort`/`--filter` pass
  through unchanged, and the agent loops itself using the response's `total`. `search` uses `--page`/`--count`
  (not offset).
- List responses are kept as `{"data": [...], "total": N}` unchanged, with no processing.

## Destructive operations

- Require `--yes` (missing → stderr JSON error, exit 2): `recycle-bin destroy`, `users delete`.
- All other DELETEs run directly (pages/chapters/books/shelves go to Recycle Bin and can be restored).
- No interactive confirmation, no dry-run; `recycle-bin destroy` and `users delete` are irreversible.

## Examples

```bash
CLI="uv run python3 scripts/bookstack-api-cli.py"

# Offline credential check / connection validation
$CLI auth status
$CLI auth check | jq .version

# Listing with server-side filtering (no automatic pagination)
$CLI books list --count 50 --filter name:like=%api% --sort -created_at | jq .total

# Create a Page: content injected from a file, never in argv
$CLI pages create --chapter-id 12 --name "v1.0" --markdown @doc.md --tags '[{"name":"release","value":"v1"}]'

# Export an image/document: raw stdout or saved to disk
$CLI pages export 42 --format markdown -o verify.md
$CLI image-gallery data 7 -o cover.png

# Destructive operations require --yes
$CLI recycle-bin destroy 99 --yes
$CLI users delete 4 --migrate-ownership-id 2 --yes
```
