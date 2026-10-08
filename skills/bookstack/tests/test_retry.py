"""429-only retry policy: Retry-After, backoff 1/2/4, max 3 retries, exit 6."""

import unittest
from unittest import mock

from cli_harness import RecordingTransport, load_cli, run

RATE_BODY = b'{"error":{"code":429,"message":"Too Many Attempts."}}'


class RetryTest(unittest.TestCase):
    def test_429_then_200_retries_once_and_succeeds(self):
        cli = load_cli()
        transport = RecordingTransport(
            [
                (429, {}, RATE_BODY),
                (200, {}, b'{"version":"v24"}'),
            ]
        )
        with mock.patch("time.sleep") as sleeper:
            result = run(cli, ["system"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(b'{"version":"v24"}\n', result.stdout)
        self.assertEqual(2, len(transport.requests))
        self.assertEqual(1, sleeper.call_count)
        self.assertEqual(1, sleeper.call_args.args[0])
        self.assertIn(b"429", result.stderr)
        self.assertIn(b"retry", result.stderr.lower())

    def test_retry_after_header_is_used(self):
        cli = load_cli()
        transport = RecordingTransport(
            [
                (429, {"Retry-After": "7"}, RATE_BODY),
                (200, {}, b"{}"),
            ]
        )
        with mock.patch("time.sleep") as sleeper:
            result = run(cli, ["system"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(1, sleeper.call_count)
        self.assertEqual(7, sleeper.call_args.args[0])

    def test_invalid_retry_after_falls_back_to_backoff(self):
        cli = load_cli()
        transport = RecordingTransport(
            [
                (429, {"Retry-After": "soon"}, RATE_BODY),
                (200, {}, b"{}"),
            ]
        )
        with mock.patch("time.sleep") as sleeper:
            result = run(cli, ["system"], transport=transport)
        self.assertEqual(0, result.code)
        self.assertEqual(1, sleeper.call_args.args[0])

    def test_exhausted_429_uses_backoff_1_2_4_and_exits_6(self):
        cli = load_cli()
        transport = RecordingTransport([(429, {}, RATE_BODY)] * 4)
        with mock.patch("time.sleep") as sleeper:
            result = run(cli, ["system"], transport=transport)
        self.assertEqual(6, result.code)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(4, len(transport.requests))
        self.assertEqual([1, 2, 4], [call.args[0] for call in sleeper.call_args_list])
        self.assertIn(RATE_BODY, result.stderr)
        self.assertEqual(3, result.stderr.count(b"429 rate limited"))

    def test_non_429_failures_fail_fast(self):
        for status, expected in ((401, 3), (403, 3), (404, 4), (422, 5), (500, 8)):
            with self.subTest(status=status):
                cli = load_cli()
                transport = RecordingTransport([(status, {}, RATE_BODY)])
                with mock.patch("time.sleep") as sleeper:
                    result = run(cli, ["system"], transport=transport)
                self.assertEqual(expected, result.code)
                self.assertEqual(1, len(transport.requests))
                self.assertEqual(0, sleeper.call_count)
                self.assertEqual(b"", result.stdout)
                self.assertEqual(RATE_BODY, result.stderr)

    def test_429_then_other_error_maps_after_retry(self):
        cli = load_cli()
        transport = RecordingTransport(
            [
                (429, {}, RATE_BODY),
                (404, {}, b'{"error":{"code":404,"message":"Not found"}}'),
            ]
        )
        with mock.patch("time.sleep"):
            result = run(cli, ["system"], transport=transport)
        self.assertEqual(4, result.code)
        self.assertEqual(2, len(transport.requests))


if __name__ == "__main__":
    unittest.main()
