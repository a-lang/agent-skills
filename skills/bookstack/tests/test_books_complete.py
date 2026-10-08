"""Ticket 04: books CRUD, five exports, and the shared multipart upload layer."""

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

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) + b"\r\n--not-the-boundary\r\n"


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


class BooksListTest(unittest.TestCase):
    def test_books_list_passes_listing_parameters_through(self):
        cli = load_cli()
        transport = RecordingTransport(
            [(200, {}, b'{"data":[{"id":1,"name":"Handbook"}],"total":1}')]
        )
        result = run(
            cli,
            [
                "books", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "name:like=%hand%",
                "--filter", "id=3",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            b'{"data":[{"id":1,"name":"Handbook"}],"total":1}\n', result.stdout
        )
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("wiki.example.com", parsed.netloc)
        self.assertEqual("/api/books", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["%hand%"], query["filter[name:like]"])
        self.assertEqual(["3"], query["filter[id]"])


class BooksCreateJsonTest(unittest.TestCase):
    def test_create_minimal_name_posts_json(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7,"name":"Handbook"}')])
        result = run(cli, ["books", "create", "--name", "Handbook"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"id":7,"name":"Handbook"}\n', result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/books", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual({"name": "Handbook"}, json.loads(request.body))

    def test_create_with_all_supported_fields(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":8}')])
        result = run(
            cli,
            [
                "books", "create",
                "--name", "Handbook",
                "--description", "plain description",
                "--description-html", "<p>html description</p>",
                "--tags", '[{"name":"team","value":"docs"}]',
                "--default-template-id", "5",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {
                "name": "Handbook",
                "description": "plain description",
                "description_html": "<p>html description</p>",
                "tags": [{"name": "team", "value": "docs"}],
                "default_template_id": 5,
            },
            json.loads(transport.requests[0].body),
        )

    def test_content_flags_accept_at_file(self):
        cli = load_cli()
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        path = Path(directory) / "description.html"
        path.write_text("<p>from file</p>", encoding="utf-8")
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli,
            [
                "books", "create",
                "--name", "Handbook",
                "--description-html", "@" + str(path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {"name": "Handbook", "description_html": "<p>from file</p>"},
            json.loads(transport.requests[0].body),
        )

    def test_json_stdin_satisfies_required_name_and_flags_override(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":10}')])
        result = run(
            cli,
            ["books", "create", "--json", "-", "--name", "Override"],
            stdin=b'{"name": "From stdin", "description": "kept"}',
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {"name": "Override", "description": "kept"},
            json.loads(transport.requests[0].body),
        )


class BooksReadTest(unittest.TestCase):
    def test_read_passes_contents_tree_and_shelves_through_byte_for_byte(self):
        cli = load_cli()
        body = (
            b'{"id":42,"name":"Handbook","description":"d",'
            b'"contents":[{"id":1,"name":"Chapter","type":"chapter",'
            b'"pages":[{"id":2,"name":"Page","type":"page"}]},'
            b'{"id":3,"name":"Loose page","type":"page"}],'
            b'"shelves":[{"id":9,"name":"Great reads","slug":"great-reads"}]}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["books", "read", "42"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/books/42", request.url)
        self.assertIsNone(request.body)


class BooksUpdateJsonTest(unittest.TestCase):
    def test_update_puts_partial_body_without_other_keys(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli, ["books", "update", "9", "--name", "Renamed"], transport=transport
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/books/9", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual({"name": "Renamed"}, json.loads(request.body))

    def test_update_with_image_null_clears_cover_via_json(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli, ["books", "update", "9", "--image", "null"], transport=transport
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/books/9", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual({"image": None}, json.loads(request.body))


class BooksDeleteTest(unittest.TestCase):
    def test_delete_sends_delete_and_is_silent_on_204(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(cli, ["books", "delete", "42"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("DELETE", request.method)
        self.assertEqual("https://wiki.example.com/api/books/42", request.url)
        self.assertIsNone(request.body)


class BooksExportRawTest(unittest.TestCase):
    def test_all_five_formats_map_to_the_matching_endpoint(self):
        for fmt in EXPORT_FORMATS:
            with self.subTest(format=fmt):
                cli = load_cli()
                transport = RecordingTransport([(200, {}, b"payload")])
                result = run(
                    cli,
                    ["books", "export", "42", "--format", fmt],
                    transport=transport,
                )
                self.assertEqual(0, result.code, "format=%s" % fmt)
                self.assertEqual(b"payload", result.stdout)
                self.assertEqual(b"", result.stderr)
                self.assertEqual(1, len(transport.requests))
                request = transport.requests[0]
                self.assertEqual("GET", request.method)
                self.assertEqual(
                    "https://wiki.example.com/api/books/42/export/" + fmt,
                    request.url,
                )

    def test_raw_binary_bytes_are_written_verbatim_without_added_newline(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, BINARY_BODY)])
        result = run(
            cli, ["books", "export", "7", "--format", "zip"], transport=transport
        )
        self.assertEqual(0, result.code)
        self.assertEqual(BINARY_BODY, result.stdout)
        self.assertEqual(b"", result.stderr)


class BooksExportFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def target(self, name):
        return os.path.join(self.directory, name)

    def test_output_flag_saves_identical_bytes_and_prints_json_summary(self):
        cli = load_cli()
        target = self.target("book.pdf")
        transport = RecordingTransport([(200, {}, BINARY_BODY)])
        result = run(
            cli,
            ["books", "export", "42", "--format", "pdf", "-o", target],
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
            "https://wiki.example.com/api/books/42/export/pdf",
            transport.requests[0].url,
        )

    def test_export_error_with_output_flag_writes_no_file(self):
        cli = load_cli()
        target = self.target("book.html")
        body = b'{"error":{"code":404,"message":"Not found"}}'
        transport = RecordingTransport([(404, {}, body)])
        result = run(
            cli,
            ["books", "export", "42", "--format", "html", "-o", target],
            transport=transport,
        )
        self.assertEqual(4, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(body, result.stderr)
        self.assertFalse(os.path.exists(target))


class BooksMultipartUploadTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.image_path = Path(self.directory) / "cover.png"
        self.image_path.write_bytes(PNG_BYTES)

    def test_create_with_image_switches_the_whole_request_to_multipart(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":11}')])
        result = run(
            cli,
            [
                "books", "create",
                "--name", "Handbook",
                "--description", "plain",
                "--tags", '[{"name":"team","value":"docs"}]',
                "--default-template-id", "5",
                "--image", "@" + str(self.image_path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"id":11}\n', result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/books", request.url)
        parts = parse_multipart(
            self, request.headers["Content-Type"], request.body
        )
        fields = part_fields(parts)
        self.assertEqual(b"Handbook", fields["name"]["content"])
        self.assertEqual(b"plain", fields["description"]["content"])
        self.assertEqual(b"team", fields["tags[0][name]"]["content"])
        self.assertEqual(b"docs", fields["tags[0][value]"]["content"])
        self.assertEqual(b"5", fields["default_template_id"]["content"])
        self.assertNotIn("_method", fields)
        image = fields["image"]
        self.assertEqual("cover.png", part_filename(image))
        self.assertEqual("image/png", image["headers"]["content-type"])
        self.assertEqual(PNG_BYTES, image["content"])

    def test_update_with_image_spoofs_put_through_post_multipart(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli,
            [
                "books", "update", "9",
                "--name", "Renamed",
                "--image", "@" + str(self.image_path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/books/9", request.url)
        parts = parse_multipart(
            self, request.headers["Content-Type"], request.body
        )
        fields = part_fields(parts)
        self.assertEqual(b"PUT", fields["_method"]["content"])
        self.assertEqual(b"Renamed", fields["name"]["content"])
        self.assertEqual(PNG_BYTES, fields["image"]["content"])

    def test_json_body_merges_into_multipart_and_file_replaces_json_image(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":12}')])
        result = run(
            cli,
            [
                "books", "create", "--json", "-",
                "--image", "@" + str(self.image_path),
            ],
            stdin=b'{"name": "From stdin", "image": "stale-value"}',
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        parts = parse_multipart(
            self, request.headers["Content-Type"], request.body
        )
        fields = part_fields(parts)
        self.assertEqual(b"From stdin", fields["name"]["content"])
        self.assertEqual("cover.png", part_filename(fields["image"]))
        self.assertEqual(PNG_BYTES, fields["image"]["content"])
        self.assertEqual(2, len(parts))

    def test_requests_without_file_flags_stay_json_or_bodiless(self):
        cases = (
            (["books", "create", "--name", "X"], "POST", "application/json"),
            (["books", "update", "9", "--name", "X"], "PUT", "application/json"),
            (["books", "read", "9"], "GET", None),
            (["books", "delete", "9"], "DELETE", None),
        )
        for argv, method, content_type in cases:
            with self.subTest(argv=argv):
                cli = load_cli()
                transport = RecordingTransport([(200, {}, b"{}")])
                result = run(cli, argv, transport=transport)
                self.assertEqual(0, result.code, result.stderr)
                request = transport.requests[0]
                self.assertEqual(method, request.method)
                if content_type is None:
                    self.assertNotIn("Content-Type", request.headers)
                    self.assertIsNone(request.body)
                else:
                    self.assertEqual(content_type, request.headers["Content-Type"])
                    self.assertNotIn(
                        "multipart/form-data", request.headers["Content-Type"]
                    )


class BooksErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["books", "read", "42"], 401, 3),
            (["books", "list"], 403, 3),
            (["books", "update", "42", "--name", "x"], 404, 4),
            (["books", "create", "--name", "x"], 422, 5),
            (["books", "delete", "42"], 500, 8),
            (["books", "export", "42", "--format", "pdf"], 503, 8),
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
            ["books", "create", "--name", "X"],
            env={},
            transport=transport,
        )
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)


class BooksUsageErrorTest(unittest.TestCase):
    def assert_usage_error(self, argv):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, argv, transport=transport)
        self.assertEqual(2, result.code, "argv=%r stderr=%r" % (argv, result.stderr))
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_create_requires_name(self):
        self.assert_usage_error(["books", "create"])
        self.assert_usage_error(["books", "create", "--description", "d"])

    def test_create_rejects_unknown_flag(self):
        self.assert_usage_error(["books", "create", "--name", "X", "--bogus"])

    def test_create_rejects_non_integer_default_template_id(self):
        self.assert_usage_error(
            ["books", "create", "--name", "X", "--default-template-id", "x"]
        )

    def test_create_rejects_invalid_tags_json(self):
        self.assert_usage_error(
            ["books", "create", "--name", "X", "--tags", "not-json"]
        )

    def test_read_update_delete_require_id(self):
        for action in ("read", "update", "delete"):
            with self.subTest(action=action):
                self.assert_usage_error(["books", action])

    def test_export_requires_format_and_id(self):
        self.assert_usage_error(["books", "export", "42"])
        self.assert_usage_error(["books", "export", "--format", "html"])

    def test_export_rejects_invalid_format(self):
        for value in ("docx", "HTML", ""):
            with self.subTest(value=value):
                self.assert_usage_error(["books", "export", "42", "--format", value])

    def test_export_rejects_unknown_flag(self):
        self.assert_usage_error(["books", "export", "42", "--format", "pdf", "--bogus"])

    def test_image_requires_at_file_or_null(self):
        self.assert_usage_error(
            ["books", "create", "--name", "X", "--image", "cover.png"]
        )

    def test_image_missing_file_is_a_usage_error(self):
        self.assert_usage_error(
            ["books", "create", "--name", "X", "--image", "@/nonexistent/cover.png"]
        )

    def test_image_is_rejected_on_read_and_delete(self):
        self.assert_usage_error(["books", "read", "42", "--image", "@x.png"])
        self.assert_usage_error(["books", "delete", "42", "--image", "@x.png"])


class BooksHelpTest(unittest.TestCase):
    def test_resource_help_lists_all_actions(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["books", "--help"], env={}, transport=transport)
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for action in ("list", "create", "read", "update", "delete", "export"):
            self.assertIn(action, text)

    def test_create_help_lists_flags_and_multipart_semantics(self):
        cli = load_cli()
        result = run(cli, ["books", "create", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for flag in (
            "--name", "--description", "--description-html", "--tags",
            "--default-template-id", "--image",
        ):
            self.assertIn(flag, text)
        self.assertIn("multipart", text)
        self.assertIn("null", text)


if __name__ == "__main__":
    unittest.main()
