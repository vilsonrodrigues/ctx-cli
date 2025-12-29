"""
Comparison Demo: Linear Loop vs Branch-based Context Management.

This demo runs the SAME task twice:
1. LINEAR approach: Traditional conversation loop, no ctx_cli
2. BRANCH approach: Using ctx_cli with commits and branches

Compares token usage, context management, and information preservation.
"""

from __future__ import annotations

import json
import os
import sys
import time

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from tokens import TokenTracker

# Same task for both approaches
TASK_STEPS = [
    "Design the data model for a blog platform with posts, comments, and users.",
    "Now add categories and tags to the posts. How should they relate?",
    "Design the authentication system. What fields do we need for users?",
    "Add a notification system for when someone comments on your post.",
    "Now add a search feature. What should be searchable?",
    "Add analytics tracking - what metrics should we track?",
    "Design the API endpoints for all these features.",
    "Finally, summarize the complete architecture.",
]


def run_linear_approach(client: OpenAI, tracker: TokenTracker) -> dict:
    """Run the task using traditional linear conversation."""
    print("\n" + "=" * 70)
    print("APPROACH 1: LINEAR CONVERSATION (No ctx_cli)")
    print("=" * 70)
    print("Running same task without context management...\n")

    messages = [{"role": "system", "content": "You are a software architect designing a system."}]
    token_history = []
    start_time = time.time()

    for i, step in enumerate(TASK_STEPS, 1):
        print(f"Step {i}: {step[:50]}...")

        messages.append({"role": "user", "content": step})

        # Track tokens before API call
        tokens = tracker.count_messages(messages)
        token_history.append(tokens)

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
        )

        assistant_msg = response.choices[0].message.content
        messages.append({"role": "assistant", "content": assistant_msg})

        print(f"  → Tokens: {tokens}, Messages: {len(messages)}")

    elapsed = time.time() - start_time

    return {
        "approach": "linear",
        "final_tokens": token_history[-1] if token_history else 0,
        "max_tokens": max(token_history) if token_history else 0,
        "token_history": token_history,
        "message_count": len(messages),
        "elapsed_time": elapsed,
    }


def run_branch_approach(client: OpenAI, tracker: TokenTracker) -> dict:
    """Run the task using ctx_cli with commits and branches."""
    print("\n" + "=" * 70)
    print("APPROACH 2: BRANCH-BASED (With ctx_cli)")
    print("=" * 70)
    print("Running same task with context management...\n")

    store = ContextStore()
    tools = [CTX_CLI_TOOL]
    token_history = []
    commits_made = 0
    start_time = time.time()

    system_prompt = """You are a software architect designing a system.

You have ctx_cli for context management. USE IT ACTIVELY:
- Commit after each major design decision
- Keep commit messages concise but informative
- This preserves your reasoning while keeping context lean

Key commands:
- commit -m "description" - Save your current reasoning
- checkout -b name -m "note" - Create branch for new area
- log - See your commit history"""

    def chat(user_message: str) -> int:
        nonlocal commits_made
        store.add_message(Message(role="user", content=user_message))

        for _ in range(5):  # Max tool call rounds
            context = store.get_context(system_prompt)
            tokens = tracker.count_messages(context)

            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=context,
                tools=tools,
            )

            message = response.choices[0].message

            if message.tool_calls:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                    tool_calls=[tc.model_dump() for tc in message.tool_calls]
                ))

                for tool_call in message.tool_calls:
                    if tool_call.function.name == "ctx_cli":
                        args = json.loads(tool_call.function.arguments)
                        result, _ = execute_command(store, args["command"])
                        if "commit" in args["command"]:
                            commits_made += 1
                        store.add_message(Message(
                            role="tool",
                            content=result,
                            tool_call_id=tool_call.id,
                        ))
            else:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                ))
                return tokens

        return tokens

    for i, step in enumerate(TASK_STEPS, 1):
        print(f"Step {i}: {step[:50]}...")
        tokens = chat(step)
        token_history.append(tokens)
        print(f"  → Tokens: {tokens}, Commits: {commits_made}")

    elapsed = time.time() - start_time

    return {
        "approach": "branch",
        "final_tokens": token_history[-1] if token_history else 0,
        "max_tokens": max(token_history) if token_history else 0,
        "token_history": token_history,
        "message_count": sum(len(b.messages) for b in store.branches.values()),
        "commits_made": commits_made,
        "branches": len(store.branches),
        "elapsed_time": elapsed,
    }


def run_comparison():
    """Run both approaches and compare results."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    tracker = TokenTracker(model="gpt-4.1-mini")

    print("=" * 70)
    print("COMPARISON DEMO: Linear vs Branch-based Context Management")
    print("=" * 70)
    print(f"\nTask: Design a blog platform ({len(TASK_STEPS)} steps)")
    print("Running both approaches with the same task...\n")

    # Run both approaches
    linear_results = run_linear_approach(client, tracker)
    branch_results = run_branch_approach(client, tracker)

    # =========================================================================
    # Comparison Results
    # =========================================================================
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)

    print("\n📊 Token Usage:")
    print(f"  {'Metric':<25} {'Linear':>12} {'Branch':>12} {'Savings':>12}")
    print(f"  {'-' * 25} {'-' * 12} {'-' * 12} {'-' * 12}")

    linear_max = linear_results["max_tokens"]
    branch_max = branch_results["max_tokens"]
    savings_max = ((linear_max - branch_max) / linear_max * 100) if linear_max > 0 else 0

    linear_final = linear_results["final_tokens"]
    branch_final = branch_results["final_tokens"]
    savings_final = ((linear_final - branch_final) / linear_final * 100) if linear_final > 0 else 0

    print(f"  {'Max tokens':.<25} {linear_max:>12,} {branch_max:>12,} {savings_max:>11.1f}%")
    print(f"  {'Final tokens':.<25} {linear_final:>12,} {branch_final:>12,} {savings_final:>11.1f}%")

    print("\n📈 Token Growth Curve:")
    print(f"  Step   │ {'Linear':>10} │ {'Branch':>10} │ Difference")
    print(f"  {'─' * 6}┼{'─' * 12}┼{'─' * 12}┼{'─' * 12}")
    for i, (l, b) in enumerate(zip(linear_results["token_history"], branch_results["token_history"]), 1):
        diff = l - b
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"  {i:>5} │ {l:>10,} │ {b:>10,} │ {diff_str:>10}")

    print("\n📋 Context Management:")
    print(f"  {'Metric':<30} {'Linear':>12} {'Branch':>12}")
    print(f"  {'-' * 30} {'-' * 12} {'-' * 12}")
    print(f"  {'Final message count':.<30} {linear_results['message_count']:>12} {branch_results['message_count']:>12}")
    print(f"  {'Commits made':.<30} {'N/A':>12} {branch_results.get('commits_made', 0):>12}")
    print(f"  {'Branches created':.<30} {'N/A':>12} {branch_results.get('branches', 1):>12}")

    print("\n⏱️  Execution Time:")
    print(f"  Linear: {linear_results['elapsed_time']:.1f}s")
    print(f"  Branch: {branch_results['elapsed_time']:.1f}s")

    print("\n💡 Key Insights:")
    if savings_final > 0:
        print(f"  ✓ Branch approach saved {savings_final:.1f}% tokens at completion")
    else:
        print(f"  → Branch approach used {-savings_final:.1f}% more tokens (overhead from tool calls)")

    if branch_results.get("commits_made", 0) > 0:
        print(f"  ✓ {branch_results['commits_made']} commits preserved reasoning as episodic memory")
    else:
        print("  → No commits made (model didn't use ctx_cli)")

    print("\n📝 Summary:")
    print("  Linear: Simple but context grows unbounded")
    print("  Branch: Overhead from tools, but flattens growth curve")
    print("  Best for: Long tasks where context would exceed limits")


if __name__ == "__main__":
    run_comparison()
