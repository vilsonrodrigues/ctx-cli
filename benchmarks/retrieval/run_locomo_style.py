"""
LOCOMO-style benchmarks for ctx-cli.

Tests long-term conversational memory capabilities:
- Single-hop QA (factual recall)
- Multi-hop QA (reasoning across turns)
- Temporal QA (time-based reasoning)

Based on LOCOMO benchmark: https://arxiv.org/abs/2402.17753
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from tokens import TokenTracker


@dataclass
class LocomoResult:
    """Result of LOCOMO-style benchmark."""
    task_name: str
    approach: Literal["linear", "scope"]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # QA metrics
    single_hop_accuracy: float = 0.0
    multi_hop_accuracy: float = 0.0
    temporal_accuracy: float = 0.0
    overall_accuracy: float = 0.0

    # Token metrics
    total_input: int = 0
    total_output: int = 0
    peak_context: int = 0

    # Memory metrics
    notes_created: int = 0


# =============================================================================
# Simulated Long Conversation with QA
# =============================================================================

# Simulate a long conversation with facts that can be queried later
CONVERSATION_TURNS = [
    # Session 1: Personal info
    ("user", "Hi, I'm Alex. I just moved to Seattle last month from Boston."),
    ("assistant", "Welcome to Seattle, Alex! That's quite a move from Boston. How are you finding the Pacific Northwest so far?"),
    ("user", "It's great but rainy. I work as a software engineer at a startup called TechFlow."),
    ("assistant", "TechFlow sounds interesting! Seattle has a great tech scene. What kind of software do you work on?"),
    ("user", "We build project management tools. I lead the backend team - we're 5 engineers."),

    # Session 2: Hobbies
    ("user", "By the way, I started learning guitar last week. I bought a Fender acoustic."),
    ("assistant", "That's exciting! Learning an instrument is so rewarding. Do you have any musical background?"),
    ("user", "I played piano for 10 years as a kid, so reading music isn't new to me."),
    ("assistant", "That's a great foundation! Piano skills definitely transfer to understanding music theory."),

    # Session 3: Work update
    ("user", "Big news - we just raised Series A funding, $5 million!"),
    ("assistant", "Congratulations! That's a huge milestone for TechFlow. What are you planning to do with the funding?"),
    ("user", "We're hiring 10 more engineers and expanding to mobile."),

    # Session 4: Personal update
    ("user", "I adopted a dog last weekend. A golden retriever named Max."),
    ("assistant", "How wonderful! Golden retrievers are such friendly dogs. How's Max adjusting to the new home?"),
    ("user", "He's great, already learned to sit and fetch. He's 2 years old."),
]

# QA pairs to test memory
QA_PAIRS = [
    # Single-hop (direct fact recall)
    {
        "type": "single_hop",
        "question": "Where did Alex move from?",
        "answer": "Boston",
        "evidence_turns": [0],
    },
    {
        "type": "single_hop",
        "question": "What company does Alex work for?",
        "answer": "TechFlow",
        "evidence_turns": [2],
    },
    {
        "type": "single_hop",
        "question": "What instrument is Alex learning?",
        "answer": "guitar",
        "evidence_turns": [5],
    },

    # Multi-hop (requires connecting multiple facts)
    {
        "type": "multi_hop",
        "question": "What is Alex's role at TechFlow and how many people are on the team?",
        "answer": "leads the backend team with 5 engineers",
        "evidence_turns": [4],
    },
    {
        "type": "multi_hop",
        "question": "What is Alex's musical background before guitar?",
        "answer": "played piano for 10 years as a kid",
        "evidence_turns": [5, 7],
    },

    # Temporal (requires understanding time/sequence)
    {
        "type": "temporal",
        "question": "What happened first - Alex getting the dog or the Series A funding?",
        "answer": "Series A funding",
        "evidence_turns": [10, 13],
    },
    {
        "type": "temporal",
        "question": "How long has Alex been in Seattle?",
        "answer": "about a month",
        "evidence_turns": [0],
    },
]


def run_qa_evaluation(
    client: OpenAI,
    tracker: TokenTracker,
    conversation: list[tuple[str, str]],
    qa_pairs: list[dict],
    use_scope: bool,
    model: str = "gpt-4.1-mini",
) -> LocomoResult:
    """Run QA evaluation on a conversation."""
    approach = "scope" if use_scope else "linear"
    result = LocomoResult(task_name="locomo_style", approach=approach)

    if use_scope:
        store = ContextStore()
        tools = [CTX_CLI_TOOL]

        system_prompt = """You are a helpful assistant with access to ctx_cli for memory management.

As you have the conversation, use 'note -m "..."' to save important facts about the user.
This will help you recall information accurately later.

Commands:
- note -m "fact" - Save an important fact
- notes - Review saved notes"""

        # Build conversation with note-taking
        for role, content in conversation:
            store.add_message(Message(role=role, content=content))

            if role == "user":
                # Let model potentially take notes
                context = store.get_context(system_prompt)
                response = client.chat.completions.create(
                    model=model,
                    messages=context,
                    tools=tools,
                )
                msg = response.choices[0].message

                if response.usage:
                    result.total_input += response.usage.prompt_tokens
                    result.total_output += response.usage.completion_tokens
                    result.peak_context = max(result.peak_context, response.usage.prompt_tokens)

                if msg.tool_calls:
                    store.add_message(Message(
                        role="assistant",
                        content=msg.content or "",
                        tool_calls=[tc.model_dump() for tc in msg.tool_calls]
                    ))
                    for tc in msg.tool_calls:
                        if tc.function.name == "ctx_cli":
                            args = json.loads(tc.function.arguments)
                            cmd = args.get("command", "")
                            cmd_result, _ = execute_command(store, cmd)
                            if "note" in cmd:
                                result.notes_created += 1
                            store.add_message(Message(
                                role="tool",
                                content=cmd_result,
                                tool_call_id=tc.id,
                            ))

        # Now ask QA questions
        correct = {"single_hop": 0, "multi_hop": 0, "temporal": 0}
        total = {"single_hop": 0, "multi_hop": 0, "temporal": 0}

        for qa in qa_pairs:
            q_type = qa["type"]
            total[q_type] += 1

            store.add_message(Message(role="user", content=qa["question"]))
            context = store.get_context(system_prompt)

            response = client.chat.completions.create(
                model=model,
                messages=context,
            )

            answer = response.choices[0].message.content or ""
            store.add_message(Message(role="assistant", content=answer))

            if response.usage:
                result.total_input += response.usage.prompt_tokens
                result.total_output += response.usage.completion_tokens

            # Check if answer contains expected info (simple check)
            if qa["answer"].lower() in answer.lower():
                correct[q_type] += 1

    else:
        # Linear approach - just build messages
        messages = [{"role": "system", "content": "You are a helpful assistant."}]

        for role, content in conversation:
            messages.append({"role": role, "content": content})

        # Ask QA questions
        correct = {"single_hop": 0, "multi_hop": 0, "temporal": 0}
        total = {"single_hop": 0, "multi_hop": 0, "temporal": 0}

        for qa in qa_pairs:
            q_type = qa["type"]
            total[q_type] += 1

            messages.append({"role": "user", "content": qa["question"]})

            response = client.chat.completions.create(
                model=model,
                messages=messages,
            )

            answer = response.choices[0].message.content or ""
            messages.append({"role": "assistant", "content": answer})

            if response.usage:
                result.total_input += response.usage.prompt_tokens
                result.total_output += response.usage.completion_tokens
                result.peak_context = max(result.peak_context, response.usage.prompt_tokens)

            if qa["answer"].lower() in answer.lower():
                correct[q_type] += 1

    # Calculate accuracies
    result.single_hop_accuracy = correct["single_hop"] / total["single_hop"] if total["single_hop"] > 0 else 0
    result.multi_hop_accuracy = correct["multi_hop"] / total["multi_hop"] if total["multi_hop"] > 0 else 0
    result.temporal_accuracy = correct["temporal"] / total["temporal"] if total["temporal"] > 0 else 0

    total_correct = sum(correct.values())
    total_questions = sum(total.values())
    result.overall_accuracy = total_correct / total_questions if total_questions > 0 else 0

    return result


def main():
    """Run LOCOMO-style benchmarks."""
    print("=" * 60)
    print("LOCOMO-Style Memory Benchmark")
    print("=" * 60)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY environment variable")
        return

    client = OpenAI()
    tracker = TokenTracker(model="gpt-4.1-mini")

    print("\n[1/2] Running LINEAR approach...")
    linear_result = run_qa_evaluation(
        client, tracker, CONVERSATION_TURNS, QA_PAIRS, use_scope=False
    )
    print(f"  Overall accuracy: {linear_result.overall_accuracy:.1%}")

    print("\n[2/2] Running SCOPE approach...")
    scope_result = run_qa_evaluation(
        client, tracker, CONVERSATION_TURNS, QA_PAIRS, use_scope=True
    )
    print(f"  Overall accuracy: {scope_result.overall_accuracy:.1%}")
    print(f"  Notes created: {scope_result.notes_created}")

    # Print comparison
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    print(f"\n{'Metric':<25} {'Linear':>12} {'Scope':>12}")
    print("-" * 50)
    print(f"{'Single-hop accuracy':<25} {linear_result.single_hop_accuracy:>11.1%} {scope_result.single_hop_accuracy:>11.1%}")
    print(f"{'Multi-hop accuracy':<25} {linear_result.multi_hop_accuracy:>11.1%} {scope_result.multi_hop_accuracy:>11.1%}")
    print(f"{'Temporal accuracy':<25} {linear_result.temporal_accuracy:>11.1%} {scope_result.temporal_accuracy:>11.1%}")
    print(f"{'Overall accuracy':<25} {linear_result.overall_accuracy:>11.1%} {scope_result.overall_accuracy:>11.1%}")
    print(f"{'Total input tokens':<25} {linear_result.total_input:>12,} {scope_result.total_input:>12,}")
    print(f"{'Peak context':<25} {linear_result.peak_context:>12,} {scope_result.peak_context:>12,}")

    # Save results
    os.makedirs("benchmarks/results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"benchmarks/results/locomo_style_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump({
            "linear": asdict(linear_result),
            "scope": asdict(scope_result),
        }, f, indent=2)

    print(f"\nResults saved to: {filename}")


if __name__ == "__main__":
    main()
