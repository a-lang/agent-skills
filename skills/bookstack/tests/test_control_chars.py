"""F-06: control bytes stripped from text success output, preserved in streams."""

import unittest

from cli_harness import RecordingTransport, load_cli, run

ESCAPE_BODY = b"\x1b]52;c;cGF5bG9hZA==\x07\x1b[2J\x1b[H{\"page\":\"ok\"}\n"


class ControlCharTest(unittest.TestCase):
    def test_control_bytes_stripped_from_json_success(self):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, ESCAPE_BODY)])
        result = run(cli, ["system"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertNotIn(b"\x1b", result.stdout)
        self.assertNotIn(b"\x07", result.stdout)
        self.assertIn(b'{"page":"ok"}', result.stdout)

    def test_stream_binary_bytes_are_not_filtered(self):
        cli = load_cli()
        payload = b"\x1b\x00\x07binary\x7f"
        transport = RecordingTransport([(200, {}, payload)])
        result = run(
            cli,
            ["pages", "export", "42", "--format", "markdown"],
            transport=transport,
        )
        self.assertEqual(0, result.code)
        self.assertEqual(payload, result.stdout)

    def test_multibyte_utf8_text_is_preserved(self):
        cli = load_cli()
        body = "正體中文\n".encode("utf-8")
        transport = RecordingTransport([(200, {}, body)])
        result = run(cli, ["system"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(body, result.stdout)


if __name__ == "__main__":
    unittest.main()
