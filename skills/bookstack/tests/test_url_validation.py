"""F-02: BOOKSTACK_URL scheme/host validation."""

import unittest

from cli_harness import RecordingTransport, load_cli, run


def env(url, extra=None):
    values = {
        "BOOKSTACK_URL": url,
        "BOOKSTACK_TOKEN_ID": "tok-id",
        "BOOKSTACK_TOKEN_SECRET": "tok-secret",
    }
    if extra:
        values.update(extra)
    return values


class UrlValidationTest(unittest.TestCase):
    def assert_rejected(self, url, extra=None):
        cli = load_cli()
        transport = RecordingTransport()
        result = run(cli, ["system"], env=env(url, extra), transport=transport)
        self.assertEqual(2, result.code, result.stderr)
        self.assertEqual(b"", result.stdout)
        self.assertEqual([], transport.requests)
        self.assertIn(b"BOOKSTACK_URL", result.stderr)

    def test_plain_http_is_rejected(self):
        self.assert_rejected("http://wiki.example.com")

    def test_userinfo_is_rejected(self):
        self.assert_rejected("https://user:pass@wiki.example.com")

    def test_missing_host_is_rejected(self):
        self.assert_rejected("https://")

    def test_plain_http_allowed_with_opt_in(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b"{}")])
        result = run(
            cli,
            ["system"],
            env=env("http://wiki.example.com", {"BOOKSTACK_ALLOW_INSECURE": "1"}),
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            "http://wiki.example.com/api/system", transport.requests[0].url
        )

    def test_https_is_accepted(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, b"{}")])
        result = run(
            cli,
            ["system"],
            env=env("https://wiki.example.com"),
            transport=transport,
        )
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            "https://wiki.example.com/api/system", transport.requests[0].url
        )


if __name__ == "__main__":
    unittest.main()
