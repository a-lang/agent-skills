"""Ticket 14: users list / create / read / update / delete.

API facts (research-api.md §6.15):
- GET /api/users lists users with the standard listing parameters.
- POST /api/users creates a user; ``name`` (min:1, max:100) and ``email``
  (unique) are required; ``password`` (min:8), ``send_invite`` (boolean),
  ``roles`` (integer array), ``language`` (max:15) and ``external_auth_id``
  are optional.
- GET /api/users/{id} reads one user.
- PUT /api/users/{id} updates a user; same fields as create but all optional
  and without ``send_invite``.
- DELETE /api/users/{id} deletes a user; an optional
  ``migrate_ownership_id`` query parameter transfers their content to
  another user first.

Contract (cli-contract.md §2-§8): the standard list/create/read/update/
delete mapping applies; field flags override --json top-level keys without
deep merge; users delete requires --yes (missing -> stderr JSON, exit 2,
zero HTTP); 401/403 map to 3, 404 to 4, 422 to 5, 5xx to 8, usage errors to
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


class UsersListTest(unittest.TestCase):
    def test_list_passes_standard_listing_parameters_and_response_through(self):
        cli = load_cli()
        body = b'{"data":[{"id":4,"name":"Barry Scott"}],"total":1}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "users", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "name:like=%barry%",
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
        self.assertEqual("/api/users", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["%barry%"], query["filter[name:like]"])
        self.assertIsNone(request.body)


class UsersCreateTest(unittest.TestCase):
    def test_create_posts_all_optional_fields_and_passes_response_through(self):
        cli = load_cli()
        body = (
            b'{"id":4,"name":"Barry Scott","email":"barry@example.com",'
            b'"external_auth_id":"saml-barry","language":"en",'
            b'"roles":[{"id":1,"display_name":"Admin"}]}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "users", "create",
                "--name", "Barry Scott",
                "--email", "barry@example.com",
                "--password", "hunter2secret",
                "--send-invite", "true",
                "--roles", "1,2",
                "--language", "en",
                "--external-auth-id", "saml-barry",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("POST", request.method)
        self.assertEqual("https://wiki.example.com/api/users", request.url)
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual(
            {
                "name": "Barry Scott",
                "email": "barry@example.com",
                "password": "hunter2secret",
                "send_invite": True,
                "roles": [1, 2],
                "language": "en",
                "external_auth_id": "saml-barry",
            },
            json.loads(request.body.decode("utf-8")),
        )

    def test_create_with_only_required_fields_sends_only_name_and_email(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            ["users", "create", "--name", "Barry", "--email", "barry@example.com"],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"name": "Barry", "email": "barry@example.com"},
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_create_false_send_invite_is_sent_as_false(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            [
                "users", "create",
                "--name", "Barry",
                "--email", "barry@example.com",
                "--send-invite", "false",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {
                "name": "Barry",
                "email": "barry@example.com",
                "send_invite": False,
            },
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_create_missing_name_or_email_is_rejected_without_http(self):
        cases = (
            (["users", "create", "--email", "barry@example.com"], "--name"),
            (["users", "create", "--name", "Barry"], "--email"),
        )
        for argv, missing in cases:
            with self.subTest(argv=argv):
                cli = load_cli()
                transport = RecordingTransport()
                result = run(cli, argv, transport=transport)
                self.assertEqual(2, result.code)
                self.assertEqual(b"", result.stdout)
                self.assertIn(missing.encode(), result.stderr)
                self.assertEqual([], transport.requests)

    def test_create_reads_the_body_from_json_with_flag_override(self):
        cli = load_cli()
        opts = write_temp(
            self, "user.json", '{"name":"Barry","email":"barry@example.com"}'
        )
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            [
                "users", "create",
                "--json", "@" + str(opts),
                "--email", "overridden@example.com",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"name": "Barry", "email": "overridden@example.com"},
            json.loads(transport.requests[0].body.decode("utf-8")),
        )


class UsersReadTest(unittest.TestCase):
    def test_read_gets_the_user_and_passes_it_through(self):
        cli = load_cli()
        body = b'{"id":4,"name":"Barry Scott","email":"barry@example.com"}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["users", "read", "4"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/users/4", request.url)
        self.assertIsNone(request.body)

    def test_read_requires_the_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["users", "read"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class UsersUpdateTest(unittest.TestCase):
    def test_update_puts_a_partial_body(self):
        cli = load_cli()
        body = b'{"id":4,"name":"Barry S."}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli, ["users", "update", "4", "--name", "Barry S."], transport=transport
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/users/4", request.url)
        self.assertEqual(
            {"name": "Barry S."},
            json.loads(request.body.decode("utf-8")),
        )

    def test_update_accepts_roles_as_an_integer_array(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"id":4}')])
        result = run(
            cli,
            ["users", "update", "4", "--roles", "4, 5"],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            {"roles": [4, 5]},
            json.loads(transport.requests[0].body.decode("utf-8")),
        )

    def test_update_rejects_send_invite_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["users", "update", "4", "--send-invite", "true"],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_update_requires_the_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["users", "update", "--name", "Barry"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class UsersDeleteTest(unittest.TestCase):
    def test_delete_without_yes_is_rejected_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["users", "delete", "4"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        payload = json.loads(result.stderr)
        self.assertIn("--yes", payload["error"]["message"])
        self.assertEqual([], transport.requests)

    def test_delete_without_yes_is_rejected_even_with_migrate_flag(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["users", "delete", "4", "--migrate-ownership-id", "7"],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)

    def test_delete_with_yes_sends_delete_and_is_silent_on_204(self):
        for argv in (
            ["users", "delete", "4", "--yes"],
            ["users", "delete", "--yes", "4"],
        ):
            with self.subTest(argv=argv):
                cli = load_cli()
                transport = RecordingTransport([(204, {}, b"")])
                result = run(cli, argv, transport=transport)
                self.assertEqual(0, result.code, result.stderr)
                self.assertEqual(b"", result.stdout)
                self.assertEqual(b"", result.stderr)
                self.assertEqual(1, len(transport.requests))
                request = transport.requests[0]
                self.assertEqual("DELETE", request.method)
                self.assertEqual("https://wiki.example.com/api/users/4", request.url)
                self.assertIsNone(request.body)

    def test_delete_with_yes_passes_migrate_ownership_id_as_query(self):
        cli = load_cli()
        transport = RecordingTransport([(204, {}, b"")])
        result = run(
            cli,
            [
                "users", "delete", "4",
                "--migrate-ownership-id", "7",
                "--yes",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("DELETE", request.method)
        parsed = urllib.parse.urlsplit(request.url)
        self.assertEqual("/api/users/4", parsed.path)
        self.assertEqual(
            {"migrate_ownership_id": ["7"]}, urllib.parse.parse_qs(parsed.query)
        )
        self.assertIsNone(request.body)

    def test_delete_rejects_a_non_integer_migrate_id_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["users", "delete", "4", "--migrate-ownership-id", "seven", "--yes"],
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_delete_with_yes_still_requires_the_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["users", "delete", "--yes"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"<id>", result.stderr)
        self.assertEqual([], transport.requests)


class UsersErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["users", "list"], 401, 3),
            (["users", "list"], 403, 3),
            (["users", "read", "4"], 404, 4),
            (
                ["users", "create", "--name", "Barry", "--email", "b@example.com"],
                422,
                5,
            ),
            (["users", "update", "4", "--name", "Barry"], 422, 5),
            (["users", "delete", "4", "--yes"], 404, 4),
            (["users", "delete", "4", "--yes"], 500, 8),
            (["users", "list"], 503, 8),
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


class UsersHelpTest(unittest.TestCase):
    def test_resource_help_lists_all_actions(self):
        cli = load_cli()
        result = run(cli, ["users", "--help"], env={})
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stderr)
        text = result.stdout.decode("utf-8")
        for action in ("list", "create", "read", "update", "delete"):
            self.assertIn(action, text)

    def test_create_help_lists_flags_and_required_name_email(self):
        cli = load_cli()
        result = run(cli, ["users", "create", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        self.assertIn("POST /api/users", text)
        self.assertIn("--name TEXT", text)
        self.assertIn("--email TEXT", text)
        for flag in (
            "--password",
            "--send-invite",
            "--roles",
            "--language",
            "--external-auth-id",
        ):
            self.assertIn(flag, text)

    def test_delete_help_documents_yes_and_migrate_ownership(self):
        cli = load_cli()
        result = run(cli, ["users", "delete", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        self.assertIn("DELETE /api/users", text)
        self.assertIn("--migrate-ownership-id", text)
        self.assertIn("--yes", text)
        self.assertIn("irreversible", text)
        self.assertIn("dry-run", text)


if __name__ == "__main__":
    unittest.main()
