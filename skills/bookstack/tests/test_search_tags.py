"""Ticket 05: search all/book/chapter and tags names/values (read-only discovery)."""

import unittest
import urllib.parse

from cli_harness import RecordingTransport, load_cli, run


def parse_query(url):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


class SearchAllTest(unittest.TestCase):
    def test_search_all_gets_api_search_with_raw_query_syntax(self):
        cli = load_cli()
        body = (
            b'{"data":[{"id":1,"name":"Page","type":"page",'
            b'"preview_html":"<strong>Page</strong>"}],"total":1}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "search", "all", "{type:page} hello world",
                "--page", "2",
                "--count", "10",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertIsNone(request.body)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("wiki.example.com", parsed.netloc)
        self.assertEqual("/api/search", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["{type:page} hello world"], query["query"])
        self.assertEqual(["2"], query["page"])
        self.assertEqual(["10"], query["count"])

    def test_search_all_does_not_auto_paginate(self):
        cli = load_cli()
        body = b'{"data":[],"total":42}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            ["search", "all", "hello", "--count", "1"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(1, len(transport.requests))
        self.assertEqual(
            ["1"], parse_query(transport.requests[0].url)["count"]
        )

    def test_search_all_passes_type_and_preview_html_through_untouched(self):
        cli = load_cli()
        body = b'{"data":[{"type":"chapter","preview_html":"<em>a &amp; b</em>"}]}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["search", "all", "a & b"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(
            ["a & b"], parse_query(transport.requests[0].url)["query"]
        )


class SearchScopedTest(unittest.TestCase):
    def test_search_book_targets_book_path(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"data":[]}')])
        result = run(
            cli,
            ["search", "book", "42", "hello there", "--count", "5"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("/api/search/book/42", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["hello there"], query["query"])
        self.assertEqual(["5"], query["count"])

    def test_search_chapter_targets_chapter_path(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"data":[]}')])
        result = run(
            cli,
            ["search", "chapter", "7", "hello", "--page", "3"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        parsed = urllib.parse.urlsplit(transport.requests[0].url)
        self.assertEqual("/api/search/chapter/7", parsed.path)
        self.assertEqual(["3"], urllib.parse.parse_qs(parsed.query)["page"])


class SearchErrorMappingTest(unittest.TestCase):
    def test_search_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["search", "all", "q"], 401, 3),
            (["search", "book", "1", "q"], 403, 3),
            (["search", "chapter", "1", "q"], 404, 4),
            (["search", "all", "q"], 422, 5),
            (["search", "book", "1", "q"], 500, 8),
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


class SearchUsageErrorTest(unittest.TestCase):
    def assert_usage_error(self, argv):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, argv, transport=transport)
        self.assertEqual(2, result.code, "argv=%r stderr=%r" % (argv, result.stderr))
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_search_all_requires_query(self):
        self.assert_usage_error(["search", "all"])

    def test_search_book_and_chapter_require_id_and_query(self):
        self.assert_usage_error(["search", "book"])
        self.assert_usage_error(["search", "book", "42"])
        self.assert_usage_error(["search", "chapter"])
        self.assert_usage_error(["search", "chapter", "42"])

    def test_search_rejects_offset_sort_and_filter(self):
        self.assert_usage_error(["search", "all", "q", "--offset", "5"])
        self.assert_usage_error(["search", "all", "q", "--sort", "name"])
        self.assert_usage_error(["search", "all", "q", "--filter", "name=x"])

    def test_search_rejects_non_integer_page_and_count(self):
        self.assert_usage_error(["search", "all", "q", "--page", "x"])
        self.assert_usage_error(["search", "all", "q", "--count", "many"])

    def test_search_rejects_extra_positional_argument(self):
        self.assert_usage_error(["search", "all", "q", "extra"])
        self.assert_usage_error(["search", "book", "42", "q", "extra"])

    def test_search_rejects_unknown_action(self):
        self.assert_usage_error(["search", "bogus", "q"])


class TagsNamesTest(unittest.TestCase):
    def test_tags_names_passes_listing_parameters_and_name_filter(self):
        cli = load_cli()
        body = (
            b'{"data":[{"name":"status","usages":3,"page_count":2,'
            b'"chapter_count":1,"book_count":0,"shelf_count":0}],"total":1}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "tags", "names",
                "--count", "5",
                "--offset", "10",
                "--sort", "name",
                "--filter", "name:like=%sta%",
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
        self.assertEqual("/api/tags/names", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["name"], query["sort"])
        self.assertEqual(["%sta%"], query["filter[name:like]"])

    def test_tags_names_rejects_value_filter(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli, ["tags", "names", "--filter", "value=active"], transport=transport
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_tags_names_rejects_positional_argument(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["tags", "names", "extra"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class TagsValuesTest(unittest.TestCase):
    def test_tags_values_sends_name_query_param(self):
        cli = load_cli()
        body = b'{"data":[{"name":"active","usages":7}],"total":1}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["tags", "values", "status"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("/api/tags/values-for-name", parsed.path)
        self.assertEqual(["status"], urllib.parse.parse_qs(parsed.query)["name"])

    def test_tags_values_passes_value_filter_and_listing_parameters(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"data":[]}')])
        result = run(
            cli,
            [
                "tags", "values", "status",
                "--filter", "value:like=%act%",
                "--count", "5",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        query = parse_query(transport.requests[0].url)
        self.assertEqual(["status"], query["name"])
        self.assertEqual(["%act%"], query["filter[value:like]"])
        self.assertEqual(["5"], query["count"])

    def test_tags_values_rejects_name_filter(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["tags", "values", "status", "--filter", "name=status"],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)

    def test_tags_values_requires_name(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["tags", "values"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)

    def test_tags_values_rejects_extra_positional_argument(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["tags", "values", "a", "b"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class TagsErrorMappingTest(unittest.TestCase):
    def test_tags_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["tags", "names"], 403, 3),
            (["tags", "values", "status"], 404, 4),
            (["tags", "names"], 422, 5),
            (["tags", "values", "status"], 503, 8),
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


class SearchTagsHelpTest(unittest.TestCase):
    def test_search_resource_help_lists_all_actions(self):
        cli = load_cli()
        result = run(cli, ["search", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for action in ("all", "book", "chapter"):
            self.assertIn(action, text)
        for flag in ("--page", "--count"):
            self.assertIn(flag, text)

    def test_tags_resource_help_lists_actions(self):
        cli = load_cli()
        result = run(cli, ["tags", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for action in ("names", "values"):
            self.assertIn(action, text)

    def test_top_help_lists_search_and_tags_actions(self):
        cli = load_cli()
        result = run(cli, ["--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        self.assertIn("search", text)
        self.assertIn("tags", text)
        for action in ("all", "book", "chapter", "names", "values"):
            self.assertIn(action, text)


if __name__ == "__main__":
    unittest.main()
