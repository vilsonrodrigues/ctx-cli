"""
ctx_cli - Task-based CLI for LLM context management.

This module provides the tool definition and command parser for ctx_cli.
The model uses this tool to manage its own context/memory.

IMPORTANT: This is NOT git. Commands manage MEMORY, not files.
- Tasks = isolated memory spaces (like branches, but for your thoughts)
- Saves = snapshots of what you learned (like commits, but for knowledge)
"""

from __future__ import annotations

import re
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
        "description": """Task-based context/memory management. NOT git - manages your MEMORY, not files.

IMPORTANT: Files are on DISK. Tasks are in MEMORY. Switching tasks does NOT change files.

CORE COMMANDS:

  start <task> -m "<note>"
    Begin a new task. Creates isolated memory space.
    Example: ctx_cli start step-2-repository -m "Building JSON persistence layer"

  resume <task> -m "<note>"
    Continue an existing task.
    Example: ctx_cli resume step-1 -m "Checking what was done"

  save -m "<message>"
    Save your current knowledge to memory. CRITICAL: Write detailed messages!
    Good saves include: what was built, key decisions, patterns, files, next steps.
    Example: ctx_cli save -m "COMPLETED: TaskRepository with atomic writes..."

  tasks
    List all your tasks (past work areas).
    Example: ctx_cli tasks

  recall [task]
    Remember what you learned in a task. Use to review past work.
    Example: ctx_cli recall step-1
    Example: ctx_cli recall  (current task)

  done -m "<summary>"
    Mark current task complete and return to main with knowledge transfer.
    Example: ctx_cli done -m "Completed: Repository pattern implemented..."

WORKFLOW:
1. start <task> -m "what I'll do"
2. Do the work (read/write files)
3. save -m "detailed knowledge summary"
4. done -m "knowledge to carry forward"

REMEMBER: Files persist on disk regardless of task. Don't switch tasks to find files.""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The ctx_cli command (e.g., 'start step-1 -m \"note\"', 'save -m \"what I learned\"')"
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
        "description": """Write a plan before starting work. ALWAYS use this before 'ctx_cli start'.

WHEN TO USE:
- Before starting any new task
- Before creating a new task with 'start'

WHAT TO INCLUDE:
1. TASK: What needs to be done
2. DEPENDENCIES: What previous work this builds on
3. APPROACH: Steps you'll take
4. TASK NAME: Name for the new task

Example:
plan(content="TASK: Create TaskRepository for JSON persistence

DEPENDENCIES: Task model from step-1

APPROACH:
1. Read models/task.py to understand Task structure
2. Create repositories/task_repository.py with CRUD methods
3. Use atomic writes (temp file + rename)
4. Verify by reading the file back

TASK NAME: step-2-repository")
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
    return f"Plan recorded ({len(lines)} items). Now proceed with: ctx_cli start <task-name> -m \"<note>\""


# =============================================================================
# Command Parser
# =============================================================================

@dataclass
class ParsedCommand:
    """Result of parsing a ctx_cli command."""

    action: Literal[
        "start", "resume", "save", "tasks", "recall", "done",
        "status", "diff", "history", "stash", "merge",
        "cherry-pick", "bisect", "reset", "tag",
        # Legacy aliases for backwards compatibility
        "commit", "checkout", "branch", "log",
        "error"
    ]
    args: dict
    error: str | None = None


def parse_command(command: str) -> ParsedCommand:
    """
    Parse a ctx_cli command string into structured form.

    New commands:
        start <task> -m "note"     -> create new task
        resume <task> -m "note"    -> continue existing task
        save -m "message"          -> save knowledge
        tasks                      -> list all tasks
        recall [task]              -> remember past work
        done -m "summary"          -> complete task, return to main

    Legacy aliases (for backwards compatibility):
        checkout -b <branch> -m    -> start
        checkout <branch> -m       -> resume
        commit -m                  -> save
        branch                     -> tasks
        log                        -> recall
    """
    try:
        tokens = shlex.split(command.strip())
    except ValueError as e:
        return ParsedCommand(action="error", args={}, error=f"Parse error: {e}")

    if not tokens:
        return ParsedCommand(action="error", args={}, error="Empty command")

    action = tokens[0].lower()

    # -------------------------------------------------------------------------
    # start <task> -m "note" - Begin new task
    # -------------------------------------------------------------------------
    if action == "start":
        task_name = None
        note = None
        i = 1

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                note = tokens[i + 1]
                i += 2
            elif not task_name and not tokens[i].startswith("-"):
                task_name = tokens[i]
                i += 1
            else:
                i += 1

        if not task_name:
            return ParsedCommand(
                action="error",
                args={},
                error="start requires task name. Example: start step-1 -m \"note\""
            )

        if not note:
            return ParsedCommand(
                action="error",
                args={},
                error="start requires -m \"note\". Example: start step-1 -m \"what I'll do\""
            )

        # Map to checkout with create=True
        return ParsedCommand(
            action="checkout",
            args={"branch": task_name, "note": note, "create": True}
        )

    # -------------------------------------------------------------------------
    # resume <task> -m "note" - Continue existing task
    # -------------------------------------------------------------------------
    if action == "resume":
        task_name = None
        note = None
        i = 1

        while i < len(tokens):
            if tokens[i] == "-m" and i + 1 < len(tokens):
                note = tokens[i + 1]
                i += 2
            elif not task_name and not tokens[i].startswith("-"):
                task_name = tokens[i]
                i += 1
            else:
                i += 1

        if not task_name:
            return ParsedCommand(
                action="error",
                args={},
                error="resume requires task name. Example: resume step-1 -m \"note\""
            )

        if not note:
            return ParsedCommand(
                action="error",
                args={},
                error="resume requires -m \"note\". Example: resume step-1 -m \"continuing work\""
            )

        # Map to checkout with create=False
        return ParsedCommand(
            action="checkout",
            args={"branch": task_name, "note": note, "create": False}
        )

    # -------------------------------------------------------------------------
    # save -m "message" - Save knowledge to memory
    # -------------------------------------------------------------------------
    if action == "save":
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
                error="save requires -m \"message\". Write what you learned!"
            )

        return ParsedCommand(action="commit", args={"message": message})

    # -------------------------------------------------------------------------
    # tasks - List all tasks
    # -------------------------------------------------------------------------
    if action == "tasks":
        return ParsedCommand(action="branch", args={"name": None})

    # -------------------------------------------------------------------------
    # recall [task] - Remember past work
    # -------------------------------------------------------------------------
    if action == "recall":
        task_name = tokens[1] if len(tokens) > 1 else None
        return ParsedCommand(action="log", args={"branch": task_name})

    # -------------------------------------------------------------------------
    # done -m "summary" - Complete task and return to main
    # -------------------------------------------------------------------------
    if action == "done":
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
                error="done requires -m \"summary\". What knowledge to carry forward?"
            )

        # Map to checkout main with the summary as note
        return ParsedCommand(
            action="checkout",
            args={"branch": "main", "note": summary, "create": False}
        )

    # =========================================================================
    # LEGACY COMMANDS (backwards compatibility)
    # =========================================================================

    # -------------------------------------------------------------------------
    # commit -m "message" (legacy -> save)
    # -------------------------------------------------------------------------
    if action == "commit":
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
                error="commit requires -m \"message\". Prefer using 'save -m \"...\"'"
            )

        return ParsedCommand(action="commit", args={"message": message})

    # -------------------------------------------------------------------------
    # checkout [-b] <branch> -m "note" (legacy -> start/resume)
    # -------------------------------------------------------------------------
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
                error="checkout requires branch name. Prefer 'start' or 'resume'"
            )

        if not note:
            return ParsedCommand(
                action="error",
                args={},
                error="checkout requires -m \"note\". Prefer 'start' or 'resume'"
            )

        return ParsedCommand(
            action="checkout",
            args={"branch": branch_name, "note": note, "create": create}
        )

    # -------------------------------------------------------------------------
    # branch [name] (legacy -> tasks)
    # -------------------------------------------------------------------------
    if action == "branch":
        name = tokens[1] if len(tokens) > 1 else None
        return ParsedCommand(action="branch", args={"name": name})

    # -------------------------------------------------------------------------
    # log [branch] (legacy -> recall)
    # -------------------------------------------------------------------------
    if action == "log":
        branch_name = tokens[1] if len(tokens) > 1 else None
        return ParsedCommand(action="log", args={"branch": branch_name})

    # -------------------------------------------------------------------------
    # tag <name> [-m "description"]
    # -------------------------------------------------------------------------
    if action == "tag":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="tag requires a name"
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
    # status
    # -------------------------------------------------------------------------
    if action == "status":
        return ParsedCommand(action="status", args={})

    # -------------------------------------------------------------------------
    # diff <branch>
    # -------------------------------------------------------------------------
    if action == "diff":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="diff requires a task name to compare"
            )
        return ParsedCommand(action="diff", args={"branch": tokens[1]})

    # -------------------------------------------------------------------------
    # history
    # -------------------------------------------------------------------------
    if action == "history":
        return ParsedCommand(action="history", args={})

    # -------------------------------------------------------------------------
    # stash push/pop/list
    # -------------------------------------------------------------------------
    if action == "stash":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="stash requires subcommand: push, pop, or list"
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

    # -------------------------------------------------------------------------
    # merge <branch> [-m "message"]
    # -------------------------------------------------------------------------
    if action == "merge":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="merge requires a task name"
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

    # -------------------------------------------------------------------------
    # cherry-pick <commit>
    # -------------------------------------------------------------------------
    if action == "cherry-pick":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="cherry-pick requires a commit hash or tag"
            )
        return ParsedCommand(action="cherry-pick", args={"commit": tokens[1]})

    # -------------------------------------------------------------------------
    # bisect start|good|bad|reset
    # -------------------------------------------------------------------------
    if action == "bisect":
        if len(tokens) < 2:
            return ParsedCommand(
                action="error",
                args={},
                error="bisect requires subcommand: start, good, bad, or reset"
            )

        subaction = tokens[1].lower()

        if subaction == "start":
            return ParsedCommand(action="bisect", args={"subaction": "start"})

        if subaction == "good":
            commit = tokens[2] if len(tokens) > 2 else None
            return ParsedCommand(action="bisect", args={"subaction": "good", "commit": commit})

        if subaction == "bad":
            commit = tokens[2] if len(tokens) > 2 else None
            return ParsedCommand(action="bisect", args={"subaction": "bad", "commit": commit})

        if subaction == "reset":
            return ParsedCommand(action="bisect", args={"subaction": "reset"})

        return ParsedCommand(
            action="error",
            args={},
            error=f"Unknown bisect subcommand: {subaction}"
        )

    # -------------------------------------------------------------------------
    # reset [commit] [--hard]
    # -------------------------------------------------------------------------
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

    return ParsedCommand(
        action="error",
        args={},
        error=f"Unknown command: {action}. Use: start, resume, save, tasks, recall, done"
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

    if parsed.action == "bisect":
        subaction = parsed.args["subaction"]
        if subaction == "start":
            return store.bisect_start()
        if subaction == "good":
            return store.bisect_good(parsed.args.get("commit"))
        if subaction == "bad":
            return store.bisect_bad(parsed.args.get("commit"))
        if subaction == "reset":
            return store.bisect_reset()

    if parsed.action == "reset":
        return store.reset(parsed.args.get("commit"), parsed.args.get("hard", False))

    return f"Unknown action: {parsed.action}", None
