"""Ticket 16: every request identifies as bookstack-api-cli (WAF blocks urllib default)."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cli_harness import RecordingTransport, load_cli, run

EXPECTED_USER_AGENT = "bookstack-api-cli/1.0"


class UserAgentTest(unittest.TestCase):
    def assert_user_agent(self, request):
        self.assertEqual(EXPECTED_USER_AGENT, request.headers["User-Agent"])

    def test_bodiless_request_carries_user_agent(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"version":"v24.05"}')])
        result = run(cli, ["system"], transport=transport)
        self.assertEqual(0, result.code)
        self.assert_user_agent(transport.requests[0])

    def test_multipart_upload_carries_user_agent(self):
        cli = load_cli()
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        path = Path(directory) / "spec.pdf"
        path.write_bytes(b"%PDF-1.4\n")
        transport = RecordingTransport([(200, {}, b'{"id":7}')])
        result = run(
            cli,
            [
                "attachments", "create",
                "--uploaded-to", "5",
                "--name", "Spec PDF",
                "--file", "@" + str(path),
            ],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        request = transport.requests[0]
        self.assertTrue(
            request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
        )
        self.assert_user_agent(request)

    def test_stream_request_carries_user_agent(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b"%PDF-1.4\n")])
        result = run(
            cli,
            ["pages", "export", "42", "--format", "pdf"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assert_user_agent(transport.requests[0])

    def test_auth_check_carries_user_agent(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"version":"v24.05"}')])
        result = run(cli, ["auth", "check"], transport=transport)
        self.assertEqual(0, result.code)
        self.assert_user_agent(transport.requests[0])

    def test_every_retry_attempt_carries_user_agent(self):
        cli = load_cli()
        transport = RecordingTransport(
            [
                (429, {}, b'{"error":{"code":429,"message":"Too Many Attempts."}}'),
                (200, {}, b'{"ok":true}'),
            ]
        )
        with mock.patch("time.sleep"):
            result = run(cli, ["system"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(2, len(transport.requests))
        for request in transport.requests:
            self.assert_user_agent(request)


if __name__ == "__main__":
    unittest.main()
