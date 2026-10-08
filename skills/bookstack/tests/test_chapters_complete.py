"""Ticket 03: chapters create/read/update/delete/export and stream states."""

import json
import os
import shutil
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from cli_harness import RecordingTransport, load_cli, run

EXPORT_FORMATS = ("html", "pdf", "plaintext", "markdown", "zip")

BINARY_BODY = b"%PDF-1.7\r\n%\x00\x01\xff\xfebinary\xfe"


class ChaptersListTest(unittest.TestCase):
    def test_chapters_list_passes_listing_parameters_through(self):
        cli = load_cli()
        transport = RecordingTransport(
            [(200, {}, b'{"data":[{"id":1,"name":"Intro"}],"total":1}')]
        )
        result = run(
            cli,
            [
                "chapters", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "name:like=%cat%",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            b'{"data":[{"id":1,"name":"Intro"}],"total":1}\n', result.stdout
        )
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("wiki.example.com", parsed.netloc)
        self.assertEqual("/api/chapters", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["%cat%"], query["filter[name:like]"])


class ChaptersCreateTest(unittest.TestCase):
    def test_create_minimal_book_and_name(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7,"name":"Intro"}')])
        result = run(
            cli,
            ["chapters", "create", "--book-id", "7", "--name", "Intro"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"id":7,"name":"Intro"}\n', result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/chapters", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual({"book_id": 7, "name": "Intro"}, json.loads(request.body))

    def test_create_with_all_supported_fields(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":8}')])
        result = run(
            cli,
            [
                "chapters", "create",
                "--book-id", "7",
                "--name", "Intro",
                "--description", "plain intro",
                "--description-html", "<p>html intro</p>",
                "--tags", '[{"name":"team","value":"docs"}]',
                "--priority", "3",
                "--default-template-id", "5",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {
                "book_id": 7,
                "name": "Intro",
                "description": "plain intro",
                "description_html": "<p>html intro</p>",
                "tags": [{"name": "team", "value": "docs"}],
                "priority": 3,
                "default_template_id": 5,
            },
            json.loads(transport.requests[0].body),
        )

    def test_content_flags_accept_at_file(self):
        cli = load_cli()
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        path = Path(directory) / "desc.html"
        path.write_text("<p>from file</p>", encoding="utf-8")
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli,
            [
                "chapters", "create",
                "--book-id", "7",
                "--name", "Intro",
                "--description-html", "@" + str(path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {"book_id": 7, "name": "Intro", "description_html": "<p>from file</p>"},
            json.loads(transport.requests[0].body),
        )

    def test_json_stdin_satisfies_required_flags_and_flags_override(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":10}')])
        result = run(
            cli,
            ["chapters", "create", "--json", "-", "--name", "Override"],
            stdin=b'{"book_id": 7, "name": "From stdin", "priority": 2}',
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {"book_id": 7, "name": "Override", "priority": 2},
            json.loads(transport.requests[0].body),
        )


class ChaptersReadTest(unittest.TestCase):
    def test_read_passes_chapter_with_pages_through_byte_for_byte(self):
        cli = load_cli()
        body = (
            b'{"id":42,"name":"Intro","description":"d",'
            b'"pages":[{"id":1,"name":"Page A"},{"id":2,"name":"Page B"}]}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["chapters", "read", "42"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/chapters/42", request.url)
        self.assertIsNone(request.body)


class ChaptersUpdateTest(unittest.TestCase):
    def test_update_puts_partial_body_without_other_keys(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli,
            ["chapters", "update", "9", "--name", "Renamed"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/chapters/9", request.url)
        self.assertEqual({"name": "Renamed"}, json.loads(request.body))

    def test_update_moves_chapter_when_book_id_given(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli,
            ["chapters", "update", "9", "--book-id", "3"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual({"book_id": 3}, json.loads(transport.requests[0].body))


class ChaptersDeleteTest(unittest.TestCase):
    def test_delete_sends_delete_and_is_silent_on_204(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(cli, ["chapters", "delete", "42"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("DELETE", request.method)
        self.assertEqual("https://wiki.example.com/api/chapters/42", request.url)
        self.assertIsNone(request.body)


class ChaptersExportRawTest(unittest.TestCase):
    def test_all_five_formats_map_to_the_matching_endpoint(self):
        for fmt in EXPORT_FORMATS:
            with self.subTest(format=fmt):
                cli = load_cli()
                transport = RecordingTransport([(200, {}, b"payload")])
                result = run(
                    cli,
                    ["chapters", "export", "42", "--format", fmt],
                    transport=transport,
                )
                self.assertEqual(0, result.code, "format=%s" % fmt)
                self.assertEqual(b"payload", result.stdout)
                self.assertEqual(b"", result.stderr)
                self.assertEqual(1, len(transport.requests))
                request = transport.requests[0]
                self.assertEqual("GET", request.method)
                self.assertEqual(
                    "https://wiki.example.com/api/chapters/42/export/" + fmt,
                    request.url,
                )

    def test_raw_binary_bytes_are_written_verbatim_without_added_newline(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, BINARY_BODY)])
        result = run(
            cli, ["chapters", "export", "7", "--format", "zip"], transport=transport
        )
        self.assertEqual(0, result.code)
        self.assertEqual(BINARY_BODY, result.stdout)
        self.assertEqual(b"", result.stderr)


class ChaptersExportFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def target(self, name):
        return os.path.join(self.directory, name)

    def test_output_flag_saves_identical_bytes_and_prints_json_summary(self):
        cli = load_cli()
        target = self.target("chapter.pdf")
        transport = RecordingTransport([(200, {}, BINARY_BODY)])
        result = run(
            cli,
            ["chapters", "export", "42", "--format", "pdf", "-o", target],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(BINARY_BODY, Path(target).read_bytes())
        self.assertEqual(
            json.dumps({"saved_to": target}).encode("utf-8") + b"\n",
            result.stdout,
        )
        self.assertEqual(b"", result.stderr)
        self.assertEqual(
            "https://wiki.example.com/api/chapters/42/export/pdf",
            transport.requests[0].url,
        )

    def test_export_error_with_output_flag_writes_no_file(self):
        cli = load_cli()
        target = self.target("chapter.html")
        body = b'{"error":{"code":404,"message":"Not found"}}'
        transport = RecordingTransport([(404, {}, body)])
        result = run(
            cli,
            ["chapters", "export", "42", "--format", "html", "-o", target],
            transport=transport,
        )
        self.assertEqual(4, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(body, result.stderr)
        self.assertFalse(os.path.exists(target))


class ChaptersUsageErrorTest(unittest.TestCase):
    def assert_usage_error(self, argv):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, argv, transport=transport)
        self.assertEqual(2, result.code, "argv=%r stderr=%r" % (argv, result.stderr))
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_create_requires_book_id(self):
        self.assert_usage_error(["chapters", "create", "--name", "Intro"])

    def test_create_requires_name(self):
        self.assert_usage_error(["chapters", "create", "--book-id", "7"])

    def test_create_rejects_unknown_flag(self):
        self.assert_usage_error(
            ["chapters", "create", "--book-id", "7", "--name", "Intro", "--bogus"]
        )

    def test_create_rejects_non_integer_book_id(self):
        self.assert_usage_error(
            ["chapters", "create", "--book-id", "x", "--name", "Intro"]
        )

    def test_create_rejects_invalid_tags_json(self):
        self.assert_usage_error(
            [
                "chapters", "create",
                "--book-id", "7", "--name", "Intro", "--tags", "not-json",
            ]
        )

    def test_read_update_delete_require_id(self):
        for action in ("read", "update", "delete"):
            with self.subTest(action=action):
                self.assert_usage_error(["chapters", action])

    def test_export_requires_format_and_id(self):
        self.assert_usage_error(["chapters", "export", "42"])
        self.assert_usage_error(["chapters", "export", "--format", "html"])

    def test_export_rejects_invalid_format(self):
        for value in ("docx", "HTML", ""):
            with self.subTest(value=value):
                self.assert_usage_error(
                    ["chapters", "export", "42", "--format", value]
                )

    def test_export_rejects_unknown_flag(self):
        self.assert_usage_error(
            ["chapters", "export", "42", "--format", "pdf", "--bogus"]
        )

    def test_format_flag_is_rejected_on_other_chapters_commands(self):
        for argv in (
            ["chapters", "read", "42", "--format", "html"],
            ["chapters", "list", "--format", "html"],
            ["chapters", "delete", "42", "--format", "html"],
        ):
            with self.subTest(argv=argv):
                self.assert_usage_error(argv)


class ChaptersErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        for status, expected in ((401, 3), (403, 3), (404, 4), (422, 5), (500, 8), (503, 8)):
            with self.subTest(status=status):
                body = ('{"error":{"code":%d,"message":"nope"}}' % status).encode("utf-8")
                cli = load_cli()
                transport = RecordingTransport([(status, {}, body)])
                result = run(cli, ["chapters", "read", "42"], transport=transport)
                self.assertEqual(expected, result.code)
                self.assertEqual(b"", result.stdout)
                self.assertEqual(body, result.stderr)

    def test_delete_and_export_errors_use_same_mapping(self):
        for argv, status, expected in (
            (["chapters", "delete", "42"], 500, 8),
            (["chapters", "export", "42", "--format", "markdown"], 403, 3),
        ):
            with self.subTest(argv=argv):
                body = ('{"error":{"code":%d,"message":"nope"}}' % status).encode("utf-8")
                cli = load_cli()
                transport = RecordingTransport([(status, {}, body)])
                result = run(cli, argv, transport=transport)
                self.assertEqual(expected, result.code)
                self.assertEqual(b"", result.stdout)
                self.assertEqual(body, result.stderr)

    def test_missing_env_exits_3_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["chapters", "create", "--book-id", "1", "--name", "X"], env={}, transport=transport)
        self.assertEqual(3, result.code)
        self.assertEqual([], transport.requests)


class ChaptersHelpTest(unittest.TestCase):
    def test_resource_help_lists_all_actions(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["chapters", "--help"], env={}, transport=transport)
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for action in ("list", "create", "read", "update", "delete", "export"):
            self.assertIn(action, text)

    def test_create_help_lists_flags(self):
        cli = load_cli()
        result = run(cli, ["chapters", "create", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for flag in (
            "--book-id", "--name", "--description", "--description-html",
            "--tags", "--priority", "--default-template-id",
        ):
            self.assertIn(flag, text)


if __name__ == "__main__":
    unittest.main()
