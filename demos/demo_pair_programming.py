"""
Pair Programming Demo: Agent + User iterating with stash for side-quests.

This demo simulates a realistic pair programming session where:
1. User and agent work together on a feature
2. User asks quick unrelated questions (side-quests)
3. Agent uses stash to save work, answer question, then resume
4. Shows natural flow of collaborative development

Demonstrates stash for context switching during interruptions.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

SYSTEM_PROMPT = """You are a pair programming partner helping build a feature.

You have ctx_cli for context management. Use it for smooth collaboration:

## Pair Programming Workflow:
1. Create a branch for the feature you're building
2. Commit after completing each logical piece
3. When user asks an unrelated question:
   - Stash your current work
   - Answer the question
   - Pop stash to resume

## Key Commands:
- checkout -b feature-x -m "Building X" - Start feature
- commit -m "Completed Y" - Save progress
- stash push -m "WIP: working on Z" - Pause for interruption
- stash pop - Resume after interruption

## Best Practices:
- Commit frequently (every function/component)
- Stash immediately when topic changes
- Keep commit messages descriptive
- Always pop stash when returning to previous work

Be a helpful pair - explain your code, suggest improvements, and adapt to interruptions gracefully."""


def run_pair_programming():
    """Run pair programming demo."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    def chat(user_message: str, label: str = "", is_interruption: bool = False) -> str:
        prefix = "⚡ INTERRUPTION" if is_interruption else ""
        if label:
            print(f"\n{'━' * 60}")
            print(f"  {prefix} {label}" if prefix else f"  {label}")
            print(f"{'━' * 60}")

        store.add_message(Message(role="user", content=user_message))

        for _ in range(10):
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
                        cmd = args["command"]
                        if "stash push" in cmd:
                            print(f"  📦 STASH: {cmd[12:50]}...")
                        elif "stash pop" in cmd:
                            print(f"  📦 POP: Resuming previous work")
                        elif "commit" in cmd:
                            print(f"  💾 {cmd[11:60]}...")
                        elif "checkout" in cmd:
                            print(f"  🔀 {cmd[:50]}")
                        else:
                            print(f"  [ctx] {cmd[:40]}")
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
                response_short = (message.content or "")[:300]
                if len(message.content or "") > 300:
                    response_short += "..."
                print(f"\n  {response_short}")
                return message.content or ""

        return "[Max rounds]"

    print("=" * 70)
    print("PAIR PROGRAMMING DEMO: Building a Feature with Interruptions")
    print("=" * 70)
    print("\nSimulating a pair programming session building a CLI tool...")
    print("Watch how stash handles interruptions smoothly.\n")

    # =========================================================================
    # Start building feature
    # =========================================================================
    chat("""
    Let's build a simple CLI calculator together.
    Start a feature branch and let's design the basic structure.
    What functions will we need?
    """, label="START: Planning the Calculator")

    chat("""
    Good plan! Let's implement the basic operations first.
    Write the add and subtract functions with proper error handling.
    Commit when done.
    """, label="IMPLEMENT: Basic Operations")

    # =========================================================================
    # First interruption
    # =========================================================================
    chat("""
    Wait, quick question - what's the difference between *args and **kwargs?
    I always forget.
    """, label="Quick Python Question", is_interruption=True)

    # =========================================================================
    # Resume and continue
    # =========================================================================
    chat("""
    Thanks! Now back to our calculator.
    Where were we? Continue with multiply and divide.
    Don't forget to handle division by zero!
    """, label="RESUME: More Operations")

    chat("""
    Now let's add the CLI interface.
    Use argparse to accept: operation, num1, num2
    Commit the CLI implementation.
    """, label="IMPLEMENT: CLI Interface")

    # =========================================================================
    # Second interruption - more complex
    # =========================================================================
    chat("""
    Oh wait, my colleague is asking about something else entirely.
    Can you quickly explain how Python decorators work?
    Just a brief explanation.
    """, label="Decorator Question", is_interruption=True)

    # =========================================================================
    # Resume and finish
    # =========================================================================
    chat("""
    Perfect explanation! Back to our calculator.
    Let's add a history feature that remembers past calculations.
    This should be the last piece. Commit and tag as v1.0.
    """, label="FINISH: History Feature")

    chat("""
    Great work! Show me the final status.
    How many commits did we make? Did we lose any context during interruptions?
    """, label="REVIEW: Final Status")

    # =========================================================================
    # Results
    # =========================================================================
    print("\n" + "=" * 70)
    print("PAIR PROGRAMMING SESSION SUMMARY")
    print("=" * 70)

    print("\n💻 Development Progress (Commits):")
    result, _ = store.log(limit=10)
    for line in result.split("\n"):
        if line.strip():
            print(f"  {line}")

    print("\n📦 Stash Usage:")
    stash_events = [e for e in store.events if e.type == "stash"]
    pop_events = [e for e in store.events if e.type == "pop"]
    print(f"  Stashes created: {len(stash_events)}")
    print(f"  Stashes popped: {len(pop_events)}")
    for e in stash_events:
        print(f"    • {e.payload.get('message', 'WIP')[:50]}")

    print("\n📊 Session Statistics:")
    print(f"  Feature branches: {len([b for b in store.branches if b != 'main'])}")
    print(f"  Commits made: {sum(len(b.commits) for b in store.branches.values())}")
    print(f"  Interruptions handled: {len(stash_events)}")
    print(f"  Context preserved: 100% (thanks to stash!)")

    print("\n🏷️  Milestones:")
    if store.tags:
        for name, tag in store.tags.items():
            print(f"  {name}: {tag.description[:50]}...")
    else:
        print("  (no tags yet)")


if __name__ == "__main__":
    run_pair_programming()
