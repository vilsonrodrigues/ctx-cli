#!/usr/bin/env python3
"""
OSWorld-Style Benchmark for ECM.

Uses continuous conversation pattern where:
1. Agent receives tasks as messages in a continuous session
2. Agent has access to ctx_cli tool for memory management
3. Agent decides when to use note/insight commands
4. Memory accumulates across tasks

Based on OSWorld (NeurIPS 2024) and ECM's conversation pattern from run_swe_cl.py.

Usage:
    uv run benchmarks/longhorizon/run_osworld.py --max-tasks 10
    uv run benchmarks/longhorizon/run_osworld.py --approach scope --max-tasks 5
"""

from __future__ import annotations

import os
import sys
import json
import time
import re
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Literal, Optional

from openai import OpenAI

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from tokens import TokenTracker


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class BenchmarkResult:
    """Result of OSWorld benchmark."""
    approach: Literal["linear", "scope"]
    model: str
    num_tasks: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Token metrics
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cached_tokens: int = 0

    # Context metrics
    peak_context: int = 0
    context_per_task: list = field(default_factory=list)

    # Memory metrics (scope only)
    notes_created: int = 0
    insights_created: int = 0
    scopes_created: int = 0

    # Task metrics
    tasks_completed: int = 0
    checks_passed: int = 0
    total_checks: int = 0
    api_calls: int = 0

    # Timing
    elapsed_seconds: float = 0.0

    # Details
    task_results: list = field(default_factory=list)

    @property
    def completion_rate(self) -> float:
        return (self.tasks_completed / self.num_tasks * 100) if self.num_tasks > 0 else 0

    @property
    def check_rate(self) -> float:
        return (self.checks_passed / self.total_checks * 100) if self.total_checks > 0 else 0


# =============================================================================
# Simulated OS Environment (simplified)
# =============================================================================

class SimulatedOS:
    """Simplified OS simulation for benchmarking."""

    def __init__(self):
        self.files = {
            "/home/user/notes.txt": "TODO: Review project",
            "/home/user/projects/app.py": "# Main application",
            "/home/user/data.csv": "id,name,value\n1,test,100",
        }
        self.cwd = "/home/user"
        self.history = []

    def execute(self, command: str) -> str:
        """Execute a command and return result."""
        self.history.append(command)
        parts = command.strip().split()
        if not parts:
            return "Error: empty command"

        cmd = parts[0]

        if cmd == "ls":
            path = parts[1] if len(parts) > 1 else self.cwd
            files = [f for f in self.files if f.startswith(path)]
            return "\n".join(f.split("/")[-1] for f in files) or "empty"

        elif cmd == "cat":
            if len(parts) < 2:
                return "Error: missing file"
            path = parts[1] if parts[1].startswith("/") else f"{self.cwd}/{parts[1]}"
            return self.files.get(path, f"Error: file not found: {path}")

        elif cmd == "pwd":
            return self.cwd

        elif cmd == "echo":
            text = " ".join(parts[1:])
            if ">" in command:
                idx = command.index(">")
                content = command[:idx].replace("echo", "").strip().strip('"')
                path = command[idx+1:].strip()
                if not path.startswith("/"):
                    path = f"{self.cwd}/{path}"
                self.files[path] = content
                return ""
            return text.strip('"')

        elif cmd == "mkdir":
            return "directory created"

        elif cmd == "grep":
            pattern = parts[1] if len(parts) > 1 else ""
            path = parts[2] if len(parts) > 2 else ""
            if path in self.files:
                matches = [l for l in self.files[path].split("\n") if pattern in l]
                return "\n".join(matches) or "no matches"
            return "Error: file not found"

        return f"executed: {command}"

    def check_state(self, checks: list[dict]) -> tuple[int, int]:
        """Check success criteria. Returns (passed, total)."""
        passed = 0
        for check in checks:
            if check.get("type") == "file_exists":
                if check["path"] in self.files:
                    passed += 1
            elif check.get("type") == "command_executed":
                pattern = check.get("pattern", "")
                if any(pattern in cmd for cmd in self.history):
                    passed += 1
        return passed, len(checks)


# =============================================================================
# Task Definitions
# =============================================================================

TASKS = [
    {
        "id": "file_search",
        "description": "Find all Python files in the projects directory and list them.",
        "checks": [{"type": "command_executed", "pattern": "ls"}],
    },
    {
        "id": "read_config",
        "description": "Read the contents of notes.txt and summarize what needs to be done.",
        "checks": [{"type": "command_executed", "pattern": "cat"}],
    },
    {
        "id": "create_backup",
        "description": "Create a backup of app.py by reading it and saving to app.py.bak",
        "checks": [{"type": "file_exists", "path": "/home/user/projects/app.py.bak"}],
    },
    {
        "id": "analyze_data",
        "description": "Read data.csv and describe what data it contains.",
        "checks": [{"type": "command_executed", "pattern": "cat"}],
    },
    {
        "id": "organize_files",
        "description": "List all files in home directory and organize them by type.",
        "checks": [{"type": "command_executed", "pattern": "ls"}],
    },
]


# =============================================================================
# System Prompts
# =============================================================================

LINEAR_SYSTEM_PROMPT = """You are an assistant helping with operating system tasks.

For each task:
1. Understand what needs to be done
2. Execute the necessary commands
3. Report the results

Available commands: ls, cat, pwd, echo, mkdir, grep

When you need to run a command, format it as:
```bash
command here
```

Be concise and efficient."""


SCOPE_SYSTEM_PROMPT = """You are an assistant helping with operating system tasks.

# PRIORITY: COMPLETE THE TASK FIRST

Your main job is to execute bash commands to complete each task.

Available bash commands: ls, cat, pwd, echo, mkdir, grep

Format bash commands as:
```bash
command here
```

# OPTIONAL: Memory Management (ctx_cli)

AFTER completing a task, you may use ctx_cli to save useful info:
- note -m "..." : Save important findings for future tasks
- insight -m "..." : Save reusable patterns

Only use ctx_cli if you learned something genuinely useful.
Do NOT use ctx_cli before executing commands.

# EXAMPLE

User: List files in /home/user
Assistant:
```bash
ls /home/user
```

[After seeing output]
Assistant: Found 3 files: notes.txt, data.csv, projects/
note -m "home contains notes.txt, data.csv, projects/"
"""


# =============================================================================
# Linear Approach
# =============================================================================

def run_linear(
    client: OpenAI,
    model: str,
    tasks: list[dict],
    os_env: SimulatedOS,
    max_rounds: int = 5,
) -> BenchmarkResult:
    """Run tasks with linear context (no memory management)."""
    result = BenchmarkResult(approach="linear", model=model, num_tasks=len(tasks))
    start_time = time.time()
    tracker = TokenTracker(model=model)

    messages = [{"role": "system", "content": LINEAR_SYSTEM_PROMPT}]

    for i, task in enumerate(tasks):
        print(f"  Task {i+1}/{len(tasks)}: {task['id']}", end="", flush=True)

        # Add task
        task_prompt = f"Task {i+1}: {task['description']}"
        messages.append({"role": "user", "content": task_prompt})

        # Multiple rounds for command execution
        for round_num in range(max_rounds):
            context_tokens = tracker.count_messages(messages)
            result.context_per_task.append(context_tokens)
            result.peak_context = max(result.peak_context, context_tokens)

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=500,
            )

            msg = response.choices[0].message
            content = msg.content or ""
            messages.append({"role": "assistant", "content": content})

            result.api_calls += 1
            if response.usage:
                result.total_prompt_tokens += response.usage.prompt_tokens
                result.total_completion_tokens += response.usage.completion_tokens

            # Extract and execute bash commands
            bash_matches = re.findall(r'```bash\n(.+?)\n```', content, re.DOTALL)
            if bash_matches:
                for cmd in bash_matches:
                    cmd_result = os_env.execute(cmd.strip())
                    messages.append({"role": "user", "content": f"Command output:\n{cmd_result}"})
            else:
                # No more commands, task done
                break

        # Check completion
        passed, total = os_env.check_state(task["checks"])
        result.checks_passed += passed
        result.total_checks += total
        if passed == total:
            result.tasks_completed += 1

        result.task_results.append({
            "task_id": task["id"],
            "completed": passed == total,
            "checks": f"{passed}/{total}",
        })

        print(f" - {'OK' if passed == total else 'FAIL'} ({passed}/{total})")

    result.elapsed_seconds = time.time() - start_time
    return result


# =============================================================================
# Scope Approach (ECM)
# =============================================================================

def run_scope(
    client: OpenAI,
    model: str,
    tasks: list[dict],
    os_env: SimulatedOS,
    max_rounds: int = 8,
) -> BenchmarkResult:
    """Run tasks with ECM scope-based memory management."""
    result = BenchmarkResult(approach="scope", model=model, num_tasks=len(tasks))
    start_time = time.time()
    tracker = TokenTracker(model=model)

    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    def call_model() -> tuple[str, bool]:
        """Call model and handle tools. Returns (content, has_tool_calls)."""
        context = store.get_context(SCOPE_SYSTEM_PROMPT)
        tokens = tracker.count_messages(context)
        result.peak_context = max(result.peak_context, tokens)
        result.context_per_task.append(tokens)

        response = client.chat.completions.create(
            model=model,
            messages=context,
            tools=tools,
            temperature=0,
            max_tokens=500,
        )

        msg = response.choices[0].message
        result.api_calls += 1

        if response.usage:
            result.total_prompt_tokens += response.usage.prompt_tokens
            result.total_completion_tokens += response.usage.completion_tokens
            if hasattr(response.usage, 'prompt_tokens_details') and response.usage.prompt_tokens_details:
                cached = getattr(response.usage.prompt_tokens_details, 'cached_tokens', 0)
                result.total_cached_tokens += cached or 0

        if msg.tool_calls:
            # Add assistant message with tool calls
            store.add_message(Message(
                role="assistant",
                content=msg.content or "",
                tool_calls=[tc.model_dump() for tc in msg.tool_calls]
            ))

            # Process each tool call
            for tc in msg.tool_calls:
                if tc.function.name == "ctx_cli":
                    args = json.loads(tc.function.arguments)
                    cmd = args.get("command", "")
                    output, event = execute_command(store, cmd)

                    # Track memory operations
                    if cmd.startswith("scope"):
                        result.scopes_created += 1
                    elif cmd.startswith("note"):
                        result.notes_created += 1
                    elif cmd.startswith("insight"):
                        result.insights_created += 1

                    store.add_message(Message(
                        role="tool",
                        content=output,
                        tool_call_id=tc.id
                    ))

            return msg.content or "", True

        else:
            # No tool calls - regular response
            store.add_message(Message(role="assistant", content=msg.content or ""))
            return msg.content or "", False

    for i, task in enumerate(tasks):
        print(f"  Task {i+1}/{len(tasks)}: {task['id']}", end="", flush=True)

        # Add task as user message
        task_prompt = f"Task {i+1}: {task['description']}"
        store.add_message(Message(role="user", content=task_prompt))

        # Run until no more tool calls or max rounds
        for round_num in range(max_rounds):
            content, has_tools = call_model()

            # Extract and execute bash commands from content
            bash_matches = re.findall(r'```bash\n(.+?)\n```', content, re.DOTALL)
            if bash_matches:
                for cmd in bash_matches:
                    cmd_result = os_env.execute(cmd.strip())
                    store.add_message(Message(
                        role="user",
                        content=f"Command output:\n{cmd_result}"
                    ))

            # If no tool calls and no bash commands, task is done
            if not has_tools and not bash_matches:
                break

        # Check completion
        passed, total = os_env.check_state(task["checks"])
        result.checks_passed += passed
        result.total_checks += total
        if passed == total:
            result.tasks_completed += 1

        result.task_results.append({
            "task_id": task["id"],
            "completed": passed == total,
            "checks": f"{passed}/{total}",
        })

        print(f" - {'OK' if passed == total else 'FAIL'} ({passed}/{total})")

    result.elapsed_seconds = time.time() - start_time
    return result


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="OSWorld-style benchmark for ECM")
    parser.add_argument("--approach", choices=["linear", "scope", "both"], default="both")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--max-tasks", type=int, default=5)
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--output-dir", default="benchmarks/results/osworld")

    args = parser.parse_args()

    # Check API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        sys.exit(1)

    client = OpenAI()
    tasks = TASKS[:args.max_tasks]

    print(f"\nOSWorld Benchmark")
    print(f"Model: {args.model}")
    print(f"Tasks: {len(tasks)}")
    print("=" * 50)

    results = []

    if args.approach in ["linear", "both"]:
        print("\n[LINEAR] Running without memory management...")
        os_env = SimulatedOS()
        linear_result = run_linear(client, args.model, tasks, os_env, args.max_rounds)
        results.append(linear_result)
        print(f"\n  Completed: {linear_result.tasks_completed}/{linear_result.num_tasks}")
        print(f"  Tokens: {linear_result.total_prompt_tokens:,} prompt, {linear_result.total_completion_tokens:,} completion")
        print(f"  Peak context: {linear_result.peak_context:,}")

    if args.approach in ["scope", "both"]:
        print("\n[SCOPE/ECM] Running with memory management...")
        os_env = SimulatedOS()
        scope_result = run_scope(client, args.model, tasks, os_env, args.max_rounds)
        results.append(scope_result)
        print(f"\n  Completed: {scope_result.tasks_completed}/{scope_result.num_tasks}")
        print(f"  Tokens: {scope_result.total_prompt_tokens:,} prompt, {scope_result.total_completion_tokens:,} completion")
        print(f"  Peak context: {scope_result.peak_context:,}")
        print(f"  Notes: {scope_result.notes_created}, Insights: {scope_result.insights_created}, Scopes: {scope_result.scopes_created}")

    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"osworld_{timestamp}.json"

    with open(output_file, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    print(f"\nResults saved: {output_file}")

    # Summary table
    if len(results) == 2:
        print("\n" + "=" * 60)
        print("COMPARISON")
        print("=" * 60)
        print(f"{'Metric':<25} {'Linear':>15} {'Scope/ECM':>15}")
        print("-" * 60)
        print(f"{'Tasks Completed':<25} {results[0].tasks_completed:>15} {results[1].tasks_completed:>15}")
        print(f"{'Completion Rate':<25} {results[0].completion_rate:>14.1f}% {results[1].completion_rate:>14.1f}%")
        print(f"{'Prompt Tokens':<25} {results[0].total_prompt_tokens:>15,} {results[1].total_prompt_tokens:>15,}")
        print(f"{'Peak Context':<25} {results[0].peak_context:>15,} {results[1].peak_context:>15,}")
        print(f"{'API Calls':<25} {results[0].api_calls:>15} {results[1].api_calls:>15}")


if __name__ == "__main__":
    main()
