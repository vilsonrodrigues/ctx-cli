"""
Comparison Demo: Linear Loop vs Scope-based Context Management.

This demo runs the SAME task twice:
1. LINEAR approach: Traditional conversation loop, no ctx_cli
2. SCOPE approach: Using ctx_cli with notes and scopes

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
from prompts import SYSTEM_PROMPT_ECM
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
    working_history = []  # Track working context (messages only, no system)
    peak_working = 0
    start_time = time.time()

    for i, step in enumerate(TASK_STEPS, 1):
        print(f"Step {i}: {step[:50]}...")

        messages.append({"role": "user", "content": step})

        # Track total tokens (with system prompt)
        tokens = tracker.count_messages(messages)
        token_history.append(tokens)

        # Track working context (messages only, excluding system prompt)
        working_messages = [m for m in messages if m.get("role") != "system"]
        working_tokens = tracker.count_messages(working_messages)
        working_history.append(working_tokens)
        peak_working = max(peak_working, working_tokens)

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
        )

        assistant_msg = response.choices[0].message.content
        messages.append({"role": "assistant", "content": assistant_msg})

        print(f"  → Tokens: {tokens}, Messages: {len(messages)}")

    elapsed = time.time() - start_time

    # Capture final working context
    working_messages = [m for m in messages if m.get("role") != "system"]
    final_working = tracker.count_messages(working_messages)

    return {
        "approach": "linear",
        "final_tokens": token_history[-1] if token_history else 0,
        "max_tokens": max(token_history) if token_history else 0,
        "token_history": token_history,
        "working_history": working_history,
        "peak_working": peak_working,
        "final_working": final_working,
        "message_count": len(messages),
        "elapsed_time": elapsed,
    }


def run_scope_approach(client: OpenAI, tracker: TokenTracker) -> dict:
    """Run the task using ctx_cli with notes and scopes."""
    print("\n" + "=" * 70)
    print("APPROACH 2: SCOPE-BASED (With ctx_cli)")
    print("=" * 70)
    print("Running same task with context management...\n")

    store = ContextStore()
    tools = [CTX_CLI_TOOL]
    token_history = []
    working_history = []  # Track working context (messages only, no system)
    peak_working = 0
    notes_made = 0
    start_time = time.time()

    system_prompt = "You are a software architect designing a system.\n\n" + SYSTEM_PROMPT_ECM

    def chat(user_message: str) -> tuple[int, int]:
        """Returns (total_tokens, working_tokens)"""
        nonlocal notes_made, peak_working
        store.add_message(Message(role="user", content=user_message))

        for _ in range(5):  # Max tool call rounds
            context = store.get_context(system_prompt)
            tokens = tracker.count_messages(context)

            # Track working context (messages only, excluding system prompt)
            working_messages = [m for m in context if m.get("role") != "system"]
            working_tokens = tracker.count_messages(working_messages)
            peak_working = max(peak_working, working_tokens)

            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=context,
                tools=tools,
            )

            message = response.choices[0].message

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "ctx_cli":
                        args = json.loads(tool_call.function.arguments)
                        cmd = args["command"]

                        # Use execute_tool_call for proper message management
                        result = store.execute_tool_call(
                            tool_call_id=tool_call.id,
                            command=cmd,
                            assistant_content=message.content or ""
                        )

                        if "note" in cmd:
                            notes_made += 1

                # Refresh context after tool calls
                context = store.get_context(system_prompt)
            else:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                ))
                return tokens, working_tokens

        return tokens, working_tokens

    for i, step in enumerate(TASK_STEPS, 1):
        print(f"Step {i}: {step[:50]}...")
        tokens, working_tokens = chat(step)
        token_history.append(tokens)
        working_history.append(working_tokens)
        print(f"  → Tokens: {tokens}, Notes: {notes_made}")

    elapsed = time.time() - start_time

    # Capture final working context
    context = store.get_context(system_prompt)
    working_messages = [m for m in context if m.get("role") != "system"]
    final_working = tracker.count_messages(working_messages)

    return {
        "approach": "scope",
        "final_tokens": token_history[-1] if token_history else 0,
        "max_tokens": max(token_history) if token_history else 0,
        "token_history": token_history,
        "working_history": working_history,
        "peak_working": peak_working,
        "final_working": final_working,
        "message_count": sum(len(b.messages) for b in store.branches.values()),
        "notes_made": notes_made,
        "scopes": len(store.branches),
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
    print("COMPARISON DEMO: Linear vs Scope-based Context Management")
    print("=" * 70)
    print(f"\nTask: Design a blog platform ({len(TASK_STEPS)} steps)")
    print("Running both approaches with the same task...\n")

    # Run both approaches
    linear_results = run_linear_approach(client, tracker)
    scope_results = run_scope_approach(client, tracker)

    # =========================================================================
    # Comparison Results
    # =========================================================================
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)

    print("\n📊 Key Metric: Peak Working Context (fair comparison)")
    print("=" * 70)
    linear_peak_working = linear_results["peak_working"]
    scope_peak_working = scope_results["peak_working"]
    peak_savings = linear_peak_working - scope_peak_working
    peak_pct = (peak_savings / linear_peak_working * 100) if linear_peak_working > 0 else 0

    print(f"  Linear:   {linear_peak_working:>6,} tokens (messages only)")
    print(f"  ECM:      {scope_peak_working:>6,} tokens (messages only)")
    print(f"  Savings:  {peak_savings:>6,} tokens ({peak_pct:>5.1f}% reduction) {'✅' if peak_savings > 0 else '❌'}")

    print("\n📋 Final Working Context (at completion)")
    print("=" * 70)
    linear_final_working = linear_results["final_working"]
    scope_final_working = scope_results["final_working"]
    final_savings = linear_final_working - scope_final_working
    final_pct = (final_savings / linear_final_working * 100) if linear_final_working > 0 else 0

    print(f"  Linear:   {linear_final_working:>6,} tokens")
    print(f"  ECM:      {scope_final_working:>6,} tokens")
    print(f"  Savings:  {final_savings:>6,} tokens ({final_pct:>5.1f}% reduction) {'✅' if final_savings > 0 else '❌'}")

    print("\n📈 Peak Total Context (includes system prompt)")
    print("=" * 70)
    linear_max = linear_results["max_tokens"]
    scope_max = scope_results["max_tokens"]

    print(f"  Linear:   {linear_max:>6,} tokens")
    print(f"  ECM:      {scope_max:>6,} tokens")

    print("\n📈 Token Growth Curve:")
    print(f"  Step   │ {'Linear':>10} │ {'Scope':>10} │ Difference")
    print(f"  {'─' * 6}┼{'─' * 12}┼{'─' * 12}┼{'─' * 12}")
    for i, (l, s) in enumerate(zip(linear_results["token_history"], scope_results["token_history"]), 1):
        diff = l - s
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"  {i:>5} │ {l:>10,} │ {s:>10,} │ {diff_str:>10}")

    print("\n📋 Context Management:")
    print(f"  {'Metric':<30} {'Linear':>12} {'Scope':>12}")
    print(f"  {'-' * 30} {'-' * 12} {'-' * 12}")
    print(f"  {'Final message count':.<30} {linear_results['message_count']:>12} {scope_results['message_count']:>12}")
    print(f"  {'Notes made':.<30} {'N/A':>12} {scope_results.get('notes_made', 0):>12}")
    print(f"  {'Scopes created':.<30} {'N/A':>12} {scope_results.get('scopes', 1):>12}")

    print("\n⏱️  Execution Time:")
    print(f"  Linear: {linear_results['elapsed_time']:.1f}s")
    print(f"  Scope: {scope_results['elapsed_time']:.1f}s")
    time_saved = linear_results['elapsed_time'] - scope_results['elapsed_time']
    if time_saved > 0:
        time_pct = (time_saved / linear_results['elapsed_time'] * 100)
        print(f"  Savings: {time_saved:.1f}s ({time_pct:.1f}% faster)")

    print("\n💡 Key Insights:")
    if peak_pct > 0:
        print(f"  ✓ ECM reduced peak working context by {peak_pct:.1f}%")
    else:
        print(f"  → ECM used {-peak_pct:.1f}% more peak context (overhead from system prompt)")

    if final_pct > 0:
        print(f"  ✓ ECM reduced final working context by {final_pct:.1f}%")

    if scope_results.get("notes_made", 0) > 0:
        print(f"  ✓ {scope_results['notes_made']} notes preserved reasoning as episodic memory")
    else:
        print("  → No notes made (model didn't use ctx_cli)")

    print("\n📝 Summary:")
    print("  Linear: Simple but context grows unbounded")
    print("  ECM: Discards working memory via scope/return, maintains sustainable context")
    print("  Best for: Long tasks where context would exceed limits")


if __name__ == "__main__":
    run_comparison()
