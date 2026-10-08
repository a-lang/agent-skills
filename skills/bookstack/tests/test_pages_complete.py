"""Ticket 02: pages list/read/delete, five export formats, raw and -o stream states."""

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


class PagesListTest(unittest.TestCase):
    def test_pages_list_passes_listing_parameters_through(self):
        cli = load_cli()
        transport = RecordingTransport(
            [(200, {}, b'{"data":[{"id":1,"name":"Doc"}],"total":1}')]
        )
        result = run(
            cli,
            [
                "pages", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "name:like=%cat%",
                "--filter", "id=3",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"data":[{"id":1,"name":"Doc"}],"total":1}\n', result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("wiki.example.com", parsed.netloc)
        self.assertEqual("/api/pages", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["%cat%"], query["filter[name:like]"])
        self.assertEqual(["3"], query["filter[id]"])

    def test_pages_list_without_query_hits_bare_collection_endpoint(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"data":[],"total":0}')])
        result = run(cli, ["pages", "list"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"data":[],"total":0}\n', result.stdout)
        self.assertEqual("https://wiki.example.com/api/pages", transport.requests[0].url)


class PagesReadTest(unittest.TestCase):
    def test_pages_read_passes_page_content_through_byte_for_byte(self):
        cli = load_cli()
        body = (
            b'{"id":42,"name":"Doc","html":"<p>hi</p>","raw_html":"<p>hi</p>",'
            b'"comments":[{"id":1,"text":"note"}]}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["pages", "read", "42"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual("GET", transport.requests[0].method)
        self.assertEqual("https://wiki.example.com/api/pages/42", transport.requests[0].url)


class PagesDeleteTest(unittest.TestCase):
    def test_pages_delete_sends_delete_and_is_silent_on_204(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(cli, ["pages", "delete", "42"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("DELETE", request.method)
        self.assertEqual("https://wiki.example.com/api/pages/42", request.url)
        self.assertIsNone(request.body)


class PagesExportRawTest(unittest.TestCase):
    def test_all_five_formats_map_to_the_matching_endpoint(self):
        for fmt in EXPORT_FORMATS:
            with self.subTest(format=fmt):
                cli = load_cli()
                transport = RecordingTransport([(200, {}, b"payload")])
                result = run(
                    cli,
                    ["pages", "export", "42", "--format", fmt],
                    transport=transport,
                )
                self.assertEqual(0, result.code, "format=%s" % fmt)
                self.assertEqual(b"payload", result.stdout)
                self.assertEqual(b"", result.stderr)
                self.assertEqual(1, len(transport.requests))
                request = transport.requests[0]
                self.assertEqual("GET", request.method)
                self.assertEqual(
                    "https://wiki.example.com/api/pages/42/export/" + fmt,
                    request.url,
                )

    def test_raw_binary_bytes_are_written_verbatim_without_added_newline(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, BINARY_BODY)])
        result = run(
            cli, ["pages", "export", "7", "--format", "zip"], transport=transport
        )
        self.assertEqual(0, result.code)
        self.assertEqual(BINARY_BODY, result.stdout)
        self.assertEqual(b"", result.stderr)


class PagesExportUsageTest(unittest.TestCase):
    def assert_usage_error(self, argv):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, argv, transport=transport)
        self.assertEqual(2, result.code, "argv=%r stderr=%r" % (argv, result.stderr))
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_invalid_format_value_is_rejected(self):
        for value in ("docx", "HTML", "", "html,pdf"):
            with self.subTest(value=value):
                self.assert_usage_error(["pages", "export", "42", "--format", value])

    def test_missing_format_is_rejected(self):
        self.assert_usage_error(["pages", "export", "42"])

    def test_duplicate_format_is_rejected(self):
        self.assert_usage_error(
            ["pages", "export", "42", "--format", "pdf", "--format", "html"]
        )

    def test_format_flag_is_rejected_on_other_pages_commands(self):
        for argv in (
            ["pages", "read", "42", "--format", "html"],
            ["pages", "list", "--format", "html"],
            ["pages", "delete", "42", "--format", "html"],
        ):
            with self.subTest(argv=argv):
                self.assert_usage_error(argv)

    def test_export_requires_id(self):
        self.assert_usage_error(["pages", "export", "--format", "html"])

    def test_export_rejects_unknown_flag(self):
        self.assert_usage_error(
            ["pages", "export", "42", "--format", "pdf", "--bogus"]
        )


class PagesExportErrorTest(unittest.TestCase):
    def test_export_http_errors_map_to_contract_exit_codes(self):
        for status, expected in ((404, 4), (403, 3), (500, 8), (503, 8)):
            with self.subTest(status=status):
                body = ('{"error":{"code":%d,"message":"nope"}}' % status).encode("utf-8")
                cli = load_cli()
                transport = RecordingTransport([(status, {}, body)])
                result = run(
                    cli,
                    ["pages", "export", "42", "--format", "plaintext"],
                    transport=transport,
                )
                self.assertEqual(expected, result.code)
                self.assertEqual(b"", result.stdout)
                self.assertEqual(body, result.stderr)


class PagesExportFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def target(self, name):
        return os.path.join(self.directory, name)

    def test_output_flag_saves_identical_bytes_and_prints_json_summary(self):
        cli = load_cli()
        target = self.target("page.zip")
        transport = RecordingTransport([(200, {}, BINARY_BODY)])
        result = run(
            cli,
            ["pages", "export", "42", "--format", "zip", "-o", target],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(BINARY_BODY, Path(target).read_bytes())
        self.assertEqual(
            json.dumps({"saved_to": target}).encode("utf-8") + b"\n",
            result.stdout,
        )
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        self.assertEqual(
            "https://wiki.example.com/api/pages/42/export/zip",
            transport.requests[0].url,
        )

    def test_output_flag_may_appear_before_the_id(self):
        cli = load_cli()
        target = self.target("page.html")
        transport = RecordingTransport([(200, {}, b"<p>raw</p>")])
        result = run(
            cli,
            ["pages", "export", "-o", target, "42", "--format", "html"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(b"<p>raw</p>", Path(target).read_bytes())

    def test_output_flag_requires_a_value(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli, ["pages", "export", "42", "--format", "pdf", "-o"], transport=transport
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_duplicate_output_flag_is_rejected(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            [
                "pages", "export", "42", "--format", "pdf",
                "-o", self.target("a.pdf"), "-o", self.target("b.pdf"),
            ],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)

    def test_export_error_with_output_flag_writes_no_file(self):
        cli = load_cli()
        target = self.target("page.pdf")
        body = b'{"error":{"code":403,"message":"No content-export permission"}}'
        transport = RecordingTransport([(403, {}, body)])
        result = run(
            cli,
            ["pages", "export", "42", "--format", "pdf", "-o", target],
            transport=transport,
        )
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(body, result.stderr)
        self.assertFalse(os.path.exists(target))

    def test_unwritable_output_path_reports_error_without_traceback(self):
        cli = load_cli()
        target = self.target(os.path.join("missing", "page.pdf"))
        transport = RecordingTransport([(200, {}, BINARY_BODY)])
        result = run(
            cli,
            ["pages", "export", "42", "--format", "pdf", "-o", target],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"cannot write", result.stderr)
        self.assertEqual(1, len(transport.requests))


if __name__ == "__main__":
    unittest.main()
