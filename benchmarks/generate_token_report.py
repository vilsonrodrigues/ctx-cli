#!/usr/bin/env python3
"""
Generate Token Economics Reports for Paper.

Aggregates benchmark results and produces paper-ready tables and CSV files.
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from metrics import CumulativeTokenReport, TaskTokenRecord, compare_token_reports


def load_results(results_dir: str) -> list[dict]:
    """Load all JSON result files from directory."""
    results = []
    results_path = Path(results_dir)
    
    for json_file in results_path.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
                data["_source_file"] = str(json_file)
                results.append(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load {json_file}: {e}")
    
    return results


def results_to_report(result: dict) -> CumulativeTokenReport:
    """Convert raw result dict to CumulativeTokenReport."""
    report = CumulativeTokenReport(
        agent_type=result.get("metadata", {}).get("agent_type", "unknown"),
        model=result.get("metadata", {}).get("model", "unknown"),
        benchmark=result.get("metadata", {}).get("benchmark", "unknown"),
    )
    
    # Convert per-task data if available
    tasks_data = result.get("tasks", [])
    for i, task in enumerate(tasks_data):
        record = TaskTokenRecord(
            task_id=task.get("task_id", f"task_{i}"),
            task_name=task.get("task_name", ""),
            input_tokens=task.get("input_tokens", 0),
            output_tokens=task.get("output_tokens", 0),
            context_at_start=task.get("context_at_start", 0),
            context_at_end=task.get("context_at_end", 0),
            api_calls=task.get("api_calls", 0),
            execution_time_seconds=task.get("execution_time", 0.0),
            success=task.get("success", False),
        )
        report.add_task(record)
    
    return report


def generate_latex_table(
    ecm_report: CumulativeTokenReport,
    linear_report: CumulativeTokenReport,
    benchmark_name: str,
) -> str:
    """Generate LaTeX table for paper."""
    comparison = compare_token_reports(ecm_report, linear_report)
    
    latex = f"""
\\begin{{table}}[h]
\\centering
\\caption{{Token Economics: {benchmark_name} ({comparison['num_tasks']} tasks)}}
\\label{{tab:{benchmark_name.lower().replace(' ', '_')}_tokens}}
\\begin{{tabular}}{{lrrr}}
\\toprule
\\textbf{{Metric}} & \\textbf{{Linear}} & \\textbf{{ECM}} & \\textbf{{Reduction}} \\\\
\\midrule
Peak Context (tokens) & {comparison['peak_context']['linear']:,} & {comparison['peak_context']['ecm']:,} & {comparison['peak_context']['reduction']*100:.1f}\\% \\\\
Final Context (tokens) & {comparison['final_context']['linear']:,} & {comparison['final_context']['ecm']:,} & - \\\\
Total Tokens & {comparison['total_tokens']['linear']:,} & {comparison['total_tokens']['ecm']:,} & - \\\\
Context Growth/Task & {comparison['context_growth_per_task']['linear']:.1f} & {comparison['context_growth_per_task']['ecm']:.1f} & - \\\\
Success Rate & {comparison['success_rate']['linear']*100:.1f}\\% & {comparison['success_rate']['ecm']*100:.1f}\\% & - \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}
"""
    return latex


def generate_summary_report(results_dir: str, output_dir: str) -> None:
    """Generate comprehensive summary report."""
    results = load_results(results_dir)
    
    if not results:
        print(f"No results found in {results_dir}")
        return
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Group by benchmark
    by_benchmark: dict[str, dict[str, list]] = {}
    for r in results:
        benchmark = r.get("metadata", {}).get("benchmark", "unknown")
        agent_type = r.get("metadata", {}).get("agent_type", "unknown")
        
        if benchmark not in by_benchmark:
            by_benchmark[benchmark] = {"ecm": [], "linear": []}
        
        by_benchmark[benchmark][agent_type].append(r)
    
    # Generate reports per benchmark
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for benchmark, agents in by_benchmark.items():
        if agents["ecm"] and agents["linear"]:
            ecm_report = results_to_report(agents["ecm"][0])
            linear_report = results_to_report(agents["linear"][0])
            
            # Save comparison JSON
            comparison = compare_token_reports(ecm_report, linear_report)
            comparison_file = output_path / f"{benchmark}_comparison_{timestamp}.json"
            with open(comparison_file, "w") as f:
                json.dump(comparison, f, indent=2)
            print(f"Saved: {comparison_file}")
            
            # Save LaTeX table
            latex = generate_latex_table(ecm_report, linear_report, benchmark)
            latex_file = output_path / f"{benchmark}_table_{timestamp}.tex"
            with open(latex_file, "w") as f:
                f.write(latex)
            print(f"Saved: {latex_file}")
            
            # Save CSVs
            ecm_csv = output_path / f"{benchmark}_ecm_trajectory_{timestamp}.csv"
            ecm_report.to_csv(str(ecm_csv))
            print(f"Saved: {ecm_csv}")
            
            linear_csv = output_path / f"{benchmark}_linear_trajectory_{timestamp}.csv"
            linear_report.to_csv(str(linear_csv))
            print(f"Saved: {linear_csv}")


def main():
    parser = argparse.ArgumentParser(description="Generate token economics reports")
    parser.add_argument(
        "--results-dir",
        default="benchmarks/results",
        help="Directory containing result JSON files",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks/results/reports",
        help="Directory to save generated reports",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "latex", "all"],
        default="all",
        help="Output format(s)",
    )
    
    args = parser.parse_args()
    
    print(f"Loading results from: {args.results_dir}")
    generate_summary_report(args.results_dir, args.output_dir)
    print("Done!")


if __name__ == "__main__":
    main()
