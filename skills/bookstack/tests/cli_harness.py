"""Black-box harness for driving bookstack-api-cli.py in tests.

The only seam under test is the module-level ``transport`` function. Every
test replaces it with a recording fake, then drives the CLI entry point with
argv + environment variables and inspects stdout bytes, stderr bytes and the
exit code.
"""

import importlib.util
import io
import os
import sys
from pathlib import Path
from typing import NamedTuple

from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bookstack-api-cli.py"

ENV = {
    "BOOKSTACK_URL": "https://wiki.example.com",
    "BOOKSTACK_TOKEN_ID": "tok-id",
    "BOOKSTACK_TOKEN_SECRET": "tok-secret",
}

AUTH_HEADER = "Token tok-id:tok-secret"


def load_cli():
    spec = importlib.util.spec_from_file_location("bookstack_api_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BinaryCapture:
    """Stands in for sys.stdout/sys.stderr; captures raw bytes writes."""

    def __init__(self):
        self.buffer = io.BytesIO()

    def flush(self):
        pass


class RecordingTransport:
    """Records full requests and replays canned responses.

    Each response is ``(status, headers, body)``; a ``BaseException`` entry is
    raised instead of returned (network failure simulation).
    """

    def __init__(self, responses=()):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        status, headers, body = item
        if body is None:
            body = b""
        if isinstance(body, str):
            body = body.encode("utf-8")
        return status, dict(headers), body

    @property
    def urls(self):
        return [request.url for request in self.requests]


class CliResult(NamedTuple):
    code: int
    stdout: bytes
    stderr: bytes
    transport: RecordingTransport


def run(module, argv, env=None, transport=None, stdin=b""):
    if env is None:
        env = ENV
    if transport is None:
        transport = RecordingTransport()
    module.transport = transport
    stdout = BinaryCapture()
    stderr = BinaryCapture()
    stdin_stream = type("Stdin", (), {"buffer": io.BytesIO(stdin)})()
    with mock.patch.dict(os.environ, env, clear=True), \
            mock.patch.object(sys, "stdout", stdout), \
            mock.patch.object(sys, "stderr", stderr), \
            mock.patch.object(sys, "stdin", stdin_stream):
        code = module.main(argv)
    return CliResult(code, stdout.buffer.getvalue(), stderr.buffer.getvalue(), transport)
