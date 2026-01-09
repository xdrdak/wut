# Commands Specification

This document serves as the authoritative specification for all wut commands. It defines the expected behavior, arguments, error conditions, and edge cases for each command.

**IMPORTANT:** When adding, editing, or changing any command, this file (`spec/commands.md`) must be used as the point of reference. This ensures all commands are documented consistently in one place.

## help

### Signature
```
wut
wut help
```

### Behavior
- Displays help text showing all available commands
- Includes the path to the config file
- No arguments or flags

### Help Output Format
```
wut - per-repo command manager

Config: <path_to_config>

Commands:
  wut, wut help     Show this help
  wut init          Initialize config
  wut dis           List commands for current repo
  wut add           Add a new command
  wut run           Interactive command selection
  wut run --cwd     Interactive command selection (run from current directory)
  wut edit          Open config in editor
```

### Error Conditions
- None

## init

### Signature
```
wut init
```

### Behavior
- Initializes the wut configuration directory and creates an empty `commands.json` file
- Config location: `${XDG_CONFIG_HOME:-~/.config}/wut/commands.json`
- Creates parent directories if they don't exist
- Idempotent: if config already exists, prints message but does not overwrite

### Error Conditions
- None (all errors during file operations should fail with appropriate system errors)

### Edge Cases
- Running init multiple times should not destroy existing data
- Config directory creation should work even if intermediate directories don't exist

## dis

### Signature
```
wut dis
```

### Behavior
- Lists all commands defined for the current git repository
- Output format: numbered list, one command per line
- Format per line: `<number>. <title> - <command>`
- Numbering starts at 1 and increments for each command

### Error Conditions
- Must be run inside a git repository (exits with error if not)
- Config file must exist and be valid JSON (exits with error if missing or corrupt)

### Edge Cases
- Repository has no commands defined in config: prints "No commands defined for this repository"
- Repository has commands but list is empty: prints "No commands defined for this repository"
- Repo exists in config but has no commands key: handled as no commands

## add

### Signature
```
wut add
```

### Behavior
- Interactively prompts for command details:
  1. `title:` (required)
  2. `command:` (required)
  3. `description (optional):` (optional)
- Adds the command to the current repository's command list
- Creates repository entry if it doesn't exist in config
- Saves updated config to disk

### Error Conditions
- Must be run inside a git repository (exits with error if not)
- Config file must exist and be valid JSON (exits with error if missing or corrupt)
- Title is empty: exits with error "wut: title is required"
- Command is empty: exits with error "wut: command is required"
- Title already exists for this repository: exits with error "wut: command "<title>" already exists"
- Cannot determine repo path when creating new entry: exits with error

### Edge Cases
- Adding first command to a repo: creates repo entry with repo path from `git rev-parse --show-toplevel`
- Empty description: stored as null/None in config
- Command validation is not performed (any shell-compatible string is accepted)

## run

### Signature
```
wut run
wut run --cwd
```

### Arguments
- `--cwd`: optional flag to run command from current working directory instead of repo root

### Behavior
- Interactive fuzzy search interface for selecting commands
- Displays all commands in a scrollable list
- Typing filters the list by fuzzy matching against command title and command string
- List is sorted by match accuracy score
- Keyboard navigation:
  - Up/Down arrows: move selection
  - Enter: execute selected command
  - Ctrl+C or Esc: cancel without running
- Working directory: repo root by default, current directory if `--cwd` flag is present
- Subprocess inherits stdio (output streams directly to terminal)
- No argument forwarding in interactive mode (commands run as-is)

### Error Conditions
- Must be run inside a git repository (exits with error if not)
- Config file must exist and be valid JSON (exits with error if missing or corrupt)
- No commands defined for repository: displays message "No commands defined for this repository" and exits

### Edge Cases
- Empty command list: displays message and exits
- No matches for typed query: shows empty list
- Command fails during execution: subprocess error propagates directly

## edit

### Signature
```
wut edit
```

### Behavior
- Opens the commands.json file in a text editor for manual editing
- Editor resolution order:
  1. `core.editor` git config setting (via `git config --get core.editor`)
  2. `EDITOR` environment variable
  3. `vi` (if available)
  4. Error if no editor found
- Opens the commands.json file at `${XDG_CONFIG_HOME:-~/.config}/wut/commands.json`
- Subprocess inherits stdio (editor output goes directly to terminal)
- Waits for editor to exit before returning
- Does not validate JSON after editing (user is responsible for ensuring valid JSON)
- Default working directory: config directory containing commands.json

### Error Conditions
- Config file doesn't exist: exits with error "wut: config file not found at <path>" and guidance to run `wut init`
- No editor can be found: exits with error "wut: no editor found" and message listing attempted editors
- Editor command fails: exits with editor's exit code

### Edge Cases
- Editor command includes arguments (e.g., "vim -p"): arguments are passed through to editor
- Editor resolution happens before checking if commands.json exists (user sees editor error first if misconfigured)
- Invalid JSON after editing: subsequent wut commands will fail with config parse errors

## Shared Behavior

### Repo Key Derivation
- Repo key format: MD5 hash of the repo's absolute path, truncated to 16 characters
- Derived from `git rev-parse --show-toplevel` to get repo root
- Hash ensures uniqueness even if multiple repos have the same directory name
- Works with or without git remotes configured
- Repo key is used as identifier in commands.json, but repo's absolute path is also stored separately for reference

### Config File Format
```json
{
  "7e8a376c8bb0893e": {
    "repo": "/absolute/path/to/repo",
    "commands": [
      {
        "title": "command-name",
        "command": "shell command string",
        "description": "optional description"
      }
    ]
  }
}
```

### Exit Codes
- 0: success
- 1: any error

### Error Messages
- All error messages are prefixed with `wut:` and written to stderr
- Help/guidance is provided for common recoverable errors (e.g., missing config)

### Environment Variables
- `XDG_CONFIG_HOME`: optional override for config directory location
- If not set, defaults to `~/.config`
