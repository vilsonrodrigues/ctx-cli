"""
Multi-Project Demo: Agent handles multiple unrelated tasks.

This demo simulates a realistic scenario where:
1. User starts working on Project A
2. Gets interrupted to work on Project B
3. Returns to Project A
4. Handles quick questions in between

Shows how stash and branch isolation prevent context contamination.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

SYSTEM_PROMPT = """You are a senior software engineer helping with multiple projects.

You have ctx_cli for context management. This is CRITICAL for multi-project work:

## Project Isolation Strategy:
- Each project gets its own branch (e.g., project-api, project-frontend)
- Use stash when switching between unrelated tasks
- Commit frequently to preserve your reasoning
- Merge completed work to main

## When user switches topics:
1. Stash current work with descriptive message
2. Checkout or create appropriate branch
3. When returning, pop stash and resume

## Best Practices:
- Never mix project contexts - it causes confusion
- Commit before any context switch
- Tag important decisions for each project
- Use diff to compare approaches between branches

Be organized. Your context is your workspace - keep it clean."""


def run_multi_project():
    """Simulate multi-project workflow."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    def chat(user_message: str, label: str = "") -> str:
        if label:
            print(f"\n{'─' * 50}")
            print(f"  {label}")
            print(f"{'─' * 50}")

        store.add_message(Message(role="user", content=user_message))

        for _ in range(12):
            context = store.get_context(SYSTEM_PROMPT)

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
                        cmd_short = args["command"][:50] + "..." if len(args["command"]) > 50 else args["command"]
                        print(f"  [ctx] {cmd_short}")
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
                response_short = (message.content or "")[:200]
                if len(message.content or "") > 200:
                    response_short += "..."
                print(f"\n  → {response_short}")
                return message.content or ""

        return "[Max rounds]"

    print("=" * 70)
    print("MULTI-PROJECT DEMO: Handling Multiple Unrelated Tasks")
    print("=" * 70)

    # =========================================================================
    # Project A: E-commerce API
    # =========================================================================
    chat("""
    I'm working on an e-commerce API. Let's start with the product catalog.

    Create a branch for this project and help me design the Product model.
    Consider: name, price, description, category, inventory, images.
    """, label="PROJECT A: E-commerce API - Start")

    chat("""
    Good. Now add the Category model and create a relationship with Product.
    Commit your work before continuing.
    """, label="PROJECT A: Adding Category")

    # =========================================================================
    # Interruption: Project B
    # =========================================================================
    chat("""
    Hey, I need to switch to a different project urgently.

    This is for a blog platform - completely different from the e-commerce work.
    Help me design the Post and Comment models.

    Make sure to properly save your e-commerce work first!
    """, label="PROJECT B: Blog Platform - Urgent Switch")

    chat("""
    For the blog, add Author model with relationship to Post.
    Also add a Tag model for categorizing posts.
    Commit when done.
    """, label="PROJECT B: Expanding Blog Models")

    # =========================================================================
    # Quick question (no project context)
    # =========================================================================
    chat("""
    Quick unrelated question: what's the difference between belongsTo and hasOne
    in ORMs? Just a conceptual question, don't need code.
    """, label="QUICK QUESTION: ORM Concepts")

    # =========================================================================
    # Back to Project A
    # =========================================================================
    chat("""
    OK, back to the e-commerce project now.

    Resume where we left off. What was I working on?
    Continue with the next logical step.
    """, label="PROJECT A: Resuming E-commerce")

    chat("""
    Add an Order model that references Products.
    Include: customer info, items, total, status, timestamps.
    Tag this as v1 when done - it's our MVP models.
    """, label="PROJECT A: Order Model")

    # =========================================================================
    # Final overview
    # =========================================================================
    print("\n" + "=" * 70)
    print("FINAL STATE: Multi-Project Overview")
    print("=" * 70)

    print("\n📁 Branches:")
    result, _ = store.branch()
    for line in result.split("\n"):
        print(f"  {line}")

    print("\n🏷️  Tags:")
    if store.tags:
        for name, tag in store.tags.items():
            print(f"  {name}: {tag.description[:40]}... ({tag.branch})")
    else:
        print("  (no tags yet)")

    print("\n📊 Events by type:")
    event_counts = {}
    for e in store.events:
        event_counts[e.type] = event_counts.get(e.type, 0) + 1
    for event_type, count in sorted(event_counts.items()):
        print(f"  {event_type}: {count}")

    print("\n🔀 Branch transitions:")
    prev_branch = "main"
    for e in store.events:
        if e.type == "checkout":
            from_b = e.payload.get("from_branch", "?")
            print(f"  {from_b} → {e.branch}")

    print(f"\nTotal operations: {len(store.events)}")


if __name__ == "__main__":
    run_multi_project()
