"""
Knowledge Retention Demo: Cross-project memory.

Scenario:
- Project A: Build a User model with validation
- Project B (NEW PROJECT): Build a Product model with similar patterns

LINEAR: Project B starts from scratch - no memory of how Project A was built
SCOPE: Project B can query notes from Project A to recall patterns/decisions

This demonstrates episodic memory across different projects.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from tokens import TokenTracker

# =============================================================================
# Tools
# =============================================================================

READ_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file's contents.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"}
            },
            "required": ["path"]
        }
    }
}

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write content to a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["path", "content"]
        }
    }
}


def execute_tool(tool_name: str, args: dict, workdir: str) -> str:
    """Execute a tool."""
    try:
        if tool_name == "read_file":
            path = os.path.join(workdir, args["path"])
            if os.path.exists(path):
                with open(path) as f:
                    return f.read()[:3000]
            return f"Error: File not found: {args['path']}"

        elif tool_name == "write_file":
            path = os.path.join(workdir, args["path"])
            os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
            with open(path, "w") as f:
                f.write(args["content"])
            return f"Written {len(args['content'])} bytes to {args['path']}"

        elif tool_name == "plan":
            return "Plan recorded. Proceed with your next action."

        return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Error: {str(e)}"


# =============================================================================
# Tasks
# =============================================================================

PROJECT_A_TASK = """Create a User model in models/user.py with:
- User dataclass with: id (str), email (str), name (str), password_hash (str), created_at (datetime), is_active (bool)
- Email validation method (must contain @)
- Password validation (min 8 chars)
- is_valid() method that checks all validations
- to_dict() method for serialization

Make sure to include proper imports and docstrings.
Read the file back to confirm."""

PROJECT_B_TASK_LINEAR = """Create a Product model in models/product.py with:
- Product dataclass with: id (str), name (str), price (float), stock (int), created_at (datetime), is_available (bool)
- Price validation (must be positive)
- Stock validation (must be >= 0)
- is_valid() method that checks all validations
- to_dict() method for serialization

Use similar patterns to what you would use for a User model.
Read the file back to confirm."""

PROJECT_B_TASK_BRANCH = """Create a Product model in models/product.py with:
- Product dataclass with: id (str), name (str), price (float), stock (int), created_at (datetime), is_available (bool)
- Price validation (must be positive)
- Stock validation (must be >= 0)
- is_valid() method that checks all validations
- to_dict() method for serialization

IMPORTANT: First use 'notes' to recall how you built the User model.
Apply the same patterns and structure you used there."""

SYSTEM_PROMPT_LINEAR = """You are a software developer.

Tools: read_file, write_file

Complete the task thoroughly."""

SYSTEM_PROMPT_BRANCH = '''You are a software developer.

Tools: read_file, write_file, ctx_cli

# WHY NOTES MATTER

Your context resets between projects. Without notes, you forget everything.
Notes are your ONLY long-term memory. They persist forever.

When you take good notes:
- Future projects can recall your patterns and decisions
- You avoid reinventing solutions you already created
- Your knowledge compounds across projects

When you skip notes:
- Next project starts from zero
- You lose all the patterns you established
- You waste time rediscovering what you already knew

# COMMANDS (4 total)

scope <name> -m "..."   Create scope. Note saves in CURRENT scope first.
note -m "..."           Save to memory. Be VERY detailed.
goto main -m "..."      Return. Note saves in main.
notes <scope>           Read notes from any scope.

# WORKFLOW (follow exactly, in this order)

1. SCOPE FIRST: scope project-name -m "what I will build"
   - NEVER read/write files before creating scope

2. WORK: read files, write code
   - Do ONLY what was asked, nothing more

3. NOTE BEFORE LEAVING: note -m "DETAILED summary"
   Include: FILES, PATTERNS, DECISIONS, REUSABLE

4. RETURN AND STOP: goto main -m "done: summary"
   - After goto main, you are DONE
   - Do NOT create more scopes or files
   - Wait for next user instruction

# EXAMPLE (Project A: User model)

scope user-model -m "Creating User dataclass with validation"

write_file models/user.py [code]
read_file models/user.py

note -m "FILES: models/user.py
PATTERNS: dataclass with validation methods
- validate_email(): checks @ symbol
- validate_password(): checks min length
- is_valid(): aggregates all validations
- to_dict(): converts to dictionary
DECISIONS: Individual validate_X methods for testability
REUSABLE: This validation pattern works for any entity"

goto main -m "User model complete with validation pattern"

# EXAMPLE (Project B: recalls Project A)

notes user-model
-> Shows the detailed note above

scope product-model -m "Applying User model validation pattern"

write_file models/product.py [using SAME pattern from notes]

note -m "FILES: models/product.py
PATTERNS: Same as User model - dataclass with validate_X methods
APPLIED FROM user-model: validate_X pattern, is_valid(), to_dict()
REUSABLE: Confirmed this pattern works for any entity"

goto main -m "Product model complete, same pattern as User"
'''


def run_task(
    task: str,
    task_name: str,
    system_prompt: str,
    tools: list[dict],
    workdir: str,
    store: ContextStore | None = None,
) -> tuple[dict, ContextStore | None]:
    """Run a single task."""
    client = OpenAI()
    tracker = TokenTracker(model="gpt-4.1-mini")
    base_input = 0  # system + tools + user (cacheable by providers)
    peak_input = 0  # maximum context window size

    if store:
        store.add_message(Message(role="user", content=task))
        messages = store.get_context(system_prompt)
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

    max_iterations = 20
    iteration = 0

    print(f"\n{'='*60}")
    print(f"{task_name}")
    print(f"{'='*60}")

    while iteration < max_iterations:
        iteration += 1

        input_tokens = tracker.update_context(messages)
        tracker.add_input(input_tokens)

        # First call = base (system + tools + user) - cacheable
        if iteration == 1:
            base_input = input_tokens

        peak_input = max(peak_input, input_tokens)

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        if response.usage:
            tracker.add_output(response.usage.completion_tokens)

        if store:
            store.add_message(Message(
                role="assistant",
                content=msg.content or "",
                tool_calls=[{
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                } for tc in (msg.tool_calls or [])]
            ))
        else:
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in (msg.tool_calls or [])
                ] if msg.tool_calls else None
            })

        if msg.tool_calls:
            returned_to_main = False
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                if name == "ctx_cli" and store:
                    cmd = args.get("command", "")
                    result, _ = execute_command(store, cmd)
                    # Check if model returned to main (task complete)
                    if cmd.startswith("goto main"):
                        returned_to_main = True
                else:
                    result = execute_tool(name, args, workdir)

                # Highlight memory access
                if name == "ctx_cli" and "notes" in args.get("command", ""):
                    print(f"  [{name}] MEMORY ACCESS: {args.get('command', '')}")
                    print(f"    -> {result[:100]}...")
                else:
                    print(f"  [{name}] {str(args)[:40]}... -> {result[:40]}...")

                if store:
                    store.add_message(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tc.id,
                    ))
                else:
                    messages.append({
                        "role": "tool",
                        "content": result,
                        "tool_call_id": tc.id,
                    })

            # Stop when model returns to main (task complete)
            if returned_to_main:
                print(f"\n  Completed in {iteration} iterations (returned to main)")
                break

            if store:
                messages = store.get_context(system_prompt)
        else:
            print(f"\n  Completed in {iteration} iterations")
            break

    stats = tracker.get_stats()
    growth = peak_input - base_input  # Context growth beyond base
    return {
        "task": task_name,
        "iterations": iteration,
        "base_input": base_input,      # system + tools + user (cacheable)
        "peak_input": peak_input,      # maximum context size
        "growth": growth,              # how much context grew
        "total_output": stats["total_output"],
    }, store


def run_comparison():
    """Run the cross-project comparison."""

    print("\n" + "#"*70)
    print("# LINEAR APPROACH - No memory between projects")
    print("#"*70)

    with tempfile.TemporaryDirectory() as project_a_linear:
        with tempfile.TemporaryDirectory() as project_b_linear:

            # Project A
            linear_a, _ = run_task(
                task=PROJECT_A_TASK,
                task_name="PROJECT A: User Model (Linear)",
                system_prompt=SYSTEM_PROMPT_LINEAR,
                tools=[READ_FILE_TOOL, WRITE_FILE_TOOL],
                workdir=project_a_linear,
            )

            print("\n" + "-"*40)
            print("Starting NEW PROJECT (no memory of Project A)")
            print("-"*40)

            # Project B - completely fresh, different directory
            linear_b, _ = run_task(
                task=PROJECT_B_TASK_LINEAR,
                task_name="PROJECT B: Product Model (Linear - no memory)",
                system_prompt=SYSTEM_PROMPT_LINEAR,
                tools=[READ_FILE_TOOL, WRITE_FILE_TOOL],
                workdir=project_b_linear,
            )

    print("\n" + "#"*70)
    print("# SCOPE APPROACH - Episodic memory across projects")
    print("#"*70)

    with tempfile.TemporaryDirectory() as project_a_branch:
        with tempfile.TemporaryDirectory() as project_b_branch:

            store = ContextStore()

            # Project A - with notes
            branch_a, store = run_task(
                task=PROJECT_A_TASK,
                task_name="PROJECT A: User Model (Scope)",
                system_prompt=SYSTEM_PROMPT_BRANCH,
                tools=[READ_FILE_TOOL, WRITE_FILE_TOOL, CTX_CLI_TOOL],
                workdir=project_a_branch,
                store=store,
            )

            print("\n" + "-"*40)
            print("Starting NEW PROJECT (but can access memory from Project A)")
            print("-"*40)

            # Clear working messages but KEEP notes
            for branch in store.branches.values():
                branch.messages = []

            # Switch back to main for new project
            store.current_branch = "main"

            # Project B - new directory but has access to notes
            branch_b, _ = run_task(
                task=PROJECT_B_TASK_BRANCH,
                task_name="PROJECT B: Product Model (Scope - with memory)",
                system_prompt=SYSTEM_PROMPT_BRANCH,
                tools=[READ_FILE_TOOL, WRITE_FILE_TOOL, CTX_CLI_TOOL],
                workdir=project_b_branch,
                store=store,
            )

    # Results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    # Calculate totals
    linear_total_output = linear_a['total_output'] + linear_b['total_output']
    scope_total_output = branch_a['total_output'] + branch_b['total_output']

    print(f"\n{'Metric':<35} {'LINEAR':>12} {'SCOPE':>12}")
    print("-"*60)

    # Project A
    print(f"\n{'PROJECT A':<35}")
    print(f"{'  Base (system+tools+user)':<35} {linear_a['base_input']:>12,} {branch_a['base_input']:>12,}")
    print(f"{'  Peak Input':<35} {linear_a['peak_input']:>12,} {branch_a['peak_input']:>12,}")
    print(f"{'  Context Growth':<35} {linear_a['growth']:>12,} {branch_a['growth']:>12,}")
    print(f"{'  Output':<35} {linear_a['total_output']:>12,} {branch_a['total_output']:>12,}")
    print(f"{'  Iterations':<35} {linear_a['iterations']:>12} {branch_a['iterations']:>12}")

    # Project B
    print(f"\n{'PROJECT B':<35}")
    print(f"{'  Base (system+tools+user)':<35} {linear_b['base_input']:>12,} {branch_b['base_input']:>12,}")
    print(f"{'  Peak Input':<35} {linear_b['peak_input']:>12,} {branch_b['peak_input']:>12,}")
    print(f"{'  Context Growth':<35} {linear_b['growth']:>12,} {branch_b['growth']:>12,}")
    print(f"{'  Output':<35} {linear_b['total_output']:>12,} {branch_b['total_output']:>12,}")
    print(f"{'  Iterations':<35} {linear_b['iterations']:>12} {branch_b['iterations']:>12}")

    # Summary
    print(f"\n{'SUMMARY':<35}")
    print(f"{'  Total Base (cacheable)':<35} {linear_a['base_input']+linear_b['base_input']:>12,} {branch_a['base_input']+branch_b['base_input']:>12,}")
    print(f"{'  Total Growth':<35} {linear_a['growth']+linear_b['growth']:>12,} {branch_a['growth']+branch_b['growth']:>12,}")
    print(f"{'  Total Output':<35} {linear_total_output:>12,} {scope_total_output:>12,}")
    print(f"{'  Max Peak':<35} {max(linear_a['peak_input'], linear_b['peak_input']):>12,} {max(branch_a['peak_input'], branch_b['peak_input']):>12,}")

    print("\n" + "="*70)
    print("KEY OBSERVATION:")
    print("Project B in SCOPE approach accesses notes from Project A before")
    print("starting work. Look for 'MEMORY ACCESS' in the output above.")
    print("="*70)


if __name__ == "__main__":
    run_comparison()
