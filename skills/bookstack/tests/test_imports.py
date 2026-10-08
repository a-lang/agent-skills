"""Ticket 12: imports upload / run / read / list / delete.

API facts (research-api.md §6.9):
- POST /api/imports is a multipart upload with a required ``file`` field; it
  stores the ZIP and returns the pending import id (two-phase import).
- POST /api/imports/{id} runs a stored import; its body carries parent_type
  (book/chapter) and parent_id.
- GET /api/imports/{id} returns the import including its ``details`` struct.
- GET /api/imports supports the standard listing parameters.
- DELETE /api/imports/{id} removes a stored import.

Contract (cli-contract.md §3): ``imports upload <zip>`` and ``imports run
<id> --json @file|-`` are the non-CRUD exceptions; read/list/delete follow
the standard mapping. Every endpoint needs the content-import permission so
403 maps to exit 3. run without a body, or with conflicting body sources, is
a usage error: exit 2, zero HTTP.
"""

import json
import shutil
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from cli_harness import RecordingTransport, load_cli, run

ZIP_BYTES = b"PK\x03\x04" + bytes(range(256)) + b"\r\n--not-the-boundary\r\n"


def parse_multipart(test, content_type, body):
    """Decode a multipart body, asserting structure against its declared boundary."""
    test.assertTrue(
        content_type.startswith("multipart/form-data; boundary="), content_type
    )
    boundary = content_type.split("boundary=", 1)[1]
    test.assertTrue(boundary)
    marker = ("--" + boundary).encode("ascii")
    chunks = body.split(marker)
    test.assertEqual(b"", chunks[0])
    test.assertEqual(b"--\r\n", chunks[-1])
    parts = []
    for chunk in chunks[1:-1]:
        test.assertTrue(chunk.startswith(b"\r\n"), chunk)
        test.assertTrue(chunk.endswith(b"\r\n"), chunk)
        header_block, content = chunk[2:-2].split(b"\r\n\r\n", 1)
        headers = {}
        for line in header_block.split(b"\r\n"):
            key, _, value = line.partition(b": ")
            headers[key.decode("ascii").lower()] = value.decode("utf-8")
        parts.append({"headers": headers, "content": content})
    return parts


def part_field_name(part):
    return part["headers"]["content-disposition"].split('name="', 1)[1].split('"', 1)[0]


def part_filename(part):
    return (
        part["headers"]["content-disposition"]
        .split('filename="', 1)[1]
        .split('"', 1)[0]
    )


def part_fields(parts):
    return {part_field_name(part): part for part in parts}


def write_temp(test, name, content):
    directory = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, directory)
    path = Path(directory) / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


class ImportsUploadTest(unittest.TestCase):
    def test_upload_posts_the_zip_as_multipart_and_passes_response_through(self):
        cli = load_cli()
        zip_path = write_temp(self, "export.zip", ZIP_BYTES)
        body = b'{"id":12,"name":"export.zip","status":"pending"}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli, ["imports", "upload", str(zip_path)], transport=transport
        )
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/imports", request.url)
        parts = parse_multipart(self, request.headers["Content-Type"], request.body)
        fields = part_fields(parts)
        self.assertEqual({"file"}, set(fields))
        upload = fields["file"]
        self.assertEqual("export.zip", part_filename(upload))
        self.assertEqual("application/zip", upload["headers"]["content-type"])
        self.assertEqual(ZIP_BYTES, upload["content"])
        self.assertNotIn("_method", fields)

    def test_upload_requires_exactly_one_zip_argument(self):
        for argv in (["imports", "upload"], ["imports", "upload", "a.zip", "b.zip"]):
            with self.subTest(argv=argv):
                cli = load_cli()
                transport = RecordingTransport()
                result = run(cli, argv, transport=transport)
                self.assertEqual(2, result.code, "argv=%r" % argv)
                self.assertEqual(b"", result.stdout)
                self.assertIn(b"usage", result.stderr.lower())
                self.assertEqual([], transport.requests)

    def test_upload_missing_zip_file_is_a_usage_error_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["imports", "upload", "/nonexistent/export.zip"],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)


class ImportsRunTest(unittest.TestCase):
    def test_run_posts_the_body_from_field_flags_to_the_import_path(self):
        cli = load_cli()
        body = b'{"id":12,"status":"running"}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            ["imports", "run", "12", "--parent-type", "book", "--parent-id", "3"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/imports/12", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual(
            {"parent_type": "book", "parent_id": 3},
            json.loads(request.body.decode("utf-8")),
        )

    def test_run_reads_the_whole_body_from_a_json_file(self):
        cli = load_cli()
        opts = write_temp(
            self, "opts.json", '{"parent_type":"chapter","parent_id":5}'
        )
        transport = RecordingTransport([(200, {}, b'{"id":12}')])
        result = run(
            cli, ["imports", "run", "12", "--json", "@" + str(opts)],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual(
            {"parent_type": "chapter", "parent_id": 5},
            json.loads(request.body.decode("utf-8")),
        )

    def test_run_reads_the_whole_body_from_stdin(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":12}')])
        result = run(
            cli, ["imports", "run", "12", "--json", "-"],
            stdin=b'{"parent_type":"book","parent_id":9}',
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"parent_type": "book", "parent_id": 9},
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_run_field_flags_override_json_top_level_keys(self):
        cli = load_cli()
        opts = write_temp(
            self, "opts.json", '{"parent_type":"book","parent_id":1}'
        )
        transport = RecordingTransport([(200, {}, b'{"id":12}')])
        result = run(
            cli,
            ["imports", "run", "12", "--json", "@" + str(opts), "--parent-id", "7"],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"parent_type": "book", "parent_id": 7},
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_run_without_a_body_is_a_usage_error_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["imports", "run", "12"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_run_rejects_conflicting_body_sources_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["imports", "run", "12", "--json", "-", "--json", "-"],
            stdin=b'{"parent_type":"book","parent_id":1}',
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_run_requires_the_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli, ["imports", "run", "--parent-type", "book"],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)


class ImportsReadTest(unittest.TestCase):
    def test_read_gets_the_import_and_passes_details_through(self):
        cli = load_cli()
        body = (
            b'{"id":12,"status":"complete","details":{"pages":2,"chapters":1,'
            b'"books":1,"errors":[]}}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["imports", "read", "12"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/imports/12", request.url)
        self.assertIsNone(request.body)

    def test_read_null_details_is_passed_through_untouched(self):
        cli = load_cli()
        body = b'{"id":12,"status":"pending","details":null}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["imports", "read", "12"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)

    def test_read_requires_the_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["imports", "read"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class ImportsListTest(unittest.TestCase):
    def test_list_passes_standard_listing_parameters_and_response_through(self):
        cli = load_cli()
        body = b'{"data":[{"id":12,"status":"pending"}],"total":1}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "imports", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "status=pending",
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
        self.assertEqual("/api/imports", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["pending"], query["filter[status]"])
        self.assertIsNone(request.body)


class ImportsDeleteTest(unittest.TestCase):
    def test_delete_sends_delete_and_is_silent_on_204(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(cli, ["imports", "delete", "12"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("DELETE", request.method)
        self.assertEqual("https://wiki.example.com/api/imports/12", request.url)
        self.assertIsNone(request.body)

    def test_delete_requires_the_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["imports", "delete"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class ImportsErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        zip_path = write_temp(self, "export.zip", ZIP_BYTES)
        cases = (
            (["imports", "upload", str(zip_path)], 403, 3),
            (
                ["imports", "run", "12", "--parent-type", "book", "--parent-id", "1"],
                403,
                3,
            ),
            (["imports", "list"], 401, 3),
            (["imports", "read", "12"], 404, 4),
            (["imports", "delete", "12"], 404, 4),
            (
                [
                    "imports", "run", "12",
                    "--parent-type", "chapter", "--parent-id", "5",
                ],
                422,
                5,
            ),
            (["imports", "list"], 500, 8),
            (["imports", "read", "12"], 503, 8),
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


class ImportsHelpTest(unittest.TestCase):
    def test_resource_help_lists_all_actions(self):
        cli = load_cli()
        result = run(cli, ["imports", "--help"], env={})
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stderr)
        text = result.stdout.decode("utf-8")
        for action in ("upload", "run", "read", "list", "delete"):
            self.assertIn(action, text)

    def test_upload_help_shows_positional_zip_and_multipart(self):
        cli = load_cli()
        result = run(cli, ["imports", "upload", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        self.assertIn("<zip>", text)
        self.assertIn("multipart", text)
        self.assertIn("POST /api/imports", text)

    def test_run_help_lists_json_and_parent_flags(self):
        cli = load_cli()
        result = run(cli, ["imports", "run", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for flag in ("--json", "--parent-type", "--parent-id"):
            self.assertIn(flag, text)


if __name__ == "__main__":
    unittest.main()
