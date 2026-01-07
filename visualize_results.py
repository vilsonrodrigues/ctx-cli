#!/usr/bin/env python3
"""
Quick visualization of demo results from JSON exports.
"""

import json
import glob
import matplotlib.pyplot as plt
from pathlib import Path

def load_results():
    """Load all JSON results from results/ directory."""
    results = []
    for json_file in sorted(glob.glob("results/coding_task_*.json")):
        with open(json_file) as f:
            data = json.load(f)
            data['filename'] = Path(json_file).name
            results.append(data)
    return results

def plot_comparison(results):
    """Create comparison plots."""
    if not results:
        print("No results found in results/ directory")
        return

    # Sort by num_steps
    results = sorted(results, key=lambda x: x['num_steps'])

    steps = [r['num_steps'] for r in results]
    linear_peak = [r['linear']['peak_working'] for r in results]
    ecm_peak = [r['ecm']['peak_working'] for r in results]
    linear_final = [r['linear']['final_working'] for r in results]
    ecm_final = [r['ecm']['final_working'] for r in results]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('ECM vs Linear: Context Management', fontsize=16, fontweight='bold')

    # Plot 1: Peak Working Context
    axes[0, 0].plot(steps, linear_peak, 'o-', color='#e74c3c', linewidth=2, markersize=8, label='Linear')
    axes[0, 0].plot(steps, ecm_peak, 's-', color='#2ecc71', linewidth=2, markersize=8, label='ECM')
    axes[0, 0].set_xlabel('Number of Steps', fontsize=11)
    axes[0, 0].set_ylabel('Peak Context (tokens)', fontsize=11)
    axes[0, 0].set_title('Peak Working Context During Task', fontsize=12, fontweight='bold')
    axes[0, 0].legend(fontsize=10)
    axes[0, 0].grid(True, alpha=0.3)

    # Plot 2: Final Working Context
    axes[0, 1].plot(steps, linear_final, 'o-', color='#e74c3c', linewidth=2, markersize=8, label='Linear')
    axes[0, 1].plot(steps, ecm_final, 's-', color='#2ecc71', linewidth=2, markersize=8, label='ECM')
    axes[0, 1].set_xlabel('Number of Steps', fontsize=11)
    axes[0, 1].set_ylabel('Final Context (tokens)', fontsize=11)
    axes[0, 1].set_title('Final Working Context at Completion', fontsize=12, fontweight='bold')
    axes[0, 1].legend(fontsize=10)
    axes[0, 1].grid(True, alpha=0.3)

    # Plot 3: Reduction Percentage
    peak_reduction = [(l - e) / l * 100 for l, e in zip(linear_peak, ecm_peak)]
    final_reduction = [(l - e) / l * 100 for l, e in zip(linear_final, ecm_final)]

    x = range(len(steps))
    width = 0.35
    axes[1, 0].bar([i - width/2 for i in x], peak_reduction, width, color='#3498db', alpha=0.8, label='Peak')
    axes[1, 0].bar([i + width/2 for i in x], final_reduction, width, color='#9b59b6', alpha=0.8, label='Final')
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels([f"{s} steps" for s in steps])
    axes[1, 0].set_ylabel('Reduction (%)', fontsize=11)
    axes[1, 0].set_title('ECM Context Reduction', fontsize=12, fontweight='bold')
    axes[1, 0].legend(fontsize=10)
    axes[1, 0].grid(True, alpha=0.3, axis='y')
    axes[1, 0].axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    # Plot 4: ECM Stats
    scopes = [r['ecm']['scopes'] for r in results]
    notes = [r['ecm']['notes'] for r in results]

    axes[1, 1].plot(steps, scopes, 'o-', color='#f39c12', linewidth=2, markersize=8, label='Scopes Created')
    axes[1, 1].plot(steps, notes, 's-', color='#1abc9c', linewidth=2, markersize=8, label='Notes Saved')
    axes[1, 1].set_xlabel('Number of Steps', fontsize=11)
    axes[1, 1].set_ylabel('Count', fontsize=11)
    axes[1, 1].set_title('ECM Usage Statistics', fontsize=12, fontweight='bold')
    axes[1, 1].legend(fontsize=10)
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()

    output_file = "results/ecm_comparison.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"📊 Visualization saved: {output_file}")

    # Print summary
    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70)
    for r in results:
        print(f"\n{r['num_steps']} steps:")
        print(f"  Peak:  {r['linear']['peak_working']:>6,} → {r['ecm']['peak_working']:>6,} ({r['savings']['peak_pct']:>5.1f}% reduction)")
        print(f"  Final: {r['linear']['final_working']:>6,} → {r['ecm']['final_working']:>6,} ({r['savings']['final_pct']:>5.1f}% reduction)")
        print(f"  ECM:   {r['ecm']['scopes']} scopes, {r['ecm']['notes']} notes")

if __name__ == "__main__":
    results = load_results()
    plot_comparison(results)
