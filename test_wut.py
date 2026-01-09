#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))
from wut import (
    get_config_path,
    load_config,
    save_config,
    get_repo_key,
    cmd_init,
    cmd_dis,
    cmd_add,
    cmd_run,
    cmd_edit,
    find_editor,
    fuzzy_match,
    Command,
    RepoConfig,
)


class TestConfigPath(unittest.TestCase):
    def test_xdg_config_home_set(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/testconfig"}):
            path = get_config_path()
            self.assertEqual(path, Path("/tmp/testconfig/wut/commands.json"))

    def test_xdg_config_home_not_set(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}):
            path = get_config_path()
            self.assertEqual(path, Path.home() / ".config" / "wut" / "commands.json")


class TestConfigLoadSave(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "commands.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("wut.get_config_path")
    def test_load_valid_config(self, mock_get_config_path):
        mock_get_config_path.return_value = self.config_file

        test_data = {
            "owner/project": {
                "repo": "/path/to/repo",
                "commands": [
                    {"title": "test", "command": "echo test", "description": "desc"}
                ],
            }
        }
        with open(self.config_file, "w") as f:
            json.dump(test_data, f)

        config = load_config()
        self.assertIn("owner/project", config)
        self.assertEqual(len(config["owner/project"].commands), 1)
        self.assertEqual(config["owner/project"].commands[0].title, "test")

    @patch("wut.get_config_path")
    def test_load_missing_config(self, mock_get_config_path):
        mock_get_config_path.return_value = self.config_file

        with patch("sys.stderr", new_callable=MagicMock) as mock_stderr:
            with self.assertRaises(SystemExit) as cm:
                load_config()
            self.assertEqual(cm.exception.code, 1)
            self.assertTrue(mock_stderr.write.called)

    @patch("wut.get_config_path")
    def test_save_config(self, mock_get_config_path):
        mock_get_config_path.return_value = self.config_file

        config = {
            "owner/project": RepoConfig(
                repo="/path/to/repo",
                commands=[Command(title="test", command="echo test")],
            )
        }
        save_config(config)

        self.assertTrue(self.config_file.exists())
        with open(self.config_file, "r") as f:
            data = json.load(f)
        self.assertIn("owner/project", data)


class TestRepoKey(unittest.TestCase):
    @patch("subprocess.run")
    def test_get_repo_key_from_path(self, mock_run):
        mock_run.return_value = MagicMock(stdout="/path/to/repo\n", stderr="")

        repo_key = get_repo_key()
        self.assertEqual(len(repo_key), 16)
        self.assertEqual(repo_key, "7e8a376c8bb0893e")

    @patch("subprocess.run")
    def test_get_repo_key_not_git_repo(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        with patch("sys.stderr", new_callable=MagicMock):
            with self.assertRaises(SystemExit) as cm:
                get_repo_key()
            self.assertEqual(cm.exception.code, 1)


class TestCmdInit(unittest.TestCase):
    @patch("wut.get_config_path")
    def test_init_creates_config(self, mock_get_config_path):
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "commands.json"
        mock_get_config_path.return_value = config_file

        cmd_init()

        self.assertTrue(config_file.exists())
        with open(config_file, "r") as f:
            data = json.load(f)
        self.assertEqual(data, {})

        import shutil

        shutil.rmtree(temp_dir)

    @patch("wut.get_config_path")
    @patch("builtins.print")
    def test_init_idempotent(self, mock_print, mock_get_config_path):
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "commands.json"
        mock_get_config_path.return_value = config_file

        cmd_init()
        cmd_init()

        self.assertEqual(mock_print.call_count, 2)

        import shutil

        shutil.rmtree(temp_dir)


class TestCmdAdd(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "commands.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("wut.get_config_path")
    @patch("wut.get_repo_key")
    @patch("subprocess.run")
    def test_add_command(self, mock_run, mock_get_repo_key, mock_get_config_path):
        mock_get_config_path.return_value = self.config_file
        mock_get_repo_key.return_value = "owner/project"
        mock_run.return_value = MagicMock(stdout="/path/to/repo\n", stderr="")

        with open(self.config_file, "w") as f:
            json.dump({}, f)

        with patch("builtins.input", side_effect=["test", "echo test", "test desc"]):
            cmd_add()

        config = load_config()
        self.assertIn("owner/project", config)
        self.assertEqual(len(config["owner/project"].commands), 1)
        self.assertEqual(config["owner/project"].commands[0].title, "test")

    @patch("wut.get_config_path")
    @patch("wut.get_repo_key")
    @patch("subprocess.run")
    @patch("builtins.input")
    def test_add_duplicate_title(
        self, mock_input, mock_run, mock_get_repo_key, mock_get_config_path
    ):
        mock_get_config_path.return_value = self.config_file
        mock_get_repo_key.return_value = "owner/project"
        mock_run.return_value = MagicMock(stdout="/path/to/repo\n", stderr="")

        test_data = {
            "owner/project": {
                "repo": "/path/to/repo",
                "commands": [{"title": "test", "command": "echo test"}],
            }
        }
        with open(self.config_file, "w") as f:
            json.dump(test_data, f)

        mock_input.side_effect = ["test", "echo test", ""]

        with patch("sys.stderr", new_callable=MagicMock):
            with self.assertRaises(SystemExit) as cm:
                cmd_add()
            self.assertEqual(cm.exception.code, 1)

    @patch("builtins.input")
    def test_add_missing_title(self, mock_input):
        mock_input.side_effect = ["", "echo test", ""]

        with patch("sys.stderr", new_callable=MagicMock):
            with self.assertRaises(SystemExit) as cm:
                cmd_add()
            self.assertEqual(cm.exception.code, 1)

    @patch("builtins.input")
    def test_add_missing_command(self, mock_input):
        mock_input.side_effect = ["test", "", ""]

        with patch("sys.stderr", new_callable=MagicMock):
            with self.assertRaises(SystemExit) as cm:
                cmd_add()
            self.assertEqual(cm.exception.code, 1)


class TestCmdDis(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "commands.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("wut.get_config_path")
    @patch("wut.get_repo_key")
    @patch("builtins.print")
    def test_dis_commands(self, mock_print, mock_get_repo_key, mock_get_config_path):
        mock_get_config_path.return_value = self.config_file
        mock_get_repo_key.return_value = "owner/project"

        test_data = {
            "owner/project": {
                "repo": "/path/to/repo",
                "commands": [
                    {"title": "test1", "command": "echo test1", "description": "desc1"},
                    {"title": "test2", "command": "echo test2", "description": "desc2"},
                ],
            }
        }
        with open(self.config_file, "w") as f:
            json.dump(test_data, f)

        cmd_dis()

        self.assertEqual(mock_print.call_count, 2)
        mock_print.assert_any_call("1. test1 - echo test1")
        mock_print.assert_any_call("2. test2 - echo test2")

    @patch("wut.get_config_path")
    @patch("wut.get_repo_key")
    @patch("builtins.print")
    def test_dis_no_commands(self, mock_print, mock_get_repo_key, mock_get_config_path):
        mock_get_config_path.return_value = self.config_file
        mock_get_repo_key.return_value = "owner/project"

        test_data = {"owner/project": {"repo": "/path/to/repo", "commands": []}}
        with open(self.config_file, "w") as f:
            json.dump(test_data, f)

        cmd_dis()

        self.assertEqual(mock_print.call_count, 1)
        mock_print.assert_called_with("No commands defined for this repository")


class TestFuzzyMatch(unittest.TestCase):
    def test_empty_query(self):
        matches, score = fuzzy_match("", "test command")
        self.assertTrue(matches)
        self.assertEqual(score, 0.0)

    def test_exact_match(self):
        matches, score = fuzzy_match("test", "test command")
        self.assertTrue(matches)
        self.assertGreater(score, 0.0)

    def test_substring_match(self):
        matches, score = fuzzy_match("tc", "test command")
        self.assertTrue(matches)
        self.assertGreater(score, 0.0)

    def test_no_match(self):
        matches, score = fuzzy_match("xyz", "test command")
        self.assertFalse(matches)
        self.assertEqual(score, 0.0)


class TestCmdRun(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "commands.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("wut.get_config_path")
    @patch("wut.get_repo_key")
    def test_run_no_commands(self, mock_get_repo_key, mock_get_config_path):
        mock_get_config_path.return_value = self.config_file
        mock_get_repo_key.return_value = "owner/project"

        test_data = {"owner/project": {"repo": "/path/to/repo", "commands": []}}
        with open(self.config_file, "w") as f:
            json.dump(test_data, f)

        with patch("builtins.print") as mock_print:
            cmd_run()
            mock_print.assert_called_with("No commands defined for this repository")

    @patch("wut.get_config_path")
    @patch("wut.get_repo_key")
    def test_run_no_repo_config(self, mock_get_repo_key, mock_get_config_path):
        mock_get_config_path.return_value = self.config_file
        mock_get_repo_key.return_value = "owner/project"

        test_data = {"other/repo": {"repo": "/path/to/other", "commands": []}}
        with open(self.config_file, "w") as f:
            json.dump(test_data, f)

        with patch("builtins.print") as mock_print:
            cmd_run()
            mock_print.assert_called_with("No commands defined for this repository")


class TestFindEditor(unittest.TestCase):
    @patch("subprocess.run")
    def test_git_config_editor(self, mock_run):
        mock_run.return_value = MagicMock(stdout="emacs\n", stderr="")
        with patch.dict(os.environ, {}, clear=True):
            editor = find_editor()
            self.assertEqual(editor, "emacs")

    @patch("subprocess.run")
    def test_editor_env_var(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            editor = find_editor()
            self.assertEqual(editor, "nano")

    @patch("subprocess.run")
    def test_vi_fallback(self, mock_run):
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "git"),
            MagicMock(stdout="", stderr=""),
        ]
        with patch.dict(os.environ, {}, clear=True):
            editor = find_editor()
            self.assertEqual(editor, "vi")

    @patch("subprocess.run")
    def test_no_editor_found(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        with patch.dict(os.environ, {}, clear=True):
            editor = find_editor()
            self.assertIsNone(editor)


class TestCmdEdit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "commands.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("wut.get_config_path")
    def test_edit_no_config_file(self, mock_get_config_path):
        mock_get_config_path.return_value = self.config_file

        with patch("sys.stderr", new_callable=MagicMock):
            with self.assertRaises(SystemExit) as cm:
                cmd_edit()
            self.assertEqual(cm.exception.code, 1)

    @patch("wut.get_config_path")
    @patch("wut.find_editor")
    @patch("subprocess.run")
    def test_edit_success(
        self, mock_subprocess_run, mock_find_editor, mock_get_config_path
    ):
        mock_get_config_path.return_value = self.config_file
        mock_find_editor.return_value = "vim"

        with open(self.config_file, "w") as f:
            json.dump({}, f)

        cmd_edit()

        self.assertEqual(mock_subprocess_run.call_count, 1)
        call_args = mock_subprocess_run.call_args_list[0]
        self.assertEqual(call_args[0][0], ["vim", str(self.config_file)])

    @patch("wut.get_config_path")
    @patch("wut.find_editor")
    def test_edit_no_editor(self, mock_find_editor, mock_get_config_path):
        mock_get_config_path.return_value = self.config_file
        mock_find_editor.return_value = None

        with open(self.config_file, "w") as f:
            json.dump({}, f)

        with patch("sys.stderr", new_callable=MagicMock):
            with self.assertRaises(SystemExit) as cm:
                cmd_edit()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
