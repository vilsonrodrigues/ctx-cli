"""
Debugging Demo: Agent uses bisect to find where reasoning went wrong.

This demo simulates a scenario where:
1. Agent works on a problem, taking notes along the way
2. At some point, the agent's reasoning goes wrong
3. Agent uses bisect to find where the error started
4. Agent resets and tries a different approach

Shows how bisect helps debug reasoning chains.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

SYSTEM_PROMPT = """You are a software engineer debugging a complex algorithm.

You have ctx_cli for context management. Key commands for debugging:

## For tracking your work:
- scope name -m "starting this area" - Create scope for new approach
- note -m "description" - Save your current reasoning state
- goto main -m "summary" - Return with findings

## For debugging reasoning:
- bisect start - Start finding where reasoning went wrong
- bisect good <note-id> - Mark a note where reasoning was correct
- bisect bad <note-id> - Mark a note where reasoning was wrong
- bisect reset - Cancel bisect session

## For recovery:
- rewind <note-id> --hard - Go back to a previous state
- notes - See your note history

IMPORTANT: Take notes frequently so you have good checkpoints for bisect.
Each note should capture your key decision or insight."""


def run_debugging():
    """Simulate debugging workflow with bisect."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    def chat(user_message: str, label: str = "") -> str:
        if label:
            print(f"\n{'━' * 60}")
            print(f"  {label}")
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
                        print(f"  [ctx] {args['command']}")
                        if "bisect" in args["command"].lower():
                            print(f"        → {result[:100]}...")
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
                response_text = (message.content or "")[:250]
                if len(message.content or "") > 250:
                    response_text += "..."
                print(f"\n  → {response_text}")
                return message.content or ""

        return "[Max rounds]"

    print("=" * 70)
    print("DEBUGGING DEMO: Using Bisect to Find Reasoning Errors")
    print("=" * 70)

    # =========================================================================
    # Phase 1: Building up notes (simulated algorithm work)
    # =========================================================================
    chat("""
    I need help implementing a rate limiter algorithm.

    Create a scope and let's work through this step by step.
    Start with the basic concept - what approach should we use?

    Take notes on your initial analysis.
    """, label="STEP 1: Initial Analysis")

    chat("""
    Good. Now let's choose between:
    - Token bucket
    - Sliding window
    - Fixed window

    Analyze each and take note of your recommendation.
    """, label="STEP 2: Algorithm Selection")

    chat("""
    Let's go with your recommendation.
    Now design the data structure we need.

    Take note of the data structure design.
    """, label="STEP 3: Data Structure Design")

    chat("""
    Now implement the core logic:
    - How do we check if request is allowed?
    - How do we update state after each request?

    Take note of the implementation approach.
    """, label="STEP 4: Core Logic")

    chat("""
    Finally, how do we handle edge cases:
    - What if clock skews?
    - What about distributed systems?

    Take notes on your edge case handling approach.
    """, label="STEP 5: Edge Cases")

    # =========================================================================
    # Phase 2: User finds problem
    # =========================================================================
    chat("""
    Wait, I think there's a problem. Your distributed system approach
    won't work because Redis isn't available in our environment.

    We need to use local storage only.

    Use bisect to find where you made the assumption about Redis.
    Check your note log first, then start bisecting.
    """, label="PROBLEM DETECTED: Wrong Assumption")

    # =========================================================================
    # Phase 3: Resolution
    # =========================================================================
    chat("""
    Based on the bisect, you found where the wrong assumption was made.

    Now reset to before that point and try a different approach.
    Use in-memory storage with periodic persistence instead.

    Take note of your new approach.
    """, label="RESOLUTION: New Approach")

    chat("""
    Good recovery. Tag this as the corrected implementation.
    Show me the final status.
    """, label="FINAL: Tag and Status")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("DEBUGGING SESSION SUMMARY")
    print("=" * 70)

    print("\n📜 Note History:")
    result, _ = execute_command(store, "notes")
    for line in result.split("\n"):
        if line.strip():
            print(f"  {line}")

    print("\n🔍 Bisect Events:")
    for e in store.events:
        if e.type == "bisect":
            action = e.payload.get("action", "?")
            print(f"  bisect {action}: {e.payload}")

    print("\n🔄 Reset Events:")
    for e in store.events:
        if e.type == "reset":
            print(f"  reset to {e.payload.get('target_commit', '?')[:7]}, removed {e.payload.get('removed_commits', 0)} notes")

    print(f"\nTotal operations: {len(store.events)}")


if __name__ == "__main__":
    run_debugging()
