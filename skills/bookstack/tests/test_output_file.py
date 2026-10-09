"""F-04: -o output safety (refuse overwrite, 0600, never follow symlink)."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cli_harness import RecordingTransport, load_cli, run

BODY = b"# exported\n"


class OutputFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def path(self, name):
        return os.path.join(self.directory, name)

    def export(self, target, extra=None):
        cli = load_cli()
        transport = RecordingTransport([(200, {}, BODY)])
        argv = ["pages", "export", "42", "--format", "markdown", "-o", target]
        if extra:
            argv += extra
        return run(cli, argv, transport=transport)

    def test_new_file_is_written_with_0600(self):
        target = self.path("out.md")
        result = self.export(target)
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(BODY, Path(target).read_bytes())
        self.assertEqual(0o600, os.stat(target).st_mode & 0o777)
        self.assertEqual({"saved_to": target}, json.loads(result.stdout))

    def test_existing_file_is_refused_without_force(self):
        target = self.path("out.md")
        Path(target).write_bytes(b"precious")
        result = self.export(target)
        self.assertEqual(2, result.code)
        self.assertEqual(b"precious", Path(target).read_bytes())
        self.assertIn("overwrite", json.loads(result.stderr)["error"]["message"])

    def test_force_overwrites_existing_file(self):
        target = self.path("out.md")
        Path(target).write_bytes(b"precious")
        result = self.export(target, extra=["--force"])
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(BODY, Path(target).read_bytes())

    def test_symlink_target_is_refused(self):
        real = self.path("real.md")
        Path(real).write_bytes(b"precious")
        link = self.path("link.md")
        os.symlink(real, link)
        for extra in (None, ["--force"]):
            with self.subTest(extra=extra):
                result = self.export(link, extra=extra)
                self.assertEqual(2, result.code)
                self.assertEqual(b"precious", Path(real).read_bytes())
                self.assertTrue(os.path.islink(link))


if __name__ == "__main__":
    unittest.main()
