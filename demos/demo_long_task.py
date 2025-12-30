"""
Long Task Demo: Agent implements a complete feature with multiple phases.

This demo simulates a realistic long-running task where the agent:
1. Plans the implementation
2. Works through multiple subtasks
3. Handles interruptions
4. Uses commits and branches extensively
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

SYSTEM_PROMPT = """You are an expert software engineer implementing features.

You have ctx_cli for context management. USE IT EXTENSIVELY:

1. Create a scope for each major subtask: scope <name> -m "what I'll do"
2. Take notes after every significant decision: note -m "what I learned"
3. Return to main when done: goto main -m "summary of work"

Think step by step, but save your reasoning as notes to prevent context overflow.
Be thorough but efficient with your context usage."""


def run_long_task():
    """Simulate a long implementation task."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    def chat(user_message: str, show_response: bool = True) -> str:
        store.add_message(Message(role="user", content=user_message))

        for _ in range(15):
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
                        print(f"    [ctx] {args['command']}")
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
                if show_response:
                    print(f"\n  Assistant: {message.content[:300]}..." if len(message.content or "") > 300 else f"\n  Assistant: {message.content}")
                return message.content or ""

        return "[Max rounds]"

    # =========================================================================
    # Scenario: Implement a complete authentication system
    # =========================================================================

    print("=" * 70)
    print("LONG TASK DEMO: Implementing Authentication System")
    print("=" * 70)

    # Phase 1: Initial Planning
    print("\n" + "=" * 70)
    print("PHASE 1: Initial Planning")
    print("=" * 70)

    chat("""
    I need you to implement a complete authentication system for a Python web app.

    Requirements:
    - User registration with email verification
    - Login with JWT tokens
    - Password reset flow
    - Role-based access control (admin, user, guest)
    - Rate limiting on auth endpoints

    Start by creating a planning branch and outlining the implementation steps.
    Then commit your plan before starting implementation.
    """)

    # Phase 2: Database Models
    print("\n" + "=" * 70)
    print("PHASE 2: Database Models")
    print("=" * 70)

    chat("""
    Good plan. Now let's implement the database models.

    Create a new branch for database work.
    Define the User model with all necessary fields.
    Also define Role and Permission models.

    Commit each model as you complete it.
    """)

    # Phase 3: Interruption!
    print("\n" + "=" * 70)
    print("PHASE 3: Interruption - Quick Question")
    print("=" * 70)

    chat("""
    Wait, quick question before you continue:
    What's the difference between JWT and session-based auth?
    Which did you choose and why?

    (Stash your current work first if needed)
    """)

    # Phase 4: Resume and Continue
    print("\n" + "=" * 70)
    print("PHASE 4: Resume Implementation")
    print("=" * 70)

    chat("""
    Thanks for the explanation. Now continue with the authentication logic.

    Pop your stash if you stashed, and continue implementing.
    Create the JWT token generation and validation functions.
    Commit when done.
    """)

    # Phase 5: User Approval
    print("\n" + "=" * 70)
    print("PHASE 5: Approval Checkpoint")
    print("=" * 70)

    chat("""
    I approve of the approach so far.

    Tag this as our approved baseline.
    Then merge your completed work back to main.
    Show me the final status.
    """)

    # Final Status
    print("\n" + "=" * 70)
    print("FINAL STATUS")
    print("=" * 70)

    print("\nBranches:")
    result, _ = store.branch()
    print(result)

    print("\nTags:")
    for name, tag in store.tags.items():
        print(f"  {name}: {tag.description} (on {tag.branch})")

    print("\nAll Events:")
    for e in store.events:
        print(f"  [{e.type:12}] {e.branch}: {str(e.payload)[:60]}...")

    print("\nTotal context operations:", len(store.events))


if __name__ == "__main__":
    run_long_task()
