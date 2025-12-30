#!/usr/bin/env python3
"""
SWE-Bench Lite Runner for ctx-cli.

Runs actual code generation tasks from SWE-Bench Lite dataset,
comparing LINEAR vs SCOPE approaches.

Generates patches that can be evaluated with the SWE-bench harness.

Usage:
    uv run python benchmarks/run_swe_bench_lite.py --tasks 5
    uv run python benchmarks/run_swe_bench_lite.py --instance django__django-11099
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from tokens import TokenTracker


# =============================================================================
# Tools (from demo_long_coding_task.py)
# =============================================================================

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Execute a bash command in the repository. Use for running tests, grep, find, etc.",
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
        "description": "Read a file's contents. Use to understand existing code before modifying.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to repo root"}
            },
            "required": ["path"]
        }
    }
}

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write content to a file. Creates directories if needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to repo root"},
                "content": {"type": "string", "description": "Full file content to write"}
            },
            "required": ["path", "content"]
        }
    }
}

EDIT_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": "Edit a file by replacing old_str with new_str. More precise than write_file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "old_str": {"type": "string", "description": "Exact string to replace"},
                "new_str": {"type": "string", "description": "Replacement string"}
            },
            "required": ["path", "old_str", "new_str"]
        }
    }
}


def execute_tool(tool_name: str, args: dict, workdir: str) -> str:
    """Execute a tool in the repository context."""
    try:
        if tool_name == "bash":
            result = subprocess.run(
                args["command"], shell=True, capture_output=True,
                text=True, timeout=60, cwd=workdir
            )
            output = result.stdout + result.stderr
            return output[:4000] if output else "(no output)"

        elif tool_name == "read_file":
            path = os.path.join(workdir, args["path"])
            if os.path.exists(path):
                with open(path) as f:
                    content = f.read()
                    if len(content) > 8000:
                        return content[:8000] + f"\n... (truncated, {len(content)} total chars)"
                    return content
            return f"Error: File not found: {args['path']}"

        elif tool_name == "write_file":
            path = os.path.join(workdir, args["path"])
            os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
            with open(path, "w") as f:
                f.write(args["content"])
            return f"Written {len(args['content'])} bytes to {args['path']}"

        elif tool_name == "edit_file":
            path = os.path.join(workdir, args["path"])
            if not os.path.exists(path):
                return f"Error: File not found: {args['path']}"
            with open(path) as f:
                content = f.read()
            if args["old_str"] not in content:
                return f"Error: old_str not found in {args['path']}"
            new_content = content.replace(args["old_str"], args["new_str"], 1)
            with open(path, "w") as f:
                f.write(new_content)
            return f"Edited {args['path']}: replaced {len(args['old_str'])} chars with {len(args['new_str'])} chars"

        return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Error: {str(e)}"


# =============================================================================
# System Prompts
# =============================================================================

SYSTEM_PROMPT_LINEAR = """You are an expert software engineer fixing a GitHub issue.

Available tools:
- bash: Execute shell commands (grep, find, python, pytest, etc.)
- read_file: Read file contents
- write_file: Write/create files
- edit_file: Edit files by replacing strings

Your task:
1. Understand the issue from the problem statement
2. Explore the codebase to find relevant files
3. Implement the fix
4. Verify your fix works

Be methodical. Read existing code before modifying."""


SYSTEM_PROMPT_SCOPE = '''You are an expert software engineer fixing a GitHub issue.

Tools: bash, read_file, write_file, edit_file, ctx_cli

# WORKFLOW (follow exactly)

1. FIRST: ctx_cli scope fix -m "analyzing issue"
2. EXPLORE: Use bash/read_file to understand the codebase
3. NOTE: ctx_cli note -m "files: X, root cause: Y, fix approach: Z"
4. IMPLEMENT: Make the fix using write_file or edit_file
5. VERIFY: Run relevant tests
6. LAST: ctx_cli goto main -m "done: summary of fix"

# COMMANDS

scope <name> -m "..."   Start isolated work
note -m "..."           Record findings (IMPORTANT for memory)
goto main -m "..."      Complete and return

# RULES

- Always start with scope
- Take detailed notes about what you find
- Read code before modifying
- Test your changes if possible
'''


# =============================================================================
# Data Loading
# =============================================================================

def load_swe_bench_lite(max_tasks: int = None) -> list[dict]:
    """Load SWE-Bench Lite from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("Error: Install datasets with: uv pip install datasets")
        sys.exit(1)

    print("Loading SWE-Bench Lite from HuggingFace...")
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    tasks = []
    for item in dataset:
        tasks.append({
            "instance_id": item["instance_id"],
            "repo": item["repo"],
            "base_commit": item["base_commit"],
            "problem_statement": item["problem_statement"],
            "hints_text": item.get("hints_text", ""),
            "patch": item["patch"],  # Gold patch for reference
        })
        if max_tasks and len(tasks) >= max_tasks:
            break

    return tasks


def setup_repo(task: dict, workdir: str) -> bool:
    """Clone and checkout the repository for a task."""
    repo = task["repo"]
    base_commit = task["base_commit"]

    repo_url = f"https://github.com/{repo}.git"
    repo_dir = os.path.join(workdir, repo.replace("/", "_"))

    print(f"    Cloning {repo}...")

    # Clone with minimal depth first, then fetch the specific commit
    result = subprocess.run(
        f"git clone --depth 1 {repo_url} {repo_dir} 2>&1",
        shell=True, capture_output=True, text=True, timeout=120
    )

    if result.returncode != 0:
        print(f"    Error cloning: {result.stderr}")
        return False

    # Fetch the specific commit
    result = subprocess.run(
        f"cd {repo_dir} && git fetch --depth 1 origin {base_commit} && git checkout {base_commit} 2>&1",
        shell=True, capture_output=True, text=True, timeout=60
    )

    if result.returncode != 0:
        # Try fetching more history
        result = subprocess.run(
            f"cd {repo_dir} && git fetch --unshallow && git checkout {base_commit} 2>&1",
            shell=True, capture_output=True, text=True, timeout=300
        )

    return result.returncode == 0


def get_patch(repo_dir: str) -> str:
    """Get git diff of changes made."""
    result = subprocess.run(
        "git diff",
        shell=True, capture_output=True, text=True, cwd=repo_dir
    )
    return result.stdout


# =============================================================================
# Agent Runner
# =============================================================================

@dataclass
class TaskResult:
    """Result of running a single task."""
    instance_id: str
    approach: Literal["linear", "scope"]
    success: bool = False
    patch: str = ""
    iterations: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    peak_context: int = 0
    elapsed_seconds: float = 0.0
    error: str = ""


def run_task(
    client: OpenAI,
    task: dict,
    approach: Literal["linear", "scope"],
    repo_dir: str,
    max_iterations: int = 50,
) -> TaskResult:
    """Run agent on a single SWE-Bench task."""
    result = TaskResult(instance_id=task["instance_id"], approach=approach)
    start_time = time.time()
    tracker = TokenTracker(model="gpt-4.1-mini")

    # Setup
    use_ctx = approach == "scope"
    store = ContextStore() if use_ctx else None

    if use_ctx:
        system_prompt = SYSTEM_PROMPT_SCOPE
        tools = [BASH_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL, EDIT_FILE_TOOL, CTX_CLI_TOOL]
    else:
        system_prompt = SYSTEM_PROMPT_LINEAR
        tools = [BASH_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL, EDIT_FILE_TOOL]

    # Initial prompt with problem statement
    user_prompt = f"""Fix this GitHub issue:

## Problem Statement
{task['problem_statement'][:6000]}

## Repository
{task['repo']} at commit {task['base_commit'][:8]}

## Instructions
1. Explore the codebase to understand the issue
2. Find the relevant files
3. Implement a fix
4. Test if possible

The repository is already cloned and checked out at the correct commit.
"""

    if store:
        store.add_message(Message(role="user", content=user_prompt))
        messages = store.get_context(system_prompt)
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    # Agent loop
    for iteration in range(max_iterations):
        result.iterations = iteration + 1

        # Track tokens
        input_tokens = tracker.count_messages(messages)
        result.peak_context = max(result.peak_context, input_tokens)

        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0,
            )
        except Exception as e:
            result.error = str(e)
            break

        msg = response.choices[0].message

        if response.usage:
            result.total_input_tokens += response.usage.prompt_tokens
            result.total_output_tokens += response.usage.completion_tokens

        # Handle response
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

        # Process tool calls
        if msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                if name == "ctx_cli" and store:
                    cmd = args.get("command", "")
                    tool_result, _ = execute_command(store, cmd)
                else:
                    tool_result = execute_tool(name, args, repo_dir)

                # Store result
                if store:
                    store.add_message(Message(
                        role="tool",
                        content=tool_result,
                        tool_call_id=tc.id,
                    ))
                else:
                    messages.append({
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": tc.id,
                    })

            # Refresh context
            if store:
                messages = store.get_context(system_prompt)
        else:
            # No tool calls - agent thinks it's done
            break

    # Get the patch
    result.patch = get_patch(repo_dir)
    result.success = len(result.patch) > 0
    result.elapsed_seconds = time.time() - start_time

    return result


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="SWE-Bench Lite Runner")
    parser.add_argument("--tasks", type=int, default=5, help="Number of tasks to run")
    parser.add_argument("--instance", type=str, help="Run specific instance ID")
    parser.add_argument("--approach", choices=["linear", "scope", "both"], default="both")
    parser.add_argument("--output", default="benchmarks/results", help="Output directory")
    parser.add_argument("--max-iterations", type=int, default=50, help="Max iterations per task")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY environment variable")
        sys.exit(1)

    print("=" * 70)
    print("SWE-Bench Lite Runner")
    print("=" * 70)

    # Load tasks
    tasks = load_swe_bench_lite(args.tasks if not args.instance else 300)

    if args.instance:
        tasks = [t for t in tasks if t["instance_id"] == args.instance]
        if not tasks:
            print(f"Error: Instance {args.instance} not found")
            sys.exit(1)

    print(f"Tasks to run: {len(tasks)}")

    client = OpenAI()
    all_results = []

    for i, task in enumerate(tasks):
        print(f"\n[Task {i+1}/{len(tasks)}] {task['instance_id']}")
        print(f"  Repo: {task['repo']}")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup repo
            if not setup_repo(task, tmpdir):
                print("  Failed to setup repo, skipping...")
                continue

            repo_dir = os.path.join(tmpdir, task["repo"].replace("/", "_"))

            # Run approaches
            approaches = ["linear", "scope"] if args.approach == "both" else [args.approach]

            for approach in approaches:
                print(f"\n  Running {approach.upper()}...")

                # Reset repo to base commit
                subprocess.run(
                    f"git checkout {task['base_commit']} -- . 2>&1",
                    shell=True, cwd=repo_dir, capture_output=True
                )

                result = run_task(
                    client, task, approach, repo_dir, args.max_iterations
                )

                all_results.append(asdict(result))

                print(f"    Iterations: {result.iterations}")
                print(f"    Peak context: {result.peak_context:,}")
                print(f"    Patch generated: {len(result.patch)} chars")
                print(f"    Time: {result.elapsed_seconds:.1f}s")

    # Save results
    os.makedirs(args.output, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{args.output}/swe_bench_lite_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump({
            "config": {
                "tasks": len(tasks),
                "max_iterations": args.max_iterations,
            },
            "results": all_results,
        }, f, indent=2)

    print(f"\nResults saved to: {filename}")

    # Summary
    if all_results:
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        for approach in ["linear", "scope"]:
            results = [r for r in all_results if r["approach"] == approach]
            if results:
                patches = sum(1 for r in results if r["success"])
                avg_ctx = sum(r["peak_context"] for r in results) / len(results)
                avg_time = sum(r["elapsed_seconds"] for r in results) / len(results)
                print(f"\n{approach.upper()}:")
                print(f"  Patches generated: {patches}/{len(results)}")
                print(f"  Avg peak context: {avg_ctx:,.0f}")
                print(f"  Avg time: {avg_time:.1f}s")


if __name__ == "__main__":
    main()
