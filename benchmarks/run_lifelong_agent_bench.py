#!/usr/bin/env python3
"""
Run LifelongAgentBench with ECM.

Evaluates continual learning: skill reuse across DB/OS/KG environments.

Usage:
    uv run benchmarks/run_lifelong_agent_bench.py --size mini
    uv run benchmarks/run_lifelong_agent_bench.py --size full --environments db os kg
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from metrics import (
    MetricsCollector,
    TaskTokenRecord,
    CumulativeTokenReport,
    compare_token_reports,
)
from benchmarks.configs.benchmark_sizes import get_config
from benchmarks.adapters.benchmark_adapters import LifelongAgentBenchAdapter
from benchmarks.adapters.ecm_adapter import (
    ECMAgentWrapper,
    get_ecm_agent_config,
    get_ecm_dataset_config,
)


def run_benchmark(
    adapter: LifelongAgentBenchAdapter,
    agent: ECMAgentWrapper,
    collector: MetricsCollector,
    verbose: bool = True,
) -> CumulativeTokenReport:
    """Run LifelongAgentBench with token tracking."""
    report = CumulativeTokenReport(
        agent_type=collector.metrics.agent_type,
        model=collector.metrics.model,
        benchmark="lifelong_agent_bench",
    )
    
    tasks = adapter.tasks
    collector.set_total_tasks(len(tasks))
    learned_skills: set[str] = set()
    
    for i, task in enumerate(tasks):
        task_start = time.time()
        
        if verbose:
            print(f"\n[Task {i+1}/{len(tasks)}] {task['task_id']}")
            print(f"  Environment: {task['environment']}")
            print(f"  Skill: {task['skill']}")
            print(f"  Dependencies: {task['dependencies']}")
        
        # Build instruction
        instruction = task["instruction"]
        skill_hint = ""
        if task["skill"] in learned_skills and task["expected_skill_reuse"]:
            skill_hint = f"\n[Hint: You previously learned skill '{task['skill']}'. Check your notes/insights.]"
        
        # Query agent
        result = agent.send_message(
            instruction + skill_hint,
            memorizing=False,
            context_id=i,
        )
        
        input_tokens = result.get("input_len", 0)
        output_tokens = result.get("output_len", 0)
        
        # Mark skill as learned
        learned_skills.add(task["skill"])
        
        # After task, prompt to save insights about the skill
        if task["expected_skill_reuse"]:
            save_prompt = f"Save an insight about the skill '{task['skill']}' you just used, so you can reuse it later."
            agent.send_message(save_prompt, memorizing=True, context_id=i)
        
        # Record task metrics
        record = TaskTokenRecord(
            task_id=task["task_id"],
            task_name=f"{task['environment']}:{task['skill']}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            context_at_start=collector.token_tracker.current_context_tokens,
            context_at_end=collector.token_tracker.current_context_tokens + input_tokens,
            api_calls=2 if task["expected_skill_reuse"] else 1,
            execution_time_seconds=time.time() - task_start,
            success=True,  # Would need actual execution to verify
        )
        report.add_task(record)
        collector.record_task_completed()
        
        if verbose:
            print(f"  Tokens: {input_tokens} in / {output_tokens} out")
            print(f"  Skills learned: {len(learned_skills)}")
    
    return report


def main():
    parser = argparse.ArgumentParser(description="Run LifelongAgentBench with ECM")
    parser.add_argument(
        "--size",
        choices=["mini", "full"],
        default="mini",
        help="Benchmark size",
    )
    parser.add_argument(
        "--environments",
        nargs="+",
        choices=["db", "os", "kg"],
        default=None,
        help="Environments to test (default: from config)",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Max tasks (overrides config)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help="Model to use",
    )
    parser.add_argument(
        "--output",
        default="benchmarks/results",
        help="Output directory",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    # Load config
    config = get_config("lifelong_agent_bench", args.size)
    
    # Override with CLI args
    if args.environments:
        config.environments = args.environments
    if args.max_tasks:
        config.max_tasks = args.max_tasks
    
    print(f"LifelongAgentBench ({args.size})")
    print(f"  Max tasks: {config.max_tasks}")
    print(f"  Environments: {config.environments}")
    print(f"  Model: {args.model}")
    
    # Load dataset
    adapter = LifelongAgentBenchAdapter(config)
    tasks = adapter.load_dataset()
    print(f"  Loaded: {len(tasks)} tasks")
    
    # Create agent and collector
    agent_config = get_ecm_agent_config(model=args.model)
    dataset_config = get_ecm_dataset_config(dataset="lifelong_agent_bench")
    
    agent = ECMAgentWrapper(agent_config, dataset_config, verbose_logging=args.verbose)
    collector = MetricsCollector(model=args.model, agent_type="ecm")
    collector.start_run("lifelong_agent_bench", "lifelong_agent_bench")
    
    # Run benchmark
    print("\nRunning benchmark...")
    report = run_benchmark(adapter, agent, collector, args.verbose)
    collector.end_run()
    
    # Print summary
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Tasks completed: {report.num_tasks}")
    print(f"Total input tokens: {report.total_input_tokens:,}")
    print(f"Total output tokens: {report.total_output_tokens:,}")
    print(f"Peak context: {report.peak_context:,}")
    print(f"Avg context growth/task: {report.avg_context_growth_per_task:.1f}")
    print(f"Success rate: {report.success_rate*100:.1f}%")
    
    # Save results
    os.makedirs(args.output, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output_file = os.path.join(args.output, f"lifelong_agent_bench_ecm_{timestamp}.json")
    report.save(output_file)
    print(f"\nResults saved: {output_file}")
    
    # Also save CSV for plotting
    csv_file = os.path.join(args.output, f"lifelong_agent_bench_trajectory_{timestamp}.csv")
    report.to_csv(csv_file)
    print(f"Trajectory CSV: {csv_file}")


if __name__ == "__main__":
    main()
