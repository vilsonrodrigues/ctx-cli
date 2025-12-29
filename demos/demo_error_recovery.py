"""
Error Recovery Demo: Agent makes mistakes and uses reset to recover.

This demo simulates a scenario where:
1. Agent works on a problem, making commits
2. User identifies a wrong approach at some point
3. Agent uses reset to go back to a good state
4. Agent tries a different approach

Shows how reset enables recovery from wrong reasoning paths.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

SYSTEM_PROMPT = """You are a software engineer solving a design problem.

You have ctx_cli for context management. Important for error recovery:

## When you realize you made a wrong decision:
1. Use 'log' to see your commit history
2. Identify which commit was the last good state
3. Use 'reset <hash> --hard' to go back to that state
4. Try a different approach

## Recovery commands:
- log - See your commits and find the good one
- reset <hash> --hard - Go back to that state, discarding later work
- checkout -b new-approach -m "Trying different solution"

## Best practices:
- Commit after each decision so you have recovery points
- When resetting, explain what went wrong
- After reset, take a different path

Don't be afraid to reset - it's better than continuing down a wrong path."""


def run_error_recovery():
    """Demonstrate error recovery with reset."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    def chat(user_message: str, label: str = "", is_error: bool = False) -> str:
        prefix = "❌ ERROR IDENTIFIED" if is_error else ""
        if label:
            print(f"\n{'━' * 60}")
            print(f"  {prefix} {label}" if prefix else f"  {label}")
            print(f"{'━' * 60}")

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
                        cmd = args["command"]
                        if "reset" in cmd:
                            print(f"  ⏪ RESET: {cmd}")
                        elif "commit" in cmd:
                            print(f"  💾 {cmd[11:60]}...")
                        elif "log" in cmd:
                            print(f"  📜 Checking history...")
                        else:
                            print(f"  [ctx] {cmd[:50]}")
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
                response_short = (message.content or "")[:280]
                if len(message.content or "") > 280:
                    response_short += "..."
                print(f"\n  {response_short}")
                return message.content or ""

        return "[Max rounds]"

    print("=" * 70)
    print("ERROR RECOVERY DEMO: Using Reset to Fix Wrong Approaches")
    print("=" * 70)
    print("\nSimulating a design session where the agent takes a wrong turn...")
    print("Watch how reset enables recovery.\n")

    # =========================================================================
    # Phase 1: Start with good decisions
    # =========================================================================
    chat("""
    I need to design a notification system for a mobile app.
    Create a branch and let's start planning.
    What are the key components we need?
    """, label="STEP 1: Initial Planning")

    chat("""
    Good start. Now let's decide on the delivery mechanism.
    Consider: push notifications, in-app notifications, email.
    Commit your recommendation.
    """, label="STEP 2: Delivery Mechanism")

    chat("""
    For push notifications, let's decide on the provider.
    Options: Firebase Cloud Messaging, AWS SNS, OneSignal.
    Analyze and commit your choice.
    """, label="STEP 3: Provider Selection")

    # =========================================================================
    # Phase 2: Wrong path (agent doesn't know yet)
    # =========================================================================
    chat("""
    Now design the data model for storing notification preferences.
    Consider user preferences, device tokens, notification history.
    Commit your design.
    """, label="STEP 4: Data Model")

    chat("""
    Let's add scheduling for notifications.
    Design how we'll handle scheduled and recurring notifications.
    Commit the scheduling approach.
    """, label="STEP 5: Scheduling")

    # =========================================================================
    # Phase 3: User identifies the error
    # =========================================================================
    chat("""
    WAIT - I just realized we have a problem.

    Our infrastructure doesn't support Firebase - we're on a private cloud
    with no external service access. We need a fully self-hosted solution.

    This means your provider choice was wrong, and everything after
    (data model, scheduling) was based on that wrong assumption.

    Use 'log' to see your commits, then reset to BEFORE the provider choice.
    We need to start fresh from the delivery mechanism decision.
    """, label="Provider Choice Was Wrong", is_error=True)

    # =========================================================================
    # Phase 4: Recovery and new approach
    # =========================================================================
    chat("""
    Good reset. Now let's take a different approach.
    For a self-hosted solution, consider:
    - RabbitMQ + custom push service
    - Redis pub/sub
    - PostgreSQL LISTEN/NOTIFY

    Which works best for a private cloud? Commit your new choice.
    """, label="RECOVERY: Self-hosted Solution")

    chat("""
    Now redesign the data model for this self-hosted approach.
    It will be different from the Firebase-based design.
    Commit the new design.
    """, label="STEP 6: New Data Model")

    chat("""
    Great recovery! Tag this as our corrected design.
    Show me the final status and history.
    """, label="FINAL: Corrected Design")

    # =========================================================================
    # Results
    # =========================================================================
    print("\n" + "=" * 70)
    print("ERROR RECOVERY RESULTS")
    print("=" * 70)

    print("\n📜 Commit History (showing recovery):")
    result, _ = store.log(limit=15)
    for line in result.split("\n"):
        if line.strip():
            print(f"  {line}")

    print("\n⏪ Reset Events:")
    reset_events = [e for e in store.events if e.type == "reset"]
    if reset_events:
        for e in reset_events:
            target = e.payload.get("target_commit", "?")[:7]
            removed = e.payload.get("removed_commits", 0)
            print(f"  Reset to [{target}], removed {removed} commits")
            print(f"  Reason: Wrong provider assumption (Firebase unavailable)")
    else:
        print("  (no resets)")

    print("\n📊 Recovery Statistics:")
    total_commits = sum(len(b.commits) for b in store.branches.values())
    print(f"  Final commits: {total_commits}")
    print(f"  Resets performed: {len(reset_events)}")
    if reset_events:
        wasted = sum(e.payload.get("removed_commits", 0) for e in reset_events)
        print(f"  Commits discarded: {wasted}")
        print(f"  Work saved: {total_commits} commits (would have continued wrong path)")

    print("\n💡 Key Insight:")
    print("  Without reset, the agent would have continued building on")
    print("  a wrong assumption. Reset enables clean recovery.")


if __name__ == "__main__":
    run_error_recovery()
