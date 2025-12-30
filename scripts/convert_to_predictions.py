#!/usr/bin/env python3
"""
Convert ctx-cli benchmark results to SWE-bench prediction format.

SWE-bench harness expects predictions in this format:
[
  {
    "instance_id": "django__django-10914",
    "model_patch": "diff --git a/...",
    "model_name_or_path": "ctx-cli-linear"
  }
]

Usage:
    python scripts/convert_to_predictions.py \
        benchmarks/results/swe_bench_lite_20251230_173212.json \
        benchmarks/predictions_lite.json
"""

import argparse
import json
from pathlib import Path


def convert_results_to_predictions(results_file: str, output_file: str, approach: str = None):
    """Convert ctx-cli results to SWE-bench prediction format.

    Args:
        results_file: Path to ctx-cli results JSON
        output_file: Path to output predictions JSON
        approach: Filter by approach (linear/scope), or None for both
    """
    with open(results_file) as f:
        data = json.load(f)

    predictions = []
    for result in data["results"]:
        # Filter by approach if specified
        if approach and result["approach"] != approach:
            continue

        # Only include successful patches
        if result["success"] and result["patch"]:
            predictions.append({
                "instance_id": result["instance_id"],
                "model_patch": result["patch"],
                "model_name_or_path": f"ctx-cli-{result['approach']}"
            })

    # Write predictions
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(predictions, f, indent=2)

    print(f"✓ Converted {len(predictions)} predictions")
    print(f"  Input:  {results_file}")
    print(f"  Output: {output_file}")

    # Show breakdown by approach
    by_approach = {}
    for p in predictions:
        approach = p["model_name_or_path"].split("-")[-1]
        by_approach[approach] = by_approach.get(approach, 0) + 1

    print(f"\nBreakdown:")
    for approach, count in sorted(by_approach.items()):
        print(f"  {approach}: {count} predictions")


def main():
    parser = argparse.ArgumentParser(description="Convert ctx-cli results to SWE-bench predictions")
    parser.add_argument("results_file", help="Path to ctx-cli results JSON")
    parser.add_argument("output_file", help="Path to output predictions JSON")
    parser.add_argument("--approach", choices=["linear", "scope"],
                       help="Filter by approach (default: both)")
    args = parser.parse_args()

    convert_results_to_predictions(
        args.results_file,
        args.output_file,
        args.approach
    )


if __name__ == "__main__":
    main()
