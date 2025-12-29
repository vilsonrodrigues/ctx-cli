"""
Interactive Demo: Chat with an agent that manages its own context.

This demo provides a REPL where you can have a long conversation
with an agent that uses ctx_cli to manage its memory.
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

SYSTEM_PROMPT = """You are an expert software engineer assistant with Git-like context management.

You have access to ctx_cli for managing your working memory and episodic memory.
USE IT PROACTIVELY - don't wait for the context to overflow.

## When to use ctx_cli:

1. **commit** - After completing any subtask or making a decision
   Example: commit -m "Decided to use Redis for caching due to X, Y, Z"

2. **checkout -b** - When starting a new distinct task or exploration
   Example: checkout -b investigate-auth -m "Going to analyze authentication options"

3. **tag** - After user approves something or you reach a stable state
   Example: tag v1-approved -m "User confirmed the database schema"

4. **stash** - When user interrupts with unrelated question
   Example: stash push -m "Was implementing login flow"

5. **merge** - When returning to main after completing a feature branch

6. **bisect** - When debugging why your reasoning went wrong

## Your behavior:
- Be concise but thorough
- Commit your reasoning frequently
- Create branches for distinct tasks
- Tag important milestones
- Use stash when interrupted

Current token budget awareness is crucial. Commit before context gets too large."""


def run_interactive():
    """Run interactive chat session."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY environment variable")
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tracker = TokenTracker(model="gpt-4.1-mini")
    tools = [CTX_CLI_TOOL]

    print("=" * 60)
    print("Interactive Context-Managed Agent")
    print("=" * 60)
    print("\nCommands:")
    print("  /status  - Show context status")
    print("  /log     - Show commit history")
    print("  /branch  - Show branches")
    print("  /tokens  - Show token usage")
    print("  /events  - Show recent events")
    print("  /save    - Save state to file")
    print("  /quit    - Exit")
    print("\n" + "=" * 60 + "\n")

    def process_message(user_input: str) -> str:
        """Process user message and get response."""
        store.add_message(Message(role="user", content=user_input))

        max_rounds = 10
        for round_num in range(max_rounds):
            context = store.get_context(SYSTEM_PROMPT)
            tokens = tracker.count_messages(context)

            # Warn if approaching limit
            if tokens > 50000:
                print(f"  [!] Context at {tokens:,} tokens - consider committing")

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
                        result, event = execute_command(store, args["command"])
                        print(f"  [ctx_cli] {args['command']}")
                        print(f"  [result] {result[:100]}..." if len(result) > 100 else f"  [result] {result}")
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

        return "[Max tool rounds reached]"

    # Main loop
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith("/"):
            cmd = user_input.lower()

            if cmd == "/quit":
                print("Goodbye!")
                break

            elif cmd == "/status":
                result, _ = store.status()
                print(f"\n{result}")

            elif cmd == "/log":
                result, _ = store.log()
                print(f"\n{result}")

            elif cmd == "/branch":
                result, _ = store.branch()
                print(f"\n{result}")

            elif cmd == "/tokens":
                context = store.get_context(SYSTEM_PROMPT)
                tokens = tracker.count_messages(context)
                print(f"\nEstimated tokens: {tokens:,}")
                print(f"Context limit: {tracker.context_limit:,}")
                print(f"Usage: {(tokens/tracker.context_limit)*100:.1f}%")

            elif cmd == "/events":
                print("\nRecent events:")
                for e in store.events[-10:]:
                    print(f"  [{e.type}] {e.branch}: {list(e.payload.values())[:2]}")

            elif cmd == "/save":
                path = "/tmp/ctx_interactive_state.json"
                store.save(path)
                print(f"\nState saved to {path}")

            else:
                print(f"Unknown command: {cmd}")

            continue

        # Process regular message
        print("\nAssistant: ", end="", flush=True)
        response = process_message(user_input)
        print(response)


if __name__ == "__main__":
    run_interactive()
