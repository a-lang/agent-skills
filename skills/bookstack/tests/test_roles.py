"""Ticket 13: roles list / create / read / update / delete.

API facts (research-api.md §6.11):
- GET /api/roles lists roles with the standard listing parameters.
- POST /api/roles creates a role; ``display_name`` is required (min:3,
  max:180); ``description`` (max:180), ``mfa_enforced`` (boolean),
  ``external_auth_id`` (max:180) and ``permissions`` (string array) are
  optional.
- GET /api/roles/{id} reads one role.
- PUT /api/roles/{id} updates a role; an empty ``permissions`` array clears
  the stored permissions (no deep merge).
- DELETE /api/roles/{id} removes a role (204, no output).

Contract (cli-contract.md §2-§8): the standard list/create/read/update/
delete mapping applies; field flags override --json top-level keys without
deep merge; 401/403 map to 3, 404 to 4, 422 to 5, 5xx to 8, usage errors to
2 with zero HTTP.
"""

import json
import shutil
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from cli_harness import RecordingTransport, load_cli, run


def write_temp(test, name, content):
    directory = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, directory)
    path = Path(directory) / name
    path.write_text(content, encoding="utf-8")
    return path


class RolesListTest(unittest.TestCase):
    def test_list_passes_standard_listing_parameters_and_response_through(self):
        cli = load_cli()
        body = b'{"data":[{"id":4,"display_name":"Editor"}],"total":1}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "roles", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-display_name",
                "--filter", "display_name:like=%ed%",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("wiki.example.com", parsed.netloc)
        self.assertEqual("/api/roles", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-display_name"], query["sort"])
        self.assertEqual(["%ed%"], query["filter[display_name:like]"])
        self.assertIsNone(request.body)


class RolesCreateTest(unittest.TestCase):
    def test_create_posts_all_optional_fields_and_passes_response_through(self):
        cli = load_cli()
        body = (
            b'{"id":4,"display_name":"Editor","description":"Can edit",'
            b'"mfa_enforced":true,"external_auth_id":"saml-editor",'
            b'"permissions":["book-view-all","book-update-all"]}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "roles", "create",
                "--display-name", "Editor",
                "--description", "Can edit",
                "--mfa-enforced", "true",
                "--external-auth-id", "saml-editor",
                "--permissions", "book-view-all,book-update-all",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/roles", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual(
            {
                "display_name": "Editor",
                "description": "Can edit",
                "mfa_enforced": True,
                "external_auth_id": "saml-editor",
                "permissions": ["book-view-all", "book-update-all"],
            },
            json.loads(request.body.decode("utf-8")),
        )

    def test_create_with_only_display_name_sends_only_that_field(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli, ["roles", "create", "--display-name", "Editor"], transport=transport
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"display_name": "Editor"},
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_create_empty_permissions_flag_sends_an_empty_array(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            ["roles", "create", "--display-name", "Auditor", "--permissions", ""],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"display_name": "Auditor", "permissions": []},
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_create_false_boolean_is_sent_as_false(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            ["roles", "create", "--display-name", "Editor", "--mfa-enforced", "false"],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"display_name": "Editor", "mfa_enforced": False},
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_create_reads_the_body_from_json_with_flag_override(self):
        cli = load_cli()
        opts = write_temp(self, "role.json", '{"display_name":"Editor","description":"x"}')
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            [
                "roles", "create",
                "--json", "@" + str(opts),
                "--description", "overridden",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"display_name": "Editor", "description": "overridden"},
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_create_requires_display_name_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["roles", "create", "--description", "x"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_create_rejects_a_non_boolean_mfa_flag_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["roles", "create", "--display-name", "Editor", "--mfa-enforced", "yes"],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)


class RolesReadTest(unittest.TestCase):
    def test_read_gets_the_role_and_passes_it_through(self):
        cli = load_cli()
        body = b'{"id":4,"display_name":"Editor","permissions":["book-view-all"]}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["roles", "read", "4"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/roles/4", request.url)
        self.assertIsNone(request.body)

    def test_read_requires_the_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["roles", "read"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class RolesUpdateTest(unittest.TestCase):
    def test_update_with_empty_permissions_clears_them(self):
        cli = load_cli()
        body = b'{"id":4,"permissions":[]}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            ["roles", "update", "4", "--permissions", ""],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/roles/4", request.url)
        self.assertEqual(
            {"permissions": []},
            json.loads(request.body.decode("utf-8")),
        )

    def test_update_without_permissions_does_not_touch_them(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            ["roles", "update", "4", "--description", "New description"],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        payload = json.loads(transport.requests[0].body.decode("utf-8"))
        self.assertEqual({"description": "New description"}, payload)
        self.assertNotIn("permissions", payload)

    def test_update_replaces_the_permissions_array_as_a_whole(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            [
                "roles", "update", "4",
                "--permissions", "book-view-all,restrictions-manage-all",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {
                "permissions": ["book-view-all", "restrictions-manage-all"],
            },
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_update_field_flag_overrides_json_permissions(self):
        cli = load_cli()
        opts = write_temp(
            self, "role.json", '{"display_name":"Editor","permissions":["book-view-all"]}'
        )
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            ["roles", "update", "4", "--json", "@" + str(opts), "--permissions", ""],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"display_name": "Editor", "permissions": []},
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_update_requires_the_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli, ["roles", "update", "--permissions", ""], transport=transport
        )
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class RolesDeleteTest(unittest.TestCase):
    def test_delete_sends_delete_and_is_silent_on_204(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(cli, ["roles", "delete", "4"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("DELETE", request.method)
        self.assertEqual("https://wiki.example.com/api/roles/4", request.url)
        self.assertIsNone(request.body)

    def test_delete_requires_the_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["roles", "delete"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class RolesErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["roles", "create", "--display-name", "Editor"], 403, 3),
            (["roles", "list"], 401, 3),
            (["roles", "read", "4"], 404, 4),
            (["roles", "delete", "4"], 404, 4),
            (["roles", "update", "4", "--permissions", ""], 422, 5),
            (["roles", "list"], 500, 8),
            (["roles", "read", "4"], 503, 8),
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


class RolesHelpTest(unittest.TestCase):
    def test_resource_help_lists_all_actions(self):
        cli = load_cli()
        result = run(cli, ["roles", "--help"], env={})
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stderr)
        text = result.stdout.decode("utf-8")
        for action in ("list", "create", "read", "update", "delete"):
            self.assertIn(action, text)

    def test_create_help_lists_flags_and_required_display_name(self):
        cli = load_cli()
        result = run(cli, ["roles", "create", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        self.assertIn("POST /api/roles", text)
        self.assertIn("--display-name TEXT", text)
        for flag in (
            "--description",
            "--mfa-enforced",
            "--external-auth-id",
            "--permissions",
        ):
            self.assertIn(flag, text)


if __name__ == "__main__":
    unittest.main()
