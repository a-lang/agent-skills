"""F-01: redirects must not replay Authorization to a different origin.

The transport seam is replaced in every black-box test, so the redirect policy
is exercised directly on the handler that ``transport()`` installs.
"""

import io
import unittest
import urllib.error
import urllib.request

from cli_harness import load_cli


def follow(cli, handler, from_url, to_url, headers=None):
    request = urllib.request.Request(from_url, headers=headers or {})
    return handler.redirect_request(
        request, io.BytesIO(b""), 302, "Found", {"Location": to_url}, to_url
    )


class SameOriginRedirectTest(unittest.TestCase):
    def setUp(self):
        self.cli = load_cli()
        self.handler = self.cli._SameOriginRedirect()

    def test_same_origin_redirect_keeps_authorization(self):
        new = follow(
            self.cli,
            self.handler,
            "https://wiki.example.com/api/system",
            "https://wiki.example.com/api/system/",
            headers={"Authorization": "Token id:secret"},
        )
        self.assertEqual("Token id:secret", new.headers["Authorization"])

    def test_cross_host_redirect_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            follow(
                self.cli,
                self.handler,
                "https://wiki.example.com/api/system",
                "https://evil.example.net/landing",
                headers={"Authorization": "Token id:secret"},
            )
        self.assertEqual(302, ctx.exception.code)

    def test_cross_scheme_redirect_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError):
            follow(
                self.cli,
                self.handler,
                "https://wiki.example.com/api/system",
                "http://wiki.example.com/landing",
            )

    def test_origin_ignores_path_and_query(self):
        self.assertEqual(
            self.cli._origin_of("https://host:8443/a/b?c=d"),
            self.cli._origin_of("https://host:8443/x"),
        )
        self.assertNotEqual(
            self.cli._origin_of("https://host:8443/a"),
            self.cli._origin_of("https://host:9443/a"),
        )


if __name__ == "__main__":
    unittest.main()
