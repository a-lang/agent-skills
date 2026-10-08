# bookstack

An **Agent Skill** for operating a self-hosted BookStack wiki's REST API via a zero-dependency CLI.

Based on the [Agent Skills open standard](https://agentskills.io/specification): a directory containing `SKILL.md`, plus a single-file Python CLI (`scripts/bookstack-api-cli.py`), contract references, and black-box tests. Install it as-is into Claude Code, OpenCode, Gemini CLI, Cursor, GitHub Copilot, Codex, or any platform that supports Agent Skills.

## Features

- **Thin REST wrapper** — each subcommand is exactly one HTTP call; the shared layer handles only authentication, multipart, 429 retries, and error mapping
- **Agent-first** — any coding agent with shell access calls it via bash; output is programmatically parseable (`jq` / pipelines)
- **Zero dependencies** — Python standard library only (`urllib` / `json` / `ssl`); runs with `uv run python3` or bare `python3`, no installation step
- **Env-only auth** — credentials come only from `BOOKSTACK_URL`, `BOOKSTACK_TOKEN_ID`, `BOOKSTACK_TOKEN_SECRET`; nothing written to disk, no session, no logout
- **Explicit contract** — stdout passes API bytes through unchanged, non-2xx error JSON goes to stderr unchanged, exit codes `0–8` are stable and documented
- **Full coverage** — Pages, Books, Chapters, Shelves, Attachments, Comments, Image Gallery, Imports, Recycle Bin, Roles, Users, Search, Tags, System, Audit Log, Content Permissions
- **Safe by default** — destructive operations (`recycle-bin destroy`, `users delete`) require `--yes`; no interactive prompts, no dry-run, no hidden retries

## Directory structure

```
bookstack/                      # skill directory (copy or link this directory on install)
├── README.md                   # skill description (this file)
├── AGENTS.md                   # skill development rules and commands
├── SKILL.md                    # skill entry point: CLI usage and SOP
├── references/
│   ├── api.md                  # BookStack REST API facts (auth, listing params, 16 resources, permissions)
│   └── cli.md                  # Full CLI contract (argv grammar, I/O, exit codes, retries, examples)
├── scripts/
│   └── bookstack-api-cli.py    # Single-file CLI, stdlib-only
└── tests/                      # Black-box unittest suite (stdlib only) + cli_harness.py
```

## Installation

Installation means placing this skill directory (repo path `skills/bookstack/`, i.e. the directory containing this file) into your platform's skills directory. Two methods: **copy** or **symlink**:

- **Copy** — independent from the repo after install, unaffected by later updates
- **Symlink** — multiple platforms share the same skill, update with a single `git pull` in the repo

### 1. Prerequisites

- `uv` (recommended) or any Python 3 standard library runtime — no third-party packages required
- Network access to the target BookStack instance
- A BookStack API token (see [Getting API credentials](#getting-api-credentials) below; the secret is shown only once)

### 2. Get the skill

Skip if already cloned; all commands below run from the **repo root**:

```bash
git clone https://github.com/a-lang/agent-skills
cd agent-skills
```

### 3. Install (copy or symlink)

```bash
# Copy (e.g. to your OpenCode user directory)
cp -r skills/bookstack ~/.config/opencode/skills/

# Or symlink (e.g. to a Claude Code project directory)
ln -s "$PWD/skills/bookstack" .claude/skills/bookstack
```

### Platform install locations

| Platform | Personal (global) | Project |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenCode | `~/.config/opencode/skills/` | `.opencode/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` |
| GitHub Copilot / VS Code | `~/.copilot/skills/` | `.github/skills/` |
| Codex | `~/.codex/skills/` | `.codex/skills/` |
| Open standard (multi-platform) | `~/.agents/skills/` | `.agents/skills/` |

> Cursor, Copilot and Codex are also compatible with the `.claude/skills/` location; `~/.agents/skills/` is the emerging cross-platform location scanned by most platforms.

### 4. Command-line install (alternative)

Cross-platform tool (skills.sh ecosystem, auto-detects installed agents, installs via symlink; use `--skill bookstack` for this skill only, `-a {agent}` for a specific platform, `-y` to skip confirmation):

```bash
# Project mode (default): install into the current project (e.g. .claude/skills/), shareable via git
npx skills add https://github.com/a-lang/agent-skills --skill bookstack

# Global mode (-g): install into the user directory (e.g. ~/.claude/skills/), available across projects
npx skills add https://github.com/a-lang/agent-skills --skill bookstack -g
```

### 5. Verify installation

Run from the skill directory to confirm the runtime works:

```bash
uv run python3 scripts/bookstack-api-cli.py --help   # prints usage to stdout, exits 0
uv run python3 scripts/bookstack-api-cli.py auth status  # offline env check, no HTTP
```

Without `uv`, bare `python3` works identically (stdlib-only, no install step).

## Getting API credentials

The CLI has no login command and accepts no credential flags. All three values come from the BookStack Web UI and are passed only via environment variables.

### 1. What you need

- `BOOKSTACK_URL` — base URL of your instance, e.g. `https://wiki.example.com` (no trailing `/api`).
- `BOOKSTACK_TOKEN_ID` and `BOOKSTACK_TOKEN_SECRET` — issued as a pair when you create an API token.
- Your user must have the **Access System API** permission on at least one assigned role. Without it, the API Tokens UI is hidden and API calls return `403`. Content accessed via the API is further limited by that user's normal view/edit roles.

> Least privilege: create a dedicated user/role for the agent with only **Access System API** plus the content permissions it actually needs (e.g. view/update on specific books), and set a short token expiry; the token can do everything that user can do, so avoid reusing an admin token.

### 2. Create a token (Web UI)

Tokens can only be created in the browser; the CLI cannot create them:

1. Log in to your BookStack instance in the browser.
2. For your own token: click your avatar (top-right) → **Profile** / **My Account** → find the **API Tokens** section. For another user (as admin): **Settings → Users → Edit user** → **API Tokens**.
3. Choose **Create Token**, enter a descriptive name (e.g. `agent-cli`) and an expiry date, then **Save**.
4. The next screen shows a **Token ID** and a **Token Secret** immediately. Copy both now — the secret is hashed in the database and **shown only once**. If you lose it, delete the token and create a new one.

### 3. Configure the CLI

```bash
export BOOKSTACK_URL="https://wiki.example.com"
export BOOKSTACK_TOKEN_ID="<token-id>"
export BOOKSTACK_TOKEN_SECRET="<token-secret>"
```

The CLI keeps no local state: there is no session file and no logout command — `unset` the variables to log out. Never put the secret in argv, files, or logs.

### 4. Verify

```bash
CLI="uv run python3 scripts/bookstack-api-cli.py"
$CLI auth status   # offline check, no HTTP: {"ready": true, "missing": []}
$CLI auth check    # live check: GET /api/system, prints system JSON on success
```

If `auth check` fails: missing/unset variables or a malformed header → stderr JSON, exit `3` without sending a request; `401` means the token is missing or malformed; `403` means the token is expired or the user lacks the **Access System API** permission. When already logged in via the browser, you can also open `/api/docs` on the instance to browse live endpoint docs.

## Usage

Once installed, just tell the AI what to do in natural language, for example:

> Search the wiki for "release notes" and create a page under chapter 12

The AI follows the `SKILL.md` SOP. Core commands (run from the skill directory):

```bash
CLI="uv run python3 scripts/bookstack-api-cli.py"

# Credential setup (env-only, never in argv or files)
export BOOKSTACK_URL="https://wiki.example.com"
export BOOKSTACK_TOKEN_ID="..."
export BOOKSTACK_TOKEN_SECRET="..."

$CLI auth status   # offline check: {"ready": bool, "missing": [...]}
$CLI auth check    # live check against GET /api/system

# Typical flow: Page authoring chain
$CLI search all "release notes" | jq '.data[].type'
$CLI chapters create --book-id 3 --name "Release" | jq -r '.id'
$CLI pages create --chapter-id 12 --name "v1.0" --markdown @doc.md | jq -r '.id'
$CLI pages update 42 --markdown @doc.md --changelog "sync docs"
$CLI pages export 42 --format markdown -o verify.md
```

When unsure about flags, ask the CLI first: `<resource> --help` and `<resource> <action> --help` are generated from the command spec table and never diverge from actual parsing. See `SKILL.md` for the full SOP.

### Resources and actions

| Resource | Actions | Notes |
|---|---|---|
| `auth` | `status` `check` | `status` is offline; `check` validates via `GET /api/system` |
| `pages` | `list` `create` `read` `update` `delete` `export` | `--book-id`/`--chapter-id` and `--html`/`--markdown` are each either/or |
| `chapters` | `list` `create` `read` `update` `delete` `export` | create requires `--book-id` and `--name` |
| `books` | `list` `create` `read` `update` `delete` `export` | `--image @cover.png` uses multipart; delete moves to Recycle Bin |
| `shelves` | `list` `create` `read` `update` `delete` | `--books 1,2,3` replaces the entire ordering |
| `attachments` | `list` `create` `read` `update` `delete` | `--file @x` (multipart) or `--link URL` (JSON) |
| `comments` | `list` `create` `read` `update` `delete` | create requires `--page-id` and `--html` |
| `image-gallery` | `list` `create` `read` `data` `url-data` `update` `delete` | `data` streams the original image |
| `imports` | `upload` `run` `read` `list` `delete` | two-phase: `upload <zip>`, then `run <id>` |
| `recycle-bin` | `list` `restore` `destroy` | `destroy` requires `--yes`, irreversible |
| `roles` | `list` `create` `read` `update` `delete` | `--permissions` replaces the whole set |
| `users` | `list` `create` `read` `update` `delete` | `delete` requires `--yes` |
| `search` | `all` `book` `chapter` | paginate with `--page`/`--count` (not offset) |
| `tags` | `names` `values` | filter supports only `name`/`value` |
| `system` | (no actions) | `GET /api/system` for version/base_url |
| `audit-log` | `list` | requires manage-users and manage-settings |
| `content-permissions` | `read` `update` | `<type>` is page/book/chapter/bookshelf; full overwrite |

Plus `docs` (defaults to `GET /api/docs.json`; `--html` switches to `/api/docs`). For complete flags per action, `<resource> <action> --help` is the source of truth.

### I/O and exit codes

- 2xx: stdout passes the API response bytes through unchanged (plus one `\n` if missing); 204 produces no output.
- Non-2xx: stdout stays empty; stderr prints the API error JSON unchanged.
- Streaming endpoints (`export`, `image-gallery data`): raw bytes to stdout, or to file with `-o FILE` (stdout then prints `{"saved_to": "<path>"}`).

| Exit code | Meaning |
|---|---|
| 0 | Success (2xx, including 204) |
| 2 | Usage/argument error |
| 3 | Auth/permission (401, 403, missing env vars) |
| 4 | Not found (404) |
| 5 | Client error (422, other 4xx such as 400, 409) |
| 6 | Rate-limit retries exhausted (429) |
| 7 | Network/timeout/TLS |
| 8 | Server error (5xx) |

Only 429 is retried (1s/2s/4s backoff, max 3 retries); all other errors fail fast. No automatic pagination — the agent loops with `--count`/`--offset` using the response's `total`. Timeout is fixed at 30s; TLS verification is always on.

## Development

See `AGENTS.md` for rules (table-driven extension, single transport seam, contract consistency, zero local state, TDD). Quick commands from the skill directory:

```bash
# Full test suite (stdlib unittest, zero dependencies)
uv run python3 -m unittest discover -s tests -p "test_*.py"

# Single module
uv run python3 -m unittest test_exit_codes
```
