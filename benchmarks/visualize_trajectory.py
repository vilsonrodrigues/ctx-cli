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
    input_tokens: list[int]
    output_tokens: list[int]
    cumulative_input: list[int]
    cumulative_output: list[int]
    context_at_end: list[int]
    
    @property
    def num_tasks(self) -> int:
        return len(self.task_ids)
    
    @property
    def peak_context(self) -> int:
        return max(self.context_at_end) if self.context_at_end else 0
    
    @property
    def total_tokens(self) -> int:
        return self.cumulative_input[-1] + self.cumulative_output[-1] if self.cumulative_input else 0


def load_trajectory(csv_path: str) -> TrajectoryData:
    """Load trajectory data from CSV file."""
    data = TrajectoryData(
        name=Path(csv_path).stem,
        task_ids=[],
        task_names=[],
        input_tokens=[],
        output_tokens=[],
        cumulative_input=[],
        cumulative_output=[],
        context_at_end=[],
    )
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.task_ids.append(int(row['task_idx']))
            data.task_names.append(row.get('task_name', ''))
            data.input_tokens.append(int(row['input_tokens']))
            data.output_tokens.append(int(row['output_tokens']))
            data.cumulative_input.append(int(row['cumulative_input']))
            data.cumulative_output.append(int(row.get('cumulative_output', 0)))
            data.context_at_end.append(int(row['context_at_end']))
    
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
        input_tokens=[],
        output_tokens=ecm_data.output_tokens.copy(),
        cumulative_input=[],
        cumulative_output=ecm_data.cumulative_output.copy(),
        context_at_end=[],
    )
    
    # Simulate: each task adds its tokens to context (no cleanup)
    base_context = 500  # System prompt overhead
    accumulated = base_context
    
    for i, (inp, out) in enumerate(zip(ecm_data.input_tokens, ecm_data.output_tokens)):
        # In linear mode, previous input+output stays in context
        accumulated += inp + out
        linear.input_tokens.append(accumulated)
        linear.cumulative_input.append(sum(linear.input_tokens))
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
    - Per-iteration token consumption (prompt + completion)
    - Task boundary markers (vertical lines)
    - Normal and log scale side by side
    """
    # Create figure: 2 rows x 2 columns
    # Row 1: Context window (normal + log)
    # Row 2: Per-task tokens (prompt + completion)
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle('ECM Token Economics', fontsize=14, fontweight='bold')
    
    # Style for each trajectory type
    styles = {
        'ecm': {'color': '#2ecc71', 'marker': 'o', 'linestyle': '-', 'label': 'ECM'},
        'linear': {'color': '#3498db', 'marker': 's', 'linestyle': '--', 'label': 'Linear'},
    }
    
    for data in trajectories:
        # Determine style: default to ECM unless 'linear' is explicitly in the name
        is_linear = 'linear' in data.name.lower()
        key = 'linear' if is_linear else 'ecm'
        style = styles[key]
        
        x_vals = data.task_ids
        
        # Row 1, Col 1: Context Window - Normal Scale
        axes[0, 0].plot(x_vals, data.context_at_end, 
                        marker=style['marker'], linestyle=style['linestyle'],
                        color=style['color'], label=style['label'], 
                        linewidth=2, markersize=6)
        
        # Row 1, Col 2: Context Window - Log Scale
        axes[0, 1].plot(x_vals, data.context_at_end,
                        marker=style['marker'], linestyle=style['linestyle'],
                        color=style['color'], label=style['label'],
                        linewidth=2, markersize=6)
        
        # Row 2, Col 1: Prompt Tokens per Task
        bar_width = 0.35
        offset = -bar_width/2 if not is_linear else bar_width/2
        axes[1, 0].bar([x + offset for x in x_vals], data.input_tokens,
                       width=bar_width, color=style['color'], alpha=0.8,
                       label=f"{style['label']} - Prompt")
        
        # Row 2, Col 2: Completion Tokens per Task
        axes[1, 1].bar([x + offset for x in x_vals], data.output_tokens,
                       width=bar_width, color=style['color'], alpha=0.8,
                       label=f"{style['label']} - Completion")
    
    # Add task boundary markers (vertical lines) to context plots
    for ax in [axes[0, 0], axes[0, 1]]:
        for task_id in trajectories[0].task_ids[::5]:  # Every 5 tasks
            ax.axvline(x=task_id, color='gray', linestyle=':', alpha=0.4, linewidth=1)
    
    # Configure axes
    # Row 1, Col 1: Context - Normal
    axes[0, 0].set_xlabel('Task #', fontsize=11)
    axes[0, 0].set_ylabel('Context Window (tokens)', fontsize=11)
    axes[0, 0].set_title('Context Window per Task - Normal Scale', fontsize=12)
    axes[0, 0].legend(fontsize=9, loc='upper left')
    axes[0, 0].grid(True, alpha=0.3)
    
    # Row 1, Col 2: Context - Log
    axes[0, 1].set_xlabel('Task #', fontsize=11)
    axes[0, 1].set_ylabel('Context Window (tokens)', fontsize=11)
    axes[0, 1].set_title('Context Window per Task - Log Scale', fontsize=12)
    axes[0, 1].set_yscale('log')
    axes[0, 1].legend(fontsize=9, loc='upper left')
    axes[0, 1].grid(True, alpha=0.3, which='both')
    
    # Row 2, Col 1: Prompt tokens
    axes[1, 0].set_xlabel('Task #', fontsize=11)
    axes[1, 0].set_ylabel('Prompt Tokens', fontsize=11)
    axes[1, 0].set_title('Prompt Tokens per Task', fontsize=12)
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
        print(f"Peak Context: {data.peak_context:,} tokens")
        print(f"Total Tokens: {data.total_tokens:,}")
        print()
        
        # ASCII bar chart for context
        max_val = max(data.context_at_end)
        width = 40
        
        print("Context per task:")
        for i, (task_id, ctx) in enumerate(zip(data.task_ids, data.context_at_end)):
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
