#!/usr/bin/env python3
"""
Run MemoryAgentBench with ECM adapter.

This script runs the MemoryAgentBench evaluation using ECM
as the memory agent, comparing against baselines.

Usage:
    uv run benchmarks/run_memoryagentbench.py --dataset HELMET_InfBench
    uv run benchmarks/run_memoryagentbench.py --dataset longmemeval --max-queries 50
"""

import os
import sys
import json
import yaml
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
from tqdm import tqdm

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.adapters.ecm_adapter import (
    ECMAgentWrapper,
    get_ecm_agent_config,
    get_ecm_dataset_config,
)
from metrics import ECMMetrics, compare_runs


# =============================================================================
# Data Loading
# =============================================================================

def load_dataset_from_huggingface(dataset_name: str, sub_dataset: str, max_contexts: int = 10, max_queries_per_context: int = 10, max_chunks_per_context: int = 50):
    """
    Load dataset from HuggingFace.

    The MemoryAgentBench dataset has 4 splits:
    - Accurate_Retrieval (22 samples)
    - Test_Time_Learning (6 samples)
    - Long_Range_Understanding (110 samples)
    - Conflict_Resolution (8 samples)

    Each sample has:
    - context: str (long document)
    - questions: list[str]
    - answers: list[str]
    - metadata: dict with qa_pair_ids

    Returns list of (context_chunks, query_answer_pairs) tuples.
    """
    try:
        from datasets import load_dataset as hf_load_dataset

        # Map friendly names to actual splits
        split_mapping = {
            "AR": "Accurate_Retrieval",
            "TTL": "Test_Time_Learning",
            "LRU": "Long_Range_Understanding",
            "CR": "Conflict_Resolution",
            "Accurate_Retrieval": "Accurate_Retrieval",
            "Test_Time_Learning": "Test_Time_Learning",
            "Long_Range_Understanding": "Long_Range_Understanding",
            "Conflict_Resolution": "Conflict_Resolution",
        }

        split_name = split_mapping.get(sub_dataset, sub_dataset)
        print(f"Loading dataset: ai-hyz/MemoryAgentBench / {split_name}")

        ds = hf_load_dataset("ai-hyz/MemoryAgentBench", split=split_name)

        all_contexts = []
        all_queries = []

        # Process each sample (1 context + N questions)
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

            # Chunk the context (split by paragraphs or fixed size)
            chunks = _chunk_context(context, chunk_size=1000)
            # Limit number of chunks to avoid huge contexts
            if max_chunks_per_context > 0 and len(chunks) > max_chunks_per_context:
                print(f"  Limiting {len(chunks)} chunks to {max_chunks_per_context}")
                chunks = chunks[:max_chunks_per_context]
            all_contexts.append(chunks)

            # Pair questions with answers
            query_pairs = []
            for i, (q, a) in enumerate(zip(questions, answers)):
                if max_queries_per_context > 0 and i >= max_queries_per_context:
                    break
                qa_id = qa_pair_ids[i] if i < len(qa_pair_ids) else f"q{i}"
                # Answer can be a list of acceptable answers or a single string
                if isinstance(a, list):
                    a = a[0] if a else ""  # Use first answer as primary
                query_pairs.append((q, a, qa_id))

            all_queries.append(query_pairs)

        print(f"Loaded {len(all_contexts)} contexts with {sum(len(q) for q in all_queries)} total queries")
        return all_contexts, all_queries

    except Exception as e:
        print(f"Error loading dataset: {e}")
        print("Using synthetic data for testing...")
        return _create_synthetic_data()


def _chunk_context(context: str, chunk_size: int = 1000) -> list[str]:
    """Split context into chunks by paragraphs or token count."""
    # First try splitting by double newlines (paragraphs)
    paragraphs = [p.strip() for p in context.split("\n\n") if p.strip()]

    if len(paragraphs) <= 1:
        # If no paragraphs, split by approximate token count
        words = context.split()
        chunks = []
        current_chunk = []
        current_len = 0

        for word in words:
            current_chunk.append(word)
            current_len += len(word) + 1
            # Approximate: 4 chars per token
            if current_len >= chunk_size * 4:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_len = 0

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks if chunks else [context]

    return paragraphs


def _create_synthetic_data():
    """Create synthetic data for testing."""
    contexts = [
        [
            "The Eiffel Tower is located in Paris, France. It was built in 1889.",
            "Paris has a population of approximately 2.1 million people.",
            "The tower is 330 meters tall and was the tallest structure in the world until 1930.",
        ],
        [
            "Tokyo is the capital of Japan with a population of 13.96 million.",
            "Mount Fuji is Japan's highest mountain at 3,776 meters.",
            "The Shinkansen bullet train can travel at speeds up to 320 km/h.",
        ],
    ]

    queries = [
        [
            ("Where is the Eiffel Tower located?", "Paris, France", "q1"),
            ("What year was the Eiffel Tower built?", "1889", "q2"),
            ("How tall is the Eiffel Tower?", "330 meters", "q3"),
        ],
        [
            ("What is the capital of Japan?", "Tokyo", "q4"),
            ("How high is Mount Fuji?", "3,776 meters", "q5"),
            ("What is the top speed of the Shinkansen?", "320 km/h", "q6"),
        ],
    ]

    return contexts, queries


# =============================================================================
# Evaluation
# =============================================================================

def evaluate_answer(predicted: str, expected: str) -> dict:
    """
    Evaluate predicted answer against expected.

    Returns dict with various metrics.
    """
    pred_lower = predicted.lower().strip()
    exp_lower = expected.lower().strip()

    # Exact match
    exact_match = pred_lower == exp_lower

    # Contains match
    contains_match = exp_lower in pred_lower

    # Token overlap (simple F1)
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


def run_evaluation(
    agent: ECMAgentWrapper,
    contexts: list,
    queries: list,
    max_queries: int = 0,
    dataset_name: str = "",
    sub_dataset: str = "",
) -> dict:
    """
    Run evaluation on dataset.

    Returns dict with results and metrics.
    """
    results = []
    metrics = {
        "exact_match": [],
        "contains_match": [],
        "f1": [],
        "input_len": [],
        "output_len": [],
        "memory_time": [],
        "query_time": [],
    }

    total_queries = 0
    start_time = time.time()

    for context_id, (context_chunks, query_answer_pairs) in enumerate(
        tqdm(zip(contexts, queries), total=len(contexts), desc="Contexts")
    ):
        print(f"\n[Context {context_id}] Processing {len(context_chunks)} chunks, {len(query_answer_pairs)} queries")

        # Block BookQA-style datasets
        if dataset_name == "ai-hyz/MemoryAgentBench" and sub_dataset in ["Accurate_Retrieval", "AR"]:
            raise ValueError("Accurate_Retrieval (BookQA) benchmark explicitly blocked. Use 'Long_Range_Understanding' or other real benchmarks.")

        # Memorize chunks in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        print(f"  Ingesting {len(context_chunks)} chunks in parallel...")
        
        def process_chunk(chunk):
            agent.send_message(chunk, memorizing=True, context_id=context_id)
            
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_chunk, chunk) for chunk in context_chunks]
            for _ in as_completed(futures):
                pass # Sync point


        # Answer queries
        for query, expected_answer, qa_id in tqdm(query_answer_pairs, desc="Queries", leave=False):
            if max_queries > 0 and total_queries >= max_queries:
                break

            # Get agent response
            response = agent.send_message(
                query,
                memorizing=False,
                query_id=total_queries,
                context_id=context_id
            )

            predicted = response["output"]

            # Evaluate
            eval_result = evaluate_answer(predicted, expected_answer)

            # Record results
            results.append({
                "context_id": context_id,
                "query_id": total_queries,
                "qa_pair_id": qa_id,
                "query": query,
                "expected": expected_answer,
                "predicted": predicted,
                "exact_match": eval_result["exact_match"],
                "contains_match": eval_result["contains_match"],
                "f1": eval_result["f1"],
                "input_len": response["input_len"],
                "output_len": response["output_len"],
                "ecm_metrics": response.get("ecm_metrics", {}),
            })

            # Update metrics
            metrics["exact_match"].append(1 if eval_result["exact_match"] else 0)
            metrics["contains_match"].append(1 if eval_result["contains_match"] else 0)
            metrics["f1"].append(eval_result["f1"])
            metrics["input_len"].append(response["input_len"])
            metrics["output_len"].append(response["output_len"])
            metrics["memory_time"].append(response["memory_construction_time"])
            metrics["query_time"].append(response["query_time_len"])

            total_queries += 1

        if max_queries > 0 and total_queries >= max_queries:
            break

    # Compute aggregates
    elapsed = time.time() - start_time
    averaged_metrics = {
        key: sum(values) / len(values) * (100 if key in ["exact_match", "contains_match", "f1"] else 1)
        for key, values in metrics.items()
        if values
    }

    return {
        "results": results,
        "metrics": metrics,
        "averaged_metrics": averaged_metrics,
        "total_queries": total_queries,
        "total_contexts": len(contexts),
        "elapsed_seconds": elapsed,
        "ecm_status": agent.get_status(),
        "ecm_metrics": agent.get_metrics().to_dict(),
    }


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Run MemoryAgentBench with ECM")
    parser.add_argument("--dataset", default="synthetic", help="Dataset to use")
    parser.add_argument("--sub-dataset", default="HELMET_InfBench", help="Sub-dataset name")
    parser.add_argument("--max-contexts", type=int, default=5, help="Max contexts to process")
    parser.add_argument("--max-queries", type=int, default=0, help="Max total queries (0=all)")
    parser.add_argument("--max-queries-per-context", type=int, default=10, help="Max queries per context")
    parser.add_argument("--max-chunks", type=int, default=20, help="Max chunks per context (0=unlimited)")
    parser.add_argument("--model", default="gpt-4.1-mini", help="Model to use")
    parser.add_argument("--output", default="benchmarks/results", help="Output directory")
    parser.add_argument("--use-insights", action="store_true", default=True, help="Enable insights")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Chunk size in tokens")
    parser.add_argument("--log-file", default=None, help="File to log ECM operations")
    parser.add_argument("--verbose", action="store_true", default=True, help="Verbose logging output")

    args = parser.parse_args()

    # Setup output directory
    os.makedirs(args.output, exist_ok=True)

    # Load dataset
    print(f"Loading dataset: {args.dataset} / {args.sub_dataset}")
    if args.dataset == "synthetic":
        contexts, queries = _create_synthetic_data()
    else:
        contexts, queries = load_dataset_from_huggingface(
            args.dataset,
            args.sub_dataset,
            max_contexts=args.max_contexts,
            max_queries_per_context=args.max_queries_per_context,
            max_chunks_per_context=args.max_chunks,
        )

    print(f"Loaded {len(contexts)} contexts with {sum(len(q) for q in queries)} total queries")

    # Create ECM agent
    agent_config = get_ecm_agent_config(
        model=args.model,
        chunk_size=args.chunk_size,
        use_insights=args.use_insights,
    )
    dataset_config = get_ecm_dataset_config(
        dataset=args.dataset,
        sub_dataset=args.sub_dataset,
    )

    print(f"\nCreating ECM agent with model: {args.model}")
    agent = ECMAgentWrapper(
        agent_config,
        dataset_config,
        verbose_logging=args.verbose,
        log_file=args.log_file,
    )

    # Run evaluation
    print("\nStarting evaluation...")
    results = run_evaluation(
        agent,
        contexts,
        queries,
        max_queries=args.max_queries,
        dataset_name=args.dataset,
        sub_dataset=args.sub_dataset,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total Contexts: {results['total_contexts']}")
    print(f"Total Queries: {results['total_queries']}")
    print(f"Elapsed Time: {results['elapsed_seconds']:.2f}s")
    print()
    print("Accuracy Metrics:")
    print(f"  Exact Match: {results['averaged_metrics'].get('exact_match', 0):.1f}%")
    print(f"  Contains Match: {results['averaged_metrics'].get('contains_match', 0):.1f}%")
    print(f"  F1 Score: {results['averaged_metrics'].get('f1', 0):.1f}%")
    print()
    print("Efficiency Metrics:")
    print(f"  Avg Input Tokens: {results['averaged_metrics'].get('input_len', 0):.0f}")
    print(f"  Avg Output Tokens: {results['averaged_metrics'].get('output_len', 0):.0f}")
    print(f"  Avg Query Time: {results['averaged_metrics'].get('query_time', 0):.2f}s")
    print()
    print("ECM Status:")
    for key, value in results['ecm_status'].items():
        print(f"  {key}: {value}")

    # Print ECM operations summary
    agent.logger.print_summary()

    # Close logger file handler
    agent.logger.close()

    # Save results
    output_path = os.path.join(
        args.output,
        f"memoryagentbench_ecm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with open(output_path, "w") as f:
        json.dump({
            "config": {
                "agent_config": agent_config,
                "dataset_config": dataset_config,
                "args": vars(args),
            },
            **results
        }, f, indent=2)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
