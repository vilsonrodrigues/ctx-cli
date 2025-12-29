"""
ctx_cli - Semantic CLI for LLM context/memory management.

This module provides the tool definition and command parser for ctx_cli.
The model uses this tool to manage its own context/memory.

TERMINOLOGY:
- Paths = Lines of reasoning (isolated memory spaces)
- Notes = Episodic memories (snapshots of what you learned)
- Anchors = Fixed truths (immutable markers)
- Trace = History of your reasoning
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Literal

from ctx_store import ContextStore, Event


# =============================================================================
# Tool Definition for OpenAI
# =============================================================================

CTX_CLI_TOOL = {
    "type": "function",
    "function": {
        "name": "ctx_cli",
        "description": """Semantic context/memory management. Manages your MEMORY, not files.

IMPORTANT: Files are on DISK. Scopes are in MEMORY. Switching scopes does NOT change files.

CORE COMMANDS (with git equivalent):

  scope <path> -m "<note>"          [≈ git checkout -b]
    Enter a new scope (line of reasoning). Creates isolated memory space.
    Example: ctx_cli scope step-2-repository -m "Building JSON persistence layer"

  goto <path> -m "<note>"           [≈ git checkout]
    Switch to an existing scope.
    Example: ctx_cli goto step-1 -m "Checking what was done"

  note -m "<message>"               [≈ git commit]
    Record what you learned (episodic memory). CRITICAL: Write detailed notes!
    Good notes include: what was built, key decisions, patterns, files, next steps.
    Example: ctx_cli note -m "COMPLETED: TaskRepository with atomic writes..."

  paths                             [≈ git branch]
    List all your scopes (lines of reasoning).
    Example: ctx_cli paths

  trace [path]                      [≈ git log]
    See the history of notes in a scope. Use to review past reasoning.
    Example: ctx_cli trace step-1
    Example: ctx_cli trace  (current scope)

  finish -m "<summary>"             [≈ git checkout main]
    Complete current scope and return to main with knowledge transfer.
    Example: ctx_cli finish -m "Completed: Repository pattern implemented..."

OTHER COMMANDS (with git equivalent):

  anchor <name> -m "<description>"  [≈ git tag]
    Create an immutable marker (fixed truth). Cannot be deleted.
    Example: ctx_cli anchor v1-approved -m "User approved the architecture"

  pause -m "<message>"              [≈ git stash]
    Archive current work temporarily (when interrupted).
    Example: ctx_cli pause -m "User asked about something else"

  resume [id]                       [≈ git stash pop]
    Resume archived work.
    Example: ctx_cli resume

  delta <path>                      [≈ git diff]
    Compare current scope with another scope's notes.
    Example: ctx_cli delta step-1

  rewind [note-id] [--hard]         [≈ git reset]
    Go back to a previous note. --hard clears working messages.
    Example: ctx_cli rewind abc123 --hard

  extract <note-id>                 [≈ git cherry-pick]
    Apply a specific note from any scope to current scope.
    Example: ctx_cli extract abc123

  sync <path> -m "<message>"        [≈ git merge]
    Bring notes from another scope into current scope.
    Example: ctx_cli sync feature-auth -m "Completed auth implementation"

WORKFLOW:
1. scope <path> -m "what I'll do"
2. Do the work (read/write files)
3. note -m "detailed knowledge summary"
4. finish -m "knowledge to carry forward"

REMEMBER: Files persist on disk regardless of scope. Don't switch scopes to find files.""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The ctx_cli command (e.g., 'begin step-1 -m \"note\"', 'note -m \"what I learned\"')"
                }
            },
            "required": ["command"]
        }
    }
}


# =============================================================================
# Plan Tool - Forces agent to think before acting
# =============================================================================

PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "plan",
        "description": """Write a plan before starting work. ALWAYS use this before 'ctx_cli scope'.

WHEN TO USE:
- Before starting any new task
- Before creating a new scope with 'scope'

WHAT TO INCLUDE:
1. TASK: What needs to be done
2. DEPENDENCIES: What previous work this builds on
3. APPROACH: Steps you'll take
4. PATH NAME: Name for the new path

Example:
plan(content="TASK: Create TaskRepository for JSON persistence

DEPENDENCIES: Task model from step-1

APPROACH:
1. Read models/task.py to understand Task structure
2. Create repositories/task_repository.py with CRUD methods
3. Use atomic writes (temp file + rename)
4. Verify by reading the file back

PATH NAME: step-2-repository")
""",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Your plan describing what you'll do and how"
                }
            },
            "required": ["content"]
        }
    }
}


def execute_plan(content: str) -> str:
    """Execute plan tool - simply acknowledges the plan."""
    lines = [l for l in content.strip().split('\n') if l.strip()]
    return f"Plan recorded ({len(lines)} items). Now proceed with: ctx_cli scope <path-name> -m \"<note>\""


# =============================================================================
# Command Parser
# =============================================================================

@dataclass
class ParsedCommand:
    """Result of parsing a ctx_cli command."""

    action: Literal[
        # New semantic commands
        "begin", "goto", "note", "paths", "trace", "return",
        "anchor", "pause", "resume", "delta", "rewind", "extract", "sync",
        # Internal actions (mapped from semantic commands)
        "commit", "checkout", "branch", "log", "tag", "stash",
        "diff", "reset", "cherry-pick", "merge",
        "status", "history",
        "error"
    ]
    args: dict
    error: str | None = None


def parse_command(command: str) -> ParsedCommand:
    """
    Parse a ctx_cli command string into structured form.

    Semantic commands:
        begin <path> -m "note"     -> create new path
        goto <path> -m "note"      -> switch to existing path
        note -m "message"          -> record episodic memory
        paths                      -> list all paths
        trace [path]               -> see history of notes
        return -m "summary"        -> complete path, return to main
        anchor <name> -m "desc"    -> create immutable marker
        pause -m "message"         -> archive current work
        resume [id]                -> resume archived work
        delta <path>               -> compare paths
        rewind [id] [--hard]       -> go back in time
        extract <id>               -> selective memory
        sync <path> -m "message"   -> synchronize paths
    """
    try:
        tokens = shlex.split(command.strip())
    except ValueError as e:
        return ParsedCommand(action="error", args={}, error=f"Parse error: {e}")

    if not tokens:
        return ParsedCommand(action="error", args={}, error="Empty command")

    action = tokens[0].lower()

    # -------------------------------------------------------------------------
    # scope <path> -m "note" - Enter new scope (line of reasoning)
    # -------------------------------------------------------------------------
    if action == "scope":
        path_name = None
        note = None
        i = 1

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                note = tokens[i + 1]
                i += 2
            elif not path_name and not tokens[i].startswith("-"):
                path_name = tokens[i]
                i += 1
            else:
                i += 1

        if not path_name:
            return ParsedCommand(
                action="error",
                args={},
                error="scope requires path name. Example: scope step-1 -m \"note\""
            )

        if not note:
            return ParsedCommand(
                action="error",
                args={},
                error="scope requires -m \"note\". Example: scope step-1 -m \"what I'll do\""
            )

        return ParsedCommand(
            action="checkout",
            args={"branch": path_name, "note": note, "create": True}
        )

    # -------------------------------------------------------------------------
    # goto <path> -m "note" - Switch to existing scope
    # -------------------------------------------------------------------------
    if action == "goto":
        path_name = None
        note = None
        i = 1

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                note = tokens[i + 1]
                i += 2
            elif not path_name and not tokens[i].startswith("-"):
                path_name = tokens[i]
                i += 1
            else:
                i += 1

        if not path_name:
            return ParsedCommand(
                action="error",
                args={},
                error="goto requires path name. Example: goto step-1 -m \"note\""
            )

        if not note:
            return ParsedCommand(
                action="error",
                args={},
                error="goto requires -m \"note\". Example: goto step-1 -m \"continuing work\""
            )

        return ParsedCommand(
            action="checkout",
            args={"branch": path_name, "note": note, "create": False}
        )

    # -------------------------------------------------------------------------
    # note -m "message" - Record episodic memory
    # -------------------------------------------------------------------------
    if action == "note":
        message = None
        i = 1
        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                message = tokens[i + 1]
                i += 2
            else:
                i += 1

        if not message:
            return ParsedCommand(
                action="error",
                args={},
                error="note requires -m \"message\". Write what you learned!"
            )

        return ParsedCommand(action="commit", args={"message": message})

    # -------------------------------------------------------------------------
    # paths - List all paths
    # -------------------------------------------------------------------------
    if action == "paths":
        return ParsedCommand(action="branch", args={"name": None})

    # -------------------------------------------------------------------------
    # trace [path] - See history of notes
    # -------------------------------------------------------------------------
    if action == "trace":
        path_name = tokens[1] if len(tokens) > 1 else None
        return ParsedCommand(action="log", args={"branch": path_name})

    # -------------------------------------------------------------------------
    # finish -m "summary" - Complete scope and return to main
    # -------------------------------------------------------------------------
    if action == "finish":
        summary = None
        i = 1
        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                summary = tokens[i + 1]
                i += 2
            else:
                i += 1

        if not summary:
            return ParsedCommand(
                action="error",
                args={},
                error="finish requires -m \"summary\". What knowledge to carry forward?"
            )

        return ParsedCommand(
            action="checkout",
            args={"branch": "main", "note": summary, "create": False}
        )

    # -------------------------------------------------------------------------
    # anchor <name> -m "description" - Create immutable marker
    # -------------------------------------------------------------------------
    if action == "anchor":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="anchor requires a name"
            )

        name = tokens[1]
        description = ""
        i = 2

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                description = tokens[i + 1]
                i += 2
            else:
                i += 1

        return ParsedCommand(action="tag", args={"name": name, "description": description})

    # -------------------------------------------------------------------------
    # pause -m "message" - Archive current work
    # -------------------------------------------------------------------------
    if action == "pause":
        message = "WIP"
        i = 1
        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                message = tokens[i + 1]
                i += 2
            else:
                i += 1
        return ParsedCommand(action="stash", args={"subaction": "push", "message": message})

    # -------------------------------------------------------------------------
    # resume [id] - Resume archived work
    # -------------------------------------------------------------------------
    if action == "resume":
        stash_id = tokens[1] if len(tokens) > 1 else None
        return ParsedCommand(action="stash", args={"subaction": "pop", "stash_id": stash_id})

    # -------------------------------------------------------------------------
    # delta <path> - Compare paths
    # -------------------------------------------------------------------------
    if action == "delta":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="delta requires a path name to compare"
            )
        return ParsedCommand(action="diff", args={"branch": tokens[1]})

    # -------------------------------------------------------------------------
    # rewind [id] [--hard] - Go back in time
    # -------------------------------------------------------------------------
    if action == "rewind":
        note_id = None
        hard = False
        i = 1

        while i < len(tokens):
            if tokens[i] == "--hard":
                hard = True
                i += 1
            elif not note_id and not tokens[i].startswith("-"):
                note_id = tokens[i]
                i += 1
            else:
                i += 1

        return ParsedCommand(action="reset", args={"commit": note_id, "hard": hard})

    # -------------------------------------------------------------------------
    # extract <note-id> - Selective memory
    # -------------------------------------------------------------------------
    if action == "extract":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="extract requires a note ID"
            )
        return ParsedCommand(action="cherry-pick", args={"commit": tokens[1]})

    # -------------------------------------------------------------------------
    # sync <path> -m "message" - Synchronize paths
    # -------------------------------------------------------------------------
    if action == "sync":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="sync requires a path name"
            )

        path = tokens[1]
        message = None
        i = 2

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                message = tokens[i + 1]
                i += 2
            else:
                i += 1

        return ParsedCommand(action="merge", args={"branch": path, "message": message})

    # =========================================================================
    # LEGACY COMMANDS (backwards compatibility)
    # =========================================================================

    # commit/save -> note
    if action in ("commit", "save"):
        message = None
        i = 1
        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                message = tokens[i + 1]
                i += 2
            else:
                i += 1

        if not message:
            return ParsedCommand(
                action="error",
                args={},
                error=f"{action} requires -m \"message\". Prefer using 'note -m \"...\"'"
            )

        return ParsedCommand(action="commit", args={"message": message})

    # checkout -> begin/goto
    if action == "checkout":
        branch_name = None
        note = None
        create = False
        i = 1

        while i < len(tokens):
            if tokens[i] == "-b":
                create = True
                i += 1
            elif tokens[i] == "-m" and i + 1 < len(tokens):
                note = tokens[i + 1]
                i += 2
            elif not branch_name and not tokens[i].startswith("-"):
                branch_name = tokens[i]
                i += 1
            else:
                i += 1

        if not branch_name:
            return ParsedCommand(
                action="error",
                args={},
                error="checkout requires branch name. Prefer 'begin' or 'goto'"
            )

        if not note:
            return ParsedCommand(
                action="error",
                args={},
                error="checkout requires -m \"note\". Prefer 'begin' or 'goto'"
            )

        return ParsedCommand(
            action="checkout",
            args={"branch": branch_name, "note": note, "create": create}
        )

    # start/begin -> scope
    if action in ("start", "begin"):
        path_name = None
        note = None
        i = 1

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                note = tokens[i + 1]
                i += 2
            elif not path_name and not tokens[i].startswith("-"):
                path_name = tokens[i]
                i += 1
            else:
                i += 1

        if not path_name:
            return ParsedCommand(
                action="error",
                args={},
                error=f"{action} requires path name. Prefer 'scope'"
            )

        if not note:
            return ParsedCommand(
                action="error",
                args={},
                error=f"{action} requires -m \"note\". Prefer 'scope'"
            )

        return ParsedCommand(
            action="checkout",
            args={"branch": path_name, "note": note, "create": True}
        )

    # done/return -> finish
    if action in ("done", "return"):
        summary = None
        i = 1
        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                summary = tokens[i + 1]
                i += 2
            else:
                i += 1

        if not summary:
            return ParsedCommand(
                action="error",
                args={},
                error=f"{action} requires -m \"summary\". Prefer 'finish'"
            )

        return ParsedCommand(
            action="checkout",
            args={"branch": "main", "note": summary, "create": False}
        )

    # branch/tasks -> paths
    if action in ("branch", "tasks"):
        name = tokens[1] if len(tokens) > 1 else None
        return ParsedCommand(action="branch", args={"name": name})

    # log/recall -> trace
    if action in ("log", "recall"):
        branch_name = tokens[1] if len(tokens) > 1 else None
        return ParsedCommand(action="log", args={"branch": branch_name})

    # tag -> anchor
    if action == "tag":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="tag requires a name. Prefer 'anchor'"
            )

        name = tokens[1]
        description = ""
        i = 2

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                description = tokens[i + 1]
                i += 2
            else:
                i += 1

        return ParsedCommand(action="tag", args={"name": name, "description": description})

    # stash -> pause/resume
    if action == "stash":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="stash requires subcommand. Prefer 'pause' or 'resume'"
            )

        subaction = tokens[1].lower()

        if subaction == "push":
            message = "WIP"
            i = 2
            while i < len(tokens):
                if tokens[i] == "-m" and i + 1 < len(tokens):
                    message = tokens[i + 1]
                    i += 2
                else:
                    i += 1
            return ParsedCommand(action="stash", args={"subaction": "push", "message": message})

        if subaction == "pop":
            stash_id = tokens[2] if len(tokens) > 2 else None
            return ParsedCommand(action="stash", args={"subaction": "pop", "stash_id": stash_id})

        if subaction == "list":
            return ParsedCommand(action="stash", args={"subaction": "list"})

        return ParsedCommand(
            action="error",
            args={},
            error=f"Unknown stash subcommand: {subaction}"
        )

    # diff -> delta
    if action == "diff":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="diff requires a path name. Prefer 'delta'"
            )
        return ParsedCommand(action="diff", args={"branch": tokens[1]})

    # reset -> rewind
    if action == "reset":
        commit = None
        hard = False
        i = 1

        while i < len(tokens):
            if tokens[i] == "--hard":
                hard = True
                i += 1
            elif not commit and not tokens[i].startswith("-"):
                commit = tokens[i]
                i += 1
            else:
                i += 1

        return ParsedCommand(action="reset", args={"commit": commit, "hard": hard})

    # cherry-pick -> extract
    if action == "cherry-pick":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="cherry-pick requires a note ID. Prefer 'extract'"
            )
        return ParsedCommand(action="cherry-pick", args={"commit": tokens[1]})

    # merge -> sync
    if action == "merge":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="merge requires a path name. Prefer 'sync'"
            )

        branch = tokens[1]
        message = None
        i = 2

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                message = tokens[i + 1]
                i += 2
            else:
                i += 1

        return ParsedCommand(action="merge", args={"branch": branch, "message": message})

    # status
    if action == "status":
        return ParsedCommand(action="status", args={})

    # history
    if action == "history":
        return ParsedCommand(action="history", args={})

    return ParsedCommand(
        action="error",
        args={},
        error=f"Unknown command: {action}. Use: scope, goto, note, paths, trace, finish"
    )


# =============================================================================
# Command Executor
# =============================================================================

def execute_command(store: ContextStore, command: str) -> tuple[str, Event | None]:
    """
    Execute a ctx_cli command on the store.

    Returns:
        Tuple of (result_message, event)
    """
    parsed = parse_command(command)

    if parsed.action == "error":
        return f"Error: {parsed.error}", None

    if parsed.action == "commit":
        return store.commit(parsed.args["message"])

    if parsed.action == "checkout":
        return store.checkout(
            parsed.args["branch"],
            parsed.args["note"],
            parsed.args["create"]
        )

    if parsed.action == "branch":
        return store.branch(parsed.args["name"])

    if parsed.action == "tag":
        return store.tag(parsed.args["name"], parsed.args["description"])

    if parsed.action == "log":
        return store.log(branch_name=parsed.args.get("branch"))

    if parsed.action == "status":
        return store.status()

    if parsed.action == "diff":
        return store.diff(parsed.args["branch"])

    if parsed.action == "history":
        return store.history()

    if parsed.action == "stash":
        subaction = parsed.args["subaction"]
        if subaction == "push":
            return store.stash_push(parsed.args["message"])
        if subaction == "pop":
            return store.stash_pop(parsed.args.get("stash_id"))
        if subaction == "list":
            return store.stash_list()

    if parsed.action == "merge":
        return store.merge(parsed.args["branch"], parsed.args.get("message"))

    if parsed.action == "cherry-pick":
        return store.cherry_pick(parsed.args["commit"])

    if parsed.action == "reset":
        return store.reset(parsed.args.get("commit"), parsed.args.get("hard", False))

    return f"Unknown action: {parsed.action}", None
