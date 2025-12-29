"""
Long Coding Task Demo: Measuring context growth Linear vs Folding.

This demo measures context window growth for a LONG multi-step coding task.
Each step requires reading existing code, making decisions, and writing more code.
This accumulates significant context in the linear approach.

The goal: Show that ctx_cli's commit-based folding keeps context manageable
for tasks that would otherwise overflow the context window.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, PLAN_TOOL, execute_command, execute_plan
from ctx_store import ContextStore, Message
from tokens import TokenTracker

# =============================================================================
# Tools
# =============================================================================

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Execute a bash command. Use for running tests, scripts, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"}
            },
            "required": ["command"]
        }
    }
}

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

LIST_FILES_TOOL = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List files in directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path", "default": "."}
            },
            "required": []
        }
    }
}


def execute_tool(tool_name: str, args: dict, workdir: str) -> str:
    """Execute a tool."""
    try:
        if tool_name == "bash":
            result = subprocess.run(
                args["command"], shell=True, capture_output=True,
                text=True, timeout=30, cwd=workdir
            )
            output = result.stdout + result.stderr
            return output[:2000] if output else "(no output)"

        elif tool_name == "read_file":
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

        elif tool_name == "list_files":
            path = os.path.join(workdir, args.get("path", "."))
            if os.path.exists(path):
                return "\n".join(os.listdir(path)) or "(empty)"
            return f"Error: Not found: {args.get('path', '.')}"

        elif tool_name == "plan":
            return execute_plan(args.get("content", ""))

        return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Error: {str(e)}"


# =============================================================================
# 12-Step Complex Task
# =============================================================================

TASK_STEPS = [
    """STEP 1: Create the core Task model.
    Create models/task.py with:
    - Task dataclass with fields: id, title, description, status (todo/in_progress/done),
      priority (1-5), created_at, updated_at, due_date (optional), tags (list)
    - TaskStatus enum
    - Validation for priority range
    Read the file back to confirm it's correct.""",

    """STEP 2: Create the TaskRepository for persistence.
    Create repositories/task_repository.py with:
    - TaskRepository class using JSON file storage
    - Methods: save(task), get(id), list_all(), update(task), delete(id)
    - Atomic writes (write to temp, then rename)
    - Handle file not found gracefully
    Read models/task.py first to understand the Task model.""",

    """STEP 3: Create the TaskService business logic layer.
    Create services/task_service.py with:
    - TaskService class that uses TaskRepository
    - Methods: create_task(title, description, priority, due_date, tags)
    - get_task(id), list_tasks(status=None, priority=None, tags=None)
    - update_status(id, status), add_tags(id, tags), remove_tags(id, tags)
    - Validation logic (can't complete already done tasks, etc.)
    Read both existing files first.""",

    """STEP 4: Create the CLI command parser.
    Create cli/parser.py with:
    - create_parser() function using argparse
    - Subcommands: add, list, show, update, delete, complete, tag
    - Common flags: --priority, --status, --tags, --due
    - Output format flag: --json, --table
    Read the service file to understand available operations.""",

    """STEP 5: Create CLI command handlers.
    Create cli/handlers.py with:
    - Handler functions for each command
    - AddHandler, ListHandler, ShowHandler, UpdateHandler, etc.
    - Format output nicely (table format by default)
    - Error handling with user-friendly messages
    Read parser.py and task_service.py first.""",

    """STEP 6: Create the main CLI entry point.
    Create cli/__main__.py with:
    - Main function that wires everything together
    - Create service, parse args, call handler
    - Global exception handling
    - Also create cli/__init__.py
    Read all cli/ files first.""",

    """STEP 7: Write unit tests for TaskRepository.
    Create tests/test_repository.py with:
    - Test save and retrieve
    - Test update existing task
    - Test delete task
    - Test list all tasks
    - Test file not found handling
    - Use pytest fixtures with temp directories
    Read repositories/task_repository.py first.""",

    """STEP 8: Write unit tests for TaskService.
    Create tests/test_service.py with:
    - Test create task with all fields
    - Test validation (invalid priority, duplicate tags)
    - Test status transitions
    - Test filtering by status, priority, tags
    - Mock the repository
    Read services/task_service.py first.""",

    """STEP 9: Run all tests and fix any failures.
    Execute: pytest tests/ -v --tb=short
    Fix any failing tests by updating the code.
    Read the failing test output carefully.""",

    """STEP 10: Add configuration support.
    Create config.py with:
    - Config class loading from config.json or env vars
    - Settings: storage_path, default_priority, date_format
    - Update TaskRepository and TaskService to use config
    Read existing files to understand where config is needed.""",

    """STEP 11: Add logging throughout the application.
    Update all modules to use Python logging:
    - Configure logging in cli/__main__.py
    - Add debug logs for operations
    - Add info logs for user actions
    - Add error logs for exceptions
    Read key files and add appropriate logging.""",

    """STEP 12: Create comprehensive documentation.
    Create README.md with:
    - Project overview and features
    - Installation instructions
    - Usage examples for each command
    - Configuration options
    - Development setup (running tests)
    Read all files to understand the full feature set.""",
]

SYSTEM_PROMPT_LINEAR = """You are a software developer building a production-quality CLI application.

Available tools:
- bash: Execute shell commands
- read_file: Read files (IMPORTANT: always read existing code before modifying)
- write_file: Write/update files
- list_files: List directory contents

Instructions:
- Read existing files before adding new code that depends on them
- Build incrementally on previous work
- Create proper project structure with directories
- Complete each step thoroughly"""

SYSTEM_PROMPT_BRANCH = '''You are a software developer. You have tools for context management.

Tools: bash, read_file, write_file, list_files, plan, ctx_cli

## The plan Tool

ALWAYS use the plan tool BEFORE starting any new task. This forces you to think before acting.
The plan call is automatically removed from context after execution to save tokens.

plan(content="Task: Create TaskRepository
Understanding: Need JSON persistence for Task model
Dependencies: Task model from step-1
Approach: 1) Read task.py 2) Create repository class 3) Implement CRUD
Branch: step-2-repository")

Result: "Plan recorded (5 items). You may now proceed with ctx_cli checkout."

## ctx_cli Commands

- ctx_cli log <branch>: See commits from any branch (review previous work)
- ctx_cli checkout -b <name> -m "<note>": Create new branch
- ctx_cli commit -m "<message>": Save work with detailed summary
- ctx_cli checkout main -m "<summary>": Return to main with knowledge transfer

## Workflow

1. PLAN: Use plan tool to think through the task
2. REVIEW: ctx_cli log step-1 to see what was done in previous step
3. BRANCH: ctx_cli checkout -b step-N -m "Starting: [task]"
4. WORK: Read files, write code, verify
5. COMMIT: ctx_cli commit -m "Done: [detailed summary]"
6. RETURN: ctx_cli checkout main -m "Completed: [knowledge to carry forward]"

## Example

User: Step 2: Create TaskRepository for JSON persistence.

[calls plan with task understanding and approach]
Result: Plan recorded (6 items). You may now proceed.

[calls ctx_cli log step-1]
Result: Commit history for step-1: [abc123] Created Task dataclass with status enum and validation

[calls ctx_cli checkout -b step-2 -m "Starting TaskRepository"]
Result: Switched to branch step-2

[calls read_file models/task.py]
[calls write_file repositories/task_repository.py]

[calls ctx_cli commit -m "Created TaskRepository with save/get/list_all/delete using JSON"]
Result: Committed def456

[calls ctx_cli checkout main -m "Completed step-2: TaskRepository persists Task objects to JSON with atomic writes"]
Result: Switched to main
'''


# =============================================================================
# Agent Loop
# =============================================================================

def run_approach(
    approach: str,
    steps: list[str],
    system_prompt: str,
    tools: list[dict],
    workdir: str,
    use_ctx: bool = False,
) -> dict:
    """Run a multi-step task with given approach."""
    client = OpenAI()
    tracker = TokenTracker(model="gpt-4.1-mini")
    store = ContextStore() if use_ctx else None
    peak_input = 0

    # Initial user message with first step
    if store:
        store.add_message(Message(role="user", content=steps[0]))
        messages = store.get_context(system_prompt)
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": steps[0]},
        ]

    step_idx = 0
    max_iterations = 50  # Safety limit (reduced for testing)
    iteration = 0

    print(f"\n{'='*60}")
    print(f"Running: {approach}")
    print(f"{'='*60}")

    while iteration < max_iterations:
        iteration += 1

        # Track input tokens
        input_tokens = tracker.update_context(messages)
        tracker.add_input(input_tokens)
        peak_input = max(peak_input, input_tokens)

        # Call API
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        if response.usage:
            tracker.add_output(response.usage.completion_tokens)

        # Store assistant message
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

        # Handle tool calls
        if msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                # Execute tool
                if name == "ctx_cli" and store:
                    result, _ = execute_command(store, args.get("command", ""))
                elif name == "plan":
                    result = "Plan recorded. Now proceed with: ctx_cli checkout -b <branch> -m <note>"
                else:
                    result = execute_tool(name, args, workdir)

                print(f"  [{name}] {str(args)[:50]}... -> {result[:50]}...")

                # Store tool result
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

            # Refresh context if using store
            if store:
                messages = store.get_context(system_prompt)
        else:
            # No tool calls - step likely complete
            step_idx += 1
            if step_idx < len(steps):
                print(f"\n  [Step {step_idx + 1}/{len(steps)}]")
                next_step = steps[step_idx]
                if store:
                    store.add_message(Message(role="user", content=next_step))
                    messages = store.get_context(system_prompt)
                else:
                    messages.append({"role": "user", "content": next_step})
            else:
                print(f"\n  All {len(steps)} steps completed!")
                break

        # Show progress
        if iteration % 10 == 0:
            stats = tracker.get_stats()
            print(f"  [Iteration {iteration}] Input: {stats['total_input']:,} Output: {stats['total_output']:,}")

    stats = tracker.get_stats()
    return {
        "approach": approach,
        "iterations": iteration,
        "steps_completed": step_idx,
        "total_input_tokens": stats["total_input"],
        "total_output_tokens": stats["total_output"],
        "peak_input_tokens": peak_input,
    }


def run_comparison(num_steps: int = 6):
    """Run comparison between linear and branch approaches."""
    steps = TASK_STEPS[:num_steps]

    with tempfile.TemporaryDirectory() as tmpdir_linear:
        with tempfile.TemporaryDirectory() as tmpdir_branch:
            # Linear approach
            linear_result = run_approach(
                approach="LINEAR",
                steps=steps,
                system_prompt=SYSTEM_PROMPT_LINEAR,
                tools=[BASH_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL, LIST_FILES_TOOL],
                workdir=tmpdir_linear,
                use_ctx=False,
            )

            # Branch approach
            branch_result = run_approach(
                approach="BRANCH (ctx_cli)",
                steps=steps,
                system_prompt=SYSTEM_PROMPT_BRANCH,
                tools=[BASH_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL, LIST_FILES_TOOL, PLAN_TOOL, CTX_CLI_TOOL],
                workdir=tmpdir_branch,
                use_ctx=True,
            )

    # Print comparison
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)

    print(f"\n{'Metric':<30} {'LINEAR':>15} {'BRANCH':>15} {'Savings':>10}")
    print("-" * 70)

    input_savings = linear_result["total_input_tokens"] - branch_result["total_input_tokens"]
    input_pct = (input_savings / linear_result["total_input_tokens"] * 100) if linear_result["total_input_tokens"] > 0 else 0

    print(f"{'Total Input Tokens':<30} {linear_result['total_input_tokens']:>15,} {branch_result['total_input_tokens']:>15,} {input_pct:>9.1f}%")
    print(f"{'Total Output Tokens':<30} {linear_result['total_output_tokens']:>15,} {branch_result['total_output_tokens']:>15,}")
    print(f"{'Peak Input Tokens':<30} {linear_result['peak_input_tokens']:>15,} {branch_result['peak_input_tokens']:>15,}")
    print(f"{'Iterations':<30} {linear_result['iterations']:>15} {branch_result['iterations']:>15}")
    print(f"{'Steps Completed':<30} {linear_result['steps_completed']:>15} {branch_result['steps_completed']:>15}")

    print("\n" + "=" * 70)
    if input_savings > 0:
        print(f"Branch approach saved {input_savings:,} input tokens ({input_pct:.1f}%)")
    else:
        print(f"Linear approach used {-input_savings:,} fewer input tokens ({-input_pct:.1f}%)")
    print("=" * 70)

    return linear_result, branch_result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Long Coding Task Demo")
    parser.add_argument("--steps", type=int, default=6, help="Number of steps to run (1-12)")
    args = parser.parse_args()

    num_steps = max(1, min(12, args.steps))
    print(f"Running {num_steps}-step coding task comparison...")

    run_comparison(num_steps)
