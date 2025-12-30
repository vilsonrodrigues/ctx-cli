"""
Auto-note Policies Demo: Automatic context management based on rules.

This demo shows how policies can automatically trigger notes:
1. MaxMessagesPolicy - Take note when message count exceeds threshold
2. MaxTokensPolicy - Take note when token count exceeds threshold
3. InactivityPolicy - Take note after N messages without manual note

Policies help when agents forget to take notes or context grows too large.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from policies import PolicyEngine, MaxMessagesPolicy, MaxTokensPolicy, InactivityPolicy, PolicyAction
from tokens import TokenTracker

SYSTEM_PROMPT = """You are a helpful assistant working on a task.

You have ctx_cli for context management, but DON'T WORRY about taking notes -
the system will auto-save based on policies when needed.

Just focus on the task at hand. If you want to manually save important
milestones, you can, but it's not required.

Available commands: scope, goto, note, scopes, notes"""


def run_policies_demo():
    """Demonstrate auto-note policies."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tracker = TokenTracker(model="gpt-4.1-mini")
    tools = [CTX_CLI_TOOL]

    # Configure policies with lower thresholds for demo
    policies = PolicyEngine([
        MaxMessagesPolicy(max_messages=6, warn_at=4),
        MaxTokensPolicy(max_tokens=2000, warn_at=1500, token_counter=tracker.count),
        InactivityPolicy(max_messages_since_commit=4),
    ])

    auto_notes = []
    policy_triggers = []

    def check_and_apply_policies() -> str | None:
        """Check policies and auto-note if needed."""
        results = policies.evaluate(store)

        for result in results:
            if result.triggered:
                if result.action == PolicyAction.FORCE_COMMIT:
                    # Auto-note
                    scope = store.branches[store.current_branch]
                    note_msg = result.auto_commit_message or f"Auto-note: {len(scope.messages)} messages"
                    note_result, event = store.commit(note_msg)
                    auto_notes.append({
                        "message": note_msg,
                        "messages_count": len(scope.messages),
                    })
                    policy_triggers.append("force_note")
                    return f"[AUTO-NOTE] {note_result}"

                elif result.action == PolicyAction.SUGGEST_COMMIT:
                    policy_triggers.append("suggest")
                    return f"[POLICY] {result.message}"

                elif result.action == PolicyAction.WARN:
                    return f"[WARNING] {result.message}"

        return None

    def chat(user_message: str, label: str = "") -> str:
        if label:
            print(f"\n{'─' * 50}")
            print(f"  {label}")
            print(f"{'─' * 50}")

        store.add_message(Message(role="user", content=user_message))

        # Check policies after user message
        policy_result = check_and_apply_policies()
        if policy_result:
            print(f"  🔔 {policy_result}")

        for _ in range(8):
            context = store.get_context(SYSTEM_PROMPT)
            current_tokens = tracker.count_messages(context)

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
                        print(f"  [ctx] {args['command'][:50]}")
                        tool_results.append((tool_call.id, result))

                for tool_id, result in tool_results:
                    store.add_message(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tool_id,
                    ))

                # Check policies after tool use
                policy_result = check_and_apply_policies()
                if policy_result:
                    print(f"  🔔 {policy_result}")
            else:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                ))

                # Check policies after assistant response
                policy_result = check_and_apply_policies()
                if policy_result:
                    print(f"  🔔 {policy_result}")

                response_short = (message.content or "")[:200]
                if len(message.content or "") > 200:
                    response_short += "..."
                print(f"\n  💬 {response_short}")
                print(f"  📊 Context: {current_tokens} tokens, {len(store.branches[store.current_branch].messages)} messages")
                return message.content or ""

        return "[Max rounds]"

    print("=" * 70)
    print("AUTO-NOTE POLICIES DEMO")
    print("=" * 70)
    print("\nPolicies configured:")
    print("  • MaxMessagesPolicy: warn at 4, suggest note at 6 messages")
    print("  • MaxTokensPolicy: warn at 1500, suggest note at 2000 tokens")
    print("  • InactivityPolicy: suggest note after 4 messages since last note")
    print("\nWatch how the system monitors and suggests context management...\n")

    # =========================================================================
    # Simulate a conversation without manual notes
    # =========================================================================
    chat("""
    Start a new scope for this task. I need help designing a REST API
    for a todo application. What endpoints should we have?
    """, label="TASK START: API Design")

    chat("""
    Good list! Now let's detail the GET /todos endpoint.
    What query parameters should it support for filtering and pagination?
    """, label="STEP 2: GET Details")

    chat("""
    What about POST /todos? What should the request body look like?
    Include validation requirements.
    """, label="STEP 3: POST Details")

    chat("""
    Now explain PUT /todos/:id for updating a todo.
    What's the difference between PUT and PATCH here?
    """, label="STEP 4: PUT vs PATCH")

    chat("""
    How should we handle DELETE /todos/:id?
    Should it be soft delete or hard delete?
    """, label="STEP 5: DELETE Strategy")

    chat("""
    Let's add authentication. What auth strategy should we use?
    JWT? Session-based? API keys?
    """, label="STEP 6: Authentication")

    chat("""
    Finally, how do we handle errors consistently?
    Give me an error response format.
    """, label="STEP 7: Error Handling")

    chat("""
    Great session! Show me the status and log to see what happened.
    """, label="REVIEW: Check Results")

    # =========================================================================
    # Results
    # =========================================================================
    print("\n" + "=" * 70)
    print("POLICY MONITORING RESULTS")
    print("=" * 70)

    print("\n🔔 Policy Triggers:")
    if policy_triggers:
        from collections import Counter
        counts = Counter(policy_triggers)
        for trigger, count in counts.items():
            print(f"  {trigger}: {count} times")
    else:
        print("  (none)")

    print("\n💾 Auto-notes Made:")
    if auto_notes:
        for an in auto_notes:
            print(f"  • {an['message'][:50]}... ({an['messages_count']} msgs)")
    else:
        print("  (none - model took notes manually or policies just warned)")

    print("\n📋 Notes Log:")
    result, _ = execute_command(store, "notes")
    for line in result.split("\n"):
        if line.strip():
            print(f"  {line}")

    print("\n📊 Final Statistics:")
    total_notes = sum(len(s.commits) for s in store.branches.values())
    print(f"  Total notes: {total_notes}")
    print(f"  Auto-notes: {len(auto_notes)}")
    print(f"  Policy triggers: {len(policy_triggers)}")

    print("\n💡 Policy Value:")
    print("  Policies monitor context growth and prompt for notes.")
    print("  This prevents context overflow and lost reasoning.")


if __name__ == "__main__":
    run_policies_demo()
