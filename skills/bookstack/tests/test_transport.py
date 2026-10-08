"""Transport seam: full request recording, raw byte passthrough, single call."""

import json
import shutil
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from cli_harness import AUTH_HEADER, RecordingTransport, load_cli, run


class SystemTest(unittest.TestCase):
    def test_system_sends_get_with_token_header_and_passes_body_through(self):
        cli = load_cli()
        transport = RecordingTransport(
            [(200, {"Content-Type": "application/json"}, b'{"version":"v24.05"}')]
        )
        result = run(cli, ["system"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"version":"v24.05"}\n', result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/system", request.url)
        self.assertEqual(AUTH_HEADER, request.headers["Authorization"])
        self.assertIsNone(request.body)

    def test_existing_trailing_newline_is_not_duplicated(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"ok":true}\n')])
        result = run(cli, ["system"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"ok":true}\n', result.stdout)

    def test_204_prints_nothing_and_exits_0(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(cli, ["system"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)


class ListQueryTest(unittest.TestCase):
    def test_books_list_passes_query_parameters_through(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"data":[],"total":0}')])
        result = run(
            cli,
            [
                "books", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "name:like=%cat%",
                "--filter", "id=3",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"data":[],"total":0}\n', result.stdout)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("/api/books", parsed.path)
        self.assertEqual("wiki.example.com", parsed.netloc)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["%cat%"], query["filter[name:like]"])
        self.assertEqual(["3"], query["filter[id]"])

    def test_chapters_list_maps_to_collection_endpoint_without_query(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"data":[{"id":1}],"total":1}')])
        result = run(cli, ["chapters", "list"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"data":[{"id":1}],"total":1}\n', result.stdout)
        self.assertEqual("https://wiki.example.com/api/chapters", transport.requests[0].url)


class DocsTest(unittest.TestCase):
    def test_docs_default_fetches_docs_json(self):
        cli = load_cli()
        body = b'{"endpoints":[{"name":"pages-list"}]}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["docs"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual("GET", transport.requests[0].method)
        self.assertEqual("https://wiki.example.com/api/docs.json", transport.requests[0].url)

    def test_docs_html_flag_fetches_html_endpoint(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b"<html>docs</html>")])
        result = run(cli, ["docs", "--html"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"<html>docs</html>\n", result.stdout)
        self.assertEqual("https://wiki.example.com/api/docs", transport.requests[0].url)


class TempFileMixin:
    def write_temp(self, name, content):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        path = Path(directory) / name
        path.write_text(content, encoding="utf-8")
        return str(path)


class PagesTest(TempFileMixin, unittest.TestCase):
    def test_pages_read_gets_single_item(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":42,"name":"Doc"}')])
        result = run(cli, ["pages", "read", "42"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"id":42,"name":"Doc"}\n', result.stdout)
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/pages/42", request.url)
        self.assertIsNone(request.body)

    def test_pages_create_posts_book_page_with_merged_json_body(self):
        cli = load_cli()
        markdown_path = self.write_temp("doc.md", "# Hi\n")
        transport = RecordingTransport([(200, {}, b'{"id":1}')])
        result = run(
            cli,
            [
                "pages", "create",
                "--book-id", "7",
                "--name", "Doc",
                "--markdown", "@" + markdown_path,
                "--priority", "3",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"id":1}\n', result.stdout)
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/pages", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual(
            {
                "book_id": 7,
                "name": "Doc",
                "markdown": "# Hi\n",
                "priority": 3,
            },
            json.loads(request.body),
        )

    def test_pages_create_accepts_literal_html(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":2}')])
        result = run(
            cli,
            ["pages", "create", "--chapter-id", "4", "--html", "<b>x</b>"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {"chapter_id": 4, "html": "<b>x</b>"},
            json.loads(transport.requests[0].body),
        )

    def test_field_flags_override_json_top_level_without_deep_merge(self):
        cli = load_cli()
        body_path = self.write_temp(
            "body.json",
            json.dumps(
                {
                    "book_id": 1,
                    "name": {"nested": True},
                    "tags": [{"name": "team", "value": "docs"}],
                }
            ),
        )
        transport = RecordingTransport([(200, {}, b'{"id":3}')])
        result = run(
            cli,
            ["pages", "create", "--json", "@" + body_path, "--name", "New", "--markdown", "md"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {
                "book_id": 1,
                "name": "New",
                "tags": [{"name": "team", "value": "docs"}],
                "markdown": "md",
            },
            json.loads(transport.requests[0].body),
        )

    def test_json_dash_reads_body_from_stdin(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            ["pages", "create", "--json", "-"],
            stdin=b'{"chapter_id": 9, "markdown": "from stdin"}',
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(
            {"chapter_id": 9, "markdown": "from stdin"},
            json.loads(transport.requests[0].body),
        )

    def test_pages_update_puts_partial_body_without_other_keys(self):
        cli = load_cli()
        markdown_path = self.write_temp("doc.md", "# Updated\n")
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli,
            [
                "pages", "update", "9",
                "--markdown", "@" + markdown_path,
                "--changelog", "rev 2",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/pages/9", request.url)
        self.assertEqual(
            {"markdown": "# Updated\n", "changelog": "rev 2"},
            json.loads(request.body),
        )

    def test_pages_update_moves_page_with_chapter_id(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":9}')])
        result = run(
            cli,
            ["pages", "update", "9", "--chapter-id", "3"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual({"chapter_id": 3}, json.loads(transport.requests[0].body))


if __name__ == "__main__":
    unittest.main()
