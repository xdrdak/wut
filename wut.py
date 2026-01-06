#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Command:
    title: str
    command: str
    description: Optional[str] = None


@dataclass
class RepoConfig:
    repo: str
    commands: List[Command]


def get_config_path() -> Path:
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    config_dir = (
        Path(xdg_config) / "wut" if xdg_config else Path.home() / ".config" / "wut"
    )
    return config_dir / "commands.json"


def load_config() -> Dict[str, RepoConfig]:
    config_path = get_config_path()
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        result = {}
        for repo_key, repo_data in data.items():
            commands = [Command(**cmd) for cmd in repo_data["commands"]]
            result[repo_key] = RepoConfig(repo=repo_data["repo"], commands=commands)
        return result
    except (FileNotFoundError, json.JSONDecodeError) as e:
        sys.stderr.write(f"wut: failed to load config from {config_path}: {e}\n")
        sys.stderr.write(f'wut: run "wut init" to initialize\n')
        sys.exit(1)


def save_config(config: Dict[str, RepoConfig]) -> None:
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    for repo_key, repo_config in config.items():
        data[repo_key] = {
            "repo": repo_config.repo,
            "commands": [asdict(cmd) for cmd in repo_config.commands],
        }
    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)


def get_repo_key() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.stderr.write("wut: not in a git repository\n")
        sys.exit(1)

    repo_path = Path(repo_root)
    repo_name = repo_path.name

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
        remote_url = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.stderr.write("wut: cannot determine repo owner/project\n")
        sys.exit(1)

    if remote_url.startswith("git@github.com:"):
        parts = remote_url[len("git@github.com:") :].removesuffix(".git")
    elif remote_url.startswith("https://github.com/"):
        parts = remote_url[len("https://github.com/") :].removesuffix(".git")
    else:
        sys.stderr.write("wut: unsupported remote URL format\n")
        sys.exit(1)

    return parts


def cmd_init() -> None:
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        with open(config_path, "w") as f:
            json.dump({}, f)
        print(f"Initialized config at {config_path}")
    else:
        print(f"Config already exists at {config_path}")


def cmd_dis() -> None:
    config = load_config()
    repo_key = get_repo_key()

    if repo_key not in config:
        print("No commands defined for this repository")
        return

    repo_config = config[repo_key]
    if not repo_config.commands:
        print("No commands defined for this repository")
        return

    max_title_len = max(len(cmd.title) for cmd in repo_config.commands)
    for cmd in repo_config.commands:
        desc = cmd.description or ""
        print(f"{cmd.title:<{max_title_len}}  {desc}")


def cmd_add() -> None:
    title = input("title: ").strip()
    if not title:
        sys.stderr.write("wut: title is required\n")
        sys.exit(1)

    command = input("command: ").strip()
    if not command:
        sys.stderr.write("wut: command is required\n")
        sys.exit(1)

    description = input("description (optional): ").strip() or None

    config = load_config()
    repo_key = get_repo_key()

    if repo_key not in config:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_path = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            sys.stderr.write("wut: cannot determine repo path\n")
            sys.exit(1)
        config[repo_key] = RepoConfig(repo=repo_path, commands=[])

    repo_config = config[repo_key]
    existing_titles = [cmd.title for cmd in repo_config.commands]
    if title in existing_titles:
        sys.stderr.write(f'wut: command "{title}" already exists\n')
        sys.exit(1)

    repo_config.commands.append(
        Command(title=title, command=command, description=description)
    )
    save_config(config)
    print(f'Added command "{title}"')


def cmd_run(selector: str, args: List[str], use_cwd: bool = False) -> None:
    config = load_config()
    repo_key = get_repo_key()

    if repo_key not in config:
        sys.stderr.write("wut: no commands defined for this repository\n")
        sys.exit(1)

    repo_config = config[repo_key]
    matching = []

    for cmd in repo_config.commands:
        if cmd.title == selector:
            matching.insert(0, cmd)
            break
        elif cmd.title.startswith(selector):
            matching.append(cmd)

    if not matching:
        for cmd in repo_config.commands:
            if selector in cmd.title:
                matching.append(cmd)

    if not matching:
        sys.stderr.write(f'wut: no command matches "{selector}"\n')
        sys.exit(1)

    if len(matching) > 1:
        sys.stderr.write(
            f'wut: ambiguous selector "{selector}", matches: {", ".join(cmd.title for cmd in matching)}\n'
        )
        sys.exit(1)

    target_cmd = matching[0]
    full_command = f"{target_cmd.command} {' '.join(args)}"

    cwd = os.getcwd() if use_cwd else repo_config.repo
    subprocess.run(full_command, shell=True, cwd=cwd)


def print_help() -> None:
    config_path = get_config_path()
    print(f"wut - per-repo command manager")
    print(f"")
    print(f"Config: {config_path}")
    print(f"")
    print(f"Commands:")
    print(f"  wut, wut help     Show this help")
    print(f"  wut init          Initialize config")
    print(f"  wut dis           List commands for current repo")
    print(f"  wut add           Add a new command")
    print(f"  wut run <cmd>     Run a command (partial title matching)")
    print(f"  wut run <cmd> --cwd  Run command from current directory")


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?", default="help")
    parser.add_argument("args", nargs="*")
    parser.add_argument("--cwd", action="store_true")
    parsed = parser.parse_args()

    cmd = parsed.command

    if cmd == "help" or cmd == "wut":
        print_help()
    elif cmd == "init":
        cmd_init()
    elif cmd == "dis":
        cmd_dis()
    elif cmd == "add":
        cmd_add()
    elif cmd == "run":
        if not parsed.args:
            sys.stderr.write("wut: run requires a command selector\n")
            sys.exit(1)
        selector = parsed.args[0]
        extra_args = parsed.args[1:]
        cmd_run(selector, extra_args, parsed.cwd)
    else:
        cmd_run(cmd, parsed.args, parsed.cwd)


if __name__ == "__main__":
    main()
