"""
ctx_cli - A Git-like CLI for LLM context management.

This module provides the tool definition and command parser for ctx_cli.
The model uses this tool to manage its own context.
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
        "description": """Git-like context management CLI. Use this to manage your working memory and episodic memory.

COMMANDS:

  commit -m "<message>"
    Save current reasoning state. Clears working memory, stores as episodic memory.
    WHEN TO USE: After completing a subtask, before context gets too large.
    Example: ctx_cli commit -m "Identified bug in JSON parser, root cause is unescaped quotes"

  checkout <branch> -m "<note>"
    Switch to another branch. The note explains what you'll do there.
    Use -b to create a new branch.
    WHEN TO USE: Starting a new isolated subtask, or returning to previous work.
    Example: ctx_cli checkout -b fix-parser -m "Going to fix the JSON parser bug"

  branch [name]
    List all branches, or create a new one.
    Example: ctx_cli branch
    Example: ctx_cli branch feature-auth

  tag <name> [-m "<description>"]
    Create an immutable marker on current commit. Tags cannot be deleted.
    WHEN TO USE: After user approval, major milestones, stable states.
    Example: ctx_cli tag v1-approved -m "User approved the architecture"

  log
    Show commit history for current branch.

  status
    Show current branch, working messages count, last commit.

  diff <branch>
    Compare current branch with another branch's commits.

  history
    Show recent ctx_cli commands you've executed.

  stash push -m "<message>"
    Save current working state temporarily. Use when interrupted.
    Example: ctx_cli stash push -m "User asked about something else"

  stash pop [stash_id]
    Restore stashed state.

  stash list
    List all stash entries.

WORKFLOW:
1. Work on a task, accumulating messages in working memory
2. When subtask complete, commit with a meaningful message
3. For new tasks, checkout a new branch with a transition note
4. Tag important milestones (user approvals, stable states)
5. Use stash when interrupted mid-task""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The full ctx_cli command to execute (e.g., 'commit -m \"message\"', 'checkout -b new-branch -m \"note\"')"
                }
            },
            "required": ["command"]
        }
    }
}


# =============================================================================
# Command Parser
# =============================================================================

@dataclass
class ParsedCommand:
    """Result of parsing a ctx_cli command."""

    action: Literal[
        "commit", "checkout", "branch", "tag", "log",
        "status", "diff", "history", "stash", "error"
    ]
    args: dict
    error: str | None = None


def parse_command(command: str) -> ParsedCommand:
    """
    Parse a ctx_cli command string into structured form.

    Examples:
        commit -m "my message"
        checkout -b new-branch -m "going to work on X"
        checkout existing-branch -m "switching back"
        branch
        branch new-name
        tag v1 -m "description"
        log
        status
        diff other-branch
        history
        stash push -m "wip"
        stash pop
        stash list
    """
    try:
        # Use shlex to properly handle quoted strings
        tokens = shlex.split(command.strip())
    except ValueError as e:
        return ParsedCommand(action="error", args={}, error=f"Parse error: {e}")

    if not tokens:
        return ParsedCommand(action="error", args={}, error="Empty command")

    action = tokens[0].lower()

    # -------------------------------------------------------------------------
    # commit -m "message"
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
                error="commit requires -m \"message\""
            )

        return ParsedCommand(action="commit", args={"message": message})

    # -------------------------------------------------------------------------
    # checkout [-b] <branch> -m "note"
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
                error="checkout requires branch name"
            )

        if not note:
            return ParsedCommand(
                action="error",
                args={},
                error="checkout requires -m \"note\" (transition note is mandatory)"
            )

        return ParsedCommand(
            action="checkout",
            args={"branch": branch_name, "note": note, "create": create}
        )

    # -------------------------------------------------------------------------
    # branch [name]
    # -------------------------------------------------------------------------
    if action == "branch":
        name = tokens[1] if len(tokens) > 1 else None
        return ParsedCommand(action="branch", args={"name": name})

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
    # log
    # -------------------------------------------------------------------------
    if action == "log":
        return ParsedCommand(action="log", args={})

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
                error="diff requires a branch name to compare"
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

    return ParsedCommand(
        action="error",
        args={},
        error=f"Unknown command: {action}"
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
        return store.log()

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

    return f"Unknown action: {parsed.action}", None
