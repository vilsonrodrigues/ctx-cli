#!/usr/bin/env python3
"""
Unified Benchmark Runner for ECM Evaluation.

Usage:
    uv run benchmarks/runners/run_benchmark.py --benchmark swe-bench-cl --size mini
    uv run benchmarks/runners/run_benchmark.py --benchmark appworld --size full --output results/
    uv run benchmarks/runners/run_benchmark.py --list
"""

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from benchmarks.harnesses import AVAILABLE_HARNESSES, get_harness, list_harnesses
from benchmarks.core.metrics import CumulativeTokenReport


# Benchmark size configurations
SIZES = {
    "mini": {
        "swe-bench-cl": {"max_tasks": 5, "sequence": "django"},
        "lifelong-agent-bench": {"max_tasks": 10, "environment": "db"},
        "appworld": {"max_tasks": 5},
        "osworld": {"max_tasks": 5},
        "the-agent-company": {"max_tasks": 5, "role": None},  # All roles
    },
    "small": {
        "swe-bench-cl": {"max_tasks": 15, "sequence": "django"},
        "lifelong-agent-bench": {"max_tasks": 30, "environment": ["db", "os"]},
        "appworld": {"max_tasks": 15},
        "osworld": {"max_tasks": 15},
        "the-agent-company": {"max_tasks": 10, "role": None},
    },
    "full": {
        "swe-bench-cl": {"max_tasks": 50, "sequence": "django"},
        "lifelong-agent-bench": {"max_tasks": 100, "environment": "all"},
        "appworld": {"max_tasks": 50},
        "osworld": {"max_tasks": 50},
        "the-agent-company": {"max_tasks": 50, "role": None},
    },
}


def create_ecm_agent(model: str = "gpt-4o-mini"):
    """Create an ECM agent for benchmarking."""
    try:
        from benchmarks.memory.agents import ECMAgent
        return ECMAgent(model=model)
    except ImportError:
        print("[Warning] ECMAgent not available, using simulation")
        return None


def create_linear_agent(model: str = "gpt-4o-mini"):
    """Create a linear (long context) agent for baseline comparison."""
    try:
        from benchmarks.memory.agents import LongContextAgent
        return LongContextAgent(model=model)
    except ImportError:
        print("[Warning] LongContextAgent not available")
        return None


def run_benchmark(
    benchmark: str,
    size: str = "mini",
    model: str = "gpt-4o-mini",
    output_dir: str = "benchmarks/results",
    compare_baseline: bool = False,
    **kwargs,
) -> dict:
    """
    Run a benchmark evaluation.

    Args:
        benchmark: Benchmark name (e.g., 'swe-bench-cl')
        size: Configuration size ('mini', 'small', 'full')
        model: LLM model to use
        output_dir: Directory to save results
        compare_baseline: If True, also run linear baseline
        **kwargs: Additional config overrides

    Returns:
        dict with evaluation results
    """
    print(f"\n{'='*60}")
    print(f"ECM Benchmark Runner")
    print(f"{'='*60}")
    print(f"Benchmark: {benchmark}")
    print(f"Size: {size}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    # Get harness
    try:
        HarnessClass = get_harness(benchmark)
    except ValueError as e:
        print(f"Error: {e}")
        return {"error": str(e)}

    harness = HarnessClass()

    # Setup harness
    print(f"[{benchmark}] Setting up harness...")
    if not harness.setup():
        print(f"[{benchmark}] Harness setup failed")
        return {"error": "Harness setup failed"}

    # Get config for size
    config = SIZES.get(size, SIZES["mini"]).get(benchmark, {})
    config.update(kwargs)  # Allow overrides

    print(f"[{benchmark}] Config: {config}")

    # Create agents
    ecm_agent = create_ecm_agent(model)
    if ecm_agent is None:
        print("[Warning] Running without actual agent - metrics will be simulated")

    results = {
        "benchmark": benchmark,
        "size": size,
        "model": model,
        "config": config,
        "timestamp": datetime.now().isoformat(),
        "ecm": None,
        "linear": None,
    }

    # Run ECM evaluation
    print(f"\n[{benchmark}] Running ECM evaluation...")

    try:
        # Get adapter class from harness module
        if benchmark == "swe-bench-cl":
            from benchmarks.harnesses.swe_bench_cl import SWEBenchCLAdapter
            adapter = SWEBenchCLAdapter(harness, ecm_agent, model)
            sequence = config.get("sequence", "django")
            max_tasks = config.get("max_tasks", 50)
            token_report, correctness = adapter.run_sequence(sequence, max_tasks)

        elif benchmark == "lifelong-agent-bench":
            from benchmarks.harnesses.lifelong_agent_bench import LifelongAgentBenchAdapter
            adapter = LifelongAgentBenchAdapter(harness, ecm_agent, model)
            environments = config.get("environment", ["db"])
            if environments == "all":
                environments = ["db", "os", "kg"]
            elif isinstance(environments, str):
                environments = [environments]
            max_tasks = config.get("max_tasks", 20)
            token_report, correctness = adapter.run_sequence(
                {"environment": environments, "max_tasks": max_tasks},
                reset_between_tasks=False
            )

        elif benchmark == "appworld":
            from benchmarks.harnesses.appworld import AppWorldAdapter
            adapter = AppWorldAdapter(harness, ecm_agent, model)
            max_tasks = config.get("max_tasks", 50)
            token_report, correctness = adapter.run_evaluation(max_tasks)

        elif benchmark == "osworld":
            from benchmarks.harnesses.osworld import OSWorldAdapter
            adapter = OSWorldAdapter(harness, ecm_agent, model)
            token_report, correctness = adapter.run_sequence(config, reset_between_tasks=False)

        elif benchmark == "the-agent-company":
            from benchmarks.harnesses.the_agent_company import TheAgentCompanyAdapter
            adapter = TheAgentCompanyAdapter(harness, ecm_agent, model)
            # Company context persists across all tasks
            token_report, correctness = adapter.run_sequence(config, reset_between_tasks=False)

        else:
            print(f"[{benchmark}] Adapter not implemented")
            token_report = CumulativeTokenReport(agent_type="ecm", model=model, benchmark=benchmark)
            correctness = None

        results["ecm"] = {
            "token_report": token_report.to_dict() if token_report else None,
            "correctness": correctness.to_dict() if correctness else None,
        }

        print(f"\n[{benchmark}] ECM Results:")
        print(f"  Tasks: {token_report.num_tasks}")
        print(f"  Peak Context: {token_report.peak_context:,} tokens")
        print(f"  Success Rate: {token_report.success_rate:.1%}")

    except Exception as e:
        print(f"[{benchmark}] Error during ECM evaluation: {e}")
        import traceback
        traceback.print_exc()
        results["ecm"] = {"error": str(e)}

    # Run baseline comparison if requested
    if compare_baseline:
        print(f"\n[{benchmark}] Running Linear baseline...")
        linear_agent = create_linear_agent(model)
        if linear_agent:
            # Similar evaluation with linear agent
            # (simplified for now)
            results["linear"] = {"note": "Baseline comparison not yet implemented"}

    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = output_path / f"{benchmark}_{size}_{timestamp}.json"

    with open(result_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n[{benchmark}] Results saved to: {result_file}")

    # Cleanup
    harness.teardown()

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run ECM benchmark evaluations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List available benchmarks
    python run_benchmark.py --list

    # Run mini evaluation
    python run_benchmark.py --benchmark swe-bench-cl --size mini

    # Run full evaluation with baseline comparison
    python run_benchmark.py --benchmark appworld --size full --compare-baseline

    # Specify custom output directory
    python run_benchmark.py --benchmark lifelong-agent-bench --output ./my_results
        """,
    )

    parser.add_argument(
        "--benchmark", "-b",
        choices=list(AVAILABLE_HARNESSES.keys()),
        help="Benchmark to run",
    )
    parser.add_argument(
        "--size", "-s",
        choices=list(SIZES.keys()),
        default="mini",
        help="Evaluation size (default: mini)",
    )
    parser.add_argument(
        "--model", "-m",
        default="gpt-4.1-mini",
        help="LLM model to use (default: gpt-4.1-mini)",
    )
    parser.add_argument(
        "--output", "-o",
        default="benchmarks/results",
        help="Output directory for results",
    )
    parser.add_argument(
        "--compare-baseline",
        action="store_true",
        help="Also run linear baseline for comparison",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available benchmarks",
    )

    # Benchmark-specific options
    parser.add_argument(
        "--sequence",
        help="Repository sequence for SWE-Bench-CL (e.g., django)",
    )
    parser.add_argument(
        "--environment",
        help="Environment for LifelongAgentBench (db, os, kg, or all)",
    )
    parser.add_argument(
        "--role",
        choices=["swe", "pm", "data_scientist", "hr", "finance", "admin"],
        help="Role filter for TheAgentCompany (default: all roles)",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        help="Maximum tasks to run (overrides size default)",
    )

    args = parser.parse_args()

    if args.list:
        print("\nAvailable Benchmarks:")
        print("-" * 60)
        for info in list_harnesses():
            print(f"\n  {info['name']}")
            print(f"    Type: {info['type']}")
            print(f"    Description: {info['description']}")
            print(f"    Requires: {', '.join(info['requires'])}")
        print()
        return

    if not args.benchmark:
        parser.print_help()
        print("\nError: --benchmark is required (or use --list to see options)")
        sys.exit(1)

    # Build kwargs from optional args
    kwargs = {}
    if args.sequence:
        kwargs["sequence"] = args.sequence
    if args.environment:
        kwargs["environment"] = args.environment
    if args.role:
        kwargs["role"] = args.role
    if args.max_tasks:
        kwargs["max_tasks"] = args.max_tasks

    # Run benchmark
    results = run_benchmark(
        benchmark=args.benchmark,
        size=args.size,
        model=args.model,
        output_dir=args.output,
        compare_baseline=args.compare_baseline,
        **kwargs,
    )

    # Print summary
    if "error" not in results:
        print("\n" + "=" * 60)
        print("Evaluation Complete!")
        print("=" * 60)

        if results.get("ecm"):
            ecm = results["ecm"]
            if "token_report" in ecm and ecm["token_report"]:
                summary = ecm["token_report"]["summary"]
                print(f"\nECM Performance:")
                print(f"  Peak Context: {summary['peak_context']:,} tokens")
                print(f"  Total Input: {summary['total_input_tokens']:,} tokens")
                print(f"  Success Rate: {summary['success_rate']:.1%}")
                print(f"  Avg Growth/Task: {summary['avg_context_growth']:.1f} tokens")


if __name__ == "__main__":
    main()
