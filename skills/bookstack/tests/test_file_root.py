"""F-03: @file reads honor BOOKSTACK_FILE_ROOT and the size cap."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cli_harness import ENV, RecordingTransport, load_cli, run


class FileRootTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.addCleanup(shutil.rmtree, self.outside)

    def create_page(self, content_path, env=None, transport=None):
        cli = load_cli()
        if transport is None:
            transport = RecordingTransport([(200, {}, b'{"id":1}')])
        return run(
            cli,
            ["pages", "create", "--book-id", "1", "--markdown", "@" + str(content_path)],
            env=env,
            transport=transport,
        )

    def test_file_inside_root_is_read(self):
        path = Path(self.root) / "doc.md"
        path.write_text("# hi\n", encoding="utf-8")
        result = self.create_page(path, env=dict(ENV, BOOKSTACK_FILE_ROOT=self.root))
        self.assertEqual(0, result.code, result.stderr)

    def test_file_outside_root_is_rejected(self):
        path = Path(self.outside) / "secret.txt"
        path.write_text("secret\n", encoding="utf-8")
        transport = RecordingTransport()
        result = self.create_page(
            path, env=dict(ENV, BOOKSTACK_FILE_ROOT=self.root), transport=transport
        )
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)

    def test_symlink_escape_is_rejected(self):
        target = Path(self.outside) / "secret.txt"
        target.write_text("secret\n", encoding="utf-8")
        link = Path(self.root) / "link.txt"
        os.symlink(target, link)
        transport = RecordingTransport()
        result = self.create_page(
            link, env=dict(ENV, BOOKSTACK_FILE_ROOT=self.root), transport=transport
        )
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)

    def test_file_over_size_cap_is_rejected(self):
        path = Path(self.root) / "big.md"
        path.write_bytes(b"x" * 10)
        cli = load_cli()
        cli.MAX_FILE_BYTES = 5
        transport = RecordingTransport()
        result = run(
            cli,
            ["pages", "create", "--book-id", "1", "--markdown", "@" + str(path)],
            env=dict(ENV, BOOKSTACK_FILE_ROOT=self.root),
            transport=transport,
        )
        self.assertEqual(2, result.code)
        self.assertEqual([], transport.requests)


if __name__ == "__main__":
    unittest.main()
