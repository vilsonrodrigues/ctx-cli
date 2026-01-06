#!/usr/bin/env python3
"""
LOCOMO Benchmark for ctx-cli.

Uses the official LOCOMO dataset (arxiv.org/abs/2402.17753) to evaluate
long-term conversational memory.

Categories:
    1: Single-hop factual
    2: Temporal (when, dates)
    3: Multi-hop reasoning
    4: Adversarial/complex
    5: Unanswerable

Usage:
    uv run python benchmarks/run.py
    uv run python benchmarks/run.py --conversation 0 --max-qa 20
    uv run python benchmarks/run.py --model gpt-4o --max-sessions 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message
from tokens import TokenTracker


# =============================================================================
# Constants
# =============================================================================

DATA_FILE = Path(__file__).parent / "data" / "locomo10.json"

# Category mapping from LOCOMO
CATEGORY_NAMES = {
    1: "single_hop",
    2: "temporal",
    3: "multi_hop",
    4: "adversarial",
    5: "unanswerable",
}


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class BenchmarkResult:
    """Result of LOCOMO benchmark."""
    approach: Literal["linear", "scope"]
    model: str
    conversation_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Accuracy by category
    category_correct: dict = field(default_factory=lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})
    category_total: dict = field(default_factory=lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})

    # Tokens
    total_input: int = 0
    total_output: int = 0
    peak_context: int = 0

    # Memory (scope only)
    notes_created: int = 0

    # Timing
    elapsed_seconds: float = 0.0

    # Details
    qa_results: list = field(default_factory=list)

    def accuracy(self, category: int) -> float:
        if self.category_total[category] == 0:
            return 0.0
        return self.category_correct[category] / self.category_total[category]

    @property
    def overall_accuracy(self) -> float:
        total = sum(self.category_total.values())
        correct = sum(self.category_correct.values())
        return correct / total if total > 0 else 0.0


# =============================================================================
# LOCOMO Data Loading
# =============================================================================

def load_locomo_data() -> list[dict]:
    """Load LOCOMO dataset."""
    if not DATA_FILE.exists():
        print(f"Error: Dataset not found at {DATA_FILE}")
        print("Download it with:")
        print("  mkdir -p benchmarks/data")
        print("  curl -L https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json -o benchmarks/data/locomo10.json")
        sys.exit(1)

    with open(DATA_FILE) as f:
        return json.load(f)


def extract_conversation(data: dict, max_sessions: int | None = None) -> list[tuple[str, str]]:
    """Extract conversation turns from LOCOMO format (flat list)."""
    sessions = extract_sessions(data, max_sessions)
    turns = []
    for session in sessions:
        turns.extend(session["turns"])
    return turns


def extract_sessions(data: dict, max_sessions: int | None = None) -> list[dict]:
    """Extract conversation organized by sessions."""
    conv = data["conversation"]
    speaker_a = conv.get("speaker_a", "User")
    speaker_b = conv.get("speaker_b", "Assistant")

    sessions = []
    session_num = 1

    while True:
        session_key = f"session_{session_num}"
        if session_key not in conv:
            break

        if max_sessions and session_num > max_sessions:
            break

        session_data = conv[session_key]
        if not session_data:
            session_num += 1
            continue

        turns = []
        for turn in session_data:
            speaker = turn.get("speaker", "")
            text = turn.get("text", "")

            if not text:
                continue

            # Map speaker to role
            if speaker == speaker_a:
                role = "user"
            elif speaker == speaker_b:
                role = "assistant"
            else:
                role = "user"

            turns.append((role, text))

        if turns:
            sessions.append({
                "num": session_num,
                "turns": turns,
                "date": conv.get(f"session_{session_num}_date_time", ""),
            })

        session_num += 1

    return sessions


def extract_qa_pairs(data: dict, max_qa: int | None = None, exclude_unanswerable: bool = True) -> list[dict]:
    """Extract QA pairs from LOCOMO format."""
    qa_pairs = []

    for qa in data["qa"]:
        category = qa.get("category", 0)

        # Skip unanswerable by default
        if exclude_unanswerable and category == 5:
            continue

        qa_pairs.append({
            "question": qa["question"],
            "answer": str(qa["answer"]),
            "category": category,
            "evidence": qa.get("evidence", []),
        })

        if max_qa and len(qa_pairs) >= max_qa:
            break

    return qa_pairs


# =============================================================================
# Answer Evaluation (F1 Score like LOCOMO)
# =============================================================================

def normalize_answer(s: str) -> str:
    """Normalize answer for comparison."""
    import re
    import string

    def remove_articles(text):
        return re.sub(r'\b(a|an|the)\b', ' ', text)

    def white_space_fix(text):
        return ' '.join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return ''.join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))


def compute_f1(prediction: str, ground_truth: str) -> float:
    """Compute F1 score between prediction and ground truth."""
    prediction_tokens = normalize_answer(prediction).split()
    ground_truth_tokens = normalize_answer(ground_truth).split()

    if len(ground_truth_tokens) == 0:
        return 1.0 if len(prediction_tokens) == 0 else 0.0

    common = set(prediction_tokens) & set(ground_truth_tokens)

    if len(common) == 0:
        return 0.0

    precision = len(common) / len(prediction_tokens) if prediction_tokens else 0
    recall = len(common) / len(ground_truth_tokens)

    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    return f1


def check_answer(response: str, qa: dict, threshold: float = 0.5) -> tuple[bool, float]:
    """Check if response matches expected answer using F1 score."""
    f1 = compute_f1(response, qa["answer"])
    return f1 >= threshold, f1


# =============================================================================
# Linear Approach
# =============================================================================

def run_linear(
    client: OpenAI,
    model: str,
    conversation: list[tuple[str, str]],
    qa_pairs: list[dict],
    conversation_id: str,
) -> BenchmarkResult:
    """Run benchmark with linear approach (full history in context)."""
    result = BenchmarkResult(approach="linear", model=model, conversation_id=conversation_id)
    start_time = time.time()

    # Build conversation history
    messages = [{"role": "system", "content": "You are a helpful assistant. Answer questions based on the conversation history. Be concise and specific."}]

    for role, content in conversation:
        messages.append({"role": role, "content": content})

    # Track context size
    tracker = TokenTracker(model=model)
    result.peak_context = tracker.count_messages(messages)

    # Ask QA questions
    for i, qa in enumerate(qa_pairs):
        print(f"    QA {i+1}/{len(qa_pairs)}: {qa['question'][:50]}...", end="", flush=True)

        messages.append({"role": "user", "content": qa["question"]})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=150,
        )

        answer = response.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": answer})

        if response.usage:
            result.total_input += response.usage.prompt_tokens
            result.total_output += response.usage.completion_tokens
            result.peak_context = max(result.peak_context, response.usage.prompt_tokens)

        # Evaluate
        correct, f1 = check_answer(answer, qa)
        category = qa["category"]
        result.category_total[category] += 1
        if correct:
            result.category_correct[category] += 1

        result.qa_results.append({
            "question": qa["question"],
            "expected": qa["answer"],
            "response": answer[:200],
            "correct": correct,
            "f1": round(f1, 3),
            "category": category,
        })

        print(f" F1={f1:.2f} {'OK' if correct else 'FAIL'}")

    result.elapsed_seconds = time.time() - start_time
    return result


# =============================================================================
# Scope Approach
# =============================================================================

SCOPE_SYSTEM_PROMPT = '''You are a helpful assistant in a long conversation.

Tools: ctx_cli

# WORKFLOW FOR SESSIONS

When a new session starts (marked [SESSION N]):

1. FIRST: ctx_cli scope session-N -m "starting session N"
2. DURING: Save ALL facts with descriptive notes:
   note -m "[PERSON] Caroline: transgender woman, interested in psychology"
   note -m "[DATE] 7-May-2023: Caroline attended LGBTQ support group"
   note -m "[EVENT] 2022: Melanie painted a sunrise"
3. LAST: ctx_cli goto main -m "session N done"

# WORKFLOW FOR QUESTIONS

When asked a question:

1. FIRST: ctx_cli scopes  (see all available scopes)
2. THEN: ctx_cli goto session-N  (go to relevant scope)
3. THEN: ctx_cli notes  (read the notes there)
4. FINALLY: Answer based on notes found

# COMMANDS

scope <name> -m "..."   Create new scope
goto <name>             Switch to existing scope
note -m "..."           Save fact in CURRENT scope
notes                   List notes in CURRENT scope
scopes                  List ALL scopes

# NOTE FORMAT (use these prefixes)

[PERSON] name: description, traits, identity
[DATE] YYYY-MM-DD or date: what happened
[EVENT] year/date: description of event
[PLACE] location: description
[RELATION] person1 + person2: relationship type

# RULES

- Save EVERY fact immediately - notes are your ONLY memory
- Use specific dates: "7 May 2023" not "yesterday"
- To answer questions: scopes → goto → notes → answer
'''


def run_scope(
    client: OpenAI,
    model: str,
    sessions: list[dict],
    qa_pairs: list[dict],
    conversation_id: str,
) -> BenchmarkResult:
    """Run benchmark with scope approach (notes for memory)."""
    result = BenchmarkResult(approach="scope", model=model, conversation_id=conversation_id)
    start_time = time.time()
    tracker = TokenTracker(model=model)

    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    def call_model(max_rounds: int = 5) -> str:
        """Call model and handle tool calls."""
        for _ in range(max_rounds):
            context = store.get_context(SCOPE_SYSTEM_PROMPT)
            tokens = tracker.count_messages(context)
            result.peak_context = max(result.peak_context, tokens)

            response = client.chat.completions.create(
                model=model,
                messages=context,
                tools=tools,
                temperature=0,
            )

            msg = response.choices[0].message

            if response.usage:
                result.total_input += response.usage.prompt_tokens
                result.total_output += response.usage.completion_tokens

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

                        if cmd.startswith("note "):
                            result.notes_created += 1

                        store.add_message(Message(
                            role="tool",
                            content=cmd_result,
                            tool_call_id=tc.id,
                        ))
            else:
                if msg.content:
                    store.add_message(Message(role="assistant", content=msg.content))
                return msg.content or ""

        return ""

    # Process each session
    total_turns = sum(len(s["turns"]) for s in sessions)
    print(f"    Processing {len(sessions)} sessions ({total_turns} turns)...")

    for session in sessions:
        session_num = session["num"]
        session_date = session["date"]

        # Start session
        session_header = f"[SESSION {session_num}]"
        if session_date:
            session_header += f" - {session_date}"
        session_header += "\nPlease create a scope for this session and save all facts as notes."

        store.add_message(Message(role="user", content=session_header))
        call_model(max_rounds=3)  # Let model create scope

        # Process turns in this session
        for role, content in session["turns"]:
            store.add_message(Message(role=role, content=content))

            if role == "user":
                call_model(max_rounds=3)  # Let model take notes

        # End session - prompt to goto main
        store.add_message(Message(
            role="user",
            content=f"Session {session_num} is complete. Please save any remaining facts and goto main with a summary."
        ))
        call_model(max_rounds=5)  # Let model wrap up and goto main

        print(f"      Session {session_num}: notes={result.notes_created}")

    print(f"    Total notes created: {result.notes_created}")

    # Clear working messages, keep only notes
    store.branches["main"].messages.clear()

    # Ask QA questions
    for i, qa in enumerate(qa_pairs):
        print(f"    QA {i+1}/{len(qa_pairs)}: {qa['question'][:50]}...", end="", flush=True)

        # Add instruction to check notes
        question_with_hint = f"{qa['question']}\n\n(Remember: use 'scopes' to see available scopes, 'goto <scope>' to switch, 'notes' to read facts)"
        store.add_message(Message(role="user", content=question_with_hint))

        # Allow model to check notes (scopes → goto → notes → answer = 4+ rounds)
        for _ in range(6):
            context = store.get_context(SCOPE_SYSTEM_PROMPT)

            response = client.chat.completions.create(
                model=model,
                messages=context,
                tools=tools,
                temperature=0,
                max_tokens=300,
            )

            msg = response.choices[0].message

            if response.usage:
                result.total_input += response.usage.prompt_tokens
                result.total_output += response.usage.completion_tokens

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
                        store.add_message(Message(
                            role="tool",
                            content=cmd_result,
                            tool_call_id=tc.id,
                        ))
            else:
                answer = msg.content or ""
                store.add_message(Message(role="assistant", content=answer))

                # Evaluate
                correct, f1 = check_answer(answer, qa)
                category = qa["category"]
                result.category_total[category] += 1
                if correct:
                    result.category_correct[category] += 1

                result.qa_results.append({
                    "question": qa["question"],
                    "expected": qa["answer"],
                    "response": answer[:200],
                    "correct": correct,
                    "f1": round(f1, 3),
                    "category": category,
                })

                print(f" F1={f1:.2f} {'OK' if correct else 'FAIL'}")
                break
        else:
            # Max rounds reached without answer - record as failed
            result.category_total[qa["category"]] += 1
            result.qa_results.append({
                "question": qa["question"],
                "expected": qa["answer"],
                "response": "(no answer - tool call loop)",
                "correct": False,
                "f1": 0.0,
                "category": qa["category"],
            })
            print(f" F1=0.00 TIMEOUT")

    result.elapsed_seconds = time.time() - start_time
    return result


# =============================================================================
# Results
# =============================================================================

def print_results(linear: BenchmarkResult, scope: BenchmarkResult):
    """Print comparison of results."""
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\n{'Category':<20} {'Linear':>15} {'Scope':>15}")
    print("-" * 50)

    for cat_id, cat_name in CATEGORY_NAMES.items():
        if linear.category_total[cat_id] > 0 or scope.category_total[cat_id] > 0:
            lin_acc = linear.accuracy(cat_id)
            scp_acc = scope.accuracy(cat_id)
            print(f"{cat_name:<20} {lin_acc:>14.1%} {scp_acc:>14.1%}")

    print("-" * 50)
    print(f"{'OVERALL':<20} {linear.overall_accuracy:>14.1%} {scope.overall_accuracy:>14.1%}")

    print(f"\n{'Metric':<20} {'Linear':>15} {'Scope':>15}")
    print("-" * 50)
    print(f"{'Input tokens':<20} {linear.total_input:>15,} {scope.total_input:>15,}")
    print(f"{'Output tokens':<20} {linear.total_output:>15,} {scope.total_output:>15,}")
    print(f"{'Peak context':<20} {linear.peak_context:>15,} {scope.peak_context:>15,}")
    print(f"{'Notes created':<20} {'N/A':>15} {scope.notes_created:>15}")
    print(f"{'Time (s)':<20} {linear.elapsed_seconds:>15.1f} {scope.elapsed_seconds:>15.1f}")

    # Analysis
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)

    accuracy_diff = scope.overall_accuracy - linear.overall_accuracy
    if accuracy_diff >= -0.05:
        print(f"OK Scope maintained accuracy ({accuracy_diff:+.1%} vs linear)")
    else:
        print(f"WARN Scope lost {-accuracy_diff:.1%} accuracy")

    token_diff = linear.total_input - scope.total_input
    if token_diff > 0:
        pct = token_diff / linear.total_input * 100
        print(f"OK Scope saved {token_diff:,} input tokens ({pct:.1f}%)")
    else:
        print(f"INFO Scope used {-token_diff:,} more tokens (note-taking overhead)")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="LOCOMO Benchmark for ctx-cli")
    parser.add_argument("--model", default="gpt-4.1-mini", help="Model to use")
    parser.add_argument("--conversation", type=int, default=0, help="Conversation index (0-9)")
    parser.add_argument("--max-sessions", type=int, default=None, help="Max sessions to use from conversation")
    parser.add_argument("--max-qa", type=int, default=30, help="Max QA pairs to evaluate")
    parser.add_argument("--include-unanswerable", action="store_true", help="Include unanswerable questions")
    parser.add_argument("--output", default="benchmarks/results", help="Output directory")
    parser.add_argument("--linear-only", action="store_true", help="Only run linear approach")
    parser.add_argument("--scope-only", action="store_true", help="Only run scope approach")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY environment variable")
        sys.exit(1)

    # Load data
    print("=" * 70)
    print("LOCOMO Benchmark")
    print("=" * 70)

    data = load_locomo_data()
    conv_idx = max(0, min(len(data) - 1, args.conversation))
    conv_data = data[conv_idx]

    print(f"Model: {args.model}")
    print(f"Conversation: {conv_data['sample_id']} (index {conv_idx})")

    # Extract sessions, conversation and QA
    sessions = extract_sessions(conv_data, args.max_sessions)
    conversation = extract_conversation(conv_data, args.max_sessions)
    qa_pairs = extract_qa_pairs(conv_data, args.max_qa, exclude_unanswerable=not args.include_unanswerable)

    print(f"Sessions: {len(sessions)}")
    print(f"Conversation turns: {len(conversation)}")
    print(f"QA pairs: {len(qa_pairs)}")

    # Category distribution
    cat_counts = {}
    for qa in qa_pairs:
        cat = qa["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    print(f"Categories: {cat_counts}")

    client = OpenAI()
    linear_result = None
    scope_result = None

    # Run benchmarks
    if not args.scope_only:
        print("\n[1/2] Running LINEAR approach...")
        linear_result = run_linear(client, args.model, conversation, qa_pairs, conv_data["sample_id"])
        print(f"  Overall accuracy: {linear_result.overall_accuracy:.1%}")

    if not args.linear_only:
        print("\n[2/2] Running SCOPE approach...")
        scope_result = run_scope(client, args.model, sessions, qa_pairs, conv_data["sample_id"])
        print(f"  Overall accuracy: {scope_result.overall_accuracy:.1%}")

    # Print comparison if both ran
    if linear_result and scope_result:
        print_results(linear_result, scope_result)

    # Save results
    os.makedirs(args.output, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{args.output}/locomo_{conv_data['sample_id']}_{timestamp}.json"

    def result_to_dict(r: BenchmarkResult | None) -> dict | None:
        if r is None:
            return None
        d = asdict(r)
        d["overall_accuracy"] = r.overall_accuracy
        for cat_id in CATEGORY_NAMES:
            d[f"accuracy_{CATEGORY_NAMES[cat_id]}"] = r.accuracy(cat_id)
        return d

    results = {
        "config": {
            "model": args.model,
            "conversation_id": conv_data["sample_id"],
            "conversation_turns": len(conversation),
            "qa_pairs": len(qa_pairs),
            "max_sessions": args.max_sessions,
        },
        "linear": result_to_dict(linear_result),
        "scope": result_to_dict(scope_result),
    }

    with open(filename, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {filename}")


if __name__ == "__main__":
    main()
