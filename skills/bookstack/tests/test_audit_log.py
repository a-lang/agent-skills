"""Ticket 15: audit-log list (final ticket; completes the 16-resource table).

API facts (research-api.md §6.16):
- GET /api/audit-log lists audit log entries with the standard listing
  parameters (count/offset/sort/filter) via the shared apiListingResponse.
- Reading the audit log requires both the manage-users and manage-settings
  permissions; a missing-permission 403 must surface as exit 3.

Contract (cli-contract.md §2-§8): list is a plain listing passthrough;
{data, total} goes to stdout byte-for-byte; HTTP errors map to the contract
exit codes (401/403 -> 3, 404 -> 4, 422 -> 5, 5xx -> 8) with the raw error
JSON on stderr; usage errors exit 2 with zero HTTP. audit-log is the last
resource, so top-level --help must list all 16 resources with no
"(not implemented yet)" leftover.
"""

import unittest
import urllib.parse

from cli_harness import RecordingTransport, load_cli, run

PERMISSION_403 = (
    b'{"error":{"code":403,"message":"You need the Users-Manage and '
    b'Settings-Manage permissions to access this"}}'
)


class AuditLogListTest(unittest.TestCase):
    def test_list_passes_standard_listing_parameters_and_response_through(self):
        cli = load_cli()
        body = (
            b'{"data":[{"id":1,"user_id":4,"loggable_type":"page",'
            b'"loggable_id":9,"action":"page_update"}],"total":1}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(
            cli,
            [
                "audit-log", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "user_id=4",
                "--filter", "action:like=%page%",
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
        self.assertEqual("/api/audit-log", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["4"], query["filter[user_id]"])
        self.assertEqual(["%page%"], query["filter[action:like]"])
        self.assertIsNone(request.body)

    def test_list_without_flags_hits_the_plain_endpoint(self):
        cli = load_cli()
        body = b'{"data":[],"total":0}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["audit-log", "list"], transport=transport)
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        self.assertEqual(
            "https://wiki.example.com/api/audit-log", transport.requests[0].url
        )


class AuditLogErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["audit-log", "list"], 401, 3),
            (["audit-log", "list"], 403, 3),
            (["audit-log", "list"], 404, 4),
            (["audit-log", "list"], 422, 5),
            (["audit-log", "list"], 500, 8),
            (["audit-log", "list"], 503, 8),
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

    def test_403_permission_error_json_passes_through_on_stderr(self):
        cli = load_cli()
        transport = RecordingTransport([(403, {}, PERMISSION_403)])
        result = run(cli, ["audit-log", "list"], transport=transport)
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(PERMISSION_403, result.stderr)


class AuditLogUsageTest(unittest.TestCase):
    def test_unknown_action_is_a_usage_error_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["audit-log", "read", "1"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"usage", result.stderr.lower())
        self.assertEqual([], transport.requests)

    def test_unexpected_positional_argument_is_a_usage_error(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["audit-log", "list", "extra"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)


class AuditLogHelpTest(unittest.TestCase):
    def test_resource_help_lists_the_list_action(self):
        cli = load_cli()
        result = run(cli, ["audit-log", "--help"], env={})
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stderr)
        text = result.stdout.decode("utf-8")
        self.assertIn("list", text)
        self.assertIn("GET /api/audit-log", text)

    def test_action_help_lists_listing_flags(self):
        cli = load_cli()
        result = run(cli, ["audit-log", "list", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        self.assertIn("GET /api/audit-log", text)
        for flag in ("--count", "--offset", "--sort", "--filter"):
            self.assertIn(flag, text)


class TopHelpCompleteTest(unittest.TestCase):
    def test_top_help_has_no_not_implemented_leftovers(self):
        cli = load_cli()
        result = run(cli, ["--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        self.assertNotIn("not implemented yet", text)
        self.assertIn("audit-log", text)


if __name__ == "__main__":
    unittest.main()