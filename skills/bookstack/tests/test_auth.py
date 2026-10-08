"""auth status|check behavior (env-only credentials, zero local state)."""

import json
import unittest
import urllib.error

from cli_harness import ENV, RecordingTransport, load_cli, run


class AuthStatusTest(unittest.TestCase):
    def test_status_ready_exits_0_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["auth", "status"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual({"ready": True, "missing": []}, json.loads(result.stdout))
        self.assertEqual([], transport.requests)

    def test_status_reports_missing_vars_and_exits_3_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["auth", "status"],
            env={"BOOKSTACK_TOKEN_ID": "tok-id"},
            transport=transport,
        )
        self.assertEqual(3, result.code)
        self.assertEqual(
            {"ready": False, "missing": ["BOOKSTACK_URL", "BOOKSTACK_TOKEN_SECRET"]},
            json.loads(result.stdout),
        )
        self.assertEqual([], transport.requests)

    def test_status_treats_empty_values_as_missing(self):
        cli = load_cli()
        result = run(
            cli,
            ["auth", "status"],
            env={**ENV, "BOOKSTACK_TOKEN_SECRET": ""},
        )
        self.assertEqual(3, result.code)
        self.assertEqual(
            {"ready": False, "missing": ["BOOKSTACK_TOKEN_SECRET"]},
            json.loads(result.stdout),
        )


class AuthCheckTest(unittest.TestCase):
    def test_check_success_prints_system_json_and_exits_0(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b'{"version":"v24.05"}')])
        result = run(cli, ["auth", "check"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"version":"v24.05"}\n', result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, len(transport.requests))
        request = transport.requests[0]
        self.assertEqual("GET", request.method)
        self.assertEqual("https://wiki.example.com/api/system", request.url)
        self.assertEqual("Token tok-id:tok-secret", request.headers["Authorization"])

    def test_check_missing_env_exits_3_without_http(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(
            cli,
            ["auth", "check"],
            env={"BOOKSTACK_URL": "https://wiki.example.com"},
            transport=transport,
        )
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        payload = json.loads(result.stderr)
        self.assertIn("BOOKSTACK_TOKEN_ID", payload["error"]["message"])
        self.assertIn("BOOKSTACK_TOKEN_SECRET", payload["error"]["message"])
        self.assertEqual([], transport.requests)

    def test_check_api_failure_passes_error_json_to_stderr_and_exits_3(self):
        cli = load_cli()
        error_body = b'{"error":{"code":401,"message":"No authorization token found"}}'
        transport = RecordingTransport([(401, {}, error_body)])
        result = run(cli, ["auth", "check"], transport=transport)
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(error_body, result.stderr)

    def test_check_network_failure_exits_3(self):
        cli = load_cli()
        transport = RecordingTransport([urllib.error.URLError("no route to host")])
        result = run(cli, ["auth", "check"], transport=transport)
        self.assertEqual(3, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertIn(b"no route to host", result.stderr)

    def test_credentials_cannot_be_passed_as_flags(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["system", "--token-id", "leaked"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


class AuthRemovedCommandsTest(unittest.TestCase):
    def test_logout_is_rejected_as_unknown_action(self):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["auth", "logout"], transport=transport)
        self.assertEqual(2, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)

    def test_auth_help_lists_status_and_check(self):
        cli = load_cli()
        result = run(cli, ["auth", "--help"], env={})
        self.assertEqual(0, result.code)
        text = result.stdout.decode("utf-8")
        self.assertIn("status", text)
        self.assertIn("check", text)


if __name__ == "__main__":
    unittest.main()
