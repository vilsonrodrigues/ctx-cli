"""
ctx_cli - Semantic CLI for LLM context/memory management.
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
        "description": """Context management for LLM reasoning.

CORE COMMANDS:
  scope <name> -m "<note>"   Create new scope (only from main).
  return -m "<note>"         Finalize scope and return to main.
  note -m "<message>"        Record episodic memory in current scope.
  insight -m "<message>"     Record semantic memory (global).
  status                     Show current state and memory stats.
  notes                      List all episodic notes.
  notes <scope>              List notes from specific scope.
  insights                   List all global insights.

MULTIPLE COMMANDS:
  Separate with ; to run multiple commands in one call.
  Example: return -m "done"; scope plan/next -m "starting"

WORKFLOW:
  1. scope plan/task -m "Goal..."
  2. [work, take notes]
  3. return -m "[SUMMARY]... [DECISION]... [NEXT]..."
""",
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

def execute_command(store: ContextStore, command: str) -> tuple[str, Event | None]:
    """Execute one or more ctx_cli commands. Multiple commands can be separated by ;"""
    # Split by ; to support multiple commands
    commands = [c.strip() for c in command.split(';') if c.strip()]
    
    if not commands:
        return "Error: Empty command", None
    
    # If single command, execute directly
    if len(commands) == 1:
        return _execute_single_command(store, commands[0])
    
    # Multiple commands: execute each and collect results
    results = []
    last_event = None
    for cmd in commands:
        result, event = _execute_single_command(store, cmd)
        results.append(f"[{cmd.split()[0]}] {result}")
        if event:
            last_event = event
    
    return "\n".join(results), last_event


def _execute_single_command(store: ContextStore, command: str) -> tuple[str, Event | None]:
    """Execute a single ctx_cli command."""
    try:
        tokens = shlex.split(command.strip())
    except Exception as e:
        return f"Error: {e}", None

    if not tokens: return "Error: Empty command", None
    action = tokens[0].lower()

    if action == "scope":
        name = tokens[1] if len(tokens) > 1 else None
        m = ""
        if "-m" in tokens:
            idx = tokens.index("-m")
            if idx + 1 < len(tokens):
                m = tokens[idx + 1]
        return store.checkout(name, m, create=True)

    if action == "return":
        m = ""
        if "-m" in tokens:
            idx = tokens.index("-m")
            if idx + 1 < len(tokens):
                m = tokens[idx + 1]
        return store.return_to_main(m)

    if action == "note":
        m = ""
        if "-m" in tokens:
            idx = tokens.index("-m")
            if idx + 1 < len(tokens):
                m = tokens[idx + 1]
        return store.note(m)

    if action == "insight":
        m = ""
        if "-m" in tokens:
            idx = tokens.index("-m")
            if idx + 1 < len(tokens):
                m = tokens[idx + 1]
        return store.insight(m)

    if action == "insights":
        return store.get_insights(), None

    if action == "notes":
        scope_name = tokens[1] if len(tokens) > 1 else None
        if scope_name:
            if scope_name not in store.branches:
                return f"Error: scope '{scope_name}' not found.", None
            branch = store.branches[scope_name]
            if not branch.notes:
                return f"No notes in '{scope_name}' yet.", None
            
            # Sort newest first
            sorted_notes = sorted(branch.notes, key=lambda x: x.timestamp, reverse=True)
            
            lines = [f"Notes in '{scope_name}':"]
            for n in sorted_notes:
                ts = n.timestamp.astimezone()
                date_str = ts.strftime("%a %b %d %H:%M:%S %Y %z")
                lines.append(f"Date:   {date_str}")
                lines.append(f"    {n.content}\n")
            return "\n".join(lines), None
        
        return store.get_all_notes(), None

    if action == "status":
        return store.status()

    return f"Unknown command: {action}", None
