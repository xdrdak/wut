#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import termios
import tty
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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

    for i, cmd in enumerate(repo_config.commands, 1):
        print(f"{i}. {cmd.title} - {cmd.command}")


def fuzzy_match(query: str, text: str) -> Tuple[bool, float]:
    if not query:
        return True, 0.0

    query_lower = query.lower()
    text_lower = text.lower()

    idx = 0
    positions = []

    for i, char in enumerate(text_lower):
        if idx < len(query_lower) and char == query_lower[idx]:
            positions.append(i)
            idx += 1

    if idx != len(query_lower):
        return False, 0.0

    score = 0.0
    for pos in positions:
        score += 1.0 / (pos + 1)

    return True, score


def interactive_select(commands: List[Command]) -> Optional[Command]:
    import select

    if not commands:
        return None

    filtered = commands[:]
    selected_idx = 0
    query = ""

    old_settings = termios.tcgetattr(sys.stdin.fileno())

    try:
        tty.setraw(sys.stdin.fileno())

        while True:
            sys.stdout.write("\033[H\033[J")

            if filtered:
                for i, cmd in enumerate(filtered):
                    row = i + 1
                    sys.stdout.write(
                        f"\033[{row};1H\033[K{'  ' if i != selected_idx else '➡ '}{cmd.title} - {cmd.command}"
                    )
            else:
                sys.stdout.write("\033[1;1H\033[KNo matches")

            prompt_row = len(filtered) + 2 if filtered else 2
            sys.stdout.write(f"\033[{prompt_row};1H> {query}")

            help_row = prompt_row + 2
            help_text = "\033[90m↑↓: Navigate  Enter: Select  Ctrl+C/Esc: Quit\033[0m"
            sys.stdout.write(f"\033[{help_row};1H\033[K{help_text}")
            sys.stdout.flush()

            if select.select([sys.stdin], [], [], 0.1)[0]:
                char = sys.stdin.read(1)

                if char == "\x03":
                    return None
                elif char == "\r" or char == "\n":
                    if filtered:
                        return filtered[selected_idx]
                elif char == "\x1b":
                    next_char = sys.stdin.read(1)
                    if next_char == "[":
                        arrow = sys.stdin.read(1)
                        if arrow == "A":
                            selected_idx = max(0, selected_idx - 1)
                        elif arrow == "B":
                            selected_idx = min(len(filtered) - 1, selected_idx + 1)
                    else:
                        return None
                elif char == "\x7f" or char == "\x08":
                    query = query[:-1]
                elif ord(char) >= 32:
                    query += char

                filtered = []
                for cmd in commands:
                    matches, score = fuzzy_match(query, cmd.title)
                    if matches:
                        filtered.append((cmd, score))
                    else:
                        matches_cmd, score_cmd = fuzzy_match(query, cmd.command)
                        if matches_cmd:
                            filtered.append((cmd, score_cmd))

                filtered.sort(key=lambda x: -x[1])
                filtered = [item[0] for item in filtered]

                if filtered:
                    selected_idx = min(selected_idx, len(filtered) - 1)
                else:
                    selected_idx = 0

    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[H\033[J")
        sys.stdout.flush()


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


def cmd_run(use_cwd: bool = False) -> None:
    config = load_config()
    repo_key = get_repo_key()

    if repo_key not in config:
        print("No commands defined for this repository")
        return

    repo_config = config[repo_key]

    if not repo_config.commands:
        print("No commands defined for this repository")
        return

    selected_cmd = interactive_select(repo_config.commands)

    if selected_cmd:
        cwd = os.getcwd() if use_cwd else repo_config.repo
        subprocess.run(selected_cmd.command, shell=True, cwd=cwd)


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
    print(f"  wut run           Interactive command selection")
    print(
        f"  wut run --cwd     Interactive command selection (run from current directory)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?", default="help")
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
        cmd_run(parsed.cwd)
    else:
        sys.stderr.write(f'wut: unknown command "{cmd}"\n')
        sys.exit(1)


if __name__ == "__main__":
    main()
