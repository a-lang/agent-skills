"""Ticket 09: comments create (page_id + html, optional reply_to/content_ref),
read (direct replies passed through), update (html/archived), list and delete.

API facts (research-api.md §6.6 + CommentApiController):
- create requires page_id and html; reply_to is a local_id, content_ref optional
- read includes direct replies and must be passed through byte-for-byte
- update is a partial PUT accepting html and archived (boolean, top-level only)
- list takes the standard listing parameters; delete answers 204
"""

import json
import shutil
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from cli_harness import RecordingTransport, load_cli, run


class CommentsCreateTest(unittest.TestCase):
    def test_create_posts_page_id_and_html_as_json(self):
        cli = load_cli()
        body = b'{"id":7,"page_id":5,"html":"<p>Hello</p>"}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            ["comments", "create", "--page-id", "5", "--html", "<p>Hello</p>"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/comments", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual(
            {"page_id": 5, "html": "<p>Hello</p>"}, json.loads(request.body)
        )

    def test_create_with_reply_to_local_id_and_content_ref(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":8}')])
        result = run(
            cli,
            [
                "comments", "create",
                "--page-id", "5",
                "--html", "<p>Reply</p>",
                "--reply-to", "12",
                "--content-ref", "block-3",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        request = transport.requests[0]
        self.assertEqual(
            {
                "page_id": 5,
                "html": "<p>Reply</p>",
                "reply_to": 12,
                "content_ref": "block-3",
            },
            json.loads(request.body),
        )

    def test_create_html_accepts_an_at_file(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        html_path = Path(directory) / "comment.html"
        html_path.write_text("<p>From file</p>", encoding="utf-8")
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7}')])
        result = run(
            cli,
            [
                "comments", "create",
                "--page-id", "5",
                "--html", "@" + str(html_path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        request = transport.requests[0]
        self.assertEqual(
            {"page_id": 5, "html": "<p>From file</p>"}, json.loads(request.body)
        )

    def test_create_requires_page_id_and_html(self):
        cases = (
            (["comments", "create", "--html", "<p>x</p>"], b"--page-id is required"),
            (["comments", "create", "--page-id", "5"], b"--html is required"),
        )
        for argv, message in cases:
            with self.subTest(argv=argv):
                cli = load_cli()
                transport = RecordingTransport()
                result = run(cli, argv, transport=transport)
                self.assertEqual(2, result.code, result.stderr)
                self.assertEqual(b"", result.stdout)
                self.assertIn(message, result.stderr)
                self.assertEqual([], transport.requests)

    def test_create_rejects_non_integer_reply_to(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            [
                "comments", "create",
                "--page-id", "5",
                "--html", "<p>x</p>",
                "--reply-to", "abc",
            ],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class CommentsReadTest(unittest.TestCase):
    def test_read_passes_direct_replies_through_byte_for_byte(self):
        cli = load_cli()
        body = (
            b'{"id":7,"page_id":5,"html":"<p>root</p>","archived":false,'
            b'"replies":[{"id":8,"reply_to":7,"html":"<p>child</p>",'
            b'"replies":[]}]}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["comments", "read", "7"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertIn(b'"replies":[{"id":8,"reply_to":7', result.stdout)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/comments/7", request.url)
        self.assertIsNone(request.body)

    def test_read_requires_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["comments", "read"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)


class CommentsUpdateTest(unittest.TestCase):
    def test_update_html_and_archived_via_json_put(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7}')])
        result = run(
            cli,
            [
                "comments", "update", "7",
                "--html", "<p>edited</p>",
                "--archived", "true",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/comments/7", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual(
            {"html": "<p>edited</p>", "archived": True}, json.loads(request.body)
        )

    def test_update_unarchives_with_archived_false(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7}')])
        result = run(
            cli,
            ["comments", "update", "7", "--archived", "false"],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual({"archived": False}, json.loads(transport.requests[0].body))

    def test_update_requires_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli, ["comments", "update", "--html", "<p>x</p>"], transport=transport
        )
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)

    def test_update_rejects_non_boolean_archived(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli, ["comments", "update", "7", "--archived", "yes"], transport=transport
        )
        self.assertEqual(2, result.code)
        self.assertIn(b"--archived", result.stderr)
        self.assertEqual([], transport.requests)


class CommentsListTest(unittest.TestCase):
    def test_list_passes_listing_parameters_through(self):
        cli = load_cli()
        body = b'{"data":[{"id":1,"page_id":5}],"total":1}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "comments", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "page_id=5",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("wiki.example.com", parsed.netloc)
        self.assertEqual("/api/comments", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["5"], query["filter[page_id]"])

    def test_list_without_query_hits_the_bare_collection_endpoint(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"data":[],"total":0}')])
        result = run(cli, ["comments", "list"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual("https://wiki.example.com/api/comments", transport.requests[0].url)


class CommentsDeleteTest(unittest.TestCase):
    def test_delete_sends_delete_and_is_silent_on_204(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(cli, ["comments", "delete", "7"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("DELETE", request.method)
        self.assertEqual("https://wiki.example.com/api/comments/7", request.url)
        self.assertIsNone(request.body)


class CommentsErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["comments", "read", "7"], 401, 3),
            (["comments", "list"], 403, 3),
            (["comments", "update", "7", "--html", "<p>x</p>"], 404, 4),
            (["comments", "create", "--page-id", "5", "--html", "<p>x</p>"], 422, 5),
            (["comments", "delete", "7"], 500, 8),
        )
        for argv, status, expected in cases:
            with self.subTest(argv=argv, status=status):
                body = ('{"error":{"code":%d,"message":"nope"}}' % status).encode()
                cli = load_cli()
                transport = RecordingTransport([(status, {}, body)])
                result = run(cli, argv, transport=transport)
                self.assertEqual(expected, result.code)
                self.assertEqual(b"", result.stdout)
                self.assertEqual(body, result.stderr)

    def test_missing_env_exits_3_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["comments", "create", "--page-id", "5", "--html", "<p>x</p>"],
            env={},
            transport=transport,
        )
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)


class CommentsHelpTest(unittest.TestCase):
    def test_resource_help_lists_all_actions(self):
        cli = load_cli()
        result = run(cli, ["comments", "--help"], transport=RecordingTransport())
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stderr)
        for action in ("list", "create", "read", "update", "delete"):
            self.assertIn(action.encode(), result.stdout)

    def test_create_help_marks_page_id_and_html_required(self):
        cli = load_cli()
        result = run(
            cli, ["comments", "create", "--help"], transport=RecordingTransport()
        )
        self.assertEqual(0, result.code)
        self.assertIn(b"--page-id N --html TEXT", result.stdout)
        self.assertIn(b"[--reply-to N]", result.stdout)
        self.assertIn(b"[--content-ref TEXT]", result.stdout)

    def test_update_help_documents_archived_as_boolean(self):
        cli = load_cli()
        result = run(
            cli, ["comments", "update", "--help"], transport=RecordingTransport()
        )
        self.assertEqual(0, result.code)
        self.assertIn(b"[--html TEXT]", result.stdout)
        self.assertIn(b"[--archived true|false]", result.stdout)


if __name__ == "__main__":
    unittest.main()
