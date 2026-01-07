"""
Long Coding Task Demo: Measuring context growth Linear vs Folding.

This demo measures context window growth for a LONG multi-step coding task.
Each step requires reading existing code, making decisions, and writing more code.
This accumulates significant context in the linear approach.

The goal: Show that ctx_cli's note-based folding keeps context manageable
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

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from prompts import SYSTEM_PROMPT_ECM
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

SYSTEM_PROMPT_BRANCH = "You are a software developer.\n\nTools: bash, read_file, write_file, list_files, ctx_cli\n\n" + SYSTEM_PROMPT_ECM


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
    peak_working = 0  # Track working context size (without system prompt)

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
    max_iterations = 500  # Allow completion
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

        # Track working context (messages only, excluding system prompt)
        working_messages = [m for m in messages if m.get("role") != "system"]
        working_tokens = tracker.count_messages(working_messages)
        peak_working = max(peak_working, working_tokens)

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

        # Handle tool calls
        step_completed = False
        if msg.tool_calls:
            # Check if this is a context operation turn
            is_ctx_turn = any(tc.function.name == "ctx_cli" for tc in msg.tool_calls)

            if is_ctx_turn and store:
                # Delegate entirely to store harness to handle scope transitions
                for tc in msg.tool_calls:
                    if tc.function.name == "ctx_cli":
                        args = json.loads(tc.function.arguments)
                        cmd = args.get("command", "")
                        print(f"  [ctx_cli] {cmd[:60]}")  # LOG CTX_CLI USAGE
                        store.execute_tool_call(tc.id, cmd, msg.content or "")

                        if cmd.startswith("return"):
                            step_completed = True
            else:
                # Standard tool execution
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

                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments)

                    if name == "ctx_cli" and store:
                         # Fallback if mixed (shouldn't happen with logic above but safe)
                         pass
                    else:
                        result = execute_tool(name, args, workdir)

                    print(f"  [{name}] {str(args)[:50]}... -> {result[:50]}...")

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

            # If step was completed via return, advance to next step
            if step_completed:
                step_idx += 1
                if step_idx < len(steps):
                    print(f"\n  [Step {step_idx + 1}/{len(steps)}]")
                    next_step = steps[step_idx]
                    store.add_message(Message(role="user", content=next_step))
                    messages = store.get_context(system_prompt)
                else:
                    print(f"\n  All {len(steps)} steps completed!")
                    break
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

    # Count ECM usage if store was used
    ecm_stats = {}
    if store:
        ecm_stats = {
            "scopes_created": len(store.branches) - 1,  # Exclude main
            "notes_created": sum(len(b.notes) for b in store.branches.values()),
            "insights_created": len(store.insights),
        }

    return {
        "approach": approach,
        "iterations": iteration,
        "steps_completed": step_idx,
        "total_input_tokens": stats["total_input"],
        "total_output_tokens": stats["total_output"],
        "peak_input_tokens": peak_input,
        "peak_working_tokens": peak_working,
        "ecm_stats": ecm_stats,
    }


def run_comparison(num_steps: int = 6):
    """Run comparison between linear and scope approaches."""
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

            # Scope approach
            branch_result = run_approach(
                approach="SCOPE (ctx_cli)",
                steps=steps,
                system_prompt=SYSTEM_PROMPT_BRANCH,
                tools=[BASH_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL, LIST_FILES_TOOL, CTX_CLI_TOOL],
                workdir=tmpdir_branch,
                use_ctx=True,
            )

    # Print comparison
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)

    # Calculate peak working savings (fair comparison - excludes system prompt)
    working_savings = linear_result["peak_working_tokens"] - branch_result["peak_working_tokens"]
    working_pct = (working_savings / linear_result["peak_working_tokens"] * 100) if linear_result["peak_working_tokens"] > 0 else 0

    print(f"\n📊 Key Metric: Peak Working Context (fair comparison)")
    print(f"{'='*70}")
    print(f"  Linear:  {linear_result['peak_working_tokens']:>6,} tokens (messages only)")
    print(f"  ECM:     {branch_result['peak_working_tokens']:>6,} tokens (messages only)")
    print(f"  Savings: {working_savings:>6,} tokens ({working_pct:>5.1f}% reduction) {'✅' if working_savings > 0 else '⚠️'}")

    print(f"\n📋 Peak Total Context (includes system prompt)")
    print(f"{'='*70}")
    print(f"  Linear:  {linear_result['peak_input_tokens']:>6,} tokens")
    print(f"  ECM:     {branch_result['peak_input_tokens']:>6,} tokens")

    print(f"\n📈 Detailed Metrics:")
    print(f"{'='*70}")
    print(f"{'Metric':<30} {'LINEAR':>15} {'ECM':>15}")
    print("-" * 70)
    print(f"{'Steps Completed':<30} {linear_result['steps_completed']:>15} {branch_result['steps_completed']:>15}")
    print(f"{'Iterations':<30} {linear_result['iterations']:>15} {branch_result['iterations']:>15}")
    print(f"{'Total Output Tokens':<30} {linear_result['total_output_tokens']:>15,} {branch_result['total_output_tokens']:>15,}")

    # ECM specific stats
    if branch_result.get("ecm_stats"):
        ecm = branch_result["ecm_stats"]
        print(f"\n🔧 ECM Usage:")
        print(f"{'='*70}")
        print(f"  Scopes created: {ecm['scopes_created']}")
        print(f"  Notes saved:    {ecm['notes_created']}")
        print(f"  Insights saved: {ecm['insights_created']}")

    print(f"\n💡 Key Insight:")
    print(f"{'='*70}")
    if working_savings > 0:
        print(f"  ECM reduced working context by {working_pct:.1f}%!")
        print(f"  This allows longer tasks without hitting context limits.")
        print(f"  Model uses scope/return to discard working memory.")
    else:
        print(f"  For this short task, ECM had overhead without clear benefit.")
        print(f"  ECM shines on longer tasks with 6+ interdependent steps.")
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
