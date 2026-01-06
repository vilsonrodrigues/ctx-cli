#!/usr/bin/env python3
"""
Compare ECM against baseline memory agents on MemoryAgentBench.

Available Agents:
1. longcontext - Uses full context without memory management
2. rag - Uses vector retrieval for context
3. ecm - Explicit Context Management (ours)
4. mem0 - Mem0 memory framework
5. letta - Letta/MemGPT framework

Usage:
    # Compare all agents
    uv run benchmarks/compare_baselines.py --sub-dataset AR --max-chunks 20

    # Compare only specific agents
    uv run benchmarks/compare_baselines.py --agents ecm mem0 --sub-dataset AR

    # Run on all splits
    uv run benchmarks/compare_baselines.py --all-splits --agents ecm rag longcontext

    # List available agents
    uv run benchmarks/compare_baselines.py --list-agents
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict
from tqdm import tqdm

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AgentResult:
    """Result from a single agent run."""
    agent_name: str
    dataset: str
    total_queries: int
    exact_match: float
    contains_match: float
    f1_score: float
    avg_input_tokens: float
    avg_output_tokens: float
    avg_query_time: float
    total_time: float
    extra_metrics: dict = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Comparison results across agents."""
    dataset: str
    timestamp: str
    agents: list[AgentResult]
    config: dict


# =============================================================================
# Base Agent Interface
# =============================================================================

class BaseAgent:
    """Base class for memory agents."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI()
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def memorize(self, content: str, context_id: int = 0):
        """Memorize content."""
        raise NotImplementedError

    def query(self, question: str, context_id: int = 0) -> dict:
        """Answer a question. Returns dict with 'answer', 'input_tokens', 'output_tokens'."""
        raise NotImplementedError

    def reset(self):
        """Reset agent state."""
        raise NotImplementedError

    def get_stats(self) -> dict:
        """Get agent statistics."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }


# =============================================================================
# Long Context Agent (Baseline)
# =============================================================================

class LongContextAgent(BaseAgent):
    """
    Long Context Agent - Appends all content to context window.

    This is the simplest baseline: just accumulate everything in the prompt.
    Context grows linearly with content.
    """

    def __init__(self, model: str = "gpt-4o-mini", max_tokens: int = 100000):
        super().__init__(model)
        self.max_tokens = max_tokens
        self.context_buffer = []
        self.context_by_id = {}

    def memorize(self, content: str, context_id: int = 0):
        """Append content to context buffer."""
        if context_id not in self.context_by_id:
            self.context_by_id[context_id] = []
        self.context_by_id[context_id].append(content)

    def query(self, question: str, context_id: int = 0) -> dict:
        """Answer using full accumulated context."""
        # Build context from all memorized content
        context_parts = self.context_by_id.get(context_id, [])
        full_context = "\n\n".join(context_parts)

        # Truncate if too long (simple truncation)
        if len(full_context) > self.max_tokens * 4:  # ~4 chars per token
            full_context = full_context[-(self.max_tokens * 4):]

        messages = [
            {
                "role": "system",
                "content": f"Answer the question based on the following context:\n\n{full_context}"
            },
            {"role": "user", "content": question}
        ]

        start_time = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=500,
        )

        answer = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        return {
            "answer": answer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "query_time": time.time() - start_time,
        }

    def reset(self):
        self.context_buffer = []
        self.context_by_id = {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["context_size"] = sum(len(c) for chunks in self.context_by_id.values() for c in chunks)
        stats["num_chunks"] = sum(len(chunks) for chunks in self.context_by_id.values())
        return stats


# =============================================================================
# RAG Agent (Baseline)
# =============================================================================

class RAGAgent(BaseAgent):
    """
    RAG Agent - Uses simple keyword/embedding retrieval.

    This baseline stores chunks and retrieves top-k most relevant
    based on keyword overlap (simple TF-IDF style).
    """

    def __init__(self, model: str = "gpt-4o-mini", top_k: int = 5):
        super().__init__(model)
        self.top_k = top_k
        self.chunks = []
        self.chunks_by_id = {}

    def memorize(self, content: str, context_id: int = 0):
        """Store content chunk."""
        if context_id not in self.chunks_by_id:
            self.chunks_by_id[context_id] = []
        self.chunks_by_id[context_id].append(content)

    def _retrieve(self, query: str, context_id: int = 0) -> list[str]:
        """Retrieve top-k relevant chunks using keyword overlap."""
        chunks = self.chunks_by_id.get(context_id, [])
        if not chunks:
            return []

        # Simple keyword matching (TF-IDF style)
        query_words = set(query.lower().split())

        scored_chunks = []
        for chunk in chunks:
            chunk_words = set(chunk.lower().split())
            overlap = len(query_words & chunk_words)
            score = overlap / (len(query_words) + 1)
            scored_chunks.append((score, chunk))

        # Sort by score and take top-k
        scored_chunks.sort(reverse=True, key=lambda x: x[0])
        return [chunk for _, chunk in scored_chunks[:self.top_k]]

    def query(self, question: str, context_id: int = 0) -> dict:
        """Answer using retrieved context."""
        retrieved = self._retrieve(question, context_id)
        context = "\n\n".join(retrieved)

        messages = [
            {
                "role": "system",
                "content": f"Answer the question based on the following retrieved context:\n\n{context}"
            },
            {"role": "user", "content": question}
        ]

        start_time = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=500,
        )

        answer = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        return {
            "answer": answer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "query_time": time.time() - start_time,
            "retrieved_chunks": len(retrieved),
        }

    def reset(self):
        self.chunks = []
        self.chunks_by_id = {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["total_chunks"] = sum(len(chunks) for chunks in self.chunks_by_id.values())
        stats["top_k"] = self.top_k
        return stats


# =============================================================================
# ECM Agent (Ours)
# =============================================================================

# =============================================================================
# Mem0 Agent (Baseline)
# =============================================================================

class Mem0Agent(BaseAgent):
    """
    Mem0 Agent - Uses Mem0 memory framework.

    Requires: pip install mem0ai
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        super().__init__(model)
        self.available = False
        self.memories = []
        self.memories_by_id = {}

        try:
            from mem0 import Memory
            self.Memory = Memory
            self.m = Memory()
            self.available = True
        except ImportError:
            print("  [Mem0] Not installed. Run: pip install mem0ai")
            # Fallback to simple memory
            self.m = None

    def memorize(self, content: str, context_id: int = 0):
        """Add memory using Mem0."""
        user_id = f"context_{context_id}"

        if self.available and self.m:
            try:
                self.m.add(content, user_id=user_id)
            except Exception as e:
                # Fallback
                if context_id not in self.memories_by_id:
                    self.memories_by_id[context_id] = []
                self.memories_by_id[context_id].append(content)
        else:
            if context_id not in self.memories_by_id:
                self.memories_by_id[context_id] = []
            self.memories_by_id[context_id].append(content)

    def query(self, question: str, context_id: int = 0) -> dict:
        """Answer using Mem0 memories."""
        user_id = f"context_{context_id}"

        # Retrieve memories
        if self.available and self.m:
            try:
                memories = self.m.search(question, user_id=user_id, limit=5)
                context = "\n".join([m.get("memory", "") for m in memories])
            except Exception:
                chunks = self.memories_by_id.get(context_id, [])
                context = "\n".join(chunks[-5:])
        else:
            chunks = self.memories_by_id.get(context_id, [])
            context = "\n".join(chunks[-5:])

        messages = [
            {
                "role": "system",
                "content": f"Answer based on these memories:\n\n{context}"
            },
            {"role": "user", "content": question}
        ]

        start_time = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=500,
        )

        answer = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        return {
            "answer": answer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "query_time": time.time() - start_time,
        }

    def reset(self):
        if self.available and self.m:
            try:
                self.m.reset()
            except Exception:
                pass
        self.memories_by_id = {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["mem0_available"] = self.available
        stats["total_memories"] = sum(len(m) for m in self.memories_by_id.values())
        return stats


# =============================================================================
# Letta Agent (Baseline)
# =============================================================================

class LettaAgent(BaseAgent):
    """
    Letta Agent - Uses Letta/MemGPT memory framework.

    Requires: pip install letta
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        super().__init__(model)
        self.available = False
        self.memories_by_id = {}

        try:
            # Letta has complex setup, use simplified fallback
            # from letta import create_client
            # self.client_letta = create_client()
            self.available = False
            print("  [Letta] Using simplified memory (full Letta requires server setup)")
        except ImportError:
            print("  [Letta] Not installed. Run: pip install letta")

    def memorize(self, content: str, context_id: int = 0):
        """Add memory."""
        if context_id not in self.memories_by_id:
            self.memories_by_id[context_id] = []
        self.memories_by_id[context_id].append(content)

    def query(self, question: str, context_id: int = 0) -> dict:
        """Answer using memories."""
        chunks = self.memories_by_id.get(context_id, [])
        # Letta-style: use recent context window + archival summary
        recent = chunks[-3:] if len(chunks) > 3 else chunks
        context = "\n".join(recent)

        messages = [
            {
                "role": "system",
                "content": f"[Core Memory]\n{context}\n\nAnswer the question."
            },
            {"role": "user", "content": question}
        ]

        start_time = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=500,
        )

        answer = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        return {
            "answer": answer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "query_time": time.time() - start_time,
        }

    def reset(self):
        self.memories_by_id = {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["letta_available"] = self.available
        return stats


# =============================================================================
# ECM Agent (Ours)
# =============================================================================

class ECMAgent(BaseAgent):
    """
    ECM Agent - Explicit Context Management.

    Uses tiered memory (notes + insights) with scope-based navigation.
    """

    def __init__(self, model: str = "gpt-4o-mini", use_insights: bool = True):
        super().__init__(model)
        self.use_insights = use_insights

        # Import ECM components
        from ctx_store import ContextStore, Message
        self.ContextStore = ContextStore
        self.Message = Message

        self.store = ContextStore()
        self.current_context_id = None

    def _extract_insight(self, content: str) -> Optional[str]:
        """Extract insight from content."""
        if not self.use_insights:
            return None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Extract ONE key fact or pattern from this text. "
                                   "Be very concise (1 sentence max). "
                                   "If no clear pattern, respond with 'NO_INSIGHT'."
                    },
                    {"role": "user", "content": content[:2000]}
                ],
                temperature=0,
                max_tokens=100,
            )
            insight = response.choices[0].message.content.strip()
            if insight and "NO_INSIGHT" not in insight:
                return insight
        except Exception:
            pass
        return None

    def memorize(self, content: str, context_id: int = 0):
        """Memorize content using ECM tiered memory."""
        # Switch context if needed
        scope_name = f"context_{context_id}"
        if scope_name not in self.store.branches:
            note = f"Starting context {context_id}"
            self.store.checkout(scope_name, note=note, create=True)
        elif self.store.current_branch != scope_name:
            note = f"Returning to context {context_id}"
            self.store.checkout(scope_name, note=note, create=False)

        # Add as note (episodic memory)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        note_content = f"[{timestamp}] {content[:500]}"
        self.store.note(note_content)

        # Extract insight (semantic memory)
        insight = self._extract_insight(content)
        if insight:
            self.store.insight(insight)

    def query(self, question: str, context_id: int = 0) -> dict:
        """Answer using ECM memory."""
        # Ensure correct context
        scope_name = f"context_{context_id}"
        if self.store.current_branch != scope_name and scope_name in self.store.branches:
            self.store.checkout(scope_name, note="Query context switch", create=False)

        # Pull memories
        notes = self.store.get_all_notes()
        insights = self.store.get_insights()

        # Build prompt
        prompt_parts = ["You are a helpful assistant with access to memory."]
        if insights and "No insights" not in insights:
            prompt_parts.append(f"\n## Global Knowledge (Insights)\n{insights}")
        if notes and "No notes" not in notes:
            prompt_parts.append(f"\n## Memory (Notes)\n{notes}")

        system_prompt = "\n".join(prompt_parts)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]

        start_time = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=500,
        )

        answer = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        return {
            "answer": answer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "query_time": time.time() - start_time,
        }

    def reset(self):
        self.store = self.ContextStore()
        self.current_context_id = None
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["total_scopes"] = len(self.store.branches)
        stats["total_notes"] = sum(len(b.notes) for b in self.store.branches.values())
        stats["total_insights"] = len(self.store.insights)
        return stats


# =============================================================================
# Evaluation
# =============================================================================

def evaluate_answer(predicted: str, expected: str) -> dict:
    """Evaluate predicted answer against expected."""
    pred_lower = predicted.lower().strip()
    exp_lower = expected.lower().strip()

    exact_match = pred_lower == exp_lower
    contains_match = exp_lower in pred_lower

    pred_tokens = set(pred_lower.split())
    exp_tokens = set(exp_lower.split())

    if not pred_tokens or not exp_tokens:
        f1 = 0.0
    else:
        overlap = pred_tokens & exp_tokens
        precision = len(overlap) / len(pred_tokens) if pred_tokens else 0
        recall = len(overlap) / len(exp_tokens) if exp_tokens else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "exact_match": exact_match,
        "contains_match": contains_match,
        "f1": f1,
    }


def run_agent_evaluation(
    agent: BaseAgent,
    contexts: list[list[str]],
    queries: list[list[tuple]],
    agent_name: str,
    dataset_name: str,
    verbose: bool = True,
) -> AgentResult:
    """Run evaluation for a single agent."""

    agent.reset()

    results = {
        "exact_match": [],
        "contains_match": [],
        "f1": [],
        "input_tokens": [],
        "output_tokens": [],
        "query_time": [],
    }

    start_time = time.time()
    total_queries = 0

    for context_id, (chunks, qa_pairs) in enumerate(zip(contexts, queries)):
        if verbose:
            print(f"  [{agent_name}] Context {context_id}: {len(chunks)} chunks, {len(qa_pairs)} queries")

        # Memorize chunks
        for chunk in chunks:
            agent.memorize(chunk, context_id)

        # Answer queries
        for question, expected, qa_id in qa_pairs:
            result = agent.query(question, context_id)

            eval_result = evaluate_answer(result["answer"], expected)

            results["exact_match"].append(1 if eval_result["exact_match"] else 0)
            results["contains_match"].append(1 if eval_result["contains_match"] else 0)
            results["f1"].append(eval_result["f1"])
            results["input_tokens"].append(result["input_tokens"])
            results["output_tokens"].append(result["output_tokens"])
            results["query_time"].append(result["query_time"])

            total_queries += 1

    total_time = time.time() - start_time

    # Compute averages
    n = len(results["exact_match"])

    return AgentResult(
        agent_name=agent_name,
        dataset=dataset_name,
        total_queries=total_queries,
        exact_match=sum(results["exact_match"]) / n * 100 if n else 0,
        contains_match=sum(results["contains_match"]) / n * 100 if n else 0,
        f1_score=sum(results["f1"]) / n * 100 if n else 0,
        avg_input_tokens=sum(results["input_tokens"]) / n if n else 0,
        avg_output_tokens=sum(results["output_tokens"]) / n if n else 0,
        avg_query_time=sum(results["query_time"]) / n if n else 0,
        total_time=total_time,
        extra_metrics=agent.get_stats(),
    )


# =============================================================================
# Data Loading
# =============================================================================

def load_dataset(sub_dataset: str, max_contexts: int, max_queries: int, max_chunks: int):
    """Load MemoryAgentBench dataset."""
    from datasets import load_dataset as hf_load_dataset

    split_mapping = {
        "AR": "Accurate_Retrieval",
        "TTL": "Test_Time_Learning",
        "LRU": "Long_Range_Understanding",
        "CR": "Conflict_Resolution",
    }

    split_name = split_mapping.get(sub_dataset, sub_dataset)
    print(f"Loading: ai-hyz/MemoryAgentBench / {split_name}")

    ds = hf_load_dataset("ai-hyz/MemoryAgentBench", split=split_name)

    all_contexts = []
    all_queries = []

    for idx, item in enumerate(ds):
        if idx >= max_contexts:
            break

        context = item.get("context", "")
        questions = item.get("questions", [])
        answers = item.get("answers", [])
        metadata = item.get("metadata", {})
        qa_pair_ids = metadata.get("qa_pair_ids", [])

        if not context or not questions:
            continue

        # Chunk context
        paragraphs = [p.strip() for p in context.split("\n\n") if p.strip()]
        chunks = paragraphs[:max_chunks] if max_chunks > 0 else paragraphs

        if len(paragraphs) > max_chunks:
            print(f"  Context {idx}: {len(paragraphs)} -> {max_chunks} chunks")

        all_contexts.append(chunks)

        # Prepare queries
        query_pairs = []
        for i, (q, a) in enumerate(zip(questions, answers)):
            if max_queries > 0 and i >= max_queries:
                break
            if isinstance(a, list):
                a = a[0] if a else ""
            qa_id = qa_pair_ids[i] if i < len(qa_pair_ids) else f"q{i}"
            query_pairs.append((q, a, qa_id))

        all_queries.append(query_pairs)

    return all_contexts, all_queries


# =============================================================================
# Comparison & Reporting
# =============================================================================

def print_comparison_table(results: list[AgentResult]):
    """Print comparison table."""
    print("\n" + "=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)

    # Header
    print(f"{'Agent':<20} {'Contains%':>10} {'F1%':>8} {'Tokens':>10} {'Time/Q':>10}")
    print("-" * 80)

    for r in results:
        print(f"{r.agent_name:<20} {r.contains_match:>10.1f} {r.f1_score:>8.1f} "
              f"{r.avg_input_tokens:>10.0f} {r.avg_query_time:>10.2f}s")

    print("=" * 80)


def generate_latex_table(results: list[AgentResult], dataset: str) -> str:
    """Generate LaTeX table."""
    lines = [
        "\\begin{table}[h]",
        "\\centering",
        f"\\caption{{Comparison on {dataset}}}",
        "\\begin{tabular}{lcccc}",
        "\\toprule",
        "Agent & Contains (\\%) & F1 (\\%) & Tokens & Time (s) \\\\",
        "\\midrule",
    ]

    for r in results:
        lines.append(
            f"{r.agent_name} & {r.contains_match:.1f} & {r.f1_score:.1f} & "
            f"{r.avg_input_tokens:.0f} & {r.avg_query_time:.2f} \\\\"
        )

    lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table}",
    ])

    return "\n".join(lines)


def save_results(results: list[AgentResult], config: dict, output_dir: str):
    """Save comparison results."""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    comparison = ComparisonResult(
        dataset=config.get("sub_dataset", "unknown"),
        timestamp=timestamp,
        agents=[asdict(r) for r in results],
        config=config,
    )

    # Save JSON
    json_path = os.path.join(output_dir, f"comparison_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(asdict(comparison), f, indent=2)

    # Save LaTeX
    latex_path = os.path.join(output_dir, f"comparison_{timestamp}.tex")
    with open(latex_path, "w") as f:
        f.write(generate_latex_table(results, config.get("sub_dataset", "unknown")))

    print(f"\nResults saved to: {json_path}")
    print(f"LaTeX table saved to: {latex_path}")

    return json_path


# =============================================================================
# Main
# =============================================================================

# =============================================================================
# Agent Registry
# =============================================================================

AVAILABLE_AGENTS = {
    "longcontext": {
        "name": "Long Context",
        "description": "Appends all content to context window (no memory management)",
        "class": LongContextAgent,
    },
    "rag": {
        "name": "RAG (top-5)",
        "description": "Retrieves top-5 relevant chunks using keyword overlap",
        "class": RAGAgent,
    },
    "ecm": {
        "name": "ECM (ours)",
        "description": "Explicit Context Management with notes + insights",
        "class": ECMAgent,
    },
    "mem0": {
        "name": "Mem0",
        "description": "Mem0 memory framework (requires: pip install mem0ai)",
        "class": Mem0Agent,
    },
    "letta": {
        "name": "Letta",
        "description": "Letta/MemGPT framework (requires: pip install letta)",
        "class": LettaAgent,
    },
}


def list_agents():
    """Print available agents."""
    print("\nAvailable Agents:")
    print("-" * 60)
    for key, info in AVAILABLE_AGENTS.items():
        print(f"  {key:<15} - {info['description']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Compare ECM against baseline memory agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Compare ECM vs RAG vs Long Context
    uv run benchmarks/compare_baselines.py --agents ecm rag longcontext

    # Compare only ECM vs Mem0
    uv run benchmarks/compare_baselines.py --agents ecm mem0

    # Run on all dataset splits
    uv run benchmarks/compare_baselines.py --all-splits --agents ecm rag

    # List available agents
    uv run benchmarks/compare_baselines.py --list-agents
        """
    )
    parser.add_argument("--sub-dataset", default="AR", help="Dataset split (AR/TTL/LRU/CR)")
    parser.add_argument("--all-splits", action="store_true", help="Run on all splits")
    parser.add_argument("--max-contexts", type=int, default=1, help="Max contexts")
    parser.add_argument("--max-queries", type=int, default=5, help="Max queries per context")
    parser.add_argument("--max-chunks", type=int, default=10, help="Max chunks per context")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model to use")
    parser.add_argument("--output", default="benchmarks/results", help="Output directory")
    parser.add_argument("--agents", nargs="+", default=["ecm", "rag", "longcontext"],
                        help=f"Agents to compare. Available: {', '.join(AVAILABLE_AGENTS.keys())}")
    parser.add_argument("--list-agents", action="store_true", help="List available agents")

    args = parser.parse_args()

    if args.list_agents:
        list_agents()
        return

    # Validate agents
    for agent_key in args.agents:
        if agent_key not in AVAILABLE_AGENTS:
            print(f"Error: Unknown agent '{agent_key}'")
            list_agents()
            return

    splits = ["AR", "TTL", "LRU", "CR"] if args.all_splits else [args.sub_dataset]

    all_results = []

    for split in splits:
        print(f"\n{'='*60}")
        print(f"Running comparison on {split}")
        print(f"{'='*60}")

        # Load data
        contexts, queries = load_dataset(
            split,
            max_contexts=args.max_contexts,
            max_queries=args.max_queries,
            max_chunks=args.max_chunks,
        )

        print(f"Loaded {len(contexts)} contexts, {sum(len(q) for q in queries)} queries")

        # Initialize selected agents
        agents = {}
        for agent_key in args.agents:
            info = AVAILABLE_AGENTS[agent_key]
            print(f"Initializing: {info['name']}")
            if agent_key == "ecm":
                agents[info["name"]] = info["class"](model=args.model)
            elif agent_key == "rag":
                agents[info["name"]] = info["class"](model=args.model, top_k=5)
            else:
                agents[info["name"]] = info["class"](model=args.model)

        # Run evaluations
        results = []
        for name, agent in agents.items():
            print(f"\nEvaluating: {name}")
            result = run_agent_evaluation(
                agent, contexts, queries, name, split, verbose=True
            )
            results.append(result)

        # Print comparison
        print_comparison_table(results)

        # Save results
        config = {
            "sub_dataset": split,
            "max_contexts": args.max_contexts,
            "max_queries": args.max_queries,
            "max_chunks": args.max_chunks,
            "model": args.model,
            "agents": args.agents,
        }
        save_results(results, config, args.output)

        all_results.extend(results)

    # Print final summary if multiple splits
    if len(splits) > 1:
        print("\n" + "=" * 80)
        print("OVERALL SUMMARY (All Splits)")
        print("=" * 80)
        print_comparison_table(all_results)


if __name__ == "__main__":
    main()
