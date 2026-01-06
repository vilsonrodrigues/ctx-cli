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
    uv run benchmarks/memory/compare_baselines.py --sub-dataset AR --max-chunks 20

    # Compare only specific agents
    uv run benchmarks/memory/compare_baselines.py --agents ecm mem0 --sub-dataset AR

    # Run on all splits
    uv run benchmarks/memory/compare_baselines.py --all-splits --agents ecm rag longcontext

    # List available agents
    uv run benchmarks/memory/compare_baselines.py --list-agents
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
from tqdm import tqdm

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from benchmarks.common.base_agent import AgentResult, ComparisonResult
from benchmarks.common.metrics import compute_aggregate_metrics
from benchmarks.common.dataset_loaders import load_memoryagentbench, MEMORYAGENTBENCH_SPLITS
from benchmarks.memory.agents import AVAILABLE_AGENTS, ECMAgent, RAGAgent


def list_agents():
    """Print available agents."""
    print("\nAvailable Agents:")
    print("-" * 60)
    for key, info in AVAILABLE_AGENTS.items():
        print(f"  {key:12} - {info['name']}")
        print(f"               {info['description']}")
    print()


def run_agent_evaluation(
    agent,
    agent_name: str,
    dataset,
    verbose: bool = True,
) -> AgentResult:
    """Run evaluation for a single agent."""
    predictions = []
    ground_truths = []
    query_times = []
    input_tokens_list = []
    output_tokens_list = []

    total_start = datetime.now()

    for sample in tqdm(dataset.samples, desc=f"{agent_name}", disable=not verbose):
        # Memorize all chunks
        for chunk in sample.chunks:
            agent.memorize(chunk, context_id=sample.context_id)

        # Answer questions
        for q, a in zip(sample.questions, sample.answers):
            result = agent.query(q, context_id=sample.context_id)
            predictions.append(result["answer"])
            ground_truths.append(a)
            query_times.append(result.get("latency", 0))
            input_tokens_list.append(result.get("input_tokens", 0))
            output_tokens_list.append(result.get("output_tokens", 0))

    total_time = (datetime.now() - total_start).total_seconds()

    # Compute metrics
    metrics = compute_aggregate_metrics(predictions, ground_truths)
    stats = agent.get_stats()

    return AgentResult(
        agent_name=agent_name,
        dataset=dataset.split,
        total_queries=len(predictions),
        exact_match=metrics["exact_match"],
        contains_match=metrics["contains_match"],
        f1_score=metrics["f1_score"],
        avg_input_tokens=sum(input_tokens_list) / len(input_tokens_list) if input_tokens_list else 0,
        avg_output_tokens=sum(output_tokens_list) / len(output_tokens_list) if output_tokens_list else 0,
        avg_query_time=sum(query_times) / len(query_times) if query_times else 0,
        total_time=total_time,
        extra_metrics=stats,
    )


def generate_latex_table(results: list[AgentResult], dataset: str) -> str:
    """Generate LaTeX table from results."""
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
            f"{int(r.avg_input_tokens)} & {r.avg_query_time:.2f} \\\\"
        )

    lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table}",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare ECM vs baselines on MemoryAgentBench")

    parser.add_argument("--list-agents", action="store_true", help="List available agents")
    parser.add_argument("--agents", nargs="+", default=["ecm", "mem0", "letta"],
                        help="Agents to compare (default: ecm mem0 letta)")
    parser.add_argument("--sub-dataset", default="AR",
                        choices=list(MEMORYAGENTBENCH_SPLITS.keys()),
                        help="Dataset split to use")
    parser.add_argument("--all-splits", action="store_true", help="Run on all splits")
    parser.add_argument("--max-contexts", type=int, default=10, help="Max contexts to use")
    parser.add_argument("--max-queries", type=int, default=10, help="Max queries per context")
    parser.add_argument("--max-chunks", type=int, default=50, help="Max chunks per context")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model to use")
    parser.add_argument("--output-dir", default="benchmarks/results", help="Output directory")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    if args.list_agents:
        list_agents()
        return

    # Validate agents
    for agent_key in args.agents:
        if agent_key not in AVAILABLE_AGENTS:
            print(f"Error: Unknown agent '{agent_key}'")
            print(f"Available: {', '.join(AVAILABLE_AGENTS.keys())}")
            sys.exit(1)

    # Determine splits to run
    splits = list(MEMORYAGENTBENCH_SPLITS.keys()) if args.all_splits else [args.sub_dataset]

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for split in splits:
        print(f"\n{'='*60}")
        print(f"Running on {split}")
        print(f"{'='*60}")

        # Load dataset
        dataset = load_memoryagentbench(
            split=split,
            max_contexts=args.max_contexts,
            max_queries_per_context=args.max_queries,
            max_chunks_per_context=args.max_chunks,
        )

        # Initialize agents
        agents = {}
        for agent_key in args.agents:
            info = AVAILABLE_AGENTS[agent_key]
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
            result = run_agent_evaluation(agent, name, dataset, verbose=not args.quiet)
            results.append(result)
            agent.reset()

        # Print summary
        print(f"\n{'='*60}")
        print(f"Results for {split}")
        print(f"{'='*60}")
        print(f"{'Agent':<20} {'Contains%':>10} {'F1%':>8} {'Tokens':>10} {'Time/Q':>10}")
        print("-" * 60)
        for r in results:
            print(f"{r.agent_name:<20} {r.contains_match:>10.1f} {r.f1_score:>8.1f} "
                  f"{int(r.avg_input_tokens):>10} {r.avg_query_time:>9.2f}s")

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        comparison = ComparisonResult(
            dataset=split,
            timestamp=timestamp,
            agents=results,
            config={
                "sub_dataset": split,
                "max_contexts": args.max_contexts,
                "max_queries": args.max_queries,
                "max_chunks": args.max_chunks,
                "model": args.model,
                "agents": args.agents,
            },
        )

        # Save JSON
        json_path = output_dir / f"comparison_{timestamp}.json"
        with open(json_path, "w") as f:
            json.dump(asdict(comparison), f, indent=2)
        print(f"\nSaved: {json_path}")

        # Save LaTeX
        latex_path = output_dir / f"comparison_{timestamp}.tex"
        with open(latex_path, "w") as f:
            f.write(generate_latex_table(results, split))
        print(f"Saved: {latex_path}")


if __name__ == "__main__":
    main()
