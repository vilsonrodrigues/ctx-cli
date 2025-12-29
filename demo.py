"""
Demo: Git-like Context Management for LLM Agents

This demo simulates a long-running agent task to show how ctx_cli
helps manage context without overflow.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from openai import OpenAI

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message


DEMO_SYSTEM_PROMPT = """You are an AI assistant helping with a complex software project.
You have access to ctx_cli for managing your context.

IMPORTANT: Use ctx_cli proactively:
1. When starting a new distinct task, create a branch: checkout -b <name> -m "note"
2. When completing a subtask, commit: commit -m "what you learned/decided"
3. When the user approves something, tag it: tag <name> -m "description"

This keeps your context clean and your reasoning organized."""


def run_demo():
    """Run a simulated long-running agent session."""

    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("=" * 60)
        print("DEMO MODE: Simulating without API calls")
        print("Set OPENAI_API_KEY to run with real model")
        print("=" * 60)
        run_simulated_demo()
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()

    tools = [CTX_CLI_TOOL]

    def chat(user_message: str, max_tool_rounds: int = 5) -> str:
        """Simple chat function with tool handling."""
        store.add_message(Message(role="user", content=user_message))

        for _ in range(max_tool_rounds):
            context = store.get_context(DEMO_SYSTEM_PROMPT)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
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
                        result, event = execute_command(store, args["command"])
                        print(f"  [ctx_cli] {args['command']}")
                        print(f"  [result] {result}")

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
                return message.content or ""

        return "Max rounds reached"

    # Simulate a multi-phase project
    print("\n" + "=" * 60)
    print("Phase 1: Initial Analysis")
    print("=" * 60)

    response = chat("""
    I need you to help me build a REST API for a todo app.
    Let's start by planning the architecture.
    Please create a branch for this planning phase.
    """)
    print(f"\nAssistant: {response}")

    print("\n" + "=" * 60)
    print("Phase 2: Design Decisions")
    print("=" * 60)

    response = chat("""
    Good. Let's decide on the tech stack:
    - Python with FastAPI
    - SQLite for the database
    - Pydantic for validation

    Please commit this decision and then start working on the data models.
    Create a new branch for the implementation.
    """)
    print(f"\nAssistant: {response}")

    print("\n" + "=" * 60)
    print("Phase 3: Implementation")
    print("=" * 60)

    response = chat("""
    Perfect. I approve this architecture.
    Please tag this as our approved baseline.
    Then continue with defining the Todo model.
    """)
    print(f"\nAssistant: {response}")

    print("\n" + "=" * 60)
    print("Context Status")
    print("=" * 60)

    result, _ = store.status()
    print(result)

    print("\n" + "=" * 60)
    print("Event Log")
    print("=" * 60)

    for event in store.events:
        print(f"  [{event.type}] {event.branch}: {event.payload}")


def run_simulated_demo():
    """Run a simulated demo without API calls."""

    store = ContextStore()

    print("\n--- Simulating agent workflow ---\n")

    # Simulate the agent's actions
    steps = [
        ("User asks for help with REST API", None),
        ("Agent creates planning branch",
         'checkout -b planning -m "Starting architecture planning for REST API"'),
        ("Agent analyzes requirements", None),
        ("Agent commits analysis",
         'commit -m "Analyzed requirements: need CRUD endpoints for todos, auth optional"'),
        ("User approves tech stack", None),
        ("Agent tags the decision",
         'tag v1-stack-approved -m "FastAPI + SQLite + Pydantic approved by user"'),
        ("Agent creates implementation branch",
         'checkout -b implement-models -m "Going to implement Todo data model"'),
        ("Agent works on implementation", None),
        ("Agent commits progress",
         'commit -m "Created Todo model with id, title, completed, created_at fields"'),
        ("User interrupts with different question", None),
        ("Agent stashes current work",
         'stash push -m "Interrupted while implementing model validation"'),
        ("Agent answers user question", None),
        ("Agent pops stash to resume",
         'stash pop'),
        ("Agent checks status",
         'status'),
        ("Agent views history",
         'history'),
    ]

    for description, command in steps:
        print(f"📌 {description}")

        if command:
            result, event = execute_command(store, command)
            print(f"   $ ctx_cli {command}")
            print(f"   → {result}")

            if event:
                print(f"   [EVENT] {event.type}")
        else:
            # Simulate adding some messages for non-command steps
            store.add_message(Message(role="user", content=f"Simulated: {description}"))
            store.add_message(Message(role="assistant", content=f"Acknowledged: {description}"))

        print()

    print("\n" + "=" * 60)
    print("Final State")
    print("=" * 60)

    # Show branches
    result, _ = store.branch()
    print("\nBranches:")
    print(result)

    # Show all events
    print("\nAll Events:")
    for event in store.events:
        print(f"  [{event.timestamp[:19]}] {event.type} on {event.branch}")
        for key, value in event.payload.items():
            print(f"    {key}: {value}")

    # Save state
    store.save("/tmp/ctx_demo_state.json")
    print(f"\n💾 State saved to /tmp/ctx_demo_state.json")


if __name__ == "__main__":
    run_demo()
