"""
Internal benchmarks for ctx-cli.

Compares LINEAR vs SCOPE approaches on controlled tasks.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal

from openai import OpenAI

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from tokens import TokenTracker


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    task_name: str
    approach: Literal["linear", "scope"]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Token metrics
    base_input: int = 0
    peak_input: int = 0
    growth: int = 0
    total_input: int = 0
    total_output: int = 0

    # Task metrics
    iterations: int = 0
    completed: bool = False
    notes_created: int = 0
    scopes_created: int = 0

    # Timing
    elapsed_seconds: float = 0.0


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark."""
    model: str = "gpt-4.1-mini"
    max_iterations: int = 20
    temperature: float = 0.7


# =============================================================================
# Task Definitions
# =============================================================================

MULTI_STEP_CODING_STEPS = [
    "Design the data model for a blog platform with posts, comments, and users.",
    "Now add categories and tags to the posts. How should they relate?",
    "Design the authentication system. What fields do we need for users?",
    "Add a notification system for when someone comments on your post.",
    "Now add a search feature. What should be searchable?",
    "Add analytics tracking - what metrics should we track?",
    "Design the API endpoints for all these features.",
    "Finally, summarize the complete architecture.",
]

KNOWLEDGE_TRANSFER_PROJECT_A = """Create a User model in models/user.py with:
- User dataclass with: id (str), email (str), name (str), password_hash (str), created_at (datetime), is_active (bool)
- Email validation method (must contain @)
- Password validation (min 8 chars)
- is_valid() method that checks all validations
- to_dict() method for serialization

Make sure to include proper imports and docstrings."""

KNOWLEDGE_TRANSFER_PROJECT_B = """Create a Product model in models/product.py with:
- Product dataclass with: id (str), name (str), price (float), stock (int), created_at (datetime), is_available (bool)
- Price validation (must be positive)
- Stock validation (must be >= 0)
- is_valid() method that checks all validations
- to_dict() method for serialization

IMPORTANT: First check your notes from previous work to recall patterns you used."""


# =============================================================================
# Benchmark Runners
# =============================================================================

class BenchmarkRunner:
    """Base class for running benchmarks."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig()
        self.client = OpenAI()
        self.tracker = TokenTracker(model=self.config.model)

    def run_linear(self, task_name: str, steps: list[str], system_prompt: str) -> BenchmarkResult:
        """Run task with linear conversation (no ctx_cli)."""
        result = BenchmarkResult(task_name=task_name, approach="linear")
        start_time = time.time()

        messages = [{"role": "system", "content": system_prompt}]
        token_history = []

        for i, step in enumerate(steps):
            messages.append({"role": "user", "content": step})

            tokens = self.tracker.count_messages(messages)
            token_history.append(tokens)

            if i == 0:
                result.base_input = tokens
            result.peak_input = max(result.peak_input, tokens)

            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
            )

            assistant_msg = response.choices[0].message.content
            messages.append({"role": "assistant", "content": assistant_msg})

            if response.usage:
                result.total_input += response.usage.prompt_tokens
                result.total_output += response.usage.completion_tokens

            result.iterations += 1

        result.growth = result.peak_input - result.base_input
        result.completed = True
        result.elapsed_seconds = time.time() - start_time

        return result

    def run_scope(self, task_name: str, steps: list[str], system_prompt: str) -> BenchmarkResult:
        """Run task with scope-based context management."""
        result = BenchmarkResult(task_name=task_name, approach="scope")
        start_time = time.time()

        store = ContextStore()
        tools = [CTX_CLI_TOOL]
        token_history = []

        for step_idx, step in enumerate(steps):
            store.add_message(Message(role="user", content=step))

            for _ in range(5):  # Max tool call rounds per step
                context = store.get_context(system_prompt)
                tokens = self.tracker.count_messages(context)
                token_history.append(tokens)

                if step_idx == 0 and len(token_history) == 1:
                    result.base_input = tokens
                result.peak_input = max(result.peak_input, tokens)

                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=context,
                    tools=tools,
                    temperature=self.config.temperature,
                )

                message = response.choices[0].message

                if response.usage:
                    result.total_input += response.usage.prompt_tokens
                    result.total_output += response.usage.completion_tokens

                result.iterations += 1

                if message.tool_calls:
                    store.add_message(Message(
                        role="assistant",
                        content=message.content or "",
                        tool_calls=[tc.model_dump() for tc in message.tool_calls]
                    ))

                    for tool_call in message.tool_calls:
                        if tool_call.function.name == "ctx_cli":
                            args = json.loads(tool_call.function.arguments)
                            cmd = args.get("command", "")
                            cmd_result, _ = execute_command(store, cmd)

                            # Track notes and scopes
                            if cmd.startswith("note "):
                                result.notes_created += 1
                            elif cmd.startswith("scope "):
                                result.scopes_created += 1

                            store.add_message(Message(
                                role="tool",
                                content=cmd_result,
                                tool_call_id=tool_call.id,
                            ))
                else:
                    store.add_message(Message(
                        role="assistant",
                        content=message.content or "",
                    ))
                    break  # No more tool calls, move to next step

        result.growth = result.peak_input - result.base_input
        result.completed = True
        result.elapsed_seconds = time.time() - start_time

        return result


def run_multi_step_coding(runner: BenchmarkRunner) -> tuple[BenchmarkResult, BenchmarkResult]:
    """Run multi-step coding benchmark."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Multi-Step Coding Task")
    print("=" * 60)

    system_prompt_linear = "You are a software architect designing a system."

    system_prompt_scope = """You are a software architect designing a system.

You have ctx_cli for context management. USE IT ACTIVELY:
- scope name -m "starting this area" - Create scope for new area
- note -m "description" - Save your current reasoning
- goto main -m "summary" - Return with findings

Save notes after each major design decision to preserve your reasoning."""

    print("\n[1/2] Running LINEAR approach...")
    linear_result = runner.run_linear(
        "multi_step_coding",
        MULTI_STEP_CODING_STEPS,
        system_prompt_linear
    )
    print(f"  Completed in {linear_result.iterations} iterations, {linear_result.elapsed_seconds:.1f}s")

    print("\n[2/2] Running SCOPE approach...")
    scope_result = runner.run_scope(
        "multi_step_coding",
        MULTI_STEP_CODING_STEPS,
        system_prompt_scope
    )
    print(f"  Completed in {scope_result.iterations} iterations, {scope_result.elapsed_seconds:.1f}s")
    print(f"  Notes created: {scope_result.notes_created}, Scopes: {scope_result.scopes_created}")

    return linear_result, scope_result


def print_comparison(linear: BenchmarkResult, scope: BenchmarkResult):
    """Print comparison of results."""
    print("\n" + "=" * 60)
    print("RESULTS COMPARISON")
    print("=" * 60)

    def pct_change(old, new):
        if old == 0:
            return 0
        return ((new - old) / old) * 100

    print(f"\n{'Metric':<30} {'Linear':>12} {'Scope':>12} {'Change':>12}")
    print("-" * 66)

    metrics = [
        ("Base Input (cacheable)", linear.base_input, scope.base_input),
        ("Peak Input", linear.peak_input, scope.peak_input),
        ("Growth (peak - base)", linear.growth, scope.growth),
        ("Total Input", linear.total_input, scope.total_input),
        ("Total Output", linear.total_output, scope.total_output),
        ("Iterations", linear.iterations, scope.iterations),
    ]

    for name, lin_val, scope_val in metrics:
        change = pct_change(lin_val, scope_val)
        change_str = f"{change:+.1f}%" if change != 0 else "—"
        print(f"{name:<30} {lin_val:>12,} {scope_val:>12,} {change_str:>12}")

    print(f"\n{'Notes created':<30} {'N/A':>12} {scope.notes_created:>12}")
    print(f"{'Scopes created':<30} {'N/A':>12} {scope.scopes_created:>12}")


def save_results(results: list[BenchmarkResult], output_dir: str = "benchmarks/results"):
    """Save results to JSON file."""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/internal_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    print(f"\nResults saved to: {filename}")


def main():
    """Run internal benchmarks."""
    print("=" * 60)
    print("ctx-cli Internal Benchmarks")
    print("=" * 60)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY environment variable")
        return

    runner = BenchmarkRunner()
    results = []

    # Run multi-step coding benchmark
    linear, scope = run_multi_step_coding(runner)
    results.extend([linear, scope])
    print_comparison(linear, scope)

    # Save results
    save_results(results)

    print("\n" + "=" * 60)
    print("Benchmarks completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
