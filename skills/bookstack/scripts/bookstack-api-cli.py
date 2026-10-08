#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bookstack-api-cli.py — agent-first BookStack REST thin CLI (stdlib-only).

Grammar:
    bookstack-api-cli.py <resource> <action> [args] [flags]
    bookstack-api-cli.py -auth login|status|logout
    bookstack-api-cli.py --help

The single seam is the module-level ``transport(request)`` function: it takes
a complete request (method, url, headers, body) and returns
``(status, headers, body)``. Tests replace it with a recording fake.
"""

import json
import mimetypes
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import NamedTuple, Optional

ENV_URL = "BOOKSTACK_URL"
ENV_TOKEN_ID = "BOOKSTACK_TOKEN_ID"
ENV_TOKEN_SECRET = "BOOKSTACK_TOKEN_SECRET"
ENV_NAMES = (ENV_URL, ENV_TOKEN_ID, ENV_TOKEN_SECRET)

RESOURCE_ORDER = (
    "pages",
    "chapters",
    "books",
    "shelves",
    "attachments",
    "comments",
    "image-gallery",
    "imports",
    "recycle-bin",
    "roles",
    "users",
    "search",
    "tags",
    "system",
    "audit-log",
    "content-permissions",
)

USAGE_LINE = "usage: bookstack-api-cli.py <resource> <action> [args] [flags]"
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
BACKOFF_SECONDS = (1, 2, 4)

# WAFs block urllib's default UA (Python-urllib/x.y) with 403/1010.
# Version is hardcoded for now; aligning it with the SKILL version strategy is TBD.
USER_AGENT = "bookstack-api-cli/1.0"

STRING = "STRING"
INTEGER = "INTEGER"
INTEGER_LIST = "INTEGER_LIST"
STRING_LIST = "STRING_LIST"
JSON_VALUE = "JSON"
CONTENT = "CONTENT"
FILE = "FILE"
BOOLEAN = "BOOLEAN"

QUERY_FIELDS = (
    ("count", "count", INTEGER),
    ("offset", "offset", INTEGER),
    ("sort", "sort", STRING),
)

SEARCH_QUERY_FIELDS = (
    ("page", "page", INTEGER),
    ("count", "count", INTEGER),
)

EXPORT_FORMATS = ("html", "pdf", "plaintext", "markdown", "zip")

PAGE_BODY = (
    {"flag": "name", "key": "name", "kind": STRING},
    {"flag": "book-id", "key": "book_id", "kind": INTEGER, "group": "parent"},
    {"flag": "chapter-id", "key": "chapter_id", "kind": INTEGER, "group": "parent"},
    {"flag": "html", "key": "html", "kind": CONTENT, "group": "content"},
    {"flag": "markdown", "key": "markdown", "kind": CONTENT, "group": "content"},
    {"flag": "tags", "key": "tags", "kind": JSON_VALUE},
    {"flag": "priority", "key": "priority", "kind": INTEGER},
    {"flag": "changelog", "key": "changelog", "kind": STRING},
)

CHAPTER_BODY = (
    {"flag": "book-id", "key": "book_id", "kind": INTEGER},
    {"flag": "name", "key": "name", "kind": STRING},
    {"flag": "description", "key": "description", "kind": CONTENT},
    {"flag": "description-html", "key": "description_html", "kind": CONTENT},
    {"flag": "tags", "key": "tags", "kind": JSON_VALUE},
    {"flag": "priority", "key": "priority", "kind": INTEGER},
    {"flag": "default-template-id", "key": "default_template_id", "kind": INTEGER},
)

BOOK_BODY = (
    {"flag": "name", "key": "name", "kind": STRING},
    {"flag": "description", "key": "description", "kind": CONTENT},
    {"flag": "description-html", "key": "description_html", "kind": CONTENT},
    {"flag": "tags", "key": "tags", "kind": JSON_VALUE},
    {"flag": "default-template-id", "key": "default_template_id", "kind": INTEGER},
    {"flag": "image", "key": "image", "kind": FILE},
)

SHELF_BODY = (
    {"flag": "name", "key": "name", "kind": STRING},
    {"flag": "description", "key": "description", "kind": CONTENT},
    {"flag": "description-html", "key": "description_html", "kind": CONTENT},
    {"flag": "books", "key": "books", "kind": INTEGER_LIST},
    {"flag": "tags", "key": "tags", "kind": JSON_VALUE},
    {"flag": "image", "key": "image", "kind": FILE},
)

ATTACHMENT_BODY = (
    {"flag": "name", "key": "name", "kind": STRING},
    {"flag": "uploaded-to", "key": "uploaded_to", "kind": INTEGER},
    {"flag": "file", "key": "file", "kind": FILE, "group": "source"},
    {"flag": "link", "key": "link", "kind": STRING, "group": "source"},
)

IMAGE_GALLERY_CREATE_BODY = (
    {"flag": "type", "key": "type", "kind": STRING},
    {"flag": "uploaded-to", "key": "uploaded_to", "kind": INTEGER},
    {"flag": "image", "key": "image", "kind": FILE},
    {"flag": "name", "key": "name", "kind": STRING},
)

IMAGE_GALLERY_UPDATE_BODY = (
    {"flag": "name", "key": "name", "kind": STRING},
    {"flag": "image", "key": "image", "kind": FILE},
)

COMMENT_CREATE_BODY = (
    {"flag": "page-id", "key": "page_id", "kind": INTEGER},
    {"flag": "html", "key": "html", "kind": CONTENT},
    {"flag": "reply-to", "key": "reply_to", "kind": INTEGER},
    {"flag": "content-ref", "key": "content_ref", "kind": STRING},
)

COMMENT_UPDATE_BODY = (
    {"flag": "html", "key": "html", "kind": CONTENT},
    {"flag": "archived", "key": "archived", "kind": BOOLEAN},
)

CONTENT_PERMISSION_TYPES = ("page", "book", "chapter", "bookshelf")

CONTENT_PERMISSIONS_BODY = (
    {"flag": "owner-id", "key": "owner_id", "kind": INTEGER},
    {"flag": "role-permissions", "key": "role_permissions", "kind": JSON_VALUE},
    {"flag": "fallback-permissions", "key": "fallback_permissions", "kind": JSON_VALUE},
)

IMPORT_RUN_BODY = (
    {"flag": "parent-type", "key": "parent_type", "kind": STRING},
    {"flag": "parent-id", "key": "parent_id", "kind": INTEGER},
)

ROLE_BODY = (
    {"flag": "display-name", "key": "display_name", "kind": STRING},
    {"flag": "description", "key": "description", "kind": STRING},
    {"flag": "mfa-enforced", "key": "mfa_enforced", "kind": BOOLEAN},
    {"flag": "external-auth-id", "key": "external_auth_id", "kind": STRING},
    {"flag": "permissions", "key": "permissions", "kind": STRING_LIST},
)

USER_CREATE_BODY = (
    {"flag": "name", "key": "name", "kind": STRING},
    {"flag": "email", "key": "email", "kind": STRING},
    {"flag": "password", "key": "password", "kind": STRING},
    {"flag": "send-invite", "key": "send_invite", "kind": BOOLEAN},
    {"flag": "roles", "key": "roles", "kind": INTEGER_LIST},
    {"flag": "language", "key": "language", "kind": STRING},
    {"flag": "external-auth-id", "key": "external_auth_id", "kind": STRING},
)

USER_UPDATE_BODY = (
    {"flag": "name", "key": "name", "kind": STRING},
    {"flag": "email", "key": "email", "kind": STRING},
    {"flag": "password", "key": "password", "kind": STRING},
    {"flag": "roles", "key": "roles", "kind": INTEGER_LIST},
    {"flag": "language", "key": "language", "kind": STRING},
    {"flag": "external-auth-id", "key": "external_auth_id", "kind": STRING},
)

USER_DELETE_QUERY = (
    {"flag": "migrate-ownership-id", "key": "migrate_ownership_id", "kind": INTEGER},
)

ACTIONS = {
    "pages": {
        "list": {
            "method": "GET",
            "path": "/api/pages",
            "query": True,
            "summary": "List pages",
        },
        "create": {
            "method": "POST",
            "path": "/api/pages",
            "summary": "Create a page",
            "json": True,
            "body": PAGE_BODY,
            "groups": {"parent": "exactly_one", "content": "exactly_one"},
        },
        "read": {
            "method": "GET",
            "path": "/api/pages/{id}",
            "arg": "id",
            "summary": "Read a page",
        },
        "update": {
            "method": "PUT",
            "path": "/api/pages/{id}",
            "arg": "id",
            "summary": "Update a page",
            "json": True,
            "body": PAGE_BODY,
            "groups": {"parent": "at_most_one", "content": "at_most_one"},
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/pages/{id}",
            "arg": "id",
            "summary": "Delete a page (moves it to the recycle bin)",
        },
        "export": {
            "method": "GET",
            "path": "/api/pages/{id}/export/{format}",
            "arg": "id",
            "format": EXPORT_FORMATS,
            "stream": True,
            "summary": "Export a page as html, pdf, plaintext, markdown or zip",
        },
    },
    "chapters": {
        "list": {
            "method": "GET",
            "path": "/api/chapters",
            "query": True,
            "summary": "List chapters",
        },
        "create": {
            "method": "POST",
            "path": "/api/chapters",
            "summary": "Create a chapter",
            "json": True,
            "body": CHAPTER_BODY,
            "required": ("book-id", "name"),
        },
        "read": {
            "method": "GET",
            "path": "/api/chapters/{id}",
            "arg": "id",
            "summary": "Read a chapter",
        },
        "update": {
            "method": "PUT",
            "path": "/api/chapters/{id}",
            "arg": "id",
            "summary": "Update a chapter",
            "json": True,
            "body": CHAPTER_BODY,
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/chapters/{id}",
            "arg": "id",
            "summary": "Delete a chapter (moves it to the recycle bin)",
        },
        "export": {
            "method": "GET",
            "path": "/api/chapters/{id}/export/{format}",
            "arg": "id",
            "format": EXPORT_FORMATS,
            "stream": True,
            "summary": "Export a chapter as html, pdf, plaintext, markdown or zip",
        },
    },
    "books": {
        "list": {
            "method": "GET",
            "path": "/api/books",
            "query": True,
            "summary": "List books",
        },
        "create": {
            "method": "POST",
            "path": "/api/books",
            "summary": "Create a book",
            "json": True,
            "body": BOOK_BODY,
            "required": ("name",),
        },
        "read": {
            "method": "GET",
            "path": "/api/books/{id}",
            "arg": "id",
            "summary": "Read a book (includes contents tree and shelves)",
        },
        "update": {
            "method": "PUT",
            "path": "/api/books/{id}",
            "arg": "id",
            "summary": "Update a book",
            "json": True,
            "body": BOOK_BODY,
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/books/{id}",
            "arg": "id",
            "summary": "Delete a book (moves it to the recycle bin)",
        },
        "export": {
            "method": "GET",
            "path": "/api/books/{id}/export/{format}",
            "arg": "id",
            "format": EXPORT_FORMATS,
            "stream": True,
            "summary": "Export a book as html, pdf, plaintext, markdown or zip",
        },
    },
    "shelves": {
        "list": {
            "method": "GET",
            "path": "/api/shelves",
            "query": True,
            "summary": "List shelves",
        },
        "create": {
            "method": "POST",
            "path": "/api/shelves",
            "summary": "Create a shelf",
            "json": True,
            "body": SHELF_BODY,
            "required": ("name",),
        },
        "read": {
            "method": "GET",
            "path": "/api/shelves/{id}",
            "arg": "id",
            "summary": "Read a shelf (includes its books in order)",
        },
        "update": {
            "method": "PUT",
            "path": "/api/shelves/{id}",
            "arg": "id",
            "summary": "Update a shelf (--books replaces the whole order)",
            "json": True,
            "body": SHELF_BODY,
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/shelves/{id}",
            "arg": "id",
            "summary": "Delete a shelf (moves it to the recycle bin)",
        },
    },
    "attachments": {
        "list": {
            "method": "GET",
            "path": "/api/attachments",
            "query": True,
            "summary": "List attachments (the external field marks links)",
        },
        "create": {
            "method": "POST",
            "path": "/api/attachments",
            "summary": "Create a file (multipart) or link (JSON) attachment",
            "json": True,
            "body": ATTACHMENT_BODY,
            "required": ("name", "uploaded-to"),
            "groups": {"source": "exactly_one"},
        },
        "read": {
            "method": "GET",
            "path": "/api/attachments/{id}",
            "arg": "id",
            "summary": "Read an attachment (file content is base64, passed through)",
        },
        "update": {
            "method": "PUT",
            "path": "/api/attachments/{id}",
            "arg": "id",
            "summary": "Update an attachment",
            "json": True,
            "body": ATTACHMENT_BODY,
            "groups": {"source": "at_most_one"},
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/attachments/{id}",
            "arg": "id",
            "summary": "Delete an attachment",
        },
    },
    "image-gallery": {
        "list": {
            "method": "GET",
            "path": "/api/image-gallery",
            "query": True,
            "summary": "List gallery and drawio images",
        },
        "create": {
            "method": "POST",
            "path": "/api/image-gallery",
            "summary": "Create a gallery or drawio image (multipart upload)",
            "json": True,
            "body": IMAGE_GALLERY_CREATE_BODY,
            "required": ("type", "uploaded-to", "image"),
        },
        "read": {
            "method": "GET",
            "path": "/api/image-gallery/{id}",
            "arg": "id",
            "summary": (
                "Read an image (includes thumbs and suggested html/markdown snippets)"
            ),
        },
        "data": {
            "method": "GET",
            "path": "/api/image-gallery/{id}/data",
            "arg": "id",
            "stream": True,
            "summary": "Stream the raw image bytes",
        },
        "url-data": {
            "method": "GET",
            "path": "/api/image-gallery/url/data",
            "url_arg": True,
            "stream": True,
            "summary": "Stream the raw image bytes for a BookStack image URL",
        },
        "update": {
            "method": "PUT",
            "path": "/api/image-gallery/{id}",
            "arg": "id",
            "summary": "Update an image (rename and/or replace the file)",
            "json": True,
            "body": IMAGE_GALLERY_UPDATE_BODY,
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/image-gallery/{id}",
            "arg": "id",
            "summary": (
                "Delete an image (does not check references; pages embedding it "
                "will show broken images)"
            ),
        },
    },
    "imports": {
        "upload": {
            "method": "POST",
            "path": "/api/imports",
            "arg": "zip",
            "file_arg": "file",
            "summary": (
                "Upload a ZIP file for import (returns the pending import id "
                "to run afterwards)"
            ),
        },
        "run": {
            "method": "POST",
            "path": "/api/imports/{id}",
            "arg": "id",
            "summary": "Run an uploaded import at a parent book or chapter",
            "json": True,
            "body": IMPORT_RUN_BODY,
            "required_body": True,
        },
        "read": {
            "method": "GET",
            "path": "/api/imports/{id}",
            "arg": "id",
            "summary": "Read an import (includes its details structure)",
        },
        "list": {
            "method": "GET",
            "path": "/api/imports",
            "query": True,
            "summary": "List imports",
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/imports/{id}",
            "arg": "id",
            "summary": "Delete an uploaded import",
        },
    },
    "comments": {
        "list": {
            "method": "GET",
            "path": "/api/comments",
            "query": True,
            "summary": "List comments",
        },
        "create": {
            "method": "POST",
            "path": "/api/comments",
            "summary": "Create a comment (or reply via --reply-to local id)",
            "json": True,
            "body": COMMENT_CREATE_BODY,
            "required": ("page-id", "html"),
        },
        "read": {
            "method": "GET",
            "path": "/api/comments/{id}",
            "arg": "id",
            "summary": "Read a comment (includes direct replies)",
        },
        "update": {
            "method": "PUT",
            "path": "/api/comments/{id}",
            "arg": "id",
            "summary": (
                "Update a comment's html or archived flag "
                "(only top-level comments can be archived)"
            ),
            "json": True,
            "body": COMMENT_UPDATE_BODY,
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/comments/{id}",
            "arg": "id",
            "summary": "Delete a comment",
        },
    },
    "recycle-bin": {
        "list": {
            "method": "GET",
            "path": "/api/recycle-bin",
            "query": True,
            "summary": (
                "List deleted items (each with deletionId and the deletable relation)"
            ),
        },
        "restore": {
            "method": "PUT",
            "path": "/api/recycle-bin/{id}",
            "arg": "id",
            "arg_label": "deletionId",
            "summary": "Restore a deleted item (response includes restore_count)",
        },
        "destroy": {
            "method": "DELETE",
            "path": "/api/recycle-bin/{id}",
            "arg": "id",
            "arg_label": "deletionId",
            "requires_yes": True,
            "summary": "Permanently destroy a deleted item (irreversible; no dry-run)",
        },
    },
    "roles": {
        "list": {
            "method": "GET",
            "path": "/api/roles",
            "query": True,
            "summary": "List roles",
        },
        "create": {
            "method": "POST",
            "path": "/api/roles",
            "summary": "Create a role",
            "json": True,
            "body": ROLE_BODY,
            "required": ("display-name",),
        },
        "read": {
            "method": "GET",
            "path": "/api/roles/{id}",
            "arg": "id",
            "summary": "Read a role",
        },
        "update": {
            "method": "PUT",
            "path": "/api/roles/{id}",
            "arg": "id",
            "summary": (
                "Update a role; --permissions replaces the whole array, an "
                "empty value clears it (no deep merge)"
            ),
            "json": True,
            "body": ROLE_BODY,
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/roles/{id}",
            "arg": "id",
            "summary": "Delete a role",
        },
    },
    "users": {
        "list": {
            "method": "GET",
            "path": "/api/users",
            "query": True,
            "summary": "List users",
        },
        "create": {
            "method": "POST",
            "path": "/api/users",
            "summary": (
                "Create a user (set a password or send an invite; --roles "
                "takes comma-separated role ids)"
            ),
            "json": True,
            "body": USER_CREATE_BODY,
            "required": ("name", "email"),
        },
        "read": {
            "method": "GET",
            "path": "/api/users/{id}",
            "arg": "id",
            "summary": "Read a user",
        },
        "update": {
            "method": "PUT",
            "path": "/api/users/{id}",
            "arg": "id",
            "summary": "Update a user (send_invite is not accepted here)",
            "json": True,
            "body": USER_UPDATE_BODY,
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/users/{id}",
            "arg": "id",
            "requires_yes": True,
            "query_flags": USER_DELETE_QUERY,
            "summary": (
                "Delete a user (irreversible; --migrate-ownership-id N "
                "transfers their content to user N first)"
            ),
        },
    },
    "audit-log": {
        "list": {
            "method": "GET",
            "path": "/api/audit-log",
            "query": True,
            "summary": (
                "List audit log entries (requires a user with both "
                "manage-users and manage-settings permissions)"
            ),
        },
    },
    "search": {
        "all": {
            "method": "GET",
            "path": "/api/search",
            "page_query": True,
            "args": ("query",),
            "query_args": {"query": "query"},
            "allowed_filters": (),
            "summary": "Search shelves, books, chapters and pages",
        },
        "book": {
            "method": "GET",
            "path": "/api/search/book/{id}",
            "page_query": True,
            "args": ("id", "query"),
            "query_args": {"query": "query"},
            "allowed_filters": (),
            "summary": "Search chapters and pages within a book",
        },
        "chapter": {
            "method": "GET",
            "path": "/api/search/chapter/{id}",
            "page_query": True,
            "args": ("id", "query"),
            "query_args": {"query": "query"},
            "allowed_filters": (),
            "summary": "Search pages within a chapter",
        },
    },
    "content-permissions": {
        "read": {
            "method": "GET",
            "path": "/api/content-permissions/{type}/{id}",
            "args": ("type", "id"),
            "choices": {"type": CONTENT_PERMISSION_TYPES},
            "summary": (
                "Read the permission overrides for a page, book, chapter or "
                "bookshelf (fallback may be null)"
            ),
        },
        "update": {
            "method": "PUT",
            "path": "/api/content-permissions/{type}/{id}",
            "args": ("type", "id"),
            "choices": {"type": CONTENT_PERMISSION_TYPES},
            "summary": (
                "Replace the whole permission override block; an empty "
                "role_permissions array clears it (no deep merge)"
            ),
            "json": True,
            "body": CONTENT_PERMISSIONS_BODY,
        },
    },
    "tags": {
        "names": {
            "method": "GET",
            "path": "/api/tags/names",
            "query": True,
            "allowed_filters": ("name",),
            "summary": "List tag names with usage counts",
        },
        "values": {
            "method": "GET",
            "path": "/api/tags/values-for-name",
            "query": True,
            "allowed_filters": ("value",),
            "args": ("name",),
            "query_args": {"name": "name"},
            "summary": "List values used for a tag name",
        },
    },
}


class UsageError(Exception):
    pass


class NetworkError(Exception):
    pass


class Request(NamedTuple):
    method: str
    url: str
    headers: dict
    body: Optional[bytes]


def transport(request):
    url_request = urllib.request.Request(
        request.url, data=request.body, headers=request.headers, method=request.method
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(
            url_request, timeout=TIMEOUT_SECONDS, context=context
        ) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def missing_env():
    return [name for name in ENV_NAMES if not os.environ.get(name)]


def auth_header():
    return "Token %s:%s" % (os.environ[ENV_TOKEN_ID], os.environ[ENV_TOKEN_SECRET])


def base_headers():
    return {"Authorization": auth_header(), "User-Agent": USER_AGENT}


def api_url(path):
    return os.environ[ENV_URL].rstrip("/") + path


def error_json(message):
    payload = {"error": {"message": message}}
    return json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"


def exit_code_for(status):
    if status in (401, 403):
        return 3
    if status == 404:
        return 4
    if status == 422:
        return 5
    if status == 429:
        return 6
    if 400 <= status < 500:
        return 5
    if status >= 500:
        return 8
    return 2


def write_success(out, body):
    if not body:
        return
    out.write(body)
    if not body.endswith(b"\n"):
        out.write(b"\n")


def retry_delay(headers, fallback):
    for key in headers:
        if key.lower() == "retry-after":
            try:
                return max(0, int(str(headers[key]).strip()))
            except (TypeError, ValueError):
                return fallback
    return fallback


def request_with_retry(request, err):
    for attempt in range(MAX_RETRIES + 1):
        try:
            status, headers, body = transport(request)
        except (urllib.error.URLError, OSError) as error:
            raise NetworkError(error) from error
        if status != 429 or attempt == MAX_RETRIES:
            return status, headers, body
        delay = retry_delay(headers, BACKOFF_SECONDS[attempt])
        err.write(
            (
                "429 rate limited; retrying in %ss (attempt %d/%d)\n"
                % (delay, attempt + 1, MAX_RETRIES)
            ).encode("utf-8")
        )
        err.flush()
        time.sleep(delay)
    raise AssertionError("unreachable")


def execute(
    method,
    path,
    body,
    out,
    err,
    failure_code=None,
    stream=False,
    output_path=None,
    content_type=None,
):
    missing = missing_env()
    if missing:
        err.write(error_json("missing environment variables: " + ", ".join(missing)))
        return 3 if failure_code is None else failure_code
    headers = base_headers()
    if body is not None:
        headers["Content-Type"] = content_type or "application/json"
    request = Request(method, api_url(path), headers, body)
    try:
        status, _response_headers, response_body = request_with_retry(request, err)
    except NetworkError as error:
        err.write(error_json(str(error)))
        return 7 if failure_code is None else failure_code
    if 200 <= status < 300:
        if output_path is not None:
            try:
                with open(output_path, "wb") as handle:
                    handle.write(response_body)
            except OSError as error:
                err.write(error_json("cannot write %s: %s" % (output_path, error)))
                return 2
            summary = json.dumps({"saved_to": output_path}, ensure_ascii=False)
            out.write(summary.encode("utf-8") + b"\n")
        elif stream:
            out.write(response_body)
        else:
            write_success(out, response_body)
        return 0
    err.write(response_body)
    return exit_code_for(status) if failure_code is None else failure_code


def auth_status(out):
    missing = missing_env()
    payload = {"ready": not missing, "missing": missing}
    out.write(json.dumps(payload).encode("utf-8") + b"\n")
    return 0 if not missing else 3


def auth_login(out, err):
    return execute("GET", "/api/system", None, out, err, failure_code=3)


def auth_logout(out):
    payload = {
        "logged_out": True,
        "unset": list(ENV_NAMES),
        "message": "BookStack CLI stores no credentials; unset these environment variables to log out.",
    }
    out.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
    return 0


def auth_command(args, out, err):
    if not args or args[0] in ("--help", "-h"):
        out.write(auth_help().encode("utf-8"))
        return 0
    command = args[0]
    if command not in ("login", "status", "logout"):
        raise UsageError("unknown -auth command: %s" % command)
    if len(args) > 1:
        raise UsageError("unexpected argument for -auth %s: %s" % (command, args[1]))
    if command == "status":
        return auth_status(out)
    if command == "login":
        return auth_login(out, err)
    return auth_logout(out)


def auth_help():
    return (
        "usage: bookstack-api-cli.py -auth login|status|logout\n"
        "\n"
        "  login   verify env credentials against GET /api/system\n"
        "  status  offline credentials check: {\"ready\": bool, \"missing\": [...]}\n"
        "  logout  print hint for unsetting the credentials (no local state)\n"
    )


def metavar(field):
    return {
        "STRING": "TEXT",
        "INTEGER": "N",
        "INTEGER_LIST": "ID,...",
        "STRING_LIST": "A,B,...",
        "JSON": "JSON",
        "CONTENT": "TEXT",
        "FILE": "FILE",
        "BOOLEAN": "true|false",
    }[field["kind"]]


def body_usage(spec):
    fragments = []
    required = set(spec.get("required", ()))
    seen_groups = set()
    for field in spec.get("body", ()):
        group = field.get("group")
        if group:
            if group in seen_groups:
                continue
            seen_groups.add(group)
            members = [f for f in spec["body"] if f.get("group") == group]
            alternatives = " | ".join(
                "--%s %s" % (member["flag"], metavar(member)) for member in members
            )
            if spec.get("groups", {}).get(group) == "exactly_one":
                fragments.append("(%s)" % alternatives)
            else:
                fragments.append("[%s]" % alternatives)
        elif field["flag"] in required:
            fragments.append("--%s %s" % (field["flag"], metavar(field)))
        else:
            fragments.append("[--%s %s]" % (field["flag"], metavar(field)))
    return fragments


def action_usage(resource, action_name, spec):
    parts = ["bookstack-api-cli.py", resource, action_name]
    for arg in spec.get("args", ()):
        parts.append("<%s>" % arg)
    if spec.get("arg"):
        parts.append("<%s>" % spec.get("arg_label", spec["arg"]))
    if spec.get("page_query"):
        parts.extend(["[--page N]", "[--count N]"])
    elif spec.get("query"):
        parts.extend(["[--count N]", "[--offset N]", "[--sort FIELD]", "[--filter K=V]"])
    if spec.get("json"):
        parts.append("[--json @file|-]")
    parts.extend(body_usage(spec))
    for field in spec.get("query_flags", ()):
        parts.append("[--%s %s]" % (field["flag"], metavar(field)))
    if spec.get("requires_yes"):
        parts.append("--yes")
    if spec.get("format"):
        parts.append("--format %s" % "|".join(spec["format"]))
    if spec.get("url_arg"):
        parts.append("--url URL")
    if spec.get("format") or spec.get("stream"):
        parts.append("[-o FILE]")
    return " ".join(parts)


def action_help(resource, action_name, spec):
    lines = [
        "usage: %s" % action_usage(resource, action_name, spec),
        "",
        "%s %s: %s %s" % (resource, action_name, spec["method"], spec["path"]),
    ]
    if spec.get("summary"):
        lines.append(spec["summary"])
    if spec.get("requires_yes"):
        lines.extend(
            [
                "",
                "--yes : required to confirm; this operation is irreversible and",
                "there is no dry-run",
            ]
        )
    if spec.get("allowed_filters"):
        lines.extend(
            [
                "",
                "--filter keys allowed here: %s"
                % ", ".join(spec["allowed_filters"]),
            ]
        )
    if spec.get("choices"):
        for name, allowed in spec["choices"].items():
            lines.extend(
                ["", "<%s> allowed values: %s" % (name, ", ".join(allowed))]
            )
    if spec.get("json"):
        lines.extend(
            [
                "",
                "--json @file|- : whole JSON body; field flags override top-level keys",
                "content flags accept @file, otherwise the value is literal text",
            ]
        )
    if any(field["kind"] == FILE for field in spec.get("body", ())):
        file_flags = ", ".join(
            "--" + field["flag"]
            for field in spec.get("body", ())
            if field["kind"] == FILE
        )
        lines.extend(
            [
                "",
                "%s @file uploads a file and switches the whole request to" % file_flags,
                "multipart/form-data; pass null to clear the field (JSON null)",
            ]
        )
    if spec.get("file_arg"):
        lines.extend(
            [
                "",
                "<%s> is uploaded as a multipart/form-data field (%r)"
                % (spec.get("arg_label", spec["arg"]), spec["file_arg"]),
            ]
        )
    if spec.get("format") or spec.get("stream"):
        lines.append("")
        if spec.get("format"):
            lines.append("--format %s : required" % "|".join(spec["format"]))
        lines.extend(
            [
                "without -o, raw response bytes go to stdout unchanged (no newline added)",
                '-o FILE : write raw bytes to FILE; stdout prints {"saved_to": "<path>"}',
            ]
        )
    return "\n".join(lines) + "\n"


def resource_help(resource):
    lines = [
        "usage: bookstack-api-cli.py %s <action> [args] [flags]" % resource,
        "",
        "%s:" % resource,
    ]
    if resource == "system":
        lines.append("  GET /api/system")
        return "\n".join(lines) + "\n"
    actions = ACTIONS.get(resource, {})
    if not actions:
        lines.append("  no actions available in this build")
        return "\n".join(lines) + "\n"
    lines.append("actions:")
    for action_name, spec in actions.items():
        lines.append("  %-8s %s %s" % (action_name, spec["method"], spec["path"]))
        lines.append("           %s" % action_usage(resource, action_name, spec))
    return "\n".join(lines) + "\n"


def top_help():
    lines = [
        USAGE_LINE,
        "       bookstack-api-cli.py -auth login|status|logout",
        "       bookstack-api-cli.py --help",
        "",
        "BookStack REST API thin CLI: 2xx responses are written to stdout as-is,",
        "non-2xx error JSON goes to stderr. Credentials come only from",
        "BOOKSTACK_URL, BOOKSTACK_TOKEN_ID and BOOKSTACK_TOKEN_SECRET.",
        "",
        "resources:",
    ]
    for resource in RESOURCE_ORDER:
        if resource == "system":
            lines.append("  %-20s GET /api/system" % resource)
        elif resource in ACTIONS and ACTIONS[resource]:
            lines.append(
                "  %-20s %s" % (resource, ", ".join(ACTIONS[resource]))
            )
        else:
            lines.append("  %-20s (not implemented yet)" % resource)
    lines.extend(
        [
            "",
            "commands:",
            "  %-20s %s" % ("docs", "GET /api/docs.json (--html for /api/docs)"),
            "  %-20s %s" % ("-auth", "login | status | logout"),
            "",
            "exit codes:",
            "  0  success (2xx, including 204)",
            "  2  usage / argument error",
            "  3  authentication or permission error (401, 403, missing env)",
            "  4  not found (404)",
            "  5  client error (422 validation and other unlisted 4xx)",
            "  6  rate limit retries exhausted (429)",
            "  7  network, timeout or TLS error",
            "  8  server error (5xx)",
            "",
            'Run "bookstack-api-cli.py <resource> --help" for details.',
        ]
    )
    return "\n".join(lines) + "\n"


def docs_help():
    return (
        "usage: bookstack-api-cli.py docs [--html]\n"
        "\n"
        "GET /api/docs.json (default) or /api/docs (--html)\n"
    )


def convert_value(value, kind, flag):
    if kind == INTEGER:
        try:
            return int(value)
        except ValueError:
            raise UsageError("--%s expects an integer: %r" % (flag, value))
    return value


def take_value(tokens, index, flag):
    if index + 1 >= len(tokens):
        raise UsageError("--%s requires a value" % flag)
    return tokens[index + 1], index + 2


def query_pairs(tokens, fields=QUERY_FIELDS, allowed_filters=None):
    positional = []
    pairs = []
    filters = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            positional.append(token)
            index += 1
            continue
        flag = token[2:]
        if flag == "filter":
            value, index = take_value(tokens, index, flag)
            filters.append(value)
            continue
        field = next((field for field in fields if field[0] == flag), None)
        if field is None:
            raise UsageError("unknown flag: %s" % token)
        value, index = take_value(tokens, index, flag)
        pairs.append((field[1], convert_value(value, field[2], flag)))
    for value in filters:
        if "=" not in value:
            raise UsageError("--filter must be k=v or k:op=v: %r" % value)
        key, filter_value = value.split("=", 1)
        if not key:
            raise UsageError("--filter must be k=v or k:op=v: %r" % value)
        if allowed_filters is not None and key.split(":", 1)[0] not in allowed_filters:
            raise UsageError(
                "--filter key %r is not allowed here (allowed: %s)"
                % (key, ", ".join(allowed_filters))
            )
        pairs.append(("filter[%s]" % key, filter_value))
    return positional, [(key, str(value)) for key, value in pairs]


def apply_positional_args(resource, action_name, spec, positional, pairs):
    expected = spec.get("args", ())
    if len(positional) != len(expected):
        if expected:
            raise UsageError(
                "%s %s requires %s"
                % (resource, action_name, " ".join("<%s>" % arg for arg in expected))
            )
        raise UsageError("unexpected argument: %s" % positional[0])
    values = dict(zip(expected, positional))
    for name, allowed in spec.get("choices", {}).items():
        if values.get(name) not in allowed:
            raise UsageError(
                "invalid <%s>: %r (choose from %s)"
                % (name, values.get(name), ", ".join(allowed))
            )
    query_args = spec.get("query_args", {})
    path = spec["path"]
    for name in expected:
        if name in query_args:
            pairs.append((query_args[name], values[name]))
        else:
            path = path.replace(
                "{%s}" % name, urllib.parse.quote(values[name], safe="")
            )
    return path, pairs


def read_text(value):
    if value.startswith("@"):
        try:
            with open(value[1:], "r", encoding="utf-8") as handle:
                return handle.read()
        except (OSError, UnicodeDecodeError) as error:
            raise UsageError("cannot read %s: %s" % (value[1:], error))
    return value


def read_json_source(value):
    if value == "-":
        return sys.stdin.buffer.read()
    if value.startswith("@"):
        try:
            with open(value[1:], "rb") as handle:
                return handle.read()
        except OSError as error:
            raise UsageError("cannot read %s: %s" % (value[1:], error))
    raise UsageError("--json expects @file or -")


class MultipartFile(NamedTuple):
    field: str
    filename: str
    content: bytes
    content_type: str


def read_file_source(path, key):
    try:
        with open(path, "rb") as handle:
            content = handle.read()
    except OSError as error:
        raise UsageError("cannot read %s: %s" % (path, error))
    guessed = mimetypes.guess_type(path)[0]
    return MultipartFile(
        key, os.path.basename(path), content, guessed or "application/octet-stream"
    )


def read_upload(value, key, flag):
    if not value.startswith("@") or len(value) == 1:
        raise UsageError("--%s expects @file (or null to clear)" % flag)
    return read_file_source(value[1:], key)


def form_scalar(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def form_pairs(body, prefix=None):
    """Flatten a JSON-shaped body into form field pairs using bracket notation."""
    if isinstance(body, dict):
        pairs = []
        for key, value in body.items():
            name = str(key) if prefix is None else "%s[%s]" % (prefix, key)
            pairs.extend(form_pairs(value, name))
        return pairs
    if isinstance(body, (list, tuple)):
        pairs = []
        for index, value in enumerate(body):
            pairs.extend(form_pairs(value, "%s[%d]" % (prefix, index)))
        return pairs
    return [(prefix, form_scalar(body))]


def header_safe(text):
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace('"', "%22")
        .replace("\r", "")
        .replace("\n", "")
    )


def encode_multipart(boundary, fields, files):
    marker = b"--" + boundary.encode("ascii")
    chunks = []
    for name, value in fields:
        chunks.append(marker)
        chunks.append(
            b'Content-Disposition: form-data; name="%s"'
            % header_safe(name).encode("utf-8")
        )
        chunks.append(b"")
        chunks.append(value.encode("utf-8"))
    for upload in files:
        chunks.append(marker)
        chunks.append(
            b'Content-Disposition: form-data; name="%s"; filename="%s"'
            % (
                header_safe(upload.field).encode("utf-8"),
                header_safe(upload.filename).encode("utf-8"),
            )
        )
        chunks.append(b"Content-Type: " + upload.content_type.encode("ascii"))
        chunks.append(b"")
        chunks.append(upload.content)
    chunks.append(marker + b"--")
    chunks.append(b"")
    return b"\r\n".join(chunks)


def build_multipart(body, files, spoof_method=None):
    boundary = "bookstack-" + uuid.uuid4().hex
    fields = []
    if spoof_method:
        fields.append(("_method", spoof_method))
    fields.extend(form_pairs(body))
    payload = encode_multipart(boundary, fields, [files[key] for key in files])
    return "multipart/form-data; boundary=%s" % boundary, payload


def convert_body_value(value, field, flag):
    kind = field["kind"]
    if kind == INTEGER:
        try:
            return int(value)
        except ValueError:
            raise UsageError("--%s expects an integer: %r" % (flag, value))
    if kind == INTEGER_LIST:
        if not value.strip():
            return []
        try:
            return [int(item.strip()) for item in value.split(",")]
        except ValueError:
            raise UsageError(
                "--%s expects comma-separated integer ids: %r" % (flag, value)
            )
    if kind == STRING_LIST:
        if not value.strip():
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    if kind == JSON_VALUE:
        try:
            return json.loads(value)
        except ValueError:
            raise UsageError("--%s expects JSON: %r" % (flag, value))
    if kind == BOOLEAN:
        if value not in ("true", "false"):
            raise UsageError("--%s expects true or false: %r" % (flag, value))
        return value == "true"
    if kind == CONTENT:
        return read_text(value)
    return value


def parse_query_flags(tokens, spec):
    declared = {field["flag"]: field for field in spec.get("query_flags", ())}
    if not declared:
        return tokens, []
    remaining = []
    pairs = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--") and token[2:] in declared:
            field = declared[token[2:]]
            value, index = take_value(tokens, index, field["flag"])
            pairs.append(
                (
                    field["key"],
                    str(convert_value(value, field["kind"], field["flag"])),
                )
            )
        else:
            remaining.append(token)
            index += 1
    return remaining, pairs


def parse_body_flags(tokens, spec):
    fields = {field["flag"]: field for field in spec.get("body", ())}
    positional = []
    values = {}
    files = {}
    json_source = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--"):
            flag = token[2:]
            if flag == "json" and spec.get("json"):
                value, index = take_value(tokens, index, flag)
                if json_source is not None:
                    raise UsageError("--json given more than once")
                json_source = value
                continue
            field = fields.get(flag)
            if field is None:
                raise UsageError("unknown flag: %s" % token)
            value, index = take_value(tokens, index, flag)
            if field["kind"] == FILE:
                if value == "null":
                    values[field["key"]] = None
                else:
                    files[field["key"]] = read_upload(value, field["key"], flag)
            else:
                values[field["key"]] = convert_body_value(value, field, flag)
        else:
            positional.append(token)
            index += 1
    return positional, json_source, values, files


def parse_stream_flags(tokens, spec):
    positional = []
    fmt = None
    output_path = None
    url = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--format" and spec.get("format"):
            if index + 1 >= len(tokens):
                raise UsageError("--format requires a value")
            if fmt is not None:
                raise UsageError("--format given more than once")
            fmt = tokens[index + 1]
            index += 2
        elif token == "--url" and spec.get("url_arg"):
            value, index = take_value(tokens, index, "url")
            if url is not None:
                raise UsageError("--url given more than once")
            url = value
        elif token == "-o":
            if index + 1 >= len(tokens):
                raise UsageError("-o requires a FILE")
            if output_path is not None:
                raise UsageError("-o given more than once")
            output_path = tokens[index + 1]
            index += 2
        elif token.startswith("-"):
            raise UsageError("unknown flag: %s" % token)
        else:
            positional.append(token)
            index += 1
    if spec.get("format"):
        if fmt is None:
            raise UsageError("export requires --format %s" % "|".join(spec["format"]))
        if fmt not in spec["format"]:
            raise UsageError(
                "invalid --format %r (choose from %s)"
                % (fmt, "|".join(spec["format"]))
            )
    if spec.get("url_arg") and url is None:
        raise UsageError("url-data requires --url URL")
    return positional, output_path, fmt, url


def build_body(json_source, values):
    body = {}
    if json_source is not None:
        try:
            parsed = json.loads(read_json_source(json_source))
        except ValueError as error:
            raise UsageError("invalid --json body: %s" % error)
        if not isinstance(parsed, dict):
            raise UsageError("--json body must be a JSON object")
        body.update(parsed)
    body.update(values)
    return body


def validate_groups(spec, body, files=()):
    fields = {field["flag"]: field for field in spec.get("body", ())}
    present_keys = set(body) | set(files)
    for flag in spec.get("required", ()):
        if fields[flag]["key"] not in present_keys:
            raise UsageError("--%s is required" % flag)
    for group, mode in spec.get("groups", {}).items():
        members = [field for field in spec["body"] if field.get("group") == group]
        present = [field for field in members if field["key"] in present_keys]
        names = ", ".join("--" + field["flag"] for field in members)
        if mode == "exactly_one" and len(present) != 1:
            raise UsageError("provide exactly one of: %s" % names)
        if mode == "at_most_one" and len(present) > 1:
            raise UsageError("provide at most one of: %s" % names)


def run_action(resource, args, out, err):
    actions = ACTIONS.get(resource, {})
    if len(args) < 2:
        raise UsageError("missing action for %s" % resource)
    if args[1] in ("--help", "-h"):
        out.write(resource_help(resource).encode("utf-8"))
        return 0
    action_name = args[1]
    if action_name not in actions:
        raise UsageError("unknown action for %s: %s" % (resource, action_name))
    spec = actions[action_name]
    if "--help" in args[2:] or "-h" in args[2:]:
        out.write(action_help(resource, action_name, spec).encode("utf-8"))
        return 0
    rest = args[2:]
    if spec.get("requires_yes"):
        if "--yes" not in rest:
            err.write(
                error_json(
                    "%s %s requires --yes: this operation is irreversible and has no dry-run"
                    % (resource, action_name)
                )
            )
            return 2
        rest = [token for token in rest if token != "--yes"]
    rest, query_flags = parse_query_flags(rest, spec)
    if spec.get("query") or spec.get("page_query"):
        fields = SEARCH_QUERY_FIELDS if spec.get("page_query") else QUERY_FIELDS
        positional, pairs = query_pairs(
            rest, fields, spec.get("allowed_filters")
        )
        path, pairs = apply_positional_args(
            resource, action_name, spec, positional, pairs
        )
        query = urllib.parse.urlencode(pairs)
        path = path + ("?" + query if query else "")
        return execute(spec["method"], path, None, out, err)
    if spec.get("format") or spec.get("stream"):
        positional, output_path, fmt, url = parse_stream_flags(rest, spec)
        if spec.get("arg"):
            if len(positional) != 1:
                raise UsageError(
                    "%s %s requires <%s>"
                    % (resource, action_name, spec.get("arg_label", spec["arg"]))
                )
            path = spec["path"].replace(
                "{id}", urllib.parse.quote(positional[0], safe="")
            )
        else:
            if positional:
                raise UsageError("unexpected argument: %s" % positional[0])
            path = spec["path"]
        if fmt:
            path = path.replace("{format}", fmt)
        if url is not None:
            path = path + "?" + urllib.parse.urlencode({"url": url})
        return execute(
            spec["method"],
            path,
            None,
            out,
            err,
            stream=spec.get("stream", False),
            output_path=output_path,
        )
    positional, json_source, values, files = parse_body_flags(rest, spec)
    if spec.get("args"):
        path, _ = apply_positional_args(resource, action_name, spec, positional, [])
    elif spec.get("arg"):
        if len(positional) != 1:
            raise UsageError(
                "%s %s requires <%s>"
                % (resource, action_name, spec.get("arg_label", spec["arg"]))
            )
        path = spec["path"].replace("{id}", urllib.parse.quote(positional[0], safe=""))
    else:
        if positional:
            raise UsageError("unexpected argument: %s" % positional[0])
        path = spec["path"]
    if query_flags:
        path = path + "?" + urllib.parse.urlencode(query_flags)
    if spec.get("file_arg"):
        upload = read_file_source(positional[0], spec["file_arg"])
        content_type, payload = build_multipart({}, {spec["file_arg"]: upload})
        return execute(
            spec["method"], path, payload, out, err, content_type=content_type
        )
    if spec.get("required_body") and json_source is None and not values and not files:
        raise UsageError(
            "%s %s requires a body: --json @file|- or field flags"
            % (resource, action_name)
        )
    payload = None
    content_type = None
    method = spec["method"]
    if spec.get("body") or spec.get("json"):
        body = build_body(json_source, values)
        validate_groups(spec, body, files)
        if files:
            for key in files:
                body.pop(key, None)
            spoof = "PUT" if method == "PUT" else None
            content_type, payload = build_multipart(body, files, spoof_method=spoof)
            if spoof:
                method = "POST"
        else:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    return execute(method, path, payload, out, err, content_type=content_type)


def run_docs(args, out, err):
    if "--help" in args[1:] or "-h" in args[1:]:
        out.write(docs_help().encode("utf-8"))
        return 0
    html = False
    for token in args[1:]:
        if token == "--html":
            html = True
        else:
            raise UsageError("unknown flag for docs: %s" % token)
    return execute("GET", "/api/docs" if html else "/api/docs.json", None, out, err)


def run_resource(resource, args, out, err):
    if len(args) > 1 and args[1] in ("--help", "-h"):
        out.write(resource_help(resource).encode("utf-8"))
        return 0
    if resource == "system":
        if len(args) > 1:
            raise UsageError("unknown action for system: %s" % args[1])
        return execute("GET", "/api/system", None, out, err)
    return run_action(resource, args, out, err)


def main(argv=None):
    args = list(sys.argv[1:]) if argv is None else list(argv)
    out = sys.stdout.buffer
    err = sys.stderr.buffer
    try:
        if not args:
            raise UsageError("missing resource")
        if args[0] in ("--help", "-h"):
            out.write(top_help().encode("utf-8"))
            return 0
        if args[0] == "-auth":
            return auth_command(args[1:], out, err)
        if args[0] == "docs":
            return run_docs(args, out, err)
        resource = args[0]
        if resource == "auth" or resource not in RESOURCE_ORDER:
            raise UsageError("unknown resource: %s" % resource)
        return run_resource(resource, args, out, err)
    except UsageError as error:
        err.write(("usage error: %s\n" % error).encode("utf-8"))
        err.write(('Run "bookstack-api-cli.py --help" for usage.\n').encode("utf-8"))
        return 2


if __name__ == "__main__":
    sys.exit(main())
