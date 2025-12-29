"""
Knowledge Retention Demo: Cross-project memory.

Scenario:
- Project A: Build a User model with validation
- Project B (NEW PROJECT): Build a Product model with similar patterns

LINEAR: Project B starts from scratch - no memory of how Project A was built
BRANCH: Project B can query commits from Project A to recall patterns/decisions

This demonstrates episodic memory across different projects.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, PLAN_TOOL, execute_command
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

IMPORTANT: Before starting, use ctx_cli log project-a to recall how you built the User model.
Apply the same patterns and structure you used there."""

SYSTEM_PROMPT_LINEAR = """You are a software developer.

Tools: read_file, write_file

Complete the task thoroughly."""

SYSTEM_PROMPT_BRANCH = '''You are a software developer with episodic memory via ctx_cli.

Tools: read_file, write_file, plan, ctx_cli

# MEMORY SYSTEM

Your commits are your long-term memory. They persist across projects and sessions.
When you start a new project, you can recall patterns and decisions from past projects.

## Commands

- `ctx_cli branch`: List all branches (past projects)
- `ctx_cli log <branch>`: Read commits from any branch (recall learnings)
- `ctx_cli checkout -b <name> -m "<note>"`: Start new branch
- `ctx_cli commit -m "<message>"`: Save knowledge to memory

# WORKFLOW FOR NEW PROJECTS

## Step 1: CHECK PAST WORK

Before starting, check if you have relevant past experience:

```
ctx_cli branch
ctx_cli log project-a
```

Look for:
- Similar patterns you established
- Decisions and their rationale
- Code structures to reuse

## Step 2: PLAN (referencing past learnings)

```
plan(content="""
TASK: Create Product model
PAST EXPERIENCE: User model from project-a used dataclass with validation methods
APPLY FROM PAST:
- Same dataclass structure
- Same validation pattern (is_valid method)
- Same to_dict serialization
APPROACH:
1. Recall project-a patterns via ctx_cli log
2. Apply same structure to Product
""")
```

## Step 3: WORK

Apply patterns from past projects.

## Step 4: COMMIT (capture knowledge for future)

Write commits that your future self can learn from:

```
ctx_cli commit -m """
COMPLETED: Product model with validation

WHAT WAS BUILT:
- Product dataclass: id, name, price, stock, created_at, is_available
- validate_price(): must be positive
- validate_stock(): must be >= 0
- is_valid(): checks all validations
- to_dict(): serialization

PATTERNS APPLIED (from project-a User model):
- Dataclass with validation methods
- Individual validate_X methods for each rule
- is_valid() aggregates all validations
- to_dict() for serialization

KEY DECISIONS:
- Same structure as User model for consistency
- Price as float, stock as int

REUSABLE FOR FUTURE:
- This validation pattern works for any entity model
"""
```

# EXAMPLE: Cross-Project Memory

User: Create a Product model similar to User model patterns.

[1. RECALL PAST WORK]
ctx_cli log project-a
-> Shows: User model with dataclass, email validation, password validation, is_valid(), to_dict()

[2. PLAN]
plan(content="""
TASK: Create Product model
LEARNINGS FROM project-a:
- Dataclass structure with typed fields
- Individual validation methods
- is_valid() aggregates validations
- to_dict() for serialization
APPROACH: Apply same patterns to Product domain
""")

[3. BRANCH]
ctx_cli checkout -b project-b -m "Starting: Product model using patterns from User model"

[4. WORK]
write_file models/product.py [using patterns from project-a]
read_file models/product.py [verify]

[5. COMMIT]
ctx_cli commit -m """
COMPLETED: Product model

APPLIED PATTERNS FROM project-a:
- Dataclass with validation methods (same as User)
- is_valid() + to_dict() pattern

DIFFERENCES FROM User:
- Price/stock validation instead of email/password
- is_available flag instead of is_active

REUSABLE: This entity pattern now proven across 2 models
"""
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
    peak_input = 0

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
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                if name == "ctx_cli" and store:
                    result, _ = execute_command(store, args.get("command", ""))
                else:
                    result = execute_tool(name, args, workdir)

                # Highlight memory access
                if name == "ctx_cli" and "log" in args.get("command", ""):
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

            if store:
                messages = store.get_context(system_prompt)
        else:
            print(f"\n  Completed in {iteration} iterations")
            break

    stats = tracker.get_stats()
    return {
        "task": task_name,
        "iterations": iteration,
        "total_input": stats["total_input"],
        "total_output": stats["total_output"],
        "peak_input": peak_input,
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
    print("# BRANCH APPROACH - Episodic memory across projects")
    print("#"*70)

    with tempfile.TemporaryDirectory() as project_a_branch:
        with tempfile.TemporaryDirectory() as project_b_branch:

            store = ContextStore()

            # Project A - with commits
            branch_a, store = run_task(
                task=PROJECT_A_TASK,
                task_name="PROJECT A: User Model (Branch)",
                system_prompt=SYSTEM_PROMPT_BRANCH,
                tools=[READ_FILE_TOOL, WRITE_FILE_TOOL, PLAN_TOOL, CTX_CLI_TOOL],
                workdir=project_a_branch,
                store=store,
            )

            print("\n" + "-"*40)
            print("Starting NEW PROJECT (but can access memory from Project A)")
            print("-"*40)

            # Clear working messages but KEEP commits
            for branch in store.branches.values():
                branch.messages = []

            # Switch back to main for new project
            store.current_branch = "main"

            # Project B - new directory but has access to commits
            branch_b, _ = run_task(
                task=PROJECT_B_TASK_BRANCH,
                task_name="PROJECT B: Product Model (Branch - with memory)",
                system_prompt=SYSTEM_PROMPT_BRANCH,
                tools=[READ_FILE_TOOL, WRITE_FILE_TOOL, PLAN_TOOL, CTX_CLI_TOOL],
                workdir=project_b_branch,
                store=store,
            )

    # Results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    print(f"\n{'Metric':<40} {'LINEAR':>12} {'BRANCH':>12}")
    print("-"*65)
    print(f"{'Project A - Input Tokens':<40} {linear_a['total_input']:>12,} {branch_a['total_input']:>12,}")
    print(f"{'Project B - Input Tokens':<40} {linear_b['total_input']:>12,} {branch_b['total_input']:>12,}")
    print(f"{'TOTAL Input Tokens':<40} {linear_a['total_input']+linear_b['total_input']:>12,} {branch_a['total_input']+branch_b['total_input']:>12,}")
    print(f"{'Project A - Iterations':<40} {linear_a['iterations']:>12} {branch_a['iterations']:>12}")
    print(f"{'Project B - Iterations':<40} {linear_b['iterations']:>12} {branch_b['iterations']:>12}")

    print("\n" + "="*70)
    print("KEY OBSERVATION:")
    print("Watch for 'MEMORY ACCESS' in Branch approach - the agent recalls")
    print("how it built Project A before starting Project B.")
    print("="*70)


if __name__ == "__main__":
    run_comparison()
