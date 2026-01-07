"""
Quick test demo: Verify ECM prompt adherence.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL
from ctx_store import ContextStore, Message
from prompts import SYSTEM_PROMPT_ECM

SYSTEM_PROMPT = SYSTEM_PROMPT_ECM


def run_quick_test():
    """Quick test of ECM workflow."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    command_log = []  # Track command sequence

    def chat(user_message: str, label: str = "") -> str:
        if label:
            print(f"\n{'━' * 60}")
            print(f"  {label}")
            print(f"{'━' * 60}")

        store.add_message(Message(role="user", content=user_message))

        for iteration in range(8):  # Reduced iterations
            context = store.get_context(SYSTEM_PROMPT)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=context,
                tools=tools,
            )

            message = response.choices[0].message

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "ctx_cli":
                        args = json.loads(tool_call.function.arguments)
                        cmd = args["command"]

                        # Log command
                        command_log.append(cmd)

                        # Execute
                        result = store.execute_tool_call(
                            tool_call_id=tool_call.id,
                            command=cmd,
                            assistant_content=message.content or ""
                        )

                        # Print
                        if cmd.startswith("scope "):
                            print(f"  → SCOPE: {cmd[6:40]}")
                        elif cmd.startswith("return "):
                            print(f"  → RETURN")
                        elif cmd == "status":
                            print(f"  → STATUS ✓")
                        elif cmd.startswith("notes"):
                            print(f"  → NOTES: {cmd}")
                        elif cmd.startswith("note "):
                            print(f"  → NOTE")
            else:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                ))
                print(f"  → Response: {(message.content or '')[:60]}...")
                return message.content or ""

        return "[Max rounds]"

    print("=" * 70)
    print("QUICK ECM TEST")
    print("=" * 70)

    # Test 1: Simpler scope workflow
    chat("""
    Task: Create a user authentication design.

    Workflow:
    1. Create scope 'auth/design'
    2. Call status to see context
    3. Take a note about the approach
    4. Return to main

    Keep it simple and concise.
    """, label="TEST: Basic scope workflow")

    # Analyze command sequence
    print("\n" + "=" * 70)
    print("COMMAND SEQUENCE ANALYSIS")
    print("=" * 70)

    scope_entries = []
    for i, cmd in enumerate(command_log):
        if cmd.startswith("scope "):
            scope_entries.append(i)
            # Check if status follows
            if i + 1 < len(command_log):
                next_cmd = command_log[i + 1]
                if next_cmd == "status":
                    print(f"✓ Scope {len(scope_entries)}: status called immediately")
                else:
                    print(f"✗ Scope {len(scope_entries)}: status NOT called (next was: {next_cmd[:30]})")

            # Check if notes was called before return
            found_notes = False
            found_return = False
            for j in range(i + 1, min(i + 10, len(command_log))):
                if command_log[j].startswith("notes"):
                    found_notes = True
                if command_log[j].startswith("return"):
                    found_return = True
                    break

            if found_return:
                if found_notes:
                    print(f"  ✓ notes consulted before return")
                else:
                    print(f"  ✗ notes NOT consulted before return")

    print(f"\nTotal scopes created: {len(scope_entries)}")
    print(f"Total commands: {len(command_log)}")

    # Show full command sequence
    print("\nFull command sequence:")
    for i, cmd in enumerate(command_log):
        cmd_short = cmd[:50] + "..." if len(cmd) > 50 else cmd
        print(f"  {i+1}. {cmd_short}")


if __name__ == "__main__":
    run_quick_test()
