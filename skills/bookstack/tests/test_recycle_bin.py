"""Ticket 10: recycle-bin list / restore / destroy.

API facts (research-api.md §6.10):
- GET /api/recycle-bin lists top-level deletions; each item carries a
  deletion id plus a `deletable` relation (with counts or parent info).
- PUT /api/recycle-bin/{deletionId} restores and returns `restore_count`.
- DELETE /api/recycle-bin/{deletionId} destroys permanently (irreversible).

Contract (cli-contract.md §8): only destroy (and users delete) requires
--yes; missing --yes is a usage error: stderr JSON, exit 2, zero HTTP.
"""

import json
import unittest
import urllib.parse

from cli_harness import RecordingTransport, load_cli, run


class RecycleBinListTest(unittest.TestCase):
    def test_list_passes_deletions_through_byte_for_byte(self):
        cli = load_cli()
        body = (
            b'{"data":[{"id":5,"deletable_type":"page","deletable_id":7,'
            b'"deletable":{"id":7,"name":"Old page"}}],"total":1}'
        )
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["recycle-bin", "list"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/recycle-bin", request.url)
        self.assertIsNone(request.body)

    def test_list_passes_listing_parameters_through(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"data":[],"total":0}')])
        result = run(
            cli,
            [
                "recycle-bin", "list",
                "--count", "5",
                "--offset", "10",
                "--sort", "-created_at",
                "--filter", "deletable_type=page",
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        parsed = urllib.parse.urlsplit(transport.requests[0].url)
        self.assertEqual("/api/recycle-bin", parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(["5"], query["count"])
        self.assertEqual(["10"], query["offset"])
        self.assertEqual(["-created_at"], query["sort"])
        self.assertEqual(["page"], query["filter[deletable_type]"])


class RecycleBinRestoreTest(unittest.TestCase):
    def test_restore_puts_deletion_id_and_passes_restore_count_through(self):
        cli = load_cli()
        body = b'{"restore_count":3}'
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["recycle-bin", "restore", "5"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body + b"\n", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("PUT", request.method)
        self.assertEqual("https://wiki.example.com/api/recycle-bin/5", request.url)
        self.assertIsNone(request.body)

    def test_restore_requires_deletion_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["recycle-bin", "restore"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"deletionId", result.stderr)
        self.assertEqual([], transport.requests)


class RecycleBinDestroyTest(unittest.TestCase):
    def test_destroy_without_yes_is_rejected_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["recycle-bin", "destroy", "5"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        payload = json.loads(result.stderr)
        self.assertIn("--yes", payload["error"]["message"])
        self.assertEqual([], transport.requests)

    def test_destroy_with_yes_sends_delete_and_is_silent_on_204(self):
        for argv in (
            ["recycle-bin", "destroy", "5", "--yes"],
            ["recycle-bin", "destroy", "--yes", "5"],
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
                self.assertEqual(
                    "https://wiki.example.com/api/recycle-bin/5", request.url
                )
                self.assertIsNone(request.body)

    def test_destroy_with_yes_still_requires_deletion_id(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["recycle-bin", "destroy", "--yes"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"deletionId", result.stderr)
        self.assertEqual([], transport.requests)


class RecycleBinErrorMappingTest(unittest.TestCase):
    def test_http_errors_map_to_contract_exit_codes(self):
        cases = (
            (["recycle-bin", "list"], 403, 3),
            (["recycle-bin", "restore", "5"], 403, 3),
            (["recycle-bin", "restore", "5"], 404, 4),
            (["recycle-bin", "destroy", "5", "--yes"], 403, 3),
            (["recycle-bin", "destroy", "5", "--yes"], 404, 4),
            (["recycle-bin", "destroy", "5", "--yes"], 500, 8),
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


class RecycleBinHelpTest(unittest.TestCase):
    def test_resource_help_lists_all_actions(self):
        cli = load_cli()
        result = run(cli, ["recycle-bin", "--help"], transport=RecordingTransport())
        self.assertEqual(0, result.code)
        self.assertEqual(b"", result.stderr)
        for action in ("list", "restore", "destroy"):
            self.assertIn(action.encode(), result.stdout)

    def test_restore_help_names_the_deletion_id(self):
        cli = load_cli()
        result = run(
            cli, ["recycle-bin", "restore", "--help"], transport=RecordingTransport()
        )
        self.assertEqual(0, result.code)
        self.assertIn(b"<deletionId>", result.stdout)
        self.assertIn(b"PUT /api/recycle-bin", result.stdout)

    def test_destroy_help_documents_yes_and_irreversibility(self):
        cli = load_cli()
        result = run(
            cli, ["recycle-bin", "destroy", "--help"], transport=RecordingTransport()
        )
        self.assertEqual(0, result.code)
        self.assertIn(b"DELETE /api/recycle-bin", result.stdout)
        self.assertIn(b"--yes", result.stdout)
        self.assertIn(b"irreversible", result.stdout)
        self.assertIn(b"dry-run", result.stdout)


if __name__ == "__main__":
    unittest.main()
