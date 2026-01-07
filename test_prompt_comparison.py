"""
Comparison test: Original prompt vs Refined prompt.
Shows improvement in ECM adherence.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ctx_cli import CTX_CLI_TOOL
from ctx_store import ContextStore, Message


def test_prompt(prompt_module, label):
    """Test a prompt and return metrics."""
    print(f"\n{'='*70}")
    print(f"  TESTING: {label}")
    print(f"{'='*70}")

    # Import the prompt
    if prompt_module == "original":
        from prompts_backup import SYSTEM_PROMPT_ECM
    else:
        from prompts import SYSTEM_PROMPT_ECM

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return None

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    command_log = []
    status_compliance = {"pass": 0, "fail": 0}
    notes_compliance = {"pass": 0, "fail": 0}

    def chat(user_message: str):
        store.add_message(Message(role="user", content=user_message))

        for _ in range(8):
            context = store.get_context(SYSTEM_PROMPT_ECM)

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
                        command_log.append(cmd)

                        result = store.execute_tool_call(
                            tool_call_id=tool_call.id,
                            command=cmd,
                            assistant_content=message.content or ""
                        )
            else:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                ))
                return message.content or ""

        return "[Max rounds]"

    # Run test
    chat("""
    Task: Analyze two approaches (A and B) for solving problem X.

    Requirements:
    - Scalability
    - Performance
    - Maintainability

    Create scopes to analyze each approach, then recommend one.
    """)

    # Analyze compliance
    for i, cmd in enumerate(command_log):
        if cmd.startswith("scope "):
            # Check status compliance
            if i + 1 < len(command_log) and command_log[i + 1] == "status":
                status_compliance["pass"] += 1
            else:
                status_compliance["fail"] += 1

            # Check notes compliance
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
                    notes_compliance["pass"] += 1
                else:
                    notes_compliance["fail"] += 1

    # Calculate metrics
    total_scopes = status_compliance["pass"] + status_compliance["fail"]
    status_rate = (status_compliance["pass"] / total_scopes * 100) if total_scopes > 0 else 0
    notes_rate = (notes_compliance["pass"] / total_scopes * 100) if total_scopes > 0 else 0
    total_notes = sum(len(b.notes) for b in store.branches.values())

    print(f"\nMetrics:")
    print(f"  Total scopes: {total_scopes}")
    print(f"  Total commands: {len(command_log)}")
    print(f"  Total notes saved: {total_notes}")
    print(f"  Status compliance: {status_rate:.0f}% ({status_compliance['pass']}/{total_scopes})")
    print(f"  Notes consultation: {notes_rate:.0f}% ({notes_compliance['pass']}/{total_scopes})")

    return {
        "scopes": total_scopes,
        "commands": len(command_log),
        "notes": total_notes,
        "status_rate": status_rate,
        "notes_rate": notes_rate,
    }


if __name__ == "__main__":
    print("\n" + "="*70)
    print("  ECM PROMPT COMPARISON TEST")
    print("="*70)

    # Test original
    print("\n[1/2] Testing ORIGINAL prompt...")
    original_metrics = test_prompt("original", "Original Prompt (prompts_backup.py)")

    # Test refined
    print("\n[2/2] Testing REFINED prompt...")
    refined_metrics = test_prompt("refined", "Refined Prompt (prompts.py)")

    # Compare
    print("\n" + "="*70)
    print("  COMPARISON RESULTS")
    print("="*70)

    if original_metrics and refined_metrics:
        print(f"\nStatus Compliance:")
        print(f"  Original: {original_metrics['status_rate']:.0f}%")
        print(f"  Refined:  {refined_metrics['status_rate']:.0f}%")
        improvement = refined_metrics['status_rate'] - original_metrics['status_rate']
        print(f"  Improvement: {improvement:+.0f}%")

        print(f"\nNotes Consultation:")
        print(f"  Original: {original_metrics['notes_rate']:.0f}%")
        print(f"  Refined:  {refined_metrics['notes_rate']:.0f}%")
        improvement = refined_metrics['notes_rate'] - original_metrics['notes_rate']
        print(f"  Improvement: {improvement:+.0f}%")

        print(f"\nNotes Persistence:")
        print(f"  Original: {original_metrics['notes']} notes saved")
        print(f"  Refined:  {refined_metrics['notes']} notes saved")

        print("\n" + "="*70)
        if refined_metrics['status_rate'] == 100 and refined_metrics['notes_rate'] == 100:
            print("  ✓ REFINED PROMPT: 100% COMPLIANCE")
        else:
            print("  ⚠ REFINED PROMPT: Needs further iteration")
        print("="*70)
