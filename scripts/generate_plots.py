import json
import matplotlib.pyplot as plt
import os
from glob import glob
import numpy as np

def generate_precise_stacked_plots():
    # Find the latest results file
    files = sorted(glob("benchmarks/results/full_turn_comparison_*.json"))
    if not files:
        print("No results found.")
        return
    
    with open(files[-1]) as f:
        data = json.load(f)
    
    os.makedirs("paper/figures", exist_ok=True)
    
    # 3 subplots: Input Linear, Input Log, Output
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 15), sharex=False) # Not sharing X because lengths differ
    
    # We will use two different X axes if needed, or one long one. 
    # Let's find the max turns to set the limit
    max_turns = max(len(data["linear"]["turns"]), len(data["scope"]["turns"]))

    for approach in ["linear", "scope"]:
        turns = data[approach]["turns"]
        inputs = [t["input_tokens"] for t in turns]
        outputs = [t["output_tokens"] for t in turns]
        x = list(range(1, len(inputs) + 1))
        
        main_color = '#e74c3c' if approach == 'linear' else '#2ecc71'
        label_prefix = 'Linear' if approach == 'linear' else 'ECM (SCOPE)'
        
        # Plotting
        for ax, vals, y_lab, is_log in zip([ax1, ax2], [inputs, inputs], ['Input (Linear)', 'Input (Log)'], [False, True]):
            ax.plot(x, vals, label=f"{label_prefix}", linewidth=2.5, color=main_color, alpha=0.9)
            ax.fill_between(x, vals, alpha=0.05, color=main_color)
            if is_log: ax.set_yscale('log')
            ax.set_ylabel(y_lab)

        marker = 'o' if approach == 'linear' else 's'
        ax3.scatter(x, outputs, label=f"{label_prefix} Output", color=main_color, marker=marker, s=40, alpha=0.6)
        ax3.plot(x, outputs, color=main_color, linewidth=1, alpha=0.2)
        ax3.set_ylabel('Output Tokens')

        # Add Task Boundaries for THIS approach
        last_task = -1
        for i, t in enumerate(turns):
            if t["task_idx"] > last_task and i > 0:
                for ax in [ax1, ax2, ax3]:
                    ax.axvline(x=i, color=main_color, linestyle='--', alpha=0.3, linewidth=1)
                # Label only on the first plot to avoid clutter
                ax1.text(i+0.2, ax1.get_ylim()[1]*0.9, f"T{t['task_idx']+1}", 
                        color=main_color, fontsize=8, fontweight='bold')
            last_task = t["task_idx"]

    # Global Styling
    ax1.set_title('Token Usage Dynamics: Linear vs. Explicit Context Management', fontsize=16, pad=25)
    ax3.set_xlabel('Cumulative API Turns (Calls)', fontsize=12)
    
    for ax in [ax1, ax2, ax3]:
        ax.grid(True, which="both", linestyle=':', alpha=0.5)
        ax.legend(loc='upper left', fontsize=10)
        ax.set_xlim(0, max_turns + 2)

    plt.tight_layout()
    plt.savefig("paper/figures/stacked_comprehensive_analysis.png", dpi=300)
    print("Saved paper/figures/stacked_comprehensive_analysis.png with multi-approach boundaries")

if __name__ == "__main__":
    generate_precise_stacked_plots()
