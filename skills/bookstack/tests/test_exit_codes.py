"""Exit code matrix (0/2/3/4/5/6/7/8), usage errors and --help text."""

import json
import shutil
import tempfile
import unittest
import urllib.error
from pathlib import Path

from cli_harness import RecordingTransport, load_cli, run

ERROR_BODY = b'{"error":{"code":401,"message":"No authorization token found"}}'

RESOURCES = (
    "pages",
    "chapters",
    "books",
    "shelves",
    "attachments",
    "comments",
    "image-gallery",
    "imports",
    "recycle-bin",
    "roles",
    "users",
    "search",
    "tags",
    "system",
    "audit-log",
    "content-permissions",
)


class HttpErrorMappingTest(unittest.TestCase):
    def system_with_status(self, status):
        cli = load_cli()
        transport = RecordingTransport([(status, {}, ERROR_BODY)])
        return run(cli, ["system"], transport=transport)

    def test_401_and_403_map_to_3(self):
        for status in (401, 403):
            with self.subTest(status=status):
                result = self.system_with_status(status)
                self.assertEqual(3, result.code)
                self.assertEqual(b"", result.stdout)
                self.assertEqual(ERROR_BODY, result.stderr)

    def test_404_maps_to_4(self):
        result = self.system_with_status(404)
        self.assertEqual(4, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(ERROR_BODY, result.stderr)

    def test_422_maps_to_5(self):
        result = self.system_with_status(422)
        self.assertEqual(5, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(ERROR_BODY, result.stderr)

    def test_unlisted_4xx_maps_to_5(self):
        for status in (400, 409, 418):
            with self.subTest(status=status):
                result = self.system_with_status(status)
                self.assertEqual(5, result.code)
                self.assertEqual(b"", result.stdout)
                self.assertEqual(ERROR_BODY, result.stderr)

    def test_5xx_maps_to_8(self):
        for status in (500, 503):
            with self.subTest(status=status):
                result = self.system_with_status(status)
                self.assertEqual(8, result.code)
                self.assertEqual(b"", result.stdout)
                self.assertEqual(ERROR_BODY, result.stderr)

    def test_network_error_maps_to_7(self):
        cli = load_cli()
        transport = RecordingTransport([urllib.error.URLError("connection refused")])
        result = run(cli, ["system"], transport=transport)
        self.assertEqual(7, result.code)
        self.assertEqual(b"", result.stdout)
        payload = json.loads(result.stderr)
        self.assertIn("connection refused", payload["error"]["message"])

    def test_timeout_maps_to_7(self):
        cli = load_cli()
        transport = RecordingTransport([TimeoutError("timed out")])
        result = run(cli, ["system"], transport=transport)
        self.assertEqual(7, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"timed out", result.stderr)

    def test_missing_env_exits_3_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["system"], env={}, transport=transport)
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn("BOOKSTACK_URL", json.loads(result.stderr)["error"]["message"])
        self.assertEqual([], transport.requests)


class UsageErrorTest(unittest.TestCase):
    def write_temp(self, name, content):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        path = Path(directory) / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def assert_usage_error(self, argv, env=None):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, argv, env=env, transport=transport)
        self.assertEqual(2, result.code, "argv=%r stderr=%r" % (argv, result.stderr))
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)
        return result

    def test_unknown_resource(self):
        self.assert_usage_error(["widgets", "list"])

    def test_auth_is_not_a_resource(self):
        self.assert_usage_error(["auth", "status"])

    def test_unknown_action(self):
        self.assert_usage_error(["pages", "archive", "1"])

    def test_missing_action(self):
        self.assert_usage_error(["pages"])

    def test_no_arguments(self):
        self.assert_usage_error([])

    def test_system_rejects_actions(self):
        self.assert_usage_error(["system", "list"])

    def test_pages_create_parent_flags_are_exclusive(self):
        self.assert_usage_error(
            ["pages", "create", "--book-id", "1", "--chapter-id", "2", "--markdown", "x"]
        )

    def test_pages_create_requires_a_parent(self):
        self.assert_usage_error(["pages", "create", "--markdown", "x"])

    def test_pages_create_content_flags_are_exclusive(self):
        self.assert_usage_error(
            ["pages", "create", "--book-id", "1", "--html", "a", "--markdown", "b"]
        )

    def test_pages_create_requires_content(self):
        self.assert_usage_error(["pages", "create", "--book-id", "1"])

    def test_pages_update_parent_flags_are_exclusive(self):
        self.assert_usage_error(["pages", "update", "5", "--book-id", "1", "--chapter-id", "2"])

    def test_unknown_flag(self):
        self.assert_usage_error(["pages", "read", "5", "--bogus"])

    def test_flag_requires_value(self):
        self.assert_usage_error(["pages", "create", "--book-id"])

    def test_integer_flag_rejects_non_number(self):
        self.assert_usage_error(
            ["pages", "create", "--book-id", "x", "--markdown", "m"]
        )

    def test_tags_flag_rejects_invalid_json(self):
        self.assert_usage_error(
            ["pages", "create", "--book-id", "1", "--markdown", "m", "--tags", "not-json"]
        )

    def test_filter_requires_key_equals_value(self):
        self.assert_usage_error(["books", "list", "--filter", "name"])

    def test_unexpected_positional_argument(self):
        self.assert_usage_error(
            ["pages", "create", "--book-id", "1", "--markdown", "m", "extra"]
        )

    def test_pages_read_requires_id(self):
        self.assert_usage_error(["pages", "read"])

    def test_json_missing_file(self):
        self.assert_usage_error(
            ["pages", "create", "--json", "@/nonexistent/body.json"]
        )

    def test_json_invalid_payload(self):
        path = self.write_temp("bad.json", "{not json")
        self.assert_usage_error(["pages", "create", "--json", "@" + path])

    def test_json_inline_literal_is_rejected(self):
        self.assert_usage_error(["pages", "create", "--json", '{"book_id":1}'])

    def test_content_file_missing(self):
        self.assert_usage_error(
            ["pages", "create", "--book-id", "1", "--markdown", "@/nonexistent/doc.md"]
        )

    def test_docs_unknown_flag(self):
        self.assert_usage_error(["docs", "--bogus"])

    def test_auth_unknown_command(self):
        self.assert_usage_error(["-auth", "bogus"])

    def test_auth_extra_argument(self):
        self.assert_usage_error(["-auth", "status", "extra"])

    def test_json_non_object_body(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["pages", "create", "--json", "-"],
            stdin=b'[{"book_id":1}]',
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)


class HelpTest(unittest.TestCase):
    def test_top_help_lists_all_resources_and_auth(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["--help"], env={}, transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stderr)
        text = result.stdout.decode("utf-8")
        for resource in RESOURCES:
            self.assertIn(resource, text)
        self.assertIn("-auth", text)
        self.assertIn("docs", text)
        self.assertEqual([], transport.requests)

    def test_top_help_documents_exit_codes(self):
        cli = load_cli()
        result = run(cli, ["--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        self.assertIn("exit codes:", text)
        for line in (
            "0  success",
            "2  usage",
            "3  authentication",
            "4  not found",
            "5  client error",
            "6  rate limit",
            "7  network",
            "8  server error",
        ):
            self.assertIn(line, text)

    def test_resource_help_lists_actions(self):
        cli = load_cli()
        result = run(cli, ["pages", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for action in ("create", "read", "update"):
            self.assertIn(action, text)

    def test_action_help_lists_flags(self):
        cli = load_cli()
        result = run(cli, ["pages", "create", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for flag in ("--json", "--name", "--book-id", "--chapter-id", "--html", "--markdown"):
            self.assertIn(flag, text)

    def test_system_and_docs_and_auth_help(self):
        cli = load_cli()
        for argv, needle in (
            (["system", "--help"], "/api/system"),
            (["docs", "--help"], "/api/docs.json"),
            (["-auth", "--help"], "login"),
        ):
            with self.subTest(argv=argv):
                result = run(cli, argv, env={})
                self.assertEqual(0, result.code)
                self.assertIn(needle, result.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
