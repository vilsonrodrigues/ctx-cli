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
        "description": """Context management for LLM reasoning. Manages your MEMORY, not files.

WHY USE THIS:
- Notes persist even when chat messages are cleared
- Isolate reasoning paths to avoid confusion
- Return to main with learnings preserved

CORE COMMANDS (4 total):

  scope <name> -m "<note>"
    Create new reasoning scope. Note stays in CURRENT scope (explains why you're leaving).
    Example: ctx_cli scope investigate-bug -m "Going to investigate the auth bug. Expect to find DB issue."

  goto <name> -m "<note>"
    Switch to existing scope. Note goes to DESTINATION scope (explains what you bring/conclude).
    Example: ctx_cli goto main -m "Found bug: race condition in save(). Fix: add mutex."

  note -m "<message>"
    Record learning in current scope. Be DETAILED: motives, objectives, results, conclusions.
    Example: ctx_cli note -m "Discovered: TaskRepo uses JSON. Files: task_repository.py. Pattern: atomic writes."

  scopes
    List all scopes.
    Example: ctx_cli scopes

  notes
    List notes in current scope.
    Example: ctx_cli notes

WORKFLOW:
  scope step-1 -m "Starting step 1: will create Task model"
  [work]
  note -m "Created Task with id, title, done. File: models/task.py"
  goto main -m "Step 1 complete: Task model ready at models/task.py"

RULES:
- Files are on DISK, scopes are in MEMORY. Switching scopes does NOT change files.
- ALWAYS use -m with scope and goto. No transitions without explanation.
- Write DETAILED notes: motives, objectives, what you found, conclusions.""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The ctx_cli command"
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
        # Core semantic commands
        "scope", "goto", "note", "scopes", "notes",
        # Legacy/other commands
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
    # scope <name> -m "note" - Create new scope, note stays in CURRENT (origin)
    # -------------------------------------------------------------------------
    if action == "scope":
        scope_name = None
        note = None
        i = 1

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                note = tokens[i + 1]
                i += 2
            elif not scope_name and not tokens[i].startswith("-"):
                scope_name = tokens[i]
                i += 1
            else:
                i += 1

        if not scope_name:
            return ParsedCommand(
                action="error",
                args={},
                error="scope requires name. Example: scope step-1 -m \"why I'm creating this\""
            )

        if not note:
            return ParsedCommand(
                action="error",
                args={},
                error="scope requires -m \"note\". Explain WHY you're creating this scope."
            )

        # Returns "scope" action - executor will:
        # 1. commit note to CURRENT branch
        # 2. then checkout to new branch
        return ParsedCommand(
            action="scope",
            args={"name": scope_name, "note": note}
        )

    # -------------------------------------------------------------------------
    # goto <name> -m "note" - Switch to scope, note goes to DESTINATION
    # -------------------------------------------------------------------------
    if action == "goto":
        scope_name = None
        note = None
        i = 1

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                note = tokens[i + 1]
                i += 2
            elif not scope_name and not tokens[i].startswith("-"):
                scope_name = tokens[i]
                i += 1
            else:
                i += 1

        if not scope_name:
            return ParsedCommand(
                action="error",
                args={},
                error="goto requires scope name. Example: goto main -m \"what I bring/conclude\""
            )

        if not note:
            return ParsedCommand(
                action="error",
                args={},
                error="goto requires -m \"note\". Explain what you bring to the destination."
            )

        # Returns "goto" action - executor will:
        # 1. checkout to destination branch
        # 2. commit note to DESTINATION branch
        return ParsedCommand(
            action="goto",
            args={"name": scope_name, "note": note}
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
    # scopes - List all scopes
    # -------------------------------------------------------------------------
    if action == "scopes":
        return ParsedCommand(action="scopes", args={})

    # -------------------------------------------------------------------------
    # notes [scope] - List notes in scope (default: current)
    # -------------------------------------------------------------------------
    if action == "notes":
        scope_name = tokens[1] if len(tokens) > 1 else None
        return ParsedCommand(action="notes", args={"scope": scope_name})

    # Legacy: paths -> scopes
    if action == "paths":
        return ParsedCommand(action="scopes", args={})

    # Legacy: trace -> notes (for viewing other scopes, use notes <scope>)
    if action == "trace":
        scope_name = tokens[1] if len(tokens) > 1 else None
        return ParsedCommand(action="notes", args={"scope": scope_name})

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
        error=f"Unknown command: {action}. Use: scope, goto, note, scopes, notes"
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

    # =========================================================================
    # Core semantic commands
    # =========================================================================

    if parsed.action == "scope":
        # scope: note goes to CURRENT (origin), then create new scope
        scope_name = parsed.args["name"]
        note = parsed.args["note"]

        # 1. Commit note to CURRENT branch (explains why leaving)
        from_branch = store.current_branch
        commit_result, commit_event = store.commit(f"[→ {scope_name}] {note}")

        # 2. Create and switch to new scope
        checkout_result, checkout_event = store.checkout(scope_name, "", create=True)

        if "error" in checkout_result.lower():
            return checkout_result, None

        return f"Created scope '{scope_name}' (note saved in '{from_branch}')", checkout_event

    if parsed.action == "goto":
        # goto: switch to destination, then add note there
        scope_name = parsed.args["name"]
        note = parsed.args["note"]
        from_branch = store.current_branch

        # 1. Switch to destination
        checkout_result, checkout_event = store.checkout(scope_name, "", create=False)

        if "error" in checkout_result.lower():
            return checkout_result, None

        # 2. Commit note to DESTINATION branch (what we bring/conclude)
        commit_result, commit_event = store.commit(f"[← {from_branch}] {note}")

        return f"Switched to '{scope_name}' (note saved)", commit_event

    if parsed.action == "scopes":
        # List all scopes
        lines = []
        for scope_name, branch in store.branches.items():
            prefix = "* " if scope_name == store.current_branch else "  "
            note_count = len(branch.commits)
            lines.append(f"{prefix}{scope_name} ({note_count} notes)")
        return "\n".join(lines) if lines else "No scopes yet.", None

    if parsed.action == "notes":
        # List notes in a scope
        scope_name = parsed.args.get("scope") or store.current_branch
        if scope_name not in store.branches:
            return f"Error: scope '{scope_name}' not found.", None

        branch = store.branches[scope_name]
        if not branch.commits:
            return f"No notes in '{scope_name}' yet.", None

        lines = [f"Notes in '{scope_name}':\n"]
        for commit in branch.commits:
            lines.append(f"  [{commit.hash[:7]}] {commit.message}")
        return "\n".join(lines), None

    # =========================================================================
    # Legacy/internal commands
    # =========================================================================

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
