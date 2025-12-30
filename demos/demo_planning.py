"""
Planning Agent Demo: Agent plans a project using scopes for alternatives.

This demo simulates a planning scenario where:
1. Agent receives a project to plan
2. Creates scopes for different approaches
3. Develops each approach in isolation
4. Returns to main with recommendation

Shows how scopes enable parallel exploration of alternatives.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

SYSTEM_PROMPT = """You are a technical architect planning a software project.

You have ctx_cli for exploring and comparing different approaches:

## Planning Strategy with Scopes:
1. Start on main with project requirements
2. Create separate scopes for each major alternative
3. Develop each approach in its scope with notes
4. Return to main with findings

## Example workflow:
- scope approach-monolith -m "Exploring monolith architecture"
- note -m "Monolith: [decision/tradeoff]"
- goto main -m "Monolith analysis complete: [summary]"
- scope approach-microservices -m "Exploring microservices"
- note -m "Microservices: [decision/tradeoff]"
- goto main -m "Microservices analysis complete: [summary]"

## Best practices:
- One scope per major alternative
- Take notes on pros, cons, and decisions in each scope
- Use descriptive scope names (approach-X, option-Y)
- Always return to main with summary

Think of scopes as parallel universes for exploring "what if" scenarios."""


def run_planning():
    """Demonstrate planning with scope alternatives."""
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
                        if cmd.startswith("scope "):
                            print(f"  🌿 SCOPE: {cmd}")
                        elif cmd.startswith("goto "):
                            print(f"  🔀 GOTO: {cmd}")
                        elif cmd.startswith("note "):
                            print(f"  📝 NOTE: {cmd[:50]}...")
                        elif cmd in ("scopes", "notes"):
                            print(f"  📋 {cmd.upper()}")
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
                response_short = (message.content or "")[:280]
                if len(message.content or "") > 280:
                    response_short += "..."
                print(f"\n  {response_short}")
                return message.content or ""

        return "[Max rounds]"

    print("=" * 70)
    print("PLANNING AGENT DEMO: Exploring Alternatives with Scopes")
    print("=" * 70)
    print("\nSimulating architecture planning with multiple approaches...")
    print("Watch how scopes enable parallel exploration.\n")

    # =========================================================================
    # Phase 1: Gather requirements
    # =========================================================================
    chat("""
    I need to design a real-time collaborative document editor (like Google Docs).

    Key requirements:
    - Multiple users editing simultaneously
    - Changes visible in real-time
    - Offline support
    - Version history
    - Scale to 100 concurrent editors per document

    First, take notes on the requirements, then we'll explore approaches.
    """, label="REQUIREMENTS: Collaborative Editor")

    # =========================================================================
    # Phase 2: Explore Approach A - OT (Operational Transformation)
    # =========================================================================
    chat("""
    Let's explore our first approach: Operational Transformation (OT).

    Create a scope for this approach and analyze:
    - How OT works
    - Pros and cons
    - Implementation complexity
    - Scalability considerations

    Take notes on your analysis.
    """, label="APPROACH A: Operational Transformation")

    chat("""
    For the OT approach, what tech stack would you recommend?
    Consider: server framework, real-time protocol, storage.
    Take notes on the tech stack for this approach.
    """, label="APPROACH A: Tech Stack")

    # =========================================================================
    # Phase 3: Explore Approach B - CRDT
    # =========================================================================
    chat("""
    Now let's explore the alternative: CRDTs (Conflict-free Replicated Data Types).

    Go back to main, then create a new scope (not from OT scope) and analyze:
    - How CRDTs work
    - Pros and cons vs OT
    - Implementation complexity
    - Offline support advantages

    Take notes on your analysis.
    """, label="APPROACH B: CRDTs")

    chat("""
    For the CRDT approach, what tech stack would you use?
    There are libraries like Yjs, Automerge - consider those.
    Take notes on the tech stack for this approach.
    """, label="APPROACH B: Tech Stack")

    # =========================================================================
    # Phase 4: Compare and decide
    # =========================================================================
    chat("""
    Now let's compare the two approaches.

    Review your notes from both scopes and give me your recommendation:
    which approach should we choose?
    """, label="COMPARISON: OT vs CRDT")

    chat("""
    Based on your analysis, let's go with your recommended approach.

    Return to main with your final recommendation and take a summary note.
    Show me the final state and your notes.
    """, label="DECISION: Final Architecture")

    # =========================================================================
    # Results
    # =========================================================================
    print("\n" + "=" * 70)
    print("PLANNING SESSION RESULTS")
    print("=" * 70)

    print("\n🌿 Scopes Explored:")
    result, _ = execute_command(store, "scopes")
    for line in result.split("\n"):
        if line.strip():
            scope_name = line.strip().replace("* ", "→ ").replace("  ", "  ")
            print(f"  {scope_name}")

    print("\n📋 Decision Trail (All Notes):")
    for scope_name, scope in store.branches.items():
        if scope.commits:
            print(f"\n  [{scope_name}]")
            for note in scope.commits:
                print(f"    [{note.hash[:7]}] {note.message[:50]}...")

    print("\n🔀 Scope Transitions:")
    goto_events = [e for e in store.events if e.type == "checkout"]
    if goto_events:
        for e in goto_events[:5]:  # Show first 5
            target = e.payload.get("branch", "?")
            print(f"  → {target}")
    else:
        print("  (no transitions)")

    print("\n🏷️  Architecture Decision:")
    if store.tags:
        for name, tag in store.tags.items():
            print(f"  {name}: {tag.description[:60]}...")
    else:
        print("  (no tags)")

    print("\n📊 Planning Statistics:")
    print(f"  Alternatives explored: {len(store.branches) - 1}")  # Exclude main
    print(f"  Total notes: {sum(len(s.commits) for s in store.branches.values())}")
    print(f"  Scope transitions: {len(goto_events)}")

    print("\n💡 Key Insight:")
    print("  Scopes allowed exploring OT and CRDT in isolation.")
    print("  Each approach was developed fully before comparison.")
    print("  Notes provided clear visibility into tradeoffs.")


if __name__ == "__main__":
    run_planning()
