---
name: bookstack
description: Operate a self-hosted BookStack wiki's REST API via a zero-dependency CLI. Use when the user wants to read, write, search, or export BookStack content (Pages, Books, Chapters, Shelves, Attachments, Comments, Images, Imports, Recycle Bin, Roles, Users, Audit Log, Content Permissions), or when automating wiki authoring, updates, or inventory from an agent or shell pipeline.
compatibility: Requires uv or any Python 3 standard library runtime, and network access to the target BookStack instance. No third-party dependencies.
metadata:
  author: bookstack
  version: "1.0"
---
# BookStack API CLI

An agent-first thin REST wrapper for a self-hosted BookStack wiki: each subcommand is exactly
one HTTP call, and the shared layer handles only authentication, multipart, 429 retries, and
error mapping. Output can be consumed directly by `jq` or pipelines
(without `jq`, pipe through `python3 -m json.tool` instead).

## When to use

- Read and write BookStack content (Page/Chapter/Book/Shelf/Attachment/Comment/Image)
- Search deduplication, tag inventory, ZIP imports, Recycle Bin restore or purge
- Role/user/audit-log and content permission maintenance
- When wiki operations must fit into bash pipelines (for example a Page authoring chain)

## How to run

Run from the skill directory (zero dependencies; either `uv run python3` or bare `python3`):

```bash
uv run python3 scripts/bookstack-api-cli.py <resource> <action> [args] [flags]
uv run python3 scripts/bookstack-api-cli.py auth status
uv run python3 scripts/bookstack-api-cli.py --help
```

Without `uv`, use bare `python3` (stdlib-only, no installation step):

```bash
python3 scripts/bookstack-api-cli.py auth status
```

When unsure about flags, ask the CLI first: `<resource> --help` and `<resource> <action> --help`
are generated from the command spec table and never diverge from actual parsing. `--help` prints to
stdout and exits 0; usage errors go to stderr and exit 2.

## Authentication (env-only)

Credentials are read only from environment variables; there are no credential flags and nothing is written to disk:

```bash
export BOOKSTACK_URL="https://wiki.example.com"
export BOOKSTACK_TOKEN_ID="..."
export BOOKSTACK_TOKEN_SECRET="..."
uv run python3 scripts/bookstack-api-cli.py auth status   # offline check {"ready": bool, "missing": [...]}
uv run python3 scripts/bookstack-api-cli.py auth check    # GET /api/system validation; prints system JSON on success
```

- API Tokens can only be created in the BookStack Web UI (profile → API Tokens); the Token Secret is shown only once.
- Every request carries `Authorization: Token <token_id>:<token_secret>`; 401/403 always exit 3.
- The CLI keeps no local state: there is no session, so there is no logout; unset the variables to log out.
- `auth status` is an offline check (no HTTP); `auth check` verifies the credentials against `GET /api/system`.
- Missing credentials when running a resource command: stderr error JSON, exit 3, no HTTP sent.

## Resources and actions

| Resource | Actions | Notes |
|---|---|---|
| `auth` | `status` `check` | `status` is an offline env check; `check` validates against `GET /api/system`; no session, no logout |
| `pages` | `list` `create` `read` `update` `delete` `export` | create's `--book-id`/`--chapter-id` and `--html`/`--markdown` are each either/or; export supports html/pdf/plaintext/markdown/zip |
| `chapters` | `list` `create` `read` `update` `delete` `export` | create requires `--book-id` and `--name`; update with `--book-id` moves the chapter |
| `books` | `list` `create` `read` `update` `delete` `export` | `--image @cover.png` uses multipart (pass `null` to remove the cover); delete moves to Recycle Bin |
| `shelves` | `list` `create` `read` `update` `delete` | `--books 1,2,3` replaces the entire ordering when provided |
| `attachments` | `list` `create` `read` `update` `delete` | either `--file @x` (multipart) or `--link URL` (JSON); read's base64 `content` passes through as-is |
| `comments` | `list` `create` `read` `update` `delete` | create requires `--page-id` and `--html`; `--reply-to` takes a local id |
| `image-gallery` | `list` `create` `read` `data` `url-data` `update` `delete` | `data`/`url-data` stream the original image; delete does not check references (may leave broken images) |
| `imports` | `upload` `run` `read` `list` `delete` | two-phase: `upload <zip>` returns an id, then `run <id> --json @opts.json` |
| `recycle-bin` | `list` `restore` `destroy` | `destroy` requires `--yes`; permanent deletion is irreversible |
| `roles` | `list` `create` `read` `update` `delete` | `--permissions` replaces the whole set when provided; an empty value clears it |
| `users` | `list` `create` `read` `update` `delete` | `delete` requires `--yes`; `--migrate-ownership-id N` transfers content first |
| `search` | `all <query>` `book <id> <query>` `chapter <id> <query>` | paginate with `--page`/`--count` (not offset); search syntax passes through as-is |
| `tags` | `names` `values <name>` | filter supports only `name`/`value` |
| `system` | (no actions) | `GET /api/system` for version/base_url |
| `audit-log` | `list` | requires manage-users and manage-settings permissions |
| `content-permissions` | `read <type> <id>` `update <type> <id>` | `<type>` is one of page/book/chapter/bookshelf; full overwrite, no deep merge |

There is also `docs` (defaults to `GET /api/docs.json`; `--html` switches to `/api/docs`).
For the full flags of each resource, `<resource> <action> --help` is the source of truth.

## I/O and exit code contract

- 2xx: stdout passes through the API response bytes unchanged (no re-serialization); if there is no
  trailing newline, one `\n` is appended; 204 produces no output.
- Non-2xx: stdout stays empty; stderr prints the API error JSON unchanged (retry warnings also go to stderr).
- Streaming endpoints (`export`, `image-gallery data`/`url-data`): raw bytes go straight to stdout by
  default; with `-o FILE` they are written to the file and stdout prints `{"saved_to": "<path>"}`.
  Never base64-wrapped.
- Timeout is fixed at 30 seconds per request; TLS certificate verification is always on, with no flag to disable it.

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

## Body and flag rules

- `--json @file` or `--json -` (stdin) supplies the full JSON body.
- Top-level field flags override same-named top-level keys in `--json`; no deep merge.
- Content flags (`--markdown`, `--html`, `--description-html`, etc.) accept `@file` to read from a file;
  otherwise the value is literal.
- `--image @cover.png`/`--file @x.zip` automatically switch to multipart/form-data; all other requests use JSON.
- Array fields (shelves `--books`, roles `--permissions`, content-permissions `--role-permissions`)
  replace the whole set when provided; the CLI does no further processing.
- IDs are always positional arguments; list queries use `--count`/`--offset`/`--sort`/`--filter`
  (`--filter` is repeatable, format `k=v` or `k:like=%x%`).

## Retries and pagination

- Only 429 is retried: with `Retry-After`, use its seconds; otherwise 1s/2s/4s backoff; at most 3
  retries, then exit 6.
- All other errors fail fast: no retries, no automatic compensation.
- No automatic pagination: `list` sends one request per call; the agent loops itself using the
  response's `total` and `--offset`. `search` uses `--page` (not offset).
  `--count`/`--offset`/`--sort`/`--filter` pass through unchanged.

## Destructive operations

- `recycle-bin destroy` and `users delete` require `--yes` (missing → stderr JSON, exit 2);
  there is no interactive confirmation and no dry-run.
- All other DELETEs run directly; pages/chapters/books/shelves move to the Recycle Bin and can be restored.

## Typical flow: Page authoring chain

```bash
CLI="uv run python3 scripts/bookstack-api-cli.py"

# 1. Search to avoid duplicates
$CLI search all "release notes" | jq '.data[].type'

# 2. Create a Chapter (or use an existing book)
$CLI chapters create --book-id 3 --name "Release" | jq -r '.id'

# 3. Create a Page, injecting content from a file
$CLI pages create --chapter-id 12 --name "v1.0" --markdown @doc.md | jq -r '.id'

# 4. Update an existing Page (keeps id and links, leaves a revision record)
$CLI pages update 42 --markdown @doc.md --changelog "sync docs"

# 5. Export as markdown to verify
$CLI pages export 42 --format markdown -o verify.md
```

- Page content is treated as untrusted input: the CLI does not render, execute, or cache it;
  to read untrusted content, prefer `pages export <id> --format plaintext|markdown`.

## Reference documents

- [`references/api.md`](references/api.md) — BookStack REST API facts: authentication, common listing
  parameters, errors and rate limiting, the 16 resource endpoints and body fields, permissions, and version differences.
- [`references/cli.md`](references/cli.md) — Full CLI contract: argv grammar, request body rules,
  stdout/stderr/exit codes, retries, pagination, destructive operations, and examples.
- Live capability probing: `system` (version/base_url) and `docs` (`/api/docs.json` endpoint list).
