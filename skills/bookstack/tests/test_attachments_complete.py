"""Ticket 07: attachments create (file multipart / link JSON), read, list,
update and delete.

API facts (research-api.md §6.5 + AttachmentApiController):
- create requires name + uploaded_to and exactly one of file/link
- file requests are multipart/form-data, link requests are JSON
- file-type read returns base64 content that the CLI must not decode
- update is partial PUT; with a file it becomes POST + _method=PUT
"""

import json
import shutil
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from cli_harness import RecordingTransport, load_cli, run

PDF_BYTES = b"%PDF-1.4\n" + bytes(range(256)) + b"\r\n--not-the-boundary\r\n"


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


class AttachmentsListTest(unittest.TestCase):
    def test_list_passes_listing_parameters_and_external_field_through(self):
        cli = load_cli()
        body = (
            b'{"data":[{"id":1,"name":"Docs","external":true,'
            b'"uploaded_to":5},{"id":2,"name":"spec.pdf","external":false,'
            b'"uploaded_to":5}],"total":2}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "attachments", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "external=false",
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
        self.assertEqual("/api/attachments", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["false"], query["filter[external]"])


class AttachmentsCreateLinkTest(unittest.TestCase):
    def test_create_with_link_posts_json_without_a_file_part(self):
        cli = load_cli()
        body = b'{"id":1,"name":"Docs","external":true}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "attachments", "create",
                "--uploaded-to", "5",
                "--name", "Docs",
                "--link", "https://example.com/docs",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/attachments", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual(
            {
                "name": "Docs",
                "uploaded_to": 5,
                "link": "https://example.com/docs",
            },
            json.loads(request.body),
        )

    def test_create_link_via_json_stdin_satisfies_required_fields(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":2}')])
        result = run(
            cli,
            ["attachments", "create", "--json", "-", "--name", "Override"],
            stdin=b'{"name":"From stdin","uploaded_to":5,'
            b'"link":"https://example.com/a"}',
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        request = transport.requests[0]
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual(
            {
                "name": "Override",
                "uploaded_to": 5,
                "link": "https://example.com/a",
            },
            json.loads(request.body),
        )


class AttachmentsCreateFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.file_path = Path(self.directory) / "spec.pdf"
        self.file_path.write_bytes(PDF_BYTES)

    def test_create_with_file_switches_the_whole_request_to_multipart(self):
        cli = load_cli()
        body = b'{"id":7,"name":"Spec PDF","external":false}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "attachments", "create",
                "--uploaded-to", "5",
                "--name", "Spec PDF",
                "--file", "@" + str(self.file_path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/attachments", request.url)
        parts = parse_multipart(self, request.headers["Content-Type"], request.body)
        fields = part_fields(parts)
        self.assertEqual(b"5", fields["uploaded_to"]["content"])
        self.assertEqual(b"Spec PDF", fields["name"]["content"])
        self.assertNotIn("link", fields)
        self.assertNotIn("_method", fields)
        upload = fields["file"]
        self.assertEqual("spec.pdf", part_filename(upload))
        self.assertEqual("application/pdf", upload["headers"]["content-type"])
        self.assertEqual(PDF_BYTES, upload["content"])

    def test_requests_without_file_flags_stay_json_or_bodiless(self):
        cases = (
            (["attachments", "read", "7"], "GET", None),
            (["attachments", "delete", "7"], "DELETE", None),
        )
        for argv, method, content_type in cases:
            with self.subTest(argv=argv):
                cli = load_cli()
                transport = RecordingTransport([(200, {}, b"{}")])
                result = run(cli, argv, transport=transport)
                self.assertEqual(0, result.code, result.stderr)
                request = transport.requests[0]
                self.assertEqual(method, request.method)
                self.assertEqual(content_type, request.headers.get("Content-Type"))
                self.assertIsNone(request.body)


class AttachmentsReadTest(unittest.TestCase):
    def test_read_file_type_passes_base64_content_through_byte_for_byte(self):
        cli = load_cli()
        content = "JVBERi0xLjQKJcOkw7zDtsOfCg=="
        body = (
            '{"id":7,"name":"spec.pdf","external":false,'
            '"uploaded_to":5,"content":"%s"}' % content
        ).encode("utf-8")
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["attachments", "read", "7"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertIn(b'"content":"' + content.encode("ascii") + b'"', result.stdout)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/attachments/7", request.url)
        self.assertIsNone(request.body)

    def test_read_link_type_passes_the_url_content_through(self):
        cli = load_cli()
        body = (
            b'{"id":1,"name":"Docs","external":true,"content":'
            b'"https://example.com/docs"}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["attachments", "read", "1"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)


class AttachmentsUpdateTest(unittest.TestCase):
    def test_update_puts_partial_json_body_without_other_keys(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7}')])
        result = run(
            cli, ["attachments", "update", "7", "--name", "Renamed"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/attachments/7", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual({"name": "Renamed"}, json.loads(request.body))

    def test_update_link_uses_json_put(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7}')])
        result = run(
            cli,
            [
                "attachments", "update", "7",
                "--link", "https://example.com/new",
                "--uploaded-to", "9",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual(
            {"link": "https://example.com/new", "uploaded_to": 9},
            json.loads(request.body),
        )

    def test_update_with_file_spoofs_put_through_post_multipart(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        file_path = Path(directory) / "spec.pdf"
        file_path.write_bytes(PDF_BYTES)
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7}')])
        result = run(
            cli,
            [
                "attachments", "update", "7",
                "--name", "Renamed",
                "--file", "@" + str(file_path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/attachments/7", request.url)
        parts = parse_multipart(self, request.headers["Content-Type"], request.body)
        fields = part_fields(parts)
        self.assertEqual(b"PUT", fields["_method"]["content"])
        self.assertEqual(b"Renamed", fields["name"]["content"])
        self.assertEqual(PDF_BYTES, fields["file"]["content"])


class AttachmentsDeleteTest(unittest.TestCase):
    def test_delete_sends_delete_and_is_silent_on_204(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(cli, ["attachments", "delete", "7"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("DELETE", request.method)
        self.assertEqual("https://wiki.example.com/api/attachments/7", request.url)
        self.assertIsNone(request.body)


class AttachmentsErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["attachments", "read", "7"], 401, 3),
            (["attachments", "list"], 403, 3),
            (["attachments", "update", "7", "--name", "x"], 404, 4),
            (
                [
                    "attachments", "create", "--uploaded-to", "5",
                    "--name", "x", "--link", "https://example.com",
                ],
                422,
                5,
            ),
            (["attachments", "delete", "7"], 500, 8),
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
            [
                "attachments", "create", "--uploaded-to", "5",
                "--name", "X", "--link", "https://example.com",
            ],
            env={},
            transport=transport,
        )
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)


class AttachmentsUsageErrorTest(unittest.TestCase):
    def assert_usage_error(self, argv, stdin=b""):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, argv, transport=transport, stdin=stdin)
        self.assertEqual(2, result.code, "argv=%r stderr=%r" % (argv, result.stderr))
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_create_requires_name_and_uploaded_to(self):
        base = [
            "attachments", "create", "--name", "X",
            "--link", "https://example.com",
        ]
        self.assert_usage_error(base[:2] + ["--link", "https://example.com"])
        self.assert_usage_error(["attachments", "create", "--name", "X"])
        self.assert_usage_error(
            ["attachments", "create", "--uploaded-to", "5"]
        )

    def test_create_requires_exactly_one_of_file_or_link(self):
        self.assert_usage_error(
            ["attachments", "create", "--uploaded-to", "5", "--name", "X"]
        )
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        file_path = Path(directory) / "spec.pdf"
        file_path.write_bytes(PDF_BYTES)
        self.assert_usage_error(
            [
                "attachments", "create", "--uploaded-to", "5", "--name", "X",
                "--file", "@" + str(file_path), "--link", "https://example.com",
            ]
        )

    def test_create_rejects_unknown_flag(self):
        self.assert_usage_error(
            ["attachments", "create", "--bogus", "x"]
        )

    def test_uploaded_to_rejects_non_integer(self):
        self.assert_usage_error(
            [
                "attachments", "create", "--uploaded-to", "five", "--name", "X",
                "--link", "https://example.com",
            ]
        )

    def test_file_flag_requires_at_file(self):
        self.assert_usage_error(
            [
                "attachments", "create", "--uploaded-to", "5", "--name", "X",
                "--file", "spec.pdf",
            ]
        )

    def test_file_flag_missing_file_is_a_usage_error(self):
        self.assert_usage_error(
            [
                "attachments", "create", "--uploaded-to", "5", "--name", "X",
                "--file", "@/nonexistent/spec.pdf",
            ]
        )

    def test_read_update_delete_require_id(self):
        for action in ("read", "update", "delete"):
            with self.subTest(action=action):
                self.assert_usage_error(["attachments", action])

    def test_file_flag_is_rejected_on_read_and_delete(self):
        self.assert_usage_error(["attachments", "read", "7", "--file", "@x.pdf"])
        self.assert_usage_error(["attachments", "delete", "7", "--file", "@x.pdf"])

    def test_update_rejects_both_file_and_link(self):
        self.assert_usage_error(
            [
                "attachments", "update", "7",
                "--file", "@/nonexistent.pdf", "--link", "https://example.com",
            ]
        )

    def test_export_action_does_not_exist(self):
        self.assert_usage_error(["attachments", "export", "7", "--format", "pdf"])


class AttachmentsHelpTest(unittest.TestCase):
    def test_resource_help_lists_all_actions_without_export(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["attachments", "--help"], env={}, transport=transport)
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for action in ("list", "create", "read", "update", "delete"):
            self.assertIn(action, text)
        self.assertNotIn("export", text)
        self.assertEqual([], transport.requests)

    def test_create_help_lists_flags_and_multipart_semantics(self):
        cli = load_cli()
        result = run(cli, ["attachments", "create", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for flag in ("--name", "--uploaded-to", "--file", "--link"):
            self.assertIn(flag, text)
        self.assertIn("multipart", text)


if __name__ == "__main__":
    unittest.main()
