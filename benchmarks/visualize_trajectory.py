#!/usr/bin/env python3
"""
Visualize Benchmark Token Trajectories.

Generates plots from benchmark CSV exports showing:
- Context window size per task
- Cumulative tokens over time
- ECM vs Linear comparison (if both available)

Supports normal and log scale.

Usage:
    uv run benchmarks/visualize_trajectory.py benchmarks/results/*.csv
    uv run benchmarks/visualize_trajectory.py --log benchmarks/results/trajectory.csv
"""

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


@dataclass
class TrajectoryData:
    """Parsed trajectory data from CSV."""
    name: str
    task_ids: list[int]
    task_names: list[str]
    # Working context metrics (excludes system prompt - the real metrics)
    prompt_start: list[int]
    prompt_end: list[int]
    prompt_delta: list[int]
    peak_prompt: list[int]
    completion_tokens: list[int]
    cumulative_prompt: list[int]
    cumulative_completion: list[int]
    # Legacy metrics (includes system prompt)
    input_tokens: list[int]
    output_tokens: list[int]
    context_at_end: list[int]

    @property
    def num_tasks(self) -> int:
        return len(self.task_ids)

    @property
    def peak_working_context(self) -> int:
        """Peak working context (excludes system prompt)."""
        return max(self.peak_prompt) if self.peak_prompt else 0

    @property
    def peak_context(self) -> int:
        """Peak context (legacy - includes system prompt)."""
        return max(self.context_at_end) if self.context_at_end else 0

    @property
    def total_completion(self) -> int:
        return self.cumulative_completion[-1] if self.cumulative_completion else 0

    @property
    def total_tokens(self) -> int:
        return self.cumulative_prompt[-1] + self.cumulative_completion[-1] if self.cumulative_prompt else 0


def load_trajectory(csv_path: str) -> TrajectoryData:
    """Load trajectory data from CSV file."""
    data = TrajectoryData(
        name=Path(csv_path).stem,
        task_ids=[],
        task_names=[],
        # Working context metrics
        prompt_start=[],
        prompt_end=[],
        prompt_delta=[],
        peak_prompt=[],
        completion_tokens=[],
        cumulative_prompt=[],
        cumulative_completion=[],
        # Legacy metrics
        input_tokens=[],
        output_tokens=[],
        context_at_end=[],
    )

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.task_ids.append(int(row['task_idx']))
            data.task_names.append(row.get('task_name', ''))
            # Working context metrics (new format)
            data.prompt_start.append(int(row.get('prompt_start', 0)))
            data.prompt_end.append(int(row.get('prompt_end', 0)))
            data.prompt_delta.append(int(row.get('prompt_delta', 0)))
            data.peak_prompt.append(int(row.get('peak_prompt', 0)))
            data.completion_tokens.append(int(row.get('completion_tokens', 0)))
            data.cumulative_prompt.append(int(row.get('cumulative_prompt', 0)))
            data.cumulative_completion.append(int(row.get('cumulative_completion', 0)))
            # Legacy metrics (backward compatibility)
            data.input_tokens.append(int(row.get('input_tokens', 0)))
            data.output_tokens.append(int(row.get('output_tokens', 0)))
            data.context_at_end.append(int(row.get('context_at_end', 0)))

    return data


def simulate_linear_baseline(ecm_data: TrajectoryData) -> TrajectoryData:
    """
    Simulate a linear agent baseline from ECM data.

    In linear mode, context grows monotonically as messages accumulate.
    """
    linear = TrajectoryData(
        name=ecm_data.name.replace('ecm', 'linear'),
        task_ids=ecm_data.task_ids.copy(),
        task_names=ecm_data.task_names.copy(),
        # Working context
        prompt_start=[],
        prompt_end=[],
        prompt_delta=[],
        peak_prompt=[],
        completion_tokens=ecm_data.completion_tokens.copy(),
        cumulative_prompt=[],
        cumulative_completion=ecm_data.cumulative_completion.copy(),
        # Legacy
        input_tokens=[],
        output_tokens=ecm_data.output_tokens.copy(),
        context_at_end=[],
    )

    # Simulate: each task adds its tokens to context (no cleanup)
    accumulated = 0

    for i, (prompt, completion) in enumerate(zip(ecm_data.prompt_end, ecm_data.completion_tokens)):
        # In linear mode, previous prompts+completions stay in context
        start = accumulated
        accumulated += prompt + completion
        linear.prompt_start.append(start)
        linear.prompt_end.append(accumulated)
        linear.prompt_delta.append(accumulated - start)
        linear.peak_prompt.append(accumulated)
        linear.cumulative_prompt.append(accumulated)
        # Legacy
        linear.input_tokens.append(accumulated)
        linear.context_at_end.append(accumulated)

    return linear


def plot_trajectories(
    trajectories: list[TrajectoryData],
    output_path: Optional[str] = None,
    log_scale: bool = False,
    show_comparison: bool = True,
) -> None:
    """
    Generate visualization with:
    - Working context per task (excludes system prompt)
    - Task boundary markers (vertical lines)
    - Normal and log scale side by side
    """
    # Create figure: 2 rows x 2 columns
    # Row 1: Working context (normal + log)
    # Row 2: Per-task tokens (prompt + completion)
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle('ECM Token Economics (Working Context)', fontsize=14, fontweight='bold')

    # Style for each trajectory type
    styles = {
        'ecm': {'color': '#2ecc71', 'marker': 'o', 'linestyle': '-', 'label': 'ECM'},
        'linear': {'color': '#e74c3c', 'marker': 's', 'linestyle': '--', 'label': 'Linear'},
    }

    for data in trajectories:
        # Determine style: default to ECM unless 'linear' is explicitly in the name
        is_linear = 'linear' in data.name.lower()
        key = 'linear' if is_linear else 'ecm'
        style = styles[key]

        x_vals = data.task_ids

        # Use working context (prompt_end) if available, else fall back to legacy
        working_context = data.prompt_end if any(data.prompt_end) else data.context_at_end
        prompt_tokens = data.prompt_end if any(data.prompt_end) else data.input_tokens
        completion = data.completion_tokens if any(data.completion_tokens) else data.output_tokens

        # Row 1, Col 1: Working Context - Normal Scale
        axes[0, 0].plot(x_vals, working_context,
                        marker=style['marker'], linestyle=style['linestyle'],
                        color=style['color'], label=style['label'],
                        linewidth=2, markersize=6)

        # Row 1, Col 2: Working Context - Log Scale
        axes[0, 1].plot(x_vals, working_context,
                        marker=style['marker'], linestyle=style['linestyle'],
                        color=style['color'], label=style['label'],
                        linewidth=2, markersize=6)

        # Row 2, Col 1: Working Context per Task (bar)
        bar_width = 0.35
        offset = -bar_width/2 if not is_linear else bar_width/2
        axes[1, 0].bar([x + offset for x in x_vals], prompt_tokens,
                       width=bar_width, color=style['color'], alpha=0.8,
                       label=f"{style['label']} - Working Context")

        # Row 2, Col 2: Completion Tokens per Task
        axes[1, 1].bar([x + offset for x in x_vals], completion,
                       width=bar_width, color=style['color'], alpha=0.8,
                       label=f"{style['label']} - Completion")

    # Add task boundary markers (vertical lines) to context plots
    for ax in [axes[0, 0], axes[0, 1]]:
        for task_id in trajectories[0].task_ids[::5]:  # Every 5 tasks
            ax.axvline(x=task_id, color='gray', linestyle=':', alpha=0.4, linewidth=1)

    # Configure axes
    # Row 1, Col 1: Working Context - Normal
    axes[0, 0].set_xlabel('Task #', fontsize=11)
    axes[0, 0].set_ylabel('Working Context (tokens)', fontsize=11)
    axes[0, 0].set_title('Working Context per Task (excludes system prompt)', fontsize=12)
    axes[0, 0].legend(fontsize=9, loc='upper left')
    axes[0, 0].grid(True, alpha=0.3)

    # Row 1, Col 2: Working Context - Log
    axes[0, 1].set_xlabel('Task #', fontsize=11)
    axes[0, 1].set_ylabel('Working Context (tokens)', fontsize=11)
    axes[0, 1].set_title('Working Context per Task - Log Scale', fontsize=12)
    axes[0, 1].set_yscale('log')
    axes[0, 1].legend(fontsize=9, loc='upper left')
    axes[0, 1].grid(True, alpha=0.3, which='both')

    # Row 2, Col 1: Working context per task
    axes[1, 0].set_xlabel('Task #', fontsize=11)
    axes[1, 0].set_ylabel('Working Context (tokens)', fontsize=11)
    axes[1, 0].set_title('Working Context per Task', fontsize=12)
    axes[1, 0].legend(fontsize=9)
    axes[1, 0].grid(True, alpha=0.3, axis='y')

    # Row 2, Col 2: Completion tokens
    axes[1, 1].set_xlabel('Task #', fontsize=11)
    axes[1, 1].set_ylabel('Completion Tokens', fontsize=11)
    axes[1, 1].set_title('Completion Tokens per Task', fontsize=12)
    axes[1, 1].legend(fontsize=9)
    axes[1, 1].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved: {output_path}")
    else:
        plt.show()


def print_text_visualization(trajectories: list[TrajectoryData]) -> None:
    """Text-based visualization when matplotlib is not available."""
    for data in trajectories:
        print(f"\n{'='*60}")
        print(f"Trajectory: {data.name}")
        print(f"{'='*60}")
        print(f"Tasks: {data.num_tasks}")
        print(f"Peak Working Context: {data.peak_working_context:,} tokens")
        print(f"Total Tokens: {data.total_tokens:,}")
        print()

        # Use working context if available
        working = data.prompt_end if any(data.prompt_end) else data.context_at_end
        max_val = max(working) if working else 1
        width = 40

        print("Working context per task:")
        for i, (task_id, ctx) in enumerate(zip(data.task_ids, working)):
            bar_len = int((ctx / max_val) * width)
            bar = '█' * bar_len
            print(f"  Task {task_id:2d}: {bar} {ctx:,}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Visualize benchmark token trajectories")
    parser.add_argument(
        "csv_files",
        nargs="+",
        help="CSV trajectory file(s) to visualize",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Use logarithmic scale",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output image path (PNG/PDF)",
    )
    parser.add_argument(
        "--compare-linear",
        action="store_true",
        help="Add simulated linear baseline for comparison",
    )
    
    args = parser.parse_args()
    
    # Load all trajectories
    trajectories = []
    for csv_file in args.csv_files:
        if os.path.exists(csv_file):
            data = load_trajectory(csv_file)
            trajectories.append(data)
            print(f"Loaded: {csv_file} ({data.num_tasks} tasks)")
            
            # Add linear comparison if requested
            if args.compare_linear and 'ecm' in data.name.lower():
                linear = simulate_linear_baseline(data)
                trajectories.append(linear)
                print(f"  Added simulated linear baseline")
        else:
            print(f"Warning: File not found: {csv_file}")
    
    if not trajectories:
        print("No trajectory data to visualize")
        return
    
    # Generate visualization
    plot_trajectories(
        trajectories,
        output_path=args.output,
        log_scale=args.log,
    )


if __name__ == "__main__":
    main()
