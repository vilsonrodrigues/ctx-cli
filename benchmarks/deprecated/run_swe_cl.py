#!/usr/bin/env python3
"""
SWE-Bench-CL Simplified Benchmark for ctx-cli.

Tests knowledge transfer across sequential coding tasks.
Based on SWE-Bench-CL (arxiv.org/abs/2507.00014).

This is a SIMPLIFIED version that measures token economics,
not actual code correctness.

Usage:
    uv run python benchmarks/run_swe_cl.py
    uv run python benchmarks/run_swe_cl.py --repo django --tasks 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
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
# Constants
# =============================================================================

DATA_FILE = Path(__file__).parent / "data" / "swe-bench-cl.json"

REPO_SHORT_NAMES = {
    "django/django": "django",
    "sympy/sympy": "sympy",
    "sphinx-doc/sphinx": "sphinx",
    "matplotlib/matplotlib": "matplotlib",
    "scikit-learn/scikit-learn": "sklearn",
    "astropy/astropy": "astropy",
    "pydata/xarray": "xarray",
    "pytest-dev/pytest": "pytest",
}


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class BenchmarkResult:
    """Result of SWE-Bench-CL benchmark."""
    approach: Literal["linear", "scope"]
    model: str
    repo: str
    num_tasks: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Token metrics (from OpenAI usage)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cached_tokens: int = 0  # Prompt cache hits

    # Context window metrics
    peak_context: int = 0
    context_per_task: list = field(default_factory=list)

    # Memory metrics (scope only)
    notes_created: int = 0
    scopes_created: int = 0

    # API calls
    api_calls: int = 0

    # Timing
    elapsed_seconds: float = 0.0

    # Task details
    task_results: list = field(default_factory=list)

    @property
    def effective_prompt_tokens(self) -> int:
        """Tokens actually processed (excluding cache hits)."""
        return self.total_prompt_tokens - self.total_cached_tokens


# =============================================================================
# Data Loading
# =============================================================================

def load_data() -> dict:
    """Load SWE-Bench-CL dataset."""
    if not DATA_FILE.exists():
        print(f"Error: Dataset not found at {DATA_FILE}")
        print("Download with:")
        print("  curl -sL https://raw.githubusercontent.com/thomasjoshi/agents-never-forget/main/data/SWE-Bench-CL-Curriculum.json -o benchmarks/data/swe-bench-cl.json")
        sys.exit(1)

    with open(DATA_FILE) as f:
        return json.load(f)


def get_sequence(data: dict, repo_name: str) -> dict | None:
    """Get sequence for a repository."""
    for seq in data["sequences"]:
        if repo_name in seq["repo"] or repo_name in seq["id"]:
            return seq
    return None


def extract_tasks(sequence: dict, max_tasks: int) -> list[dict]:
    """Extract tasks from sequence."""
    tasks = []
    for task in sequence["tasks"][:max_tasks]:
        tasks.append({
            "id": task["metadata"]["instance_id"],
            "problem": task["task"]["problem_statement"],
            "hints": task["task"].get("hints_text", ""),
            "difficulty": task["metadata"]["difficulty"],
            "position": task["continual_learning"]["sequence_position"],
            "files": task["continual_learning"]["modified_files"],
            "dependencies": task["continual_learning"]["dependencies"],
        })
    return tasks


# =============================================================================
# System Prompts
# =============================================================================

LINEAR_SYSTEM_PROMPT = """You are an expert software engineer analyzing GitHub issues.

For each task:
1. Understand the problem statement
2. Identify the relevant files and code patterns
3. Propose a solution approach
4. Note any patterns that might be useful for future similar issues

Be concise but thorough. Focus on the key changes needed."""


SCOPE_SYSTEM_PROMPT = '''You are a software engineer analyzing GitHub issues.

Tools: ctx_cli

# WORKFLOW (follow exactly)

When you receive a task:

1. FIRST: ctx_cli scope task-N -m "analyzing issue"
2. THEN: Analyze the problem and propose solution
3. THEN: ctx_cli note -m "files: X, patterns: Y, solution: Z"
4. LAST: ctx_cli goto main -m "done: summary"

# COMMANDS

scope <name> -m "..."   Start isolated work.
note -m "..."           Record what you learned. Be concise.
goto main -m "..."      Return with results.

# RULES

- ALWAYS start with scope, then analyze, then note, then goto main.
- Write ONE comprehensive note per task, not multiple.
- Be concise in notes: key files, patterns, solution approach.
'''


# =============================================================================
# Linear Approach
# =============================================================================

def run_linear(
    client: OpenAI,
    model: str,
    tasks: list[dict],
    repo: str,
) -> BenchmarkResult:
    """Run sequential tasks with linear context (no memory management)."""
    result = BenchmarkResult(approach="linear", model=model, repo=repo, num_tasks=len(tasks))
    start_time = time.time()
    tracker = TokenTracker(model=model)

    messages = [{"role": "system", "content": LINEAR_SYSTEM_PROMPT}]

    for i, task in enumerate(tasks):
        print(f"    Task {i+1}/{len(tasks)}: {task['id'][:40]}...", end="", flush=True)

        # Add task to context
        task_prompt = f"""## Task {i+1}: {task['id']}

**Problem:**
{task['problem'][:2000]}

**Files to modify:** {', '.join(task['files'][:5])}
**Difficulty:** {task['difficulty']}

Analyze this issue and propose a solution. Note any patterns useful for future issues."""

        messages.append({"role": "user", "content": task_prompt})

        # Track context before call
        context_tokens = tracker.count_messages(messages)
        result.context_per_task.append(context_tokens)
        result.peak_context = max(result.peak_context, context_tokens)

        # Get response
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=500,
        )

        answer = response.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": answer})

        result.api_calls += 1
        if response.usage:
            result.total_prompt_tokens += response.usage.prompt_tokens
            result.total_completion_tokens += response.usage.completion_tokens
            # Check for cached tokens (prompt caching)
            if hasattr(response.usage, 'prompt_tokens_details') and response.usage.prompt_tokens_details:
                cached = getattr(response.usage.prompt_tokens_details, 'cached_tokens', 0)
                result.total_cached_tokens += cached or 0

        result.task_results.append({
            "task_id": task["id"],
            "context_tokens": context_tokens,
            "response_preview": answer[:200],
        })

        print(f" ctx={context_tokens:,}")

    result.elapsed_seconds = time.time() - start_time
    return result


# =============================================================================
# Scope Approach
# =============================================================================

def run_scope(
    client: OpenAI,
    model: str,
    tasks: list[dict],
    repo: str,
) -> BenchmarkResult:
    """Run sequential tasks with scope-based memory management."""
    result = BenchmarkResult(approach="scope", model=model, repo=repo, num_tasks=len(tasks))
    start_time = time.time()
    tracker = TokenTracker(model=model)

    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    def call_model(max_rounds: int = 5) -> str:
        """Call model and handle tool calls."""
        for _ in range(max_rounds):
            context = store.get_context(SCOPE_SYSTEM_PROMPT)
            tokens = tracker.count_messages(context)
            result.peak_context = max(result.peak_context, tokens)

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
                # Check for cached tokens
                if hasattr(response.usage, 'prompt_tokens_details') and response.usage.prompt_tokens_details:
                    cached = getattr(response.usage.prompt_tokens_details, 'cached_tokens', 0)
                    result.total_cached_tokens += cached or 0

            if msg.tool_calls:
                store.add_message(Message(
                    role="assistant",
                    content=msg.content or "",
                    tool_calls=[tc.model_dump() for tc in msg.tool_calls]
                ))

                for tc in msg.tool_calls:
                    if tc.function.name == "ctx_cli":
                        args = json.loads(tc.function.arguments)
                        cmd = args.get("command", "")
                        cmd_result, _ = execute_command(store, cmd)

                        if cmd.startswith("note "):
                            result.notes_created += 1
                        elif cmd.startswith("scope "):
                            result.scopes_created += 1

                        store.add_message(Message(
                            role="tool",
                            content=cmd_result,
                            tool_call_id=tc.id,
                        ))
            else:
                if msg.content:
                    store.add_message(Message(role="assistant", content=msg.content))
                return msg.content or ""

        return ""

    for i, task in enumerate(tasks):
        print(f"    Task {i+1}/{len(tasks)}: {task['id'][:40]}...", end="", flush=True)

        # Instruction to start task
        task_prompt = f"""## Task {i+1}: {task['id']}

**Problem:**
{task['problem'][:2000]}

**Files to modify:** {', '.join(task['files'][:5])}
**Difficulty:** {task['difficulty']}

First create a scope for this task, then analyze and save useful patterns as notes.
When done, goto main with a summary."""

        store.add_message(Message(role="user", content=task_prompt))

        # Let model work (scope → analyze → note → goto = 4 rounds)
        call_model(max_rounds=4)

        # Track context after task
        context = store.get_context(SCOPE_SYSTEM_PROMPT)
        context_tokens = tracker.count_messages(context)
        result.context_per_task.append(context_tokens)

        result.task_results.append({
            "task_id": task["id"],
            "context_tokens": context_tokens,
            "notes_so_far": result.notes_created,
        })

        print(f" ctx={context_tokens:,} notes={result.notes_created}")

    result.elapsed_seconds = time.time() - start_time
    return result


# =============================================================================
# Results
# =============================================================================

def print_results(linear: BenchmarkResult, scope: BenchmarkResult):
    """Print comparison of results."""
    print("\n" + "=" * 70)
    print("RESULTS: SWE-Bench-CL Simplified")
    print("=" * 70)

    print(f"\nRepo: {linear.repo}")
    print(f"Tasks: {linear.num_tasks}")

    # Focus on context window metrics (what matters with prompt caching)
    print(f"\n{'CONTEXT WINDOW METRICS':<25} {'Linear':>12} {'Scope':>12} {'Savings':>12}")
    print("-" * 61)

    # Peak context
    lin_peak = linear.peak_context
    scp_peak = scope.peak_context
    savings_pct = ((lin_peak - scp_peak) / lin_peak * 100) if lin_peak > 0 else 0
    print(f"{'Peak context':<25} {lin_peak:>12,} {scp_peak:>12,} {savings_pct:>+11.1f}%")

    # Final task context
    lin_final = linear.context_per_task[-1] if linear.context_per_task else 0
    scp_final = scope.context_per_task[-1] if scope.context_per_task else 0
    savings_pct = ((lin_final - scp_final) / lin_final * 100) if lin_final > 0 else 0
    print(f"{'Final task context':<25} {lin_final:>12,} {scp_final:>12,} {savings_pct:>+11.1f}%")

    # Average context
    lin_avg = sum(linear.context_per_task) / len(linear.context_per_task) if linear.context_per_task else 0
    scp_avg = sum(scope.context_per_task) / len(scope.context_per_task) if scope.context_per_task else 0
    savings_pct = ((lin_avg - scp_avg) / lin_avg * 100) if lin_avg > 0 else 0
    print(f"{'Avg context/task':<25} {lin_avg:>12,.0f} {scp_avg:>12,.0f} {savings_pct:>+11.1f}%")

    # Growth
    lin_growth = linear.context_per_task[-1] - linear.context_per_task[0] if len(linear.context_per_task) > 1 else 0
    scp_growth = scope.context_per_task[-1] - scope.context_per_task[0] if len(scope.context_per_task) > 1 else 0
    print(f"{'Context growth':<25} {lin_growth:>12,} {scp_growth:>12,}")

    print(f"\n{'MEMORY USAGE':<25}")
    print("-" * 61)
    print(f"{'Notes created':<25} {'N/A':>12} {scope.notes_created:>12}")
    print(f"{'Scopes created':<25} {'N/A':>12} {scope.scopes_created:>12}")

    print(f"\n{'API USAGE (OpenAI)':<25} {'Linear':>12} {'Scope':>12} {'Diff':>12}")
    print("-" * 61)
    print(f"{'API calls':<25} {linear.api_calls:>12} {scope.api_calls:>12}")
    print(f"{'Prompt tokens':<25} {linear.total_prompt_tokens:>12,} {scope.total_prompt_tokens:>12,}")
    print(f"{'Completion tokens':<25} {linear.total_completion_tokens:>12,} {scope.total_completion_tokens:>12,}")
    print(f"{'Cached tokens':<25} {linear.total_cached_tokens:>12,} {scope.total_cached_tokens:>12,}")

    lin_effective = linear.effective_prompt_tokens
    scp_effective = scope.effective_prompt_tokens
    diff_pct = ((scp_effective - lin_effective) / lin_effective * 100) if lin_effective > 0 else 0
    print(f"{'Effective prompt*':<25} {lin_effective:>12,} {scp_effective:>12,} {diff_pct:>+11.1f}%")
    print("  * Effective = Prompt - Cached (actual cost)")

    print(f"\n{'PERFORMANCE':<25}")
    print("-" * 61)
    print(f"{'Time (s)':<25} {linear.elapsed_seconds:>12.1f} {scope.elapsed_seconds:>12.1f}", end="")
    time_diff = ((scope.elapsed_seconds - linear.elapsed_seconds) / linear.elapsed_seconds * 100) if linear.elapsed_seconds > 0 else 0
    print(f" {time_diff:>+11.1f}%")

    # Tokens per second
    lin_tps = linear.total_completion_tokens / linear.elapsed_seconds if linear.elapsed_seconds > 0 else 0
    scp_tps = scope.total_completion_tokens / scope.elapsed_seconds if scope.elapsed_seconds > 0 else 0
    print(f"{'Completion tok/s':<25} {lin_tps:>12.1f} {scp_tps:>12.1f}")

    # Context growth analysis
    print("\n" + "=" * 70)
    print("CONTEXT GROWTH")
    print("=" * 70)

    print(f"\n{'Task':<6} {'Linear':>12} {'Scope':>12} {'Savings':>12}")
    print("-" * 42)

    for i, (lin_ctx, scp_ctx) in enumerate(zip(linear.context_per_task, scope.context_per_task)):
        savings = lin_ctx - scp_ctx
        pct = (savings / lin_ctx * 100) if lin_ctx > 0 else 0
        print(f"{i+1:<6} {lin_ctx:>12,} {scp_ctx:>12,} {pct:>+11.1f}%")

    # Final analysis
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)

    final_lin = linear.context_per_task[-1] if linear.context_per_task else 0
    final_scp = scope.context_per_task[-1] if scope.context_per_task else 0
    savings = final_lin - final_scp

    if savings > 0:
        pct = (savings / final_lin * 100)
        print(f"\n✓ Scope saved {savings:,} tokens ({pct:.1f}%) on final task")
    else:
        print(f"\n✗ Scope used {-savings:,} more tokens on final task")

    if scope.notes_created > 0:
        print(f"✓ Created {scope.notes_created} notes for knowledge transfer")
    else:
        print("✗ No notes created - model didn't use ctx_cli")

    # Growth rate
    if len(linear.context_per_task) > 1:
        lin_growth = linear.context_per_task[-1] - linear.context_per_task[0]
        scp_growth = scope.context_per_task[-1] - scope.context_per_task[0]
        print(f"\nLinear growth: {lin_growth:,} tokens over {len(linear.context_per_task)} tasks")
        print(f"Scope growth: {scp_growth:,} tokens over {len(scope.context_per_task)} tasks")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="SWE-Bench-CL Simplified Benchmark")
    parser.add_argument("--model", default="gpt-4.1-mini", help="Model to use")
    parser.add_argument("--repo", default="django", help="Repository (django, sympy, pytest, etc.)")
    parser.add_argument("--tasks", type=int, default=5, help="Number of tasks")
    parser.add_argument("--output", default="benchmarks/results", help="Output directory")
    parser.add_argument("--linear-only", action="store_true", help="Only run linear")
    parser.add_argument("--scope-only", action="store_true", help="Only run scope")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY environment variable")
        sys.exit(1)

    # Load data
    print("=" * 70)
    print("SWE-Bench-CL Simplified Benchmark")
    print("=" * 70)

    data = load_data()
    sequence = get_sequence(data, args.repo)

    if not sequence:
        print(f"Error: Repository '{args.repo}' not found")
        print(f"Available: {[s['repo'] for s in data['sequences']]}")
        sys.exit(1)

    tasks = extract_tasks(sequence, args.tasks)

    print(f"Model: {args.model}")
    print(f"Repository: {sequence['repo']}")
    print(f"Tasks: {len(tasks)}")

    client = OpenAI()
    linear_result = None
    scope_result = None

    # Run benchmarks
    if not args.scope_only:
        print("\n[1/2] Running LINEAR approach...")
        linear_result = run_linear(client, args.model, tasks, sequence["repo"])
        print(f"  Peak context: {linear_result.peak_context:,}")

    if not args.linear_only:
        print("\n[2/2] Running SCOPE approach...")
        scope_result = run_scope(client, args.model, tasks, sequence["repo"])
        print(f"  Peak context: {scope_result.peak_context:,}")
        print(f"  Notes created: {scope_result.notes_created}")

    # Print comparison
    if linear_result and scope_result:
        print_results(linear_result, scope_result)

    # Save results
    os.makedirs(args.output, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    repo_short = args.repo.replace("/", "_")
    filename = f"{args.output}/swe_cl_{repo_short}_{timestamp}.json"

    results = {
        "config": {
            "model": args.model,
            "repo": sequence["repo"],
            "num_tasks": len(tasks),
        },
        "linear": asdict(linear_result) if linear_result else None,
        "scope": asdict(scope_result) if scope_result else None,
    }

    with open(filename, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {filename}")


if __name__ == "__main__":
    main()
