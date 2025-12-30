"""
Generate publication-quality plots for the paper.

Usage:
    uv run python generate_plots.py

Generates visualization of scope isolation with message inheritance.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# Set publication style
plt.rcParams.update({
    'font.size': 10,
    'font.family': 'sans-serif',
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'legend.fontsize': 9,
    'figure.figsize': (14, 10),
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})


def plot_scope_visibility():
    """
    Figure: Scope isolation with message inheritance and visibility.

    Shows:
    - main scope with original messages
    - step-1 inherits from main, adds own messages
    - step-2 inherits from main (not step-1), adds own messages
    - Messages visible (■) vs hidden (□) per scope
    """
    fig, ax = plt.subplots(figsize=(16, 12))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 12)
    ax.axis('off')
    ax.set_title('Scope Isolation: Message Visibility Across Scopes', fontsize=14, fontweight='bold', pad=20)

    # Colors
    MAIN_COLOR = '#e6f2ff'
    STEP1_COLOR = '#fff2e6'
    STEP2_COLOR = '#e6ffe6'
    VISIBLE_COLOR = '#2ca02c'
    HIDDEN_COLOR = '#cccccc'
    NOTE_COLOR = '#ffffcc'

    # === MAIN SCOPE ===
    main_box = FancyBboxPatch((0.5, 0.5), 4.5, 11, boxstyle="round,pad=0.1",
                               facecolor=MAIN_COLOR, edgecolor='#0066cc', linewidth=2)
    ax.add_patch(main_box)
    ax.text(2.75, 11.2, 'MAIN (current)', ha='center', fontsize=12, fontweight='bold', color='#0066cc')

    # Main messages
    main_msgs = [
        ('t=1', 'User', 'Start the task', VISIBLE_COLOR),
        ('t=2', 'Asst', 'Creating scope step-1', VISIBLE_COLOR),
        ('t=3', 'Tool', 'scope step-1 -m "..."', VISIBLE_COLOR),
        ('', '', '─── step-1 work (hidden) ───', HIDDEN_COLOR),
        ('t=7', 'Asst', '[← step-1] Bug found', VISIBLE_COLOR),
        ('t=8', 'User', 'Now create step-2', VISIBLE_COLOR),
        ('t=9', 'Asst', 'Creating scope step-2', VISIBLE_COLOR),
        ('t=10', 'Tool', 'scope step-2 -m "..."', VISIBLE_COLOR),
        ('', '', '─── step-2 work (hidden) ───', HIDDEN_COLOR),
        ('t=14', 'Asst', '[← step-2] Model done', VISIBLE_COLOR),
    ]

    y_pos = 10.5
    for t, role, content, color in main_msgs:
        symbol = '■' if color == VISIBLE_COLOR else '□'
        if '───' in content:
            ax.text(2.75, y_pos, content, ha='center', fontsize=8, color=HIDDEN_COLOR, style='italic')
        else:
            ax.text(0.7, y_pos, f'{symbol}', fontsize=10, color=color, fontweight='bold')
            ax.text(1.1, y_pos, f'{t}', fontsize=8, color='gray')
            ax.text(1.6, y_pos, f'{role}:', fontsize=9, fontweight='bold')
            ax.text(2.3, y_pos, content[:25], fontsize=8)
        y_pos -= 0.9

    # Notes section in main
    ax.add_patch(FancyBboxPatch((0.7, 0.7), 4.1, 1.8, boxstyle="round,pad=0.05",
                                 facecolor=NOTE_COLOR, edgecolor='#cc9900', linewidth=1))
    ax.text(2.75, 2.3, 'NOTES (episodic memory)', ha='center', fontsize=9, fontweight='bold', color='#cc6600')
    ax.text(0.9, 1.9, '[→ step-1] Investigating bug', fontsize=8)
    ax.text(0.9, 1.4, '[← step-1] Bug found: timeout=1s', fontsize=8)
    ax.text(0.9, 0.9, '[→ step-2] Creating model', fontsize=8)

    # === STEP-1 SCOPE ===
    step1_box = FancyBboxPatch((5.5, 0.5), 4.5, 11, boxstyle="round,pad=0.1",
                                facecolor=STEP1_COLOR, edgecolor='#cc6600', linewidth=2)
    ax.add_patch(step1_box)
    ax.text(7.75, 11.2, 'STEP-1', ha='center', fontsize=12, fontweight='bold', color='#cc6600')

    # Step-1 messages (inherits t=1,t=2 from main)
    step1_msgs = [
        ('t=1', 'User', 'Start the task', VISIBLE_COLOR, 'inherited'),
        ('t=2', 'Asst', 'Creating scope step-1', VISIBLE_COLOR, 'inherited'),
        ('t=3', 'Tool', 'scope step-1 -m "..."', HIDDEN_COLOR, ''),  # transition tool call
        ('t=4', 'User', 'Read the config file', VISIBLE_COLOR, 'own'),
        ('t=5', 'Asst', 'Config shows timeout=1s', VISIBLE_COLOR, 'own'),
        ('t=6', 'Tool', 'goto main -m "bug"', VISIBLE_COLOR, 'own'),
        ('', '', '', '', ''),  # spacer
        ('t=7+', '', '(messages after goto hidden)', HIDDEN_COLOR, ''),
    ]

    y_pos = 10.5
    for t, role, content, color, tag in step1_msgs:
        if not content:
            y_pos -= 0.9
            continue
        symbol = '■' if color == VISIBLE_COLOR else '□'
        ax.text(5.7, y_pos, f'{symbol}', fontsize=10, color=color, fontweight='bold')
        ax.text(6.1, y_pos, f'{t}', fontsize=8, color='gray')
        if role:
            ax.text(6.6, y_pos, f'{role}:', fontsize=9, fontweight='bold')
            ax.text(7.3, y_pos, content[:22], fontsize=8)
        else:
            ax.text(6.6, y_pos, content, fontsize=8, color=HIDDEN_COLOR, style='italic')
        if tag == 'inherited':
            ax.text(9.7, y_pos, '← inherited', fontsize=7, color='#888888', style='italic')
        elif tag == 'own':
            ax.text(9.7, y_pos, '← own', fontsize=7, color='#cc6600', style='italic')
        y_pos -= 0.9

    # Notes section in step-1
    ax.add_patch(FancyBboxPatch((5.7, 0.7), 4.1, 1.5, boxstyle="round,pad=0.05",
                                 facecolor=NOTE_COLOR, edgecolor='#cc9900', linewidth=1))
    ax.text(7.75, 2.0, 'NOTES', ha='center', fontsize=9, fontweight='bold', color='#cc6600')
    ax.text(5.9, 1.5, '[abc12] timeout was 1s not 3600s', fontsize=8)
    ax.text(5.9, 1.0, '[def34] Fixed in config.py', fontsize=8)

    # === STEP-2 SCOPE ===
    step2_box = FancyBboxPatch((10.5, 0.5), 4.5, 11, boxstyle="round,pad=0.1",
                                facecolor=STEP2_COLOR, edgecolor='#009900', linewidth=2)
    ax.add_patch(step2_box)
    ax.text(12.75, 11.2, 'STEP-2', ha='center', fontsize=12, fontweight='bold', color='#009900')

    # Step-2 messages (inherits from main at t=8, NOT from step-1)
    step2_msgs = [
        ('t=1', 'User', 'Start the task', VISIBLE_COLOR, 'inherited'),
        ('t=2', 'Asst', 'Creating scope step-1', VISIBLE_COLOR, 'inherited'),
        ('t=3', '', '(step-1 work hidden)', HIDDEN_COLOR, ''),
        ('t=7', 'Asst', '[← step-1] Bug found', VISIBLE_COLOR, 'inherited'),
        ('t=8', 'User', 'Now create step-2', VISIBLE_COLOR, 'inherited'),
        ('t=9', 'Asst', 'Creating scope step-2', VISIBLE_COLOR, 'inherited'),
        ('t=10', 'Tool', 'scope step-2 -m "..."', HIDDEN_COLOR, ''),
        ('t=11', 'User', 'Create User model', VISIBLE_COLOR, 'own'),
        ('t=12', 'Asst', 'Creating dataclass...', VISIBLE_COLOR, 'own'),
        ('t=13', 'Tool', 'goto main -m "done"', VISIBLE_COLOR, 'own'),
    ]

    y_pos = 10.5
    for t, role, content, color, tag in step2_msgs:
        symbol = '■' if color == VISIBLE_COLOR else '□'
        ax.text(10.7, y_pos, f'{symbol}', fontsize=10, color=color, fontweight='bold')
        ax.text(11.1, y_pos, f'{t}', fontsize=8, color='gray')
        if role:
            ax.text(11.6, y_pos, f'{role}:', fontsize=9, fontweight='bold')
            ax.text(12.3, y_pos, content[:20], fontsize=8)
        else:
            ax.text(11.6, y_pos, content, fontsize=8, color=HIDDEN_COLOR, style='italic')
        if tag == 'inherited':
            ax.text(14.7, y_pos, '← inherited', fontsize=7, color='#888888', style='italic')
        elif tag == 'own':
            ax.text(14.7, y_pos, '← own', fontsize=7, color='#009900', style='italic')
        y_pos -= 0.9

    # Notes section in step-2
    ax.add_patch(FancyBboxPatch((10.7, 0.7), 4.1, 1.5, boxstyle="round,pad=0.05",
                                 facecolor=NOTE_COLOR, edgecolor='#cc9900', linewidth=1))
    ax.text(12.75, 2.0, 'NOTES', ha='center', fontsize=9, fontweight='bold', color='#cc6600')
    ax.text(10.9, 1.5, '[ghi56] User model created', fontsize=8)
    ax.text(10.9, 1.0, '[jkl78] Added validation', fontsize=8)

    # Legend
    ax.add_patch(FancyBboxPatch((0.5, -1.5), 15, 1.2, boxstyle="round,pad=0.1",
                                 facecolor='white', edgecolor='gray', linewidth=1))
    ax.text(1, -0.7, '■ = Visible in API call', fontsize=10, color=VISIBLE_COLOR, fontweight='bold')
    ax.text(5, -0.7, '□ = Hidden (different scope or transition)', fontsize=10, color=HIDDEN_COLOR)
    ax.text(11, -0.7, 'inherited = Copied from main at scope creation', fontsize=9, color='#888888', style='italic')

    # Arrows showing inheritance
    ax.annotate('', xy=(5.5, 10), xytext=(5, 10),
                arrowprops=dict(arrowstyle='->', color='#0066cc', lw=2))
    ax.text(4.5, 10.5, 'inherits\nt=1,t=2', fontsize=8, ha='center', color='#0066cc')

    ax.annotate('', xy=(10.5, 8), xytext=(5, 8),
                arrowprops=dict(arrowstyle='->', color='#0066cc', lw=2))
    ax.text(7.75, 8.5, 'inherits from main\n(NOT from step-1)', fontsize=8, ha='center', color='#0066cc')

    plt.tight_layout()
    plt.savefig('fig1_scope_visibility.png', bbox_inches='tight', pad_inches=0.2)
    plt.savefig('fig1_scope_visibility.pdf', bbox_inches='tight', pad_inches=0.2)
    plt.close()
    print("Generated: fig1_scope_visibility.png/pdf")


def plot_token_growth():
    """Figure: Token growth comparison - Linear vs Scope."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    steps = list(range(1, 13))
    linear_tokens = [2847, 5632, 8419, 11847, 14238, 16892, 19124, 21456, 22134, 22847, 23124, 23249]
    scope_tokens = [3124, 3891, 4256, 4512, 3987, 4891, 5234, 5891, 5124, 5567, 6012, 6353]

    # Left: Per-call tokens
    ax1.plot(steps, linear_tokens, 'o-', color='#d62728', linewidth=2, markersize=8, label='Linear')
    ax1.plot(steps, scope_tokens, 's-', color='#2ca02c', linewidth=2, markersize=8, label='Scope-based')
    ax1.fill_between(steps, linear_tokens, alpha=0.2, color='#d62728')
    ax1.fill_between(steps, scope_tokens, alpha=0.2, color='#2ca02c')

    # Mark scope switches
    for switch in [5, 9]:
        ax1.axvline(x=switch, color='gray', linestyle='--', alpha=0.5)
        ax1.annotate('scope\nswitch', xy=(switch, scope_tokens[switch-1]),
                    xytext=(switch + 0.3, scope_tokens[switch-1] + 3000),
                    fontsize=8, color='gray')

    ax1.annotate(f'Peak: {max(linear_tokens):,}', xy=(12, max(linear_tokens)),
                xytext=(9, max(linear_tokens) + 2000), fontsize=10, color='#d62728',
                arrowprops=dict(arrowstyle='->', color='#d62728'))
    ax1.annotate(f'Peak: {max(scope_tokens):,}\n(73% lower)', xy=(12, max(scope_tokens)),
                xytext=(9, max(scope_tokens) + 4000), fontsize=10, color='#2ca02c',
                arrowprops=dict(arrowstyle='->', color='#2ca02c'))

    ax1.set_xlabel('Task Step')
    ax1.set_ylabel('Tokens per API Call')
    ax1.set_title('Context Growth per Call')
    ax1.legend(loc='upper left')
    ax1.set_xlim(0.5, 12.5)
    ax1.set_ylim(0, 28000)
    ax1.set_xticks(steps)

    # Right: Cumulative tokens
    linear_cum = np.cumsum(linear_tokens)
    scope_cum = np.cumsum(scope_tokens)

    ax2.plot(steps, linear_cum, 'o-', color='#d62728', linewidth=2, markersize=8, label='Linear')
    ax2.plot(steps, scope_cum, 's-', color='#2ca02c', linewidth=2, markersize=8, label='Scope-based')
    ax2.fill_between(steps, linear_cum, scope_cum, alpha=0.3, color='#2ca02c', label='Savings')

    savings = (1 - scope_cum[-1] / linear_cum[-1]) * 100
    ax2.annotate(f'Total: {linear_cum[-1]:,}', xy=(12, linear_cum[-1]),
                xytext=(9, linear_cum[-1] + 10000), fontsize=10, color='#d62728',
                arrowprops=dict(arrowstyle='->', color='#d62728'))
    ax2.annotate(f'Total: {scope_cum[-1]:,}\n({savings:.0f}% savings)', xy=(12, scope_cum[-1]),
                xytext=(8, scope_cum[-1] + 25000), fontsize=10, color='#2ca02c',
                arrowprops=dict(arrowstyle='->', color='#2ca02c'))

    ax2.set_xlabel('Task Step')
    ax2.set_ylabel('Cumulative Tokens')
    ax2.set_title('Total Token Usage')
    ax2.legend(loc='upper left')
    ax2.set_xlim(0.5, 12.5)
    ax2.set_xticks(steps)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x/1000)}K'))

    plt.tight_layout()
    plt.savefig('fig2_token_growth.png')
    plt.savefig('fig2_token_growth.pdf')
    plt.close()
    print("Generated: fig2_token_growth.png/pdf")


def plot_workflow():
    """Figure: Workflow showing scope/goto/note command flow."""
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis('off')
    ax.set_title('Workflow: Scope Transitions and Note Placement', fontsize=14, fontweight='bold', pad=20)

    # Timeline
    ax.axhline(y=4, color='gray', linewidth=1, linestyle='-', alpha=0.3)

    # Main scope (center line)
    ax.plot([1, 13], [4, 4], 'b-', linewidth=3, label='main scope')

    # Step-1 branch (above)
    ax.plot([3, 3], [4, 6], 'orange', linewidth=2)
    ax.plot([3, 6], [6, 6], 'orange', linewidth=3)
    ax.plot([6, 6], [6, 4], 'orange', linewidth=2)

    # Step-2 branch (below)
    ax.plot([8, 8], [4, 2], 'green', linewidth=2)
    ax.plot([8, 11], [2, 2], 'green', linewidth=3)
    ax.plot([11, 11], [2, 4], 'green', linewidth=2)

    # Labels
    ax.text(7, 4.3, 'main', fontsize=11, fontweight='bold', color='blue')
    ax.text(4.5, 6.3, 'step-1', fontsize=11, fontweight='bold', color='orange')
    ax.text(9.5, 1.5, 'step-2', fontsize=11, fontweight='bold', color='green')

    # Events on main
    ax.plot(1, 4, 'ko', markersize=8)
    ax.text(1, 3.5, 't=1\nStart', ha='center', fontsize=8)

    ax.plot(3, 4, 'o', color='orange', markersize=10)
    ax.text(3, 3.3, 'scope step-1\n-m "investigating"', ha='center', fontsize=8)

    ax.plot(6, 4, 'o', color='orange', markersize=10)
    ax.text(6, 3.3, 'goto main\n-m "bug found"', ha='center', fontsize=8)

    ax.plot(8, 4, 'o', color='green', markersize=10)
    ax.text(8, 3.3, 'scope step-2\n-m "creating model"', ha='center', fontsize=8)

    ax.plot(11, 4, 'o', color='green', markersize=10)
    ax.text(11, 3.3, 'goto main\n-m "model done"', ha='center', fontsize=8)

    ax.plot(13, 4, 'ko', markersize=8)
    ax.text(13, 3.5, 't=end\nComplete', ha='center', fontsize=8)

    # Notes annotations
    # Note placement boxes
    ax.add_patch(FancyBboxPatch((2.3, 4.5), 1.4, 0.6, boxstyle="round,pad=0.05",
                                 facecolor='#ffffcc', edgecolor='#cc9900', linewidth=1))
    ax.text(3, 4.8, '[→ step-1]', ha='center', fontsize=8, fontweight='bold')
    ax.text(3, 5.3, 'note stays\nin ORIGIN', ha='center', fontsize=7, color='gray')

    ax.add_patch(FancyBboxPatch((5.3, 4.5), 1.4, 0.6, boxstyle="round,pad=0.05",
                                 facecolor='#ffffcc', edgecolor='#cc9900', linewidth=1))
    ax.text(6, 4.8, '[← step-1]', ha='center', fontsize=8, fontweight='bold')
    ax.text(6, 5.3, 'note goes to\nDESTINATION', ha='center', fontsize=7, color='gray')

    # Work in step-1
    ax.add_patch(FancyBboxPatch((3.5, 5.7), 2, 0.8, boxstyle="round,pad=0.05",
                                 facecolor='#fff2e6', edgecolor='orange', linewidth=1))
    ax.text(4.5, 6.1, 'work + notes', ha='center', fontsize=9)

    # Work in step-2
    ax.add_patch(FancyBboxPatch((8.5, 1.7), 2, 0.8, boxstyle="round,pad=0.05",
                                 facecolor='#e6ffe6', edgecolor='green', linewidth=1))
    ax.text(9.5, 2.1, 'work + notes', ha='center', fontsize=9)

    # Legend box
    ax.add_patch(FancyBboxPatch((0.3, 0.3), 13.4, 1.2, boxstyle="round,pad=0.1",
                                 facecolor='white', edgecolor='gray', linewidth=1))
    ax.text(1, 1.1, 'scope X -m "..."', fontsize=9, fontweight='bold')
    ax.text(1, 0.6, '→ Note [→ X] stays in ORIGIN (explains why leaving)', fontsize=8)
    ax.text(7, 1.1, 'goto X -m "..."', fontsize=9, fontweight='bold')
    ax.text(7, 0.6, '→ Note [← from] goes to DESTINATION (explains what bringing)', fontsize=8)

    plt.tight_layout()
    plt.savefig('fig3_workflow.png', bbox_inches='tight', pad_inches=0.2)
    plt.savefig('fig3_workflow.pdf', bbox_inches='tight', pad_inches=0.2)
    plt.close()
    print("Generated: fig3_workflow.png/pdf")


def plot_comparison_table():
    """Figure: Comparison with related work."""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.axis('off')
    ax.set_title('Comparison with Related Work', fontsize=14, fontweight='bold', pad=20)

    # Table data
    headers = ['Approach', 'Training\nRequired', 'External\nInfra', 'Context\nReduction', 'Explicit\nControl']
    data = [
        ['MemGPT [13]', 'No', 'Yes (DB)', 'Unbounded', 'No'],
        ['Mem0 [16]', 'No', 'Yes (Vector)', '~90%', 'No'],
        ['Context-Folding [2]', 'RL', 'No', '10×', 'No'],
        ['AgentFold [1]', 'Fine-tune', 'No', 'High', 'No'],
        ['HiAgent [3]', 'No', 'No', '35%', 'Partial'],
        ['Ours', 'No', 'No', '68%', 'Yes'],
    ]

    # Create table
    table = ax.table(
        cellText=data,
        colLabels=headers,
        loc='center',
        cellLoc='center',
        colColours=['#f0f0f0'] * len(headers),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 2)

    # Highlight our row
    for j in range(len(headers)):
        table[(len(data), j)].set_facecolor('#d4edda')
        table[(len(data), j)].set_text_props(fontweight='bold')

    plt.tight_layout()
    plt.savefig('fig4_comparison.png', bbox_inches='tight', pad_inches=0.3)
    plt.savefig('fig4_comparison.pdf', bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print("Generated: fig4_comparison.png/pdf")


if __name__ == '__main__':
    print("Generating publication plots...")
    print("=" * 50)
    plot_scope_visibility()
    plot_token_growth()
    plot_workflow()
    plot_comparison_table()
    print("=" * 50)
    print("All plots generated successfully!")
