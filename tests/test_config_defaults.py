"""Defaults must not carry a personal path: the repository is public and must run on any machine."""
import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

PERSONAL = re.compile(r"onnik|[A-Za-z]:[/\\]Users|/home/|Desktop", re.IGNORECASE)


class ConfigDefaultsTests(unittest.TestCase):
    def test_no_personal_path_in_config_defaults(self):
        from app import config
        for name, value in config.DEFAULTS.items():
            self.assertIsNone(PERSONAL.search(value), f"{name} default is a personal path: {value!r}")

    def test_data_dir_default_is_relative_to_repo(self):
        from app import config
        default = config.DEFAULTS["SVINKKI_DATA_DIR"]
        self.assertFalse(os.path.isabs(default), default)
        self.assertEqual(default, "dataset")

    def test_data_dir_resolves_inside_repo_when_unset(self):
        from app import config
        env = {k: v for k, v in os.environ.items() if k != "SVINKKI_DATA_DIR"}
        env["SVINKKI_ENV_FILE"] = str(REPO / "no-such.env")
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(config.data_dir(), os.path.normpath(str(REPO / "dataset")))

    def test_ingest_default_has_no_personal_path(self):
        from app import ingest
        self.assertIsNone(PERSONAL.search(ingest.DEFAULT_DATA_DIR), ingest.DEFAULT_DATA_DIR)

    def test_env_example_has_no_personal_path(self):
        text = (REPO / ".env.example").read_text(encoding="utf-8")
        self.assertIsNone(PERSONAL.search(text))

    def test_dataset_folder_is_git_ignored(self):
        lines = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("dataset/", lines)

    def test_ingest_names_the_variable_when_folder_is_missing(self):
        from app import ingest
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "nope")
            err, out = io.StringIO(), io.StringIO()
            with redirect_stderr(err), redirect_stdout(out):
                code = ingest.main(["--data-dir", missing, "--out", os.path.join(tmp, "x.db")])
            self.assertEqual(code, 2)
            msg = err.getvalue()
            self.assertIn("SVINKKI_DATA_DIR", msg)
            self.assertIn(missing, msg)
            self.assertFalse(os.path.exists(os.path.join(tmp, "x.db")))


if __name__ == "__main__":
    unittest.main()
