"""Ticket 06: shelves CRUD, --books ordering override, and multipart cover."""

import json
import os
import shutil
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from cli_harness import RecordingTransport, load_cli, run

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


class ShelvesListTest(unittest.TestCase):
    def test_list_passes_listing_parameters_through(self):
        cli = load_cli()
        transport = RecordingTransport(
            [(200, {}, b'{"data":[{"id":3,"name":"Great reads"}],"total":1}')]
        )
        result = run(
            cli,
            [
                "shelves", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "name:like=%read%",
                "--filter", "id=3",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            b'{"data":[{"id":3,"name":"Great reads"}],"total":1}\n', result.stdout
        )
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("wiki.example.com", parsed.netloc)
        self.assertEqual("/api/shelves", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["%read%"], query["filter[name:like]"])
        self.assertEqual(["3"], query["filter[id]"])


class ShelvesCreateJsonTest(unittest.TestCase):
    def test_create_minimal_name_posts_json(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":3,"name":"Great reads"}')])
        result = run(
            cli, ["shelves", "create", "--name", "Great reads"], transport=transport
        )
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"id":3,"name":"Great reads"}\n', result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/shelves", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual({"name": "Great reads"}, json.loads(request.body))

    def test_create_with_all_supported_fields(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":8}')])
        result = run(
            cli,
            [
                "shelves", "create",
                "--name", "Great reads",
                "--description", "plain description",
                "--description-html", "<p>html description</p>",
                "--tags", '[{"name":"team","value":"docs"}]',
                "--books", "3,1,2",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {
                "name": "Great reads",
                "description": "plain description",
                "description_html": "<p>html description</p>",
                "tags": [{"name": "team", "value": "docs"}],
                "books": [3, 1, 2],
            },
            json.loads(transport.requests[0].body),
        )

    def test_books_flag_accepts_whitespace_and_empty_list(self):
        cases = (
            ("9, 8", [9, 8]),
            ("", []),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                cli = load_cli()
                transport = RecordingTransport([(200, {}, b'{"id":9}')])
                result = run(
                    cli,
                    ["shelves", "create", "--name", "X", "--books", value],
                    transport=transport,
                )
                self.assertEqual(0, result.code, result.stderr)
                self.assertEqual(
                    {"name": "X", "books": expected},
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
                "shelves", "create",
                "--name", "Great reads",
                "--description-html", "@" + str(path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {"name": "Great reads", "description_html": "<p>from file</p>"},
            json.loads(transport.requests[0].body),
        )

    def test_json_stdin_satisfies_required_name_and_flags_override(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":10}')])
        result = run(
            cli,
            ["shelves", "create", "--json", "-", "--name", "Override", "--books", "4,5"],
            stdin=b'{"name": "From stdin", "books": [1, 2], "description": "kept"}',
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {"name": "Override", "description": "kept", "books": [4, 5]},
            json.loads(transport.requests[0].body),
        )


class ShelvesReadTest(unittest.TestCase):
    def test_read_passes_books_order_through_byte_for_byte(self):
        cli = load_cli()
        body = (
            b'{"id":9,"name":"Great reads","description":"d",'
            b'"books":[{"id":3,"name":"Third","slug":"third"},'
            b'{"id":1,"name":"First","slug":"first"}]}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["shelves", "read", "9"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/shelves/9", request.url)
        self.assertIsNone(request.body)


class ShelvesUpdateJsonTest(unittest.TestCase):
    def test_update_puts_partial_body_without_other_keys(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli, ["shelves", "update", "9", "--name", "Renamed"], transport=transport
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/shelves/9", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual({"name": "Renamed"}, json.loads(request.body))

    def test_update_books_replaces_the_whole_order_without_merge(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli, ["shelves", "update", "9", "--books", "5,4"], transport=transport
        )
        self.assertEqual(0, result.code)
        self.assertEqual({"books": [5, 4]}, json.loads(transport.requests[0].body))

    def test_update_books_empty_string_clears_the_order(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli, ["shelves", "update", "9", "--books", ""], transport=transport
        )
        self.assertEqual(0, result.code)
        self.assertEqual({"books": []}, json.loads(transport.requests[0].body))

    def test_update_with_image_null_clears_cover_via_json(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli, ["shelves", "update", "9", "--image", "null"], transport=transport
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual({"image": None}, json.loads(request.body))


class ShelvesDeleteTest(unittest.TestCase):
    def test_delete_sends_delete_and_is_silent_on_204(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(cli, ["shelves", "delete", "9"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("DELETE", request.method)
        self.assertEqual("https://wiki.example.com/api/shelves/9", request.url)
        self.assertIsNone(request.body)


class ShelvesMultipartUploadTest(unittest.TestCase):
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
                "shelves", "create",
                "--name", "Great reads",
                "--description", "plain",
                "--books", "3,1,2",
                "--tags", '[{"name":"team","value":"docs"}]',
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
        self.assertEqual("https://wiki.example.com/api/shelves", request.url)
        parts = parse_multipart(
            self, request.headers["Content-Type"], request.body
        )
        fields = part_fields(parts)
        self.assertEqual(b"Great reads", fields["name"]["content"])
        self.assertEqual(b"plain", fields["description"]["content"])
        self.assertEqual(b"3", fields["books[0]"]["content"])
        self.assertEqual(b"1", fields["books[1]"]["content"])
        self.assertEqual(b"2", fields["books[2]"]["content"])
        self.assertEqual(b"team", fields["tags[0][name]"]["content"])
        self.assertEqual(b"docs", fields["tags[0][value]"]["content"])
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
                "shelves", "update", "9",
                "--name", "Renamed",
                "--books", "2,1",
                "--image", "@" + str(self.image_path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/shelves/9", request.url)
        parts = parse_multipart(
            self, request.headers["Content-Type"], request.body
        )
        fields = part_fields(parts)
        self.assertEqual(b"PUT", fields["_method"]["content"])
        self.assertEqual(b"Renamed", fields["name"]["content"])
        self.assertEqual(b"2", fields["books[0]"]["content"])
        self.assertEqual(b"1", fields["books[1]"]["content"])
        self.assertEqual(PNG_BYTES, fields["image"]["content"])

    def test_requests_without_file_flags_stay_json_or_bodiless(self):
        cases = (
            (["shelves", "create", "--name", "X"], "POST", "application/json"),
            (["shelves", "update", "9", "--name", "X"], "PUT", "application/json"),
            (["shelves", "read", "9"], "GET", None),
            (["shelves", "delete", "9"], "DELETE", None),
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


class ShelvesErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["shelves", "read", "9"], 401, 3),
            (["shelves", "list"], 403, 3),
            (["shelves", "update", "9", "--name", "x"], 404, 4),
            (["shelves", "create", "--name", "x"], 422, 5),
            (["shelves", "delete", "9"], 500, 8),
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
            ["shelves", "create", "--name", "X"],
            env={},
            transport=transport,
        )
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)


class ShelvesUsageErrorTest(unittest.TestCase):
    def assert_usage_error(self, argv):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, argv, transport=transport)
        self.assertEqual(2, result.code, "argv=%r stderr=%r" % (argv, result.stderr))
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_create_requires_name(self):
        self.assert_usage_error(["shelves", "create"])
        self.assert_usage_error(["shelves", "create", "--description", "d"])

    def test_create_rejects_unknown_flag(self):
        self.assert_usage_error(["shelves", "create", "--name", "X", "--bogus"])

    def test_create_rejects_invalid_tags_json(self):
        self.assert_usage_error(
            ["shelves", "create", "--name", "X", "--tags", "not-json"]
        )

    def test_books_flag_rejects_non_integer_ids(self):
        for value in ("1,two", "1,,2", "1.5", "one"):
            with self.subTest(value=value):
                self.assert_usage_error(
                    ["shelves", "create", "--name", "X", "--books", value]
                )

    def test_read_update_delete_require_id(self):
        for action in ("read", "update", "delete"):
            with self.subTest(action=action):
                self.assert_usage_error(["shelves", action])

    def test_books_flag_is_rejected_on_read_and_delete(self):
        self.assert_usage_error(["shelves", "read", "9", "--books", "1"])
        self.assert_usage_error(["shelves", "delete", "9", "--books", "1"])

    def test_image_requires_at_file_or_null(self):
        self.assert_usage_error(
            ["shelves", "create", "--name", "X", "--image", "cover.png"]
        )

    def test_image_missing_file_is_a_usage_error(self):
        self.assert_usage_error(
            ["shelves", "create", "--name", "X", "--image", "@/nonexistent/cover.png"]
        )

    def test_image_is_rejected_on_read_and_delete(self):
        self.assert_usage_error(["shelves", "read", "9", "--image", "@x.png"])
        self.assert_usage_error(["shelves", "delete", "9", "--image", "@x.png"])

    def test_export_action_does_not_exist(self):
        self.assert_usage_error(["shelves", "export", "9", "--format", "pdf"])


class ShelvesHelpTest(unittest.TestCase):
    def test_resource_help_lists_all_actions_without_export(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["shelves", "--help"], env={}, transport=transport)
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for action in ("list", "create", "read", "update", "delete"):
            self.assertIn(action, text)
        self.assertNotIn("export", text)
        self.assertEqual([], transport.requests)

    def test_create_help_lists_flags_and_multipart_semantics(self):
        cli = load_cli()
        result = run(cli, ["shelves", "create", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for flag in (
            "--name", "--description", "--description-html", "--tags",
            "--books", "--image",
        ):
            self.assertIn(flag, text)
        self.assertIn("multipart", text)
        self.assertIn("null", text)


if __name__ == "__main__":
    unittest.main()
