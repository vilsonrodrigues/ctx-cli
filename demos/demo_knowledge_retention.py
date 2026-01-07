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
from prompts import SYSTEM_PROMPT_ECM
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

WORKFLOW:
1. First create a scope: scope user-model -m "Building User model"
2. Write the code
3. Record a note with patterns used
4. Return to main when done"""

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

WORKFLOW:
1. First check `status` to see available scopes and memory
2. Use `notes <scope>` to recall patterns from previous work
3. Create a scope and apply the patterns
4. Record what you learned and return to main"""

SYSTEM_PROMPT_LINEAR = """You are a software developer.

Tools: read_file, write_file

Complete the task thoroughly."""

SYSTEM_PROMPT_BRANCH = "You are a software developer.\n\nTools: read_file, write_file, ctx_cli\n\n" + SYSTEM_PROMPT_ECM


def run_task(
    task: str,
    task_name: str,
    system_prompt: str,
    tools: list[dict],
    workdir: str,
    store: ContextStore | None = None,
) -> tuple[dict, ContextStore | None]:
    """Run a single task."""
    import time
    client = OpenAI()
    tracker = TokenTracker(model="gpt-4.1-mini")
    base_input = 0  # system + tools + user (cacheable by providers)
    peak_input = 0  # maximum context window size
    peak_working = 0  # peak working context (messages only, no system)
    start_time = time.time()

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

        # Track working context (messages only, excluding system prompt)
        working_messages = [m for m in messages if m.get("role") != "system"]
        working_tokens = tracker.count_messages(working_messages)
        peak_working = max(peak_working, working_tokens)

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
                    if cmd.startswith("return"):
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

    elapsed = time.time() - start_time

    # Capture final working context
    if store:
        final_messages = store.get_context(system_prompt)
    else:
        final_messages = messages
    working_messages = [m for m in final_messages if m.get("role") != "system"]
    final_working = tracker.count_messages(working_messages)

    stats = tracker.get_stats()
    growth = peak_input - base_input  # Context growth beyond base
    return {
        "task": task_name,
        "iterations": iteration,
        "base_input": base_input,      # system + tools + user (cacheable)
        "peak_input": peak_input,      # maximum context size
        "peak_working": peak_working,  # peak working context (fair metric)
        "final_working": final_working, # final working context
        "growth": growth,              # how much context grew
        "total_output": stats["total_output"],
        "elapsed_time": elapsed,
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

            # Use new_project API to start fresh project (keeps notes, clears main)
            store.new_project("ecommerce-api")

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
    linear_total_time = linear_a['elapsed_time'] + linear_b['elapsed_time']
    scope_total_time = branch_a['elapsed_time'] + branch_b['elapsed_time']

    print(f"\n{'Metric':<35} {'LINEAR':>12} {'SCOPE':>12}")
    print("-"*60)

    # Project A
    print(f"\n{'PROJECT A':<35}")
    print(f"{'  Peak Working (fair)':<35} {linear_a['peak_working']:>12,} {branch_a['peak_working']:>12,}")
    print(f"{'  Final Working':<35} {linear_a['final_working']:>12,} {branch_a['final_working']:>12,}")
    print(f"{'  Peak Total (w/ system)':<35} {linear_a['peak_input']:>12,} {branch_a['peak_input']:>12,}")
    print(f"{'  Output Tokens':<35} {linear_a['total_output']:>12,} {branch_a['total_output']:>12,}")
    print(f"{'  Iterations':<35} {linear_a['iterations']:>12} {branch_a['iterations']:>12}")
    print(f"{'  Latency':<35} {linear_a['elapsed_time']:>11.1f}s {branch_a['elapsed_time']:>11.1f}s")

    # Project B
    print(f"\n{'PROJECT B':<35}")
    print(f"{'  Peak Working (fair)':<35} {linear_b['peak_working']:>12,} {branch_b['peak_working']:>12,}")
    print(f"{'  Final Working':<35} {linear_b['final_working']:>12,} {branch_b['final_working']:>12,}")
    print(f"{'  Peak Total (w/ system)':<35} {linear_b['peak_input']:>12,} {branch_b['peak_input']:>12,}")
    print(f"{'  Output Tokens':<35} {linear_b['total_output']:>12,} {branch_b['total_output']:>12,}")
    print(f"{'  Iterations':<35} {linear_b['iterations']:>12} {branch_b['iterations']:>12}")
    print(f"{'  Latency':<35} {linear_b['elapsed_time']:>11.1f}s {branch_b['elapsed_time']:>11.1f}s")

    # Summary
    print(f"\n{'SUMMARY':<35}")
    linear_max_peak_working = max(linear_a['peak_working'], linear_b['peak_working'])
    scope_max_peak_working = max(branch_a['peak_working'], branch_b['peak_working'])
    working_savings = linear_max_peak_working - scope_max_peak_working
    working_pct = (working_savings / linear_max_peak_working * 100) if linear_max_peak_working > 0 else 0

    print(f"{'  Max Peak Working':<35} {linear_max_peak_working:>12,} {scope_max_peak_working:>12,}")
    if working_savings > 0:
        print(f"{'  Working Context Savings':<35} {working_savings:>12,} ({working_pct:>5.1f}% reduction)")
    print(f"{'  Total Output':<35} {linear_total_output:>12,} {scope_total_output:>12,}")
    print(f"{'  Total Latency':<35} {linear_total_time:>11.1f}s {scope_total_time:>11.1f}s")

    print("\n" + "="*70)
    print("KEY OBSERVATIONS:")
    print("1. Peak Working Context = fair comparison (messages only, no system)")
    print("2. Project B in SCOPE approach accesses notes from Project A before")
    print("   starting work. Look for 'MEMORY ACCESS' in the output above.")
    if working_savings > 0:
        print(f"3. ECM saved {working_pct:.1f}% of peak working context across projects")
    print("="*70)


if __name__ == "__main__":
    run_comparison()
