# BookStack REST API Reference

> Primary sources: the official API docs <https://demo.bookstackapp.com/api/docs> (auto-generated per instance version),
> the instance's `/api/docs.json`, and the source code <https://codeberg.org/bookstack/bookstack> (GitHub is a mirror).
> Version differences are governed by the target instance's `GET /api/system` and `GET /api/docs.json`.

## Authentication

- A user needs the **Access System API** permission on any role.
- API Tokens can only be created in the Web UI (profile → API Tokens); the Token Secret is shown only once,
  and the DB stores a hash.
- Request header: `Authorization: Token <token_id>:<token_secret>`.
  It must start with `Token ` and contain `:`, otherwise 401; the message when the token is missing is
  `No authorization token found on the request`.
- An expired token or lack of AccessApi permission → 403.
- Browser session authentication only allows GET; the CLI always uses the Token header, never session/Basic.

## Request format

- Accepts `application/json`, `application/x-www-form-urlencoded`, and `multipart/form-data`.
- Form formats only support POST; PUT/DELETE require the `_method` workaround (the CLI's multipart update handles this automatically).
- Responses are always JSON, except file endpoints (export, image data stream).
- Endpoints that must be multipart: books image, attachments file, image-gallery, imports.

## Common listing parameters

List responses are always `{"data": [...], "total": N}`.

| Parameter | Description | Example |
|---|---|---|
| `count` | number of items returned (default 100, max 500) | `?count=50` |
| `offset` | number of items to skip (default 0) | `?offset=100` |
| `sort` | sort field; `+`/`-` prefixes mean ascending/descending | `?sort=-created_at` |
| `filter[<field>]` | equals filter | `?filter[id]=5` |
| `filter[<field>:<op>]` | operators `eq` (default)/`ne`/`gt`/`lt`/`gte`/`lte`/`like` | `?filter[name:like]=%cat%` |

- sort/filter fields must be on the server's allowlist, otherwise they fall back to defaults; some endpoints
  restrict filter fields (tags only `name`/`value`).
- The `search` endpoint differs: `query` (required), `page` (min 1), `count` (max 100);
  offset/sort/filter are not supported. Search syntax matches the Web UI (including `{type:...}`).

## Errors and rate limiting

- Error format: `{"error": {"code": <http code>, "message": ...}}`;
  `message` may be translated by the system language, and the CLI passes it through unchanged.
- Common mappings: 401 (missing/malformed token), 403 (permission/expired token), 404 (not visible or does not exist),
  422 (Laravel validation failure).
- The default rate limit is 180 requests/min (configurable via `API_REQUESTS_PER_MIN`); exceeding it returns 429
  `Too Many Attempts.`; the web server/firewall may impose other limits as well.
- The server is the sole authority for field validation; the CLI only performs local usage and body-source checks.

## Resource endpoints

All path prefixes are `/api`.

### Pages

| Method | Path | Action |
|---|---|---|
| GET | `/api/pages` | list |
| POST | `/api/pages` | create |
| GET | `/api/pages/{id}` | read (includes comments tree) |
| PUT | `/api/pages/{id}` | update (providing a parent id moves it) |
| DELETE | `/api/pages/{id}` | delete (moves to Recycle Bin) |
| GET | `/api/pages/{id}/export/{html,pdf,plaintext,markdown,zip}` | export |

- create body: `book_id`/`chapter_id` either/or (required_without), `name` (required, max:255),
  `html`/`markdown` either/or (required_without), `tags`, `priority`, `changelog` (min:1, max:180).
- update: all the same fields are optional; providing `book_id`/`chapter_id` moves the page.
- HTML must remain a flat, single-level plain HTML block; base64 data URI images are extracted by the server into gallery images.
- Page body images have no dedicated endpoint; use image-gallery/attachments.

### Chapters

| Method | Path | Action |
|---|---|---|
| GET | `/api/chapters` | list |
| POST | `/api/chapters` | create |
| GET | `/api/chapters/{id}` | read (includes pages list) |
| PUT | `/api/chapters/{id}` | update (can move) |
| DELETE | `/api/chapters/{id}` | delete |
| GET | `/api/chapters/{id}/export/{html,pdf,plaintext,markdown,zip}` | export |

- create body: `book_id` (required), `name` (required, max:255), `description` (max:1900),
  `description_html` (max:2000), `tags`, `priority`, `default_template_id` (nullable).
- update: same fields optional; providing `book_id` moves the chapter.

### Books

| Method | Path | Action |
|---|---|---|
| GET | `/api/books` | list |
| POST | `/api/books` | create |
| GET | `/api/books/{id}` | read (includes contents tree, shelves) |
| PUT | `/api/books/{id}` | update |
| DELETE | `/api/books/{id}` | delete (moves to Recycle Bin) |
| GET | `/api/books/{id}/export/{html,pdf,plaintext,markdown,zip}` | export |

- create/update body: `name` (required on create), `description`, `description_html`, `tags`,
  `image` (nullable file, jpeg/png/gif/webp/avif, max:50000 KB, requires multipart, `null` removes the cover),
  `default_template_id`.

### Shelves (Bookshelves)

| Method | Path | Action |
|---|---|---|
| GET | `/api/shelves` | list |
| POST | `/api/shelves` | create |
| GET | `/api/shelves/{id}` | read (includes books) |
| PUT | `/api/shelves/{id}` | update (`books` array overwrites the ordering) |
| DELETE | `/api/shelves/{id}` | delete (moves to Recycle Bin) |

- create/update body: `name` (required on create), `description`, `description_html`,
  `books` (array, assigned/overwritten in order), `tags`, `image` (file, rules same as books). No export endpoint.

### Attachments

| Method | Path | Action |
|---|---|---|
| GET | `/api/attachments` | list (`external` distinguishes links/files) |
| POST | `/api/attachments` | create (files require multipart) |
| GET | `/api/attachments/{id}` | read (file `content` is base64) |
| PUT | `/api/attachments/{id}` | update |
| DELETE | `/api/attachments/{id}` | delete |

- create body: `name` (required, min:1, max:255), `uploaded_to` (required, page id),
  `file`/`link` either/or (required_without; link min:1, max:2000, safe_url).
- Creating file attachments requires `AttachmentCreateAll` and PageUpdate permission on that page.

### Comments

| Method | Path | Action |
|---|---|---|
| GET | `/api/comments` | list |
| POST | `/api/comments` | create |
| GET | `/api/comments/{id}` | read (includes direct replies) |
| PUT | `/api/comments/{id}` | update (html/archived) |
| DELETE | `/api/comments/{id}` | delete |

- create body: `page_id` (required), `html` (required), `reply_to` (nullable, the `local_id` of the
  comment being replied to), `content_ref`.
- update: `html`, `archived` (boolean); only top-level comments can be archived/unarchived.

### Content Permissions

| Method | Path | Action |
|---|---|---|
| GET | `/api/content-permissions/{contentType}/{contentId}` | read |
| PUT | `/api/content-permissions/{contentType}/{contentId}` | update |

- `contentType` is one of `page`/`book`/`chapter`/`bookshelf`; only that item's overrides are returned,
  and the fallback may be `null`.
- update body: `owner_id`, `role_permissions` (array, each with `role_id`/`view`/`create`/
  `update`/`delete`), `fallback_permissions` (`inheriting`; when `inheriting=false`, the four
  permission fields are required).
- Passing an empty `role_permissions` clears it; omit any block you do not want to update
  (full overwrite, no deep merge).

### Image Gallery

| Method | Path | Action |
|---|---|---|
| GET | `/api/image-gallery` | list (gallery + drawio) |
| POST | `/api/image-gallery` | create (multipart) |
| GET | `/api/image-gallery/url/data?url=` | url-data (streams by BookStack image URL) |
| GET | `/api/image-gallery/{id}` | read (includes thumbs, suggested HTML/Markdown) |
| GET | `/api/image-gallery/{id}/data` | data (streams original image) |
| PUT | `/api/image-gallery/{id}` | update (rename/replace file) |
| DELETE | `/api/image-gallery/{id}` | delete (does not check references; leaves broken images) |

- create body: `type` (required, `gallery`/`drawio`), `uploaded_to` (required, page id),
  `image` (required file, max:50000 KB), `name` (optional; filename is used if omitted).

### Imports (ZIP import)

| Method | Path | Action |
|---|---|---|
| GET | `/api/imports` | list |
| POST | `/api/imports` | upload (multipart ZIP upload; stored for later run only) |
| GET | `/api/imports/{id}` | read (includes `details`) |
| POST | `/api/imports/{id}` | run (executes the import) |
| DELETE | `/api/imports/{id}` | delete |

- upload body: `file` (required file, max:50000 KB), must be multipart.
- run body: `parent_type` (`book`/`chapter`), `parent_id` (int).
- All endpoints require the **content-import** permission.

### Recycle Bin

| Method | Path | Action |
|---|---|---|
| GET | `/api/recycle-bin` | list (top-level, `deletable` carries relations) |
| PUT | `/api/recycle-bin/{deletionId}` | restore (returns `restore_count`) |
| DELETE | `/api/recycle-bin/{deletionId}` | destroy (permanent deletion) |

- Requires both manage system settings and manage permissions.
- The list id is the `deletionId` (recycle bin item id), not the original content id; destroy is irreversible.

### Roles

| Method | Path | Action |
|---|---|---|
| GET | `/api/roles` | list |
| POST | `/api/roles` | create |
| GET | `/api/roles/{id}` | read |
| PUT | `/api/roles/{id}` | update |
| DELETE | `/api/roles/{id}` | delete |

- Requires manage roles permission.
- create/update body: `display_name` (required on create, min:3, max:180), `description` (max:180),
  `mfa_enforced`, `external_auth_id`, `permissions` (string array; passing an empty array on update clears it).
- Example permission names: `book-delete-all`, `book-update-all`, `book-view-all`, `restrictions-manage-all`.

### Search

| Method | Path | Action |
|---|---|---|
| GET | `/api/search?query=` | all (shelves/books/chapters/pages) |
| GET | `/api/search/book/{id}?query=` | book (that book's chapters/pages) |
| GET | `/api/search/chapter/{id}?query=` | chapter (that chapter's pages) |

- Each response item has `type` (`bookshelf`/`book`/`chapter`/`page`) that can route to the corresponding
  resource read; `preview_html` is the highlighted HTML.

### System

| Method | Path | Action |
|---|---|---|
| GET | `/api/system` | instance information |

- The response has `version`, `instance_id`, `app_name`, `app_logo`, `base_url`; used for connectivity and version probing.

### Tags

| Method | Path | Action |
|---|---|---|
| GET | `/api/tags/names` | list names (filter only `name`) |
| GET | `/api/tags/values-for-name?name=` | list values (filter only `value`) |

- The response includes `usages`, `page_count`, `chapter_count`, `book_count`, `shelf_count`.

### Users

| Method | Path | Action |
|---|---|---|
| GET | `/api/users` | list |
| POST | `/api/users` | create |
| GET | `/api/users/{id}` | read |
| PUT | `/api/users/{id}` | update |
| DELETE | `/api/users/{id}` | delete (may take `migrate_ownership_id`) |

- Requires manage users permission.
- create body: `name` (required, max:100), `email` (required, unique), `external_auth_id`,
  `language` (max:15), `password` (min:8), `roles` (integer array), `send_invite` (boolean).
- update: same fields optional, no `send_invite`; delete's `migrate_ownership_id` transfers content first.

### Audit Log

| Method | Path | Action |
|---|---|---|
| GET | `/api/audit-log` | list (supports standard listing parameters) |

- Requires both manage-users and manage-settings permissions; `loggable_type` covers page/book/bookshelf/
  chapter.

### Docs

| Method | Path | Action |
|---|---|---|
| GET | `/api` | 302 redirect to `/api/docs` |
| GET | `/api/docs` | API docs page (HTML) |
| GET | `/api/docs/download?format=json` | download docs (HTML/JSON) |
| GET | `/api/docs.json` | docs JSON (directly usable with `jq`) |

- Use `/api/docs.json` to inventory the endpoints actually supported by the instance.

## General notes

- **update is partial**: only provided fields are updated; but array fields are overwritten when provided
  (shelves `books`, roles `permissions`, content-permissions `role_permissions`).
- **DELETE is not necessarily permanent**: pages/chapters/books/shelves go to the Recycle Bin;
  only recycle-bin destroy is permanent.
- **Exports require the content-export permission** (403 maps to exit 3).
- **Content safety**: a page's `html`/`raw_html` comes from user input, is not guaranteed safe, and must not
  be rendered directly; `pages/{id}/export/plaintext` and `markdown` are the preferred paths for agents
  to consume content safely.
- **File size limits** are mostly 50000 KB (~50 MB), determined by the server; the CLI does no client-side pre-check.
- **The API has no URL version** (no `/v1`); older versions may lack endpoints (such as imports); defer to
  the instance's docs.json.
- Tokens can only be created via the Web UI; the CLI provides no credential file or credential flags.
