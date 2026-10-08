"""Ticket 08: image-gallery list/create/read/data/url-data/update/delete.

API facts (research-api.md §6.8):
- list covers gallery and drawio images
- create requires type + uploaded_to + an image file (multipart); name is optional
- read includes thumbs and suggested HTML/Markdown snippets, passed through
- /{id}/data and /url/data stream raw image bytes (stdout or -o FILE)
- update is a partial PUT; with an image it becomes POST + _method=PUT
- delete does not check references and can leave broken images
"""

import json
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


class ImageGalleryListTest(unittest.TestCase):
    def test_list_passes_listing_parameters_and_gallery_drawio_items_through(self):
        cli = load_cli()
        body = (
            b'{"data":[{"id":1,"type":"gallery","name":"diagram.png"},'
            b'{"id":2,"type":"drawio","name":"flow"}],"total":2}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "image-gallery", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "type=drawio",
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
        self.assertEqual("/api/image-gallery", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["drawio"], query["filter[type]"])

    def test_list_without_query_hits_the_bare_collection_endpoint(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"data":[],"total":0}')])
        result = run(cli, ["image-gallery", "list"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"data":[],"total":0}\n', result.stdout)
        self.assertEqual(
            "https://wiki.example.com/api/image-gallery", transport.requests[0].url
        )


class ImageGalleryCreateTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.image_path = Path(self.directory) / "diagram.png"
        self.image_path.write_bytes(PNG_BYTES)

    def test_create_uploads_image_as_multipart_with_required_fields(self):
        cli = load_cli()
        body = b'{"id":7,"type":"gallery","name":"Diagram"}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "image-gallery", "create",
                "--type", "gallery",
                "--uploaded-to", "5",
                "--image", "@" + str(self.image_path),
                "--name", "Diagram",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/image-gallery", request.url)
        parts = parse_multipart(self, request.headers["Content-Type"], request.body)
        fields = part_fields(parts)
        self.assertNotIn("_method", fields)
        self.assertEqual(b"gallery", fields["type"]["content"])
        self.assertEqual(b"5", fields["uploaded_to"]["content"])
        self.assertEqual(b"Diagram", fields["name"]["content"])
        upload = fields["image"]
        self.assertEqual("diagram.png", part_filename(upload))
        self.assertEqual("image/png", upload["headers"]["content-type"])
        self.assertEqual(PNG_BYTES, upload["content"])

    def test_create_name_is_optional(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":8}')])
        result = run(
            cli,
            [
                "image-gallery", "create",
                "--type", "drawio",
                "--uploaded-to", "5",
                "--image", "@" + str(self.image_path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        fields = part_fields(
            parse_multipart(self, request.headers["Content-Type"], request.body)
        )
        self.assertEqual(b"drawio", fields["type"]["content"])
        self.assertNotIn("name", fields)

    def test_create_requires_type_uploaded_to_and_image(self):
        base = {
            "--type": "gallery",
            "--uploaded-to": "5",
            "--image": "@" + str(self.image_path),
        }
        for missing in ("--type", "--uploaded-to", "--image"):
            argv = ["image-gallery", "create"]
            for flag, value in base.items():
                if flag != missing:
                    argv.extend([flag, value])
            with self.subTest(missing=missing):
                cli = load_cli()
                transport = RecordingTransport()
                result = run(cli, argv, transport=transport)
                self.assertEqual(2, result.code, result.stderr)
                self.assertEqual(b"", result.stdout)
                self.assertIn(b"usage", result.stderr.lower())
                self.assertEqual([], transport.requests)

    def test_create_rejects_unknown_flag_and_bad_values(self):
        cases = (
            ["image-gallery", "create", "--bogus", "x"],
            [
                "image-gallery", "create", "--type", "gallery",
                "--uploaded-to", "five", "--image", "@" + str(self.image_path),
            ],
            [
                "image-gallery", "create", "--type", "gallery",
                "--uploaded-to", "5", "--image", str(self.image_path),
            ],
            [
                "image-gallery", "create", "--type", "gallery",
                "--uploaded-to", "5", "--image", "@/nonexistent/diagram.png",
            ],
        )
        for argv in cases:
            with self.subTest(argv=argv):
                cli = load_cli()
                transport = RecordingTransport()
                result = run(cli, argv, transport=transport)
                self.assertEqual(2, result.code, result.stderr)
                self.assertEqual([], transport.requests)


class ImageGalleryReadTest(unittest.TestCase):
    def test_read_passes_thumbs_and_suggested_snippets_through(self):
        cli = load_cli()
        body = (
            b'{"id":7,"type":"gallery","name":"diagram.png",'
            b'"thumbs":{"240":"https://wiki.example.com/uploads/images/'
            b'gallery/thumbs/240-abc.png","500":"https://wiki.example.com/'
            b'uploads/images/gallery/thumbs/500-abc.png"},'
            b'"content":{"html":"<img src=\\"https://wiki.example.com/'
            b'uploads/images/gallery/abc.png\\" alt=\\"diagram.png\\">",'
            b'"markdown":"![diagram.png](https://wiki.example.com/uploads/'
            b'images/gallery/abc.png)"}}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["image-gallery", "read", "7"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual(
            "https://wiki.example.com/api/image-gallery/7", request.url
        )
        self.assertIsNone(request.body)
        self.assertIn(b'"thumbs"', result.stdout)
        self.assertIn(b'"content"', result.stdout)


class ImageGalleryDataRawTest(unittest.TestCase):
    def test_data_streams_raw_image_bytes_verbatim_without_a_newline(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {"Content-Type": "image/png"}, PNG_BYTES)])
        result = run(cli, ["image-gallery", "data", "7"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(PNG_BYTES, result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual(
            "https://wiki.example.com/api/image-gallery/7/data", request.url
        )
        self.assertIsNone(request.body)

    def test_data_requires_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["image-gallery", "data"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)


class ImageGalleryDataFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def target(self, name):
        return str(Path(self.directory) / name)

    def test_output_flag_saves_identical_bytes_and_prints_saved_to(self):
        cli = load_cli()
        target = self.target("7.png")
        transport = RecordingTransport([(200, {}, PNG_BYTES)])
        result = run(
            cli, ["image-gallery", "data", "7", "-o", target], transport=transport
        )
        self.assertEqual(0, result.code)
        self.assertEqual(PNG_BYTES, Path(target).read_bytes())
        self.assertEqual(
            json.dumps({"saved_to": target}).encode("utf-8") + b"\n", result.stdout
        )
        self.assertEqual(b"", result.stderr)
        self.assertEqual(
            "https://wiki.example.com/api/image-gallery/7/data",
            transport.requests[0].url,
        )

    def test_output_flag_may_appear_before_the_id(self):
        cli = load_cli()
        target = self.target("7.png")
        transport = RecordingTransport([(200, {}, PNG_BYTES)])
        result = run(
            cli, ["image-gallery", "data", "-o", target, "7"], transport=transport
        )
        self.assertEqual(0, result.code)
        self.assertEqual(PNG_BYTES, Path(target).read_bytes())

    def test_data_error_with_output_flag_writes_no_file(self):
        cli = load_cli()
        target = self.target("7.png")
        body = b'{"error":{"code":404,"message":"Not found"}}'
        transport = RecordingTransport([(404, {}, body)])
        result = run(
            cli, ["image-gallery", "data", "7", "-o", target], transport=transport
        )
        self.assertEqual(4, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(body, result.stderr)
        self.assertFalse(Path(target).exists())


class ImageGalleryUrlDataTest(unittest.TestCase):
    IMAGE_URL = "https://wiki.example.com/uploads/images/gallery/abc.png?ts=1"

    def test_url_data_streams_raw_bytes_and_passes_url_as_query(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, PNG_BYTES)])
        result = run(
            cli, ["image-gallery", "url-data", "--url", self.IMAGE_URL],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(PNG_BYTES, result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("/api/image-gallery/url/data", parsed.path)
        self.assertEqual([self.IMAGE_URL], urllib.parse.parse_qs(parsed.query)["url"])

    def test_url_data_output_flag_saves_identical_bytes(self):
        cli = load_cli()
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        target = str(Path(directory) / "abc.png")
        transport = RecordingTransport([(200, {}, PNG_BYTES)])
        result = run(
            cli,
            ["image-gallery", "url-data", "--url", self.IMAGE_URL, "-o", target],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(PNG_BYTES, Path(target).read_bytes())
        self.assertEqual(
            json.dumps({"saved_to": target}).encode("utf-8") + b"\n", result.stdout
        )

    def test_url_data_requires_exactly_one_url(self):
        cases = (
            ["image-gallery", "url-data"],
            ["image-gallery", "url-data", "--url"],
            [
                "image-gallery", "url-data", "--url", self.IMAGE_URL,
                "--url", self.IMAGE_URL,
            ],
            ["image-gallery", "url-data", self.IMAGE_URL],
        )
        for argv in cases:
            with self.subTest(argv=argv):
                cli = load_cli()
                transport = RecordingTransport()
                result = run(cli, argv, transport=transport)
                self.assertEqual(2, result.code, result.stderr)
                self.assertEqual(b"", result.stdout)
                self.assertIn(b"usage", result.stderr.lower())
                self.assertEqual([], transport.requests)


class ImageGalleryUpdateTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.image_path = Path(self.directory) / "diagram.png"
        self.image_path.write_bytes(PNG_BYTES)

    def test_update_renames_via_json_put(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7}')])
        result = run(
            cli, ["image-gallery", "update", "7", "--name", "Renamed"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/image-gallery/7", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual({"name": "Renamed"}, json.loads(request.body))

    def test_update_with_image_spoofs_put_through_post_multipart(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7}')])
        result = run(
            cli,
            [
                "image-gallery", "update", "7",
                "--name", "Renamed",
                "--image", "@" + str(self.image_path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/image-gallery/7", request.url)
        fields = part_fields(
            parse_multipart(self, request.headers["Content-Type"], request.body)
        )
        self.assertEqual(b"PUT", fields["_method"]["content"])
        self.assertEqual(b"Renamed", fields["name"]["content"])
        upload = fields["image"]
        self.assertEqual("diagram.png", part_filename(upload))
        self.assertEqual(PNG_BYTES, upload["content"])

    def test_update_with_only_an_image_is_multipart_without_other_fields(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":7}')])
        result = run(
            cli,
            [
                "image-gallery", "update", "7",
                "--image", "@" + str(self.image_path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        fields = part_fields(
            parse_multipart(self, request.headers["Content-Type"], request.body)
        )
        self.assertEqual(b"PUT", fields["_method"]["content"])
        self.assertNotIn("name", fields)
        self.assertEqual(PNG_BYTES, fields["image"]["content"])

    def test_update_requires_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli, ["image-gallery", "update", "--name", "Renamed"],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)


class ImageGalleryDeleteTest(unittest.TestCase):
    def test_delete_sends_delete_and_is_silent_on_204(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(cli, ["image-gallery", "delete", "7"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("DELETE", request.method)
        self.assertEqual("https://wiki.example.com/api/image-gallery/7", request.url)
        self.assertIsNone(request.body)


class ImageGalleryErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["image-gallery", "data", "7"], 401, 3),
            (["image-gallery", "list"], 403, 3),
            (["image-gallery", "read", "7"], 404, 4),
            (
                [
                    "image-gallery", "url-data",
                    "--url", "https://wiki.example.com/uploads/x.png",
                ],
                422,
                5,
            ),
            (["image-gallery", "delete", "7"], 500, 8),
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
                "image-gallery", "url-data",
                "--url", "https://wiki.example.com/uploads/x.png",
            ],
            env={},
            transport=transport,
        )
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)


class ImageGalleryHelpTest(unittest.TestCase):
    def help_text(self, argv):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, argv, env={}, transport=transport)
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual([], transport.requests)
        return result.stdout.decode("utf-8")

    def test_resource_help_lists_all_actions_without_export(self):
        text = self.help_text(["image-gallery", "--help"])
        for action in ("list", "create", "read", "data", "url-data", "update", "delete"):
            self.assertIn(action, text)
        self.assertNotIn("export", text)

    def test_create_help_lists_flags_and_multipart_semantics(self):
        text = self.help_text(["image-gallery", "create", "--help"])
        for flag in ("--type", "--uploaded-to", "--image", "--name"):
            self.assertIn(flag, text)
        self.assertIn("multipart", text)

    def test_data_help_documents_both_stream_states(self):
        text = self.help_text(["image-gallery", "data", "--help"])
        self.assertIn("<id>", text)
        self.assertIn("-o FILE", text)
        self.assertIn("saved_to", text)
        self.assertIn("stdout", text)

    def test_url_data_help_documents_url_flag_and_stream_states(self):
        text = self.help_text(["image-gallery", "url-data", "--help"])
        self.assertIn("--url", text)
        self.assertIn("-o FILE", text)
        self.assertIn("saved_to", text)

    def test_delete_help_explains_reference_semantics(self):
        text = self.help_text(["image-gallery", "delete", "--help"])
        lowered = text.lower()
        self.assertIn("does not check references", lowered)
        self.assertIn("broken", lowered)


if __name__ == "__main__":
    unittest.main()
