"""Ticket 11: content-permissions read / update.

API facts (research-api.md §6.7):
- GET /api/content-permissions/{contentType}/{contentId}
- contentType is one of page / book / chapter / bookshelf
- PUT replaces the whole override block: owner_id, role_permissions and
  fallback_permissions; an empty role_permissions array clears the existing
  settings and omitted blocks are left untouched (no deep merge).
- The override returned by read is not the inherited permission set; its
  fallback_permissions may be null and must pass through untouched.

Contract (cli-contract.md §3): non-CRUD exception with two positional args,
<type> <id>. §4: --json @file|- is the whole body and field flags override
same-named top-level keys. Invalid type is a usage error: exit 2, zero HTTP.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from cli_harness import RecordingTransport, load_cli, run


def write_temp(test, name, content):
    directory = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, directory)
    path = Path(directory) / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def request_json(request):
    return json.loads(request.body.decode("utf-8"))


class ContentPermissionsReadTest(unittest.TestCase):
    def test_read_targets_type_and_id_path_and_passes_body_through(self):
        cli = load_cli()
        body = (
            b'{"owner_id":3,"role_permissions":[{"role_id":1,"view":true}],'
            b'"fallback_permissions":null}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            ["content-permissions", "read", "page", "7"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual(
            "https://wiki.example.com/api/content-permissions/page/7", request.url
        )
        self.assertIsNone(request.body)

    def test_read_accepts_all_four_content_types(self):
        for content_type in ("page", "book", "chapter", "bookshelf"):
            with self.subTest(content_type=content_type):
                cli = load_cli()
                transport = RecordingTransport([(200, {}, b"{}")])
                result = run(
                    cli,
                    ["content-permissions", "read", content_type, "12"],
                    transport=transport,
                )
                self.assertEqual(0, result.code, result.stderr)
                self.assertEqual(
                    "https://wiki.example.com/api/content-permissions/%s/12"
                    % content_type,
                    transport.requests[0].url,
                )

    def test_read_invalid_type_is_a_usage_error_without_http(self):
        for content_type in ("pages", "shelf", "user", "PAGE"):
            with self.subTest(content_type=content_type):
                cli = load_cli()
                transport = RecordingTransport()
                result = run(
                    cli,
                    ["content-permissions", "read", content_type, "7"],
                    transport=transport,
                )
                self.assertEqual(2, result.code)
                self.assertEqual(b"", result.stdout)
                self.assertIn(b"usage", result.stderr.lower())
                self.assertEqual([], transport.requests)

    def test_read_requires_type_and_id(self):
        for argv in (
            ["content-permissions", "read"],
            ["content-permissions", "read", "page"],
            ["content-permissions", "read", "page", "7", "extra"],
        ):
            with self.subTest(argv=argv):
                cli = load_cli()
                transport = RecordingTransport()
                result = run(cli, argv, transport=transport)
                self.assertEqual(2, result.code, "argv=%r" % argv)
                self.assertEqual(b"", result.stdout)
                self.assertEqual([], transport.requests)


class ContentPermissionsUpdateTest(unittest.TestCase):
    def test_update_puts_the_whole_body_from_field_flags(self):
        cli = load_cli()
        role_permissions = [
            {
                "role_id": 2,
                "view": True,
                "create": False,
                "update": False,
                "delete": False,
            }
        ]
        fallback = {
            "inheriting": False,
            "view": True,
            "create": False,
            "update": False,
            "delete": False,
        }
        transport = RecordingTransport([(200, {}, b'{"owner_id":5}')])
        result = run(
            cli,
            [
                "content-permissions", "update", "book", "9",
                "--owner-id", "5",
                "--role-permissions", json.dumps(role_permissions),
                "--fallback-permissions", json.dumps(fallback),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"owner_id":5}\n', result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual(
            "https://wiki.example.com/api/content-permissions/book/9", request.url
        )
        self.assertEqual(
            {
                "owner_id": 5,
                "role_permissions": role_permissions,
                "fallback_permissions": fallback,
            },
            request_json(request),
        )

    def test_empty_role_permissions_array_is_passed_through_to_clear(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b"{}")])
        result = run(
            cli,
            [
                "content-permissions", "update", "chapter", "3",
                "--role-permissions", "[]",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual({"role_permissions": []}, request_json(transport.requests[0]))

    def test_null_fallback_permissions_is_passed_through_untouched(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b"{}")])
        result = run(
            cli,
            [
                "content-permissions", "update", "bookshelf", "4",
                "--fallback-permissions", "null",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"fallback_permissions": None}, request_json(transport.requests[0])
        )

    def test_json_file_body_with_field_flags_overriding_top_level(self):
        cli = load_cli()
        path = write_temp(
            self,
            "perms.json",
            '{"owner_id":1,"role_permissions":[{"role_id":8}],'
            '"fallback_permissions":{"inheriting":true}}',
        )
        transport = RecordingTransport([(200, {}, b"{}")])
        result = run(
            cli,
            [
                "content-permissions", "update", "page", "7",
                "--json", "@" + path,
                "--owner-id", "9",
                "--role-permissions", "[]",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {
                "owner_id": 9,
                "role_permissions": [],
                "fallback_permissions": {"inheriting": True},
            },
            request_json(transport.requests[0]),
        )

    def test_json_stdin_body_is_supported(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b"{}")])
        result = run(
            cli,
            ["content-permissions", "update", "book", "2", "--json", "-"],
            stdin=b'{"owner_id":4}',
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual({"owner_id": 4}, request_json(transport.requests[0]))

    def test_update_invalid_type_is_a_usage_error_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["content-permissions", "update", "pages", "7", "--owner-id", "1"],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)

    def test_update_requires_type_and_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["content-permissions", "update", "page", "--owner-id", "1"],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)


class ContentPermissionsErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["content-permissions", "read", "page", "7"], 401, 3),
            (["content-permissions", "read", "page", "7"], 403, 3),
            (
                ["content-permissions", "update", "page", "7", "--owner-id", "1"],
                401,
                3,
            ),
            (["content-permissions", "read", "book", "7"], 404, 4),
            (
                ["content-permissions", "update", "book", "7", "--owner-id", "1"],
                404,
                4,
            ),
            (
                ["content-permissions", "update", "chapter", "7", "--owner-id", "1"],
                422,
                5,
            ),
            (["content-permissions", "read", "bookshelf", "7"], 500, 8),
            (
                ["content-permissions", "update", "book", "7", "--owner-id", "1"],
                503,
                8,
            ),
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


class ContentPermissionsHelpTest(unittest.TestCase):
    def test_resource_help_lists_actions_and_positional_args(self):
        cli = load_cli()
        result = run(
            cli,
            ["content-permissions", "--help"],
            transport=RecordingTransport(),
        )
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stderr)
        text = result.stdout.decode("utf-8")
        for needle in ("read", "update", "<type>", "<id>"):
            self.assertIn(needle, text)

    def test_read_help_lists_allowed_content_types(self):
        cli = load_cli()
        result = run(
            cli,
            ["content-permissions", "read", "--help"],
            transport=RecordingTransport(),
        )
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for content_type in ("page", "book", "chapter", "bookshelf"):
            self.assertIn(content_type, text)

    def test_update_help_lists_json_and_body_flags(self):
        cli = load_cli()
        result = run(
            cli,
            ["content-permissions", "update", "--help"],
            transport=RecordingTransport(),
        )
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        for flag in (
            "--json",
            "--owner-id",
            "--role-permissions",
            "--fallback-permissions",
        ):
            self.assertIn(flag, text)

    def test_read_help_names_the_endpoint(self):
        cli = load_cli()
        result = run(
            cli,
            ["content-permissions", "read", "--help"],
            transport=RecordingTransport(),
        )
        self.assertEqual(0, result.code)
        self.assertIn(b"GET /api/content-permissions", result.stdout)


if __name__ == "__main__":
    unittest.main()
