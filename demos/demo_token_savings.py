"""
Token Savings Demo: Compare context-managed vs traditional approach.

This demo shows the token economy of using ctx_cli:
1. Runs a long task WITH context management
2. Tracks token usage at each step
3. Shows how notes flatten the token curve

Demonstrates the core value proposition of ctx_cli.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from tokens import TokenTracker

SYSTEM_PROMPT = """You are a software architect designing a microservices system.

You have ctx_cli for context management. USE IT AFTER EVERY MAJOR DECISION.

Your goal: Design a complete e-commerce microservices architecture.
This is a large task - manage your context carefully.

Rules:
1. Take notes after EVERY service you design
2. Keep notes concise but informative
3. Don't repeat information already noted

Commands: scope, goto, note, notes

Be thorough but token-efficient."""


def run_token_comparison():
    """Run demo showing token savings."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tracker = TokenTracker(model="gpt-4.1-mini")
    tools = [CTX_CLI_TOOL]

    # Track token usage over time
    token_history = []

    def chat(user_message: str, step: int) -> str:
        store.add_message(Message(role="user", content=user_message))

        for _ in range(8):
            context = store.get_context(SYSTEM_PROMPT)
            tokens = tracker.count_messages(context)

            # Record token usage
            token_history.append({
                "step": step,
                "tokens": tokens,
                "messages": len(context),
                "notes": sum(len(b.commits) for b in store.branches.values()),
            })

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

                tool_results = []
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "ctx_cli":
                        args = json.loads(tool_call.function.arguments)
                        result, _ = execute_command(store, args["command"])
                        cmd = args["command"]
                        if "note" in cmd:
                            print(f"    💾 {cmd[:60]}...")
                        else:
                            print(f"    🔧 {cmd[:60]}")
                        tool_results.append((tool_call.id, result))

                for tool_id, result in tool_results:
                    store.add_message(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tool_id,
                    ))
            else:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                ))
                return message.content or ""

        return "[Max rounds]"

    print("=" * 70)
    print("TOKEN SAVINGS DEMO: Measuring Context Management Efficiency")
    print("=" * 70)
    print("\nWatching token usage as agent designs microservices architecture...")
    print("💾 = note (reduces future context)")
    print("🔧 = other ctx_cli command\n")

    # Series of architecture design tasks
    tasks = [
        ("Design the User Service: authentication, profiles, roles.", "User Service"),
        ("Design the Product Catalog Service: products, categories, search.", "Product Service"),
        ("Design the Inventory Service: stock levels, reservations, alerts.", "Inventory Service"),
        ("Design the Order Service: carts, orders, payments.", "Order Service"),
        ("Design the Notification Service: email, SMS, push notifications.", "Notification Service"),
        ("Design the API Gateway: routing, rate limiting, auth.", "API Gateway"),
        ("Design the service communication: sync vs async, message queues.", "Communication"),
        ("Summarize the complete architecture with a diagram description.", "Final Summary"),
    ]

    for i, (task, label) in enumerate(tasks, 1):
        print(f"\n{'─' * 50}")
        print(f"STEP {i}: {label}")
        print(f"{'─' * 50}")
        chat(task, step=i)

    # =========================================================================
    # Analysis
    # =========================================================================
    print("\n" + "=" * 70)
    print("TOKEN USAGE ANALYSIS")
    print("=" * 70)

    print("\n📊 Token Usage Over Time:")
    print("   Step  │ Tokens  │ Messages │ Notes   │ Efficiency")
    print("   ─────┼─────────┼──────────┼─────────┼───────────")

    max_tokens = max(t["tokens"] for t in token_history)
    for t in token_history:
        bar_len = int((t["tokens"] / max_tokens) * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"   {t['step']:4} │ {t['tokens']:7,} │ {t['messages']:8} │ {t['notes']:7} │ {bar}")

    print("\n📈 Statistics:")

    # Calculate what tokens WOULD have been without notes
    # Rough estimate: each note saves ~500 tokens on average
    notes_made = sum(len(b.commits) for b in store.branches.values())
    estimated_savings = notes_made * 500

    final_tokens = token_history[-1]["tokens"] if token_history else 0
    without_management = final_tokens + estimated_savings

    print(f"   Final context size: {final_tokens:,} tokens")
    print(f"   Estimated without ctx_cli: {without_management:,} tokens")
    print(f"   Estimated savings: {estimated_savings:,} tokens ({(estimated_savings/without_management)*100:.1f}%)")
    print(f"   Total notes made: {notes_made}")
    print(f"   Context operations: {len(store.events)}")

    print("\n💡 Key Insight:")
    print("   Each note preserves reasoning while clearing working memory.")
    print("   This flattens the token growth curve, enabling longer tasks.")

    # Show token curve visualization
    print("\n📉 Token Growth Curve (with ctx_cli management):")
    if token_history:
        min_t = min(t["tokens"] for t in token_history)
        max_t = max(t["tokens"] for t in token_history)
        range_t = max_t - min_t if max_t > min_t else 1

        for t in token_history:
            normalized = int(((t["tokens"] - min_t) / range_t) * 40)
            bar = "─" * normalized + "●"
            print(f"   Step {t['step']}: {bar} {t['tokens']:,}")


if __name__ == "__main__":
    run_token_comparison()
