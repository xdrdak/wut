
# AGENTS.md — wut

Single-file, dependency-free Python 3 CLI for managing per-git-repo “commands” (script aliases), stored **outside** repos in XDG config.

## 0) Non-negotiables
- **One** main Python file only (no extra modules/utils).
- **Zero dependencies** (stdlib only).
- Use **type annotations** throughout.
- Assume `python3` exists (system Python).
- Follow CLI behavior guidelines from https://clig.dev.
- Not published to PyPI; installed via curl/manual.

## 1) Data model & storage
- Config location: `${XDG_CONFIG_HOME:-~/.config}/wut/commands.json`
- If config file is missing or corrupt: **fail with guidance** (do not auto-init/repair).
- No locking or concurrency handling.

### JSON shape
```json
```json
{
  "REPO_KEY": {
    "repo": "PATH_TO_REPOSITORY_ON_DISK",
    "commands": [
      {
        "command": "SHELL_COMPATIBLE_ONE_LINER",
        "title": "NAME",
        "description": "OPTIONAL"
      }
    ]
  }
}
  ```

 2) Repo identity
	•	Repo identity key (REPO_KEY) is MD5 hash of repo's absolute path, truncated to 16 characters.
	•	Derived from `git rev-parse --show-toplevel` to get repo root.
	•	Works with or without git remotes configured.
	•	User must be inside a git repository; otherwise error.

The repo's absolute path is still stored under repo for reference and locating the repo root.

3) Command schema rules
	•	title must be unique per repo; duplicates are an error.
	•	add does not validate command correctness (yolo).
	•	Missing required fields (title, command) must error.
	•	Commands may accept forwarded arguments.

4) Specs system
	•	Specs live in spec/.
	•	Specs are authoritative when present, but none are required before coding.
	•	Add specs only when precision is needed.

Important: Specs must reflect the full feature set of wut. They serve as the canonical reference for behavior, enabling new implementations (in any language) to be validated against the same test suite. When adding or changing features, update both the relevant spec markdown and add corresponding tests.

5) CLI surface
	•	wut / wut help → print help (include config path)
	•	wut init → bootstrap config dir + commands.json (idempotent)
	•	wut dis → list commands for current repo
	•	wut add → interactive add flow
	•	wut run → run a command

6) Subcommand behavior

wut add
	•	Interactive prompts only:
	•	title (required)
	•	command (required)
	•	description (optional)

wut dis
	•	Default output: human-readable table
	•	Show descriptions by default

wut run
	•	Interactive fuzzy search interface for selecting commands
	•	Typing filters the list by fuzzy matching against command title and command string
	•	List is sorted by match accuracy score
	•	Keyboard navigation: up/down arrows to move selection, enter to execute, ctrl+c or esc to cancel
	•	Default working dir: repo root
	•	Optional flag to run from current working directory
	•	Execute commands via shell
	•	Subprocess inherits stdio (stream output directly)

7) Errors & exit codes
	•	Exit code 0: success
	•	Exit code 1: any error
	•	Error messages are prefixed with wut:

8) Testing
	•	Use stdlib unittest only
	•	Use temp dirs and env overrides (XDG_CONFIG_HOME)
	•	Avoid unnecessary mocking; test observable behavior
