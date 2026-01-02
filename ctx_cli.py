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
        "description": """Context management for LLM reasoning.\n\nCORE COMMANDS:
  scope <name> -m "<note>"   Create new reasoning scope. Use namespaces (e.g., plan/task-x, fix/bug-y).
  goto <name> -m "<note>"    Switch to existing scope.
  note -m "<message>"        Record episodic memory (event) in current scope.
  insight -m "<message>"     Record semantic memory (global fact/pattern).
  scopes                     List all scopes.
  notes                      List ALL episodic notes (Journal).
  insights                   List all global semantic insights.

WORKFLOW FOR PLANNING:
  1. ctx_cli scope plan/my-task -m "Building plan for task X"
  2. ctx_cli insights           # Check global rules
  3. ctx_cli notes              # Check history
  4. [Synthesize Plan]
  5. ctx_cli goto main -m "Plan ready: ..."
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
    try:
        tokens = shlex.split(command.strip())
    except Exception as e:
        return f"Error: {e}", None

    if not tokens: return "Error: Empty command", None
    action = tokens[0].lower()

    if action == "scope":
        name = tokens[1] if len(tokens) > 1 else None
        m = ""
        if "-m" in tokens: m = tokens[tokens.index("-m") + 1]
        return store.checkout(name, m, create=True)

    if action == "goto":
        name = tokens[1] if len(tokens) > 1 else None
        m = ""
        if "-m" in tokens: m = tokens[tokens.index("-m") + 1]
        return store.checkout(name, m, create=False)

    if action == "note":
        m = ""
        if "-m" in tokens: m = tokens[tokens.index("-m") + 1]
        return store.note(m)

    if action == "insight":
        m = ""
        if "-m" in tokens: m = tokens[tokens.index("-m") + 1]
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

    if action == "scopes":
        return "\n".join([f"{'* ' if n == store.current_branch else '  '}{n}" for n in store.branches.keys()]), None

    if action == "status":
        return store.status()

    return f"Unknown command: {action}", None
