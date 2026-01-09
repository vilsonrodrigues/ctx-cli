#!/usr/bin/env python3
"""
Generate Token Growth Comparison diagram showing:
- Linear growth (monotonic)
- SPACE growth (sawtooth pattern)
- Scope boundaries marked
"""

import matplotlib.pyplot as plt
import numpy as np

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# Data simulation
turns = np.arange(1, 26)

# Linear agent: monotonic growth
base_tokens = 1200  # System prompt
tokens_per_turn = 450
linear_tokens = base_tokens + turns * tokens_per_turn

# SPACE agent: sawtooth pattern
# Simulating 3 scopes with returns
space_base = 2000  # Higher base (SPACE system prompt)
scope_boundaries = [0, 8, 16, 25]  # Turn numbers where scopes change
space_tokens = []

for t in turns:
    if t <= 8:  # Scope 1
        scope_turn = t
        space_tokens.append(space_base + scope_turn * 350)
    elif t == 9:  # Return to main
        space_tokens.append(space_base + 200)  # Reset + summary
    elif t <= 16:  # Scope 2
        scope_turn = t - 9
        space_tokens.append(space_base + 200 + scope_turn * 350)
    elif t == 17:  # Return to main
        space_tokens.append(space_base + 400)  # Reset + 2 summaries
    else:  # Scope 3
        scope_turn = t - 17
        space_tokens.append(space_base + 400 + scope_turn * 350)

space_tokens = np.array(space_tokens)

# ============================================
# TOP PLOT: Token Growth Comparison
# ============================================
ax1.fill_between(turns, linear_tokens, alpha=0.3, color='#ef4444', label='Linear (area under curve)')
ax1.plot(turns, linear_tokens, 'o-', color='#ef4444', linewidth=2.5, markersize=6, label='Linear Agent')
ax1.fill_between(turns, space_tokens, alpha=0.3, color='#2563eb')
ax1.plot(turns, space_tokens, 's-', color='#2563eb', linewidth=2.5, markersize=6, label='SPACE Agent')

# Mark scope boundaries
for boundary in [9, 17]:
    ax1.axvline(x=boundary, color='#16a34a', linestyle='--', linewidth=1.5, alpha=0.7)
    ax1.annotate('return', xy=(boundary, space_tokens[boundary-1]),
                xytext=(boundary + 0.5, space_tokens[boundary-1] + 800),
                fontsize=9, color='#16a34a', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#16a34a'))

# Annotations
ax1.annotate('O(t) - Monotonic Growth',
            xy=(20, linear_tokens[19]),
            xytext=(15, linear_tokens[19] + 1500),
            fontsize=10, color='#ef4444',
            arrowprops=dict(arrowstyle='->', color='#ef4444'))

ax1.annotate('O(k) - Bounded by scope',
            xy=(22, space_tokens[21]),
            xytext=(17, space_tokens[21] - 2000),
            fontsize=10, color='#2563eb',
            arrowprops=dict(arrowstyle='->', color='#2563eb'))

ax1.set_ylabel('Context Tokens', fontsize=12)
ax1.set_title('Context Growth: Linear vs SPACE (Sawtooth Pattern)', fontsize=14, fontweight='bold')
ax1.legend(loc='upper left', fontsize=10)
ax1.set_ylim(0, max(linear_tokens) * 1.15)

# Shade scope regions
ax1.axvspan(1, 9, alpha=0.1, color='#f59e0b', label='Scope 1')
ax1.axvspan(9, 17, alpha=0.1, color='#10b981')
ax1.axvspan(17, 25, alpha=0.1, color='#8b5cf6')

# Add scope labels
ax1.text(5, max(linear_tokens) * 1.05, 'Scope: fix/auth', ha='center', fontsize=9, color='#92400e')
ax1.text(13, max(linear_tokens) * 1.05, 'Scope: feat/api', ha='center', fontsize=9, color='#047857')
ax1.text(21, max(linear_tokens) * 1.05, 'Scope: test/unit', ha='center', fontsize=9, color='#6d28d9')

# ============================================
# BOTTOM PLOT: Cumulative Cost Comparison
# ============================================
linear_cumulative = np.cumsum(linear_tokens)
space_cumulative = np.cumsum(space_tokens)

ax2.fill_between(turns, linear_cumulative, alpha=0.3, color='#ef4444')
ax2.plot(turns, linear_cumulative, 'o-', color='#ef4444', linewidth=2.5, markersize=6, label='Linear: O(T²)')
ax2.fill_between(turns, space_cumulative, alpha=0.3, color='#2563eb')
ax2.plot(turns, space_cumulative, 's-', color='#2563eb', linewidth=2.5, markersize=6, label='SPACE: O(n·k²)')

# Calculate savings
final_savings = (1 - space_cumulative[-1] / linear_cumulative[-1]) * 100

# Annotate savings
ax2.annotate(f'Token Savings: {final_savings:.1f}%',
            xy=(25, space_cumulative[-1]),
            xytext=(20, (linear_cumulative[-1] + space_cumulative[-1]) / 2),
            fontsize=12, fontweight='bold', color='#16a34a',
            bbox=dict(boxstyle='round', facecolor='#dcfce7', edgecolor='#16a34a'),
            arrowprops=dict(arrowstyle='->', color='#16a34a', connectionstyle='arc3,rad=0.2'))

# Add formula annotations
ax2.text(5, linear_cumulative[-1] * 0.85,
         r'$\sum_{t=1}^{T} |C_{linear}(t)| = O(T^2)$',
         fontsize=11, color='#ef4444',
         bbox=dict(boxstyle='round', facecolor='white', edgecolor='#ef4444', alpha=0.8))

ax2.text(5, linear_cumulative[-1] * 0.55,
         r'$\sum_{j=1}^{n} \sum_{t=1}^{k_j} |C_{SPACE}(t)| = O(n \cdot \bar{k}^2)$',
         fontsize=11, color='#2563eb',
         bbox=dict(boxstyle='round', facecolor='white', edgecolor='#2563eb', alpha=0.8))

ax2.set_xlabel('Turn Number', fontsize=12)
ax2.set_ylabel('Cumulative Tokens', fontsize=12)
ax2.set_title('Cumulative Token Cost (Area Under Curve)', fontsize=14, fontweight='bold')
ax2.legend(loc='upper left', fontsize=10)

# Add scope boundaries
for boundary in [9, 17]:
    ax2.axvline(x=boundary, color='#16a34a', linestyle='--', linewidth=1.5, alpha=0.7)

plt.tight_layout()
plt.savefig('/home/vilson-neto/Documents/msg-projects/ctx-cli/paper/figures/token_growth_comparison.png',
            dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig('/home/vilson-neto/Documents/msg-projects/ctx-cli/paper/figures/token_growth_comparison.pdf',
            bbox_inches='tight', facecolor='white')
print("Saved: token_growth_comparison.png and token_growth_comparison.pdf")

# Print statistics
print(f"\nStatistics:")
print(f"  Linear final context: {linear_tokens[-1]:,} tokens")
print(f"  SPACE final context: {space_tokens[-1]:,} tokens")
print(f"  Peak reduction: {(1 - space_tokens.max() / linear_tokens.max()) * 100:.1f}%")
print(f"  Linear cumulative: {linear_cumulative[-1]:,} tokens")
print(f"  SPACE cumulative: {space_cumulative[-1]:,} tokens")
print(f"  Total savings: {final_savings:.1f}%")
