#!/usr/bin/env python3
"""
Generate SPACE architecture diagram showing:
- Radial navigation (hub-and-spoke)
- Message visibility (active vs deactivated)
- Notes (episodic memory)
- Insights (semantic memory)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle
from matplotlib.lines import Line2D
import numpy as np

# Set up the figure
fig, ax = plt.subplots(1, 1, figsize=(14, 10))
ax.set_xlim(0, 14)
ax.set_ylim(0, 10)
ax.set_aspect('equal')
ax.axis('off')

# Colors
MAIN_COLOR = '#2563eb'  # Blue
SCOPE_ACTIVE_COLOR = '#16a34a'  # Green
SCOPE_CLOSED_COLOR = '#9ca3af'  # Gray
MESSAGE_ACTIVE = '#dbeafe'  # Light blue
MESSAGE_INACTIVE = '#e5e7eb'  # Light gray
NOTE_COLOR = '#fef3c7'  # Yellow/amber
INSIGHT_COLOR = '#ddd6fe'  # Purple
ARROW_COLOR = '#374151'
TEXT_COLOR = '#111827'

def draw_rounded_box(ax, x, y, width, height, color, alpha=1.0, label=None, fontsize=9):
    """Draw a rounded rectangle with optional label"""
    box = FancyBboxPatch((x, y), width, height,
                         boxstyle="round,pad=0.02,rounding_size=0.1",
                         facecolor=color, edgecolor='#374151',
                         linewidth=1.5, alpha=alpha)
    ax.add_patch(box)
    if label:
        ax.text(x + width/2, y + height/2, label,
                ha='center', va='center', fontsize=fontsize,
                color=TEXT_COLOR, fontweight='bold')

def draw_message(ax, x, y, text, active=True, width=2.2):
    """Draw a message box"""
    color = MESSAGE_ACTIVE if active else MESSAGE_INACTIVE
    alpha = 1.0 if active else 0.5
    box = FancyBboxPatch((x, y), width, 0.35,
                         boxstyle="round,pad=0.01,rounding_size=0.05",
                         facecolor=color, edgecolor='#6b7280' if active else '#d1d5db',
                         linewidth=1, alpha=alpha)
    ax.add_patch(box)
    ax.text(x + width/2, y + 0.175, text, ha='center', va='center',
            fontsize=7, color=TEXT_COLOR if active else '#9ca3af',
            style='italic' if not active else 'normal')

def draw_note(ax, x, y, text, width=1.8):
    """Draw a note (episodic memory)"""
    box = FancyBboxPatch((x, y), width, 0.3,
                         boxstyle="round,pad=0.01,rounding_size=0.03",
                         facecolor=NOTE_COLOR, edgecolor='#f59e0b',
                         linewidth=1.5)
    ax.add_patch(box)
    ax.text(x + width/2, y + 0.15, f"[N] {text}", ha='center', va='center',
            fontsize=6, color='#92400e')

def draw_insight(ax, x, y, text, width=2.5):
    """Draw an insight (semantic memory)"""
    box = FancyBboxPatch((x, y), width, 0.35,
                         boxstyle="round,pad=0.01,rounding_size=0.03",
                         facecolor=INSIGHT_COLOR, edgecolor='#7c3aed',
                         linewidth=1.5)
    ax.add_patch(box)
    ax.text(x + width/2, y + 0.175, f"[I] {text}", ha='center', va='center',
            fontsize=6, color='#5b21b6')

def draw_scope_box(ax, x, y, width, height, title, active=True):
    """Draw a scope container"""
    color = SCOPE_ACTIVE_COLOR if active else SCOPE_CLOSED_COLOR
    alpha = 1.0 if active else 0.4

    # Main box
    box = FancyBboxPatch((x, y), width, height,
                         boxstyle="round,pad=0.02,rounding_size=0.15",
                         facecolor='white', edgecolor=color,
                         linewidth=2.5 if active else 1.5, alpha=alpha,
                         linestyle='-' if active else '--')
    ax.add_patch(box)

    # Title bar
    title_box = FancyBboxPatch((x, y + height - 0.4), width, 0.4,
                               boxstyle="round,pad=0.01,rounding_size=0.1",
                               facecolor=color, edgecolor=color,
                               alpha=alpha)
    ax.add_patch(title_box)

    status = "ACTIVE" if active else "CLOSED"
    ax.text(x + width/2, y + height - 0.2, f"{title} [{status}]",
            ha='center', va='center', fontsize=9,
            color='white' if active else '#4b5563', fontweight='bold')

# ============================================
# MAIN CONTEXT (Hub)
# ============================================
main_x, main_y = 5.5, 4
main_w, main_h = 3, 5.5

# Draw main scope
box = FancyBboxPatch((main_x, main_y), main_w, main_h,
                     boxstyle="round,pad=0.02,rounding_size=0.2",
                     facecolor='white', edgecolor=MAIN_COLOR,
                     linewidth=3)
ax.add_patch(box)

# Main title
title_box = FancyBboxPatch((main_x, main_y + main_h - 0.5), main_w, 0.5,
                           boxstyle="round,pad=0.01,rounding_size=0.15",
                           facecolor=MAIN_COLOR, edgecolor=MAIN_COLOR)
ax.add_patch(title_box)
ax.text(main_x + main_w/2, main_y + main_h - 0.25, "main (HUB)",
        ha='center', va='center', fontsize=11, color='white', fontweight='bold')

# Messages in main
draw_message(ax, main_x + 0.4, main_y + 4.3, "User: Fix auth bug", active=True)
draw_message(ax, main_x + 0.4, main_y + 3.8, "→ scope fix/auth", active=True)
draw_message(ax, main_x + 0.4, main_y + 3.3, "← return: Fixed null check", active=True)
draw_message(ax, main_x + 0.4, main_y + 2.8, "User: Add feature", active=True)
draw_message(ax, main_x + 0.4, main_y + 2.3, "→ scope feat/new", active=True)

# Label for main messages
ax.text(main_x + 0.2, main_y + 4.75, "Working Memory (always visible)",
        fontsize=7, color='#6b7280', style='italic')

# ============================================
# SCOPE 1: fix/auth (CLOSED)
# ============================================
scope1_x, scope1_y = 0.3, 5.5
scope1_w, scope1_h = 2.8, 3.8

draw_scope_box(ax, scope1_x, scope1_y, scope1_w, scope1_h, "fix/auth", active=False)

# Deactivated messages (grayed out)
draw_message(ax, scope1_x + 0.3, scope1_y + 2.9, "Read auth.py", active=False)
draw_message(ax, scope1_x + 0.3, scope1_y + 2.4, "Found null error", active=False)
draw_message(ax, scope1_x + 0.3, scope1_y + 1.9, "Edit: add check", active=False)
draw_message(ax, scope1_x + 0.3, scope1_y + 1.4, "Test: passed", active=False)

# Note in closed scope (still accessible!)
draw_note(ax, scope1_x + 0.5, scope1_y + 0.7, "null check pattern")
draw_note(ax, scope1_x + 0.5, scope1_y + 0.3, "auth.py:142")

# Label
ax.text(scope1_x + scope1_w/2, scope1_y + 3.5, "Messages deactivated",
        ha='center', fontsize=7, color='#9ca3af', style='italic')

# ============================================
# SCOPE 2: feat/new (ACTIVE)
# ============================================
scope2_x, scope2_y = 10.5, 5.5
scope2_w, scope2_h = 3.2, 3.8

draw_scope_box(ax, scope2_x, scope2_y, scope2_w, scope2_h, "feat/new", active=True)

# Active messages
draw_message(ax, scope2_x + 0.3, scope2_y + 2.9, "Read feature spec", active=True, width=2.6)
draw_message(ax, scope2_x + 0.3, scope2_y + 2.4, "Design API", active=True, width=2.6)
draw_message(ax, scope2_x + 0.3, scope2_y + 1.9, "Implement handler", active=True, width=2.6)

# Note being created
draw_note(ax, scope2_x + 0.5, scope2_y + 0.9, "uses @auth decorator", width=2.2)

# Label
ax.text(scope2_x + scope2_w/2, scope2_y + 3.5, "Messages in context",
        ha='center', fontsize=7, color='#16a34a', style='italic')

# ============================================
# INSIGHTS (Global - Bottom)
# ============================================
insight_y = 0.8
ax.text(7, insight_y + 1.2, "Semantic Memory (Global Insights)",
        ha='center', fontsize=10, color='#7c3aed', fontweight='bold')

draw_insight(ax, 2.5, insight_y, "All endpoints need @authenticated", width=3.5)
draw_insight(ax, 6.5, insight_y, "Use pytest for testing", width=2.8)
draw_insight(ax, 10, insight_y, "Error handling: try/except", width=3)

# Dashed line showing global scope
ax.plot([0.5, 13.5], [insight_y + 0.6, insight_y + 0.6],
        linestyle='--', color='#7c3aed', alpha=0.3, linewidth=1)
ax.plot([0.5, 13.5], [insight_y - 0.2, insight_y - 0.2],
        linestyle='--', color='#7c3aed', alpha=0.3, linewidth=1)

# ============================================
# ARROWS (Transitions)
# ============================================
# Arrow from main to scope1 (departure)
ax.annotate('', xy=(scope1_x + scope1_w, scope1_y + scope1_h/2 + 0.5),
            xytext=(main_x, main_y + main_h - 1.5),
            arrowprops=dict(arrowstyle='->', color=SCOPE_CLOSED_COLOR,
                          connectionstyle='arc3,rad=-0.2', linewidth=1.5, linestyle='--'))

# Arrow from scope1 back to main (return)
ax.annotate('', xy=(main_x, main_y + main_h - 2),
            xytext=(scope1_x + scope1_w, scope1_y + scope1_h/2),
            arrowprops=dict(arrowstyle='->', color=SCOPE_CLOSED_COLOR,
                          connectionstyle='arc3,rad=-0.2', linewidth=1.5, linestyle='--'))

# Arrow from main to scope2 (active)
ax.annotate('', xy=(scope2_x, scope2_y + scope2_h/2 + 0.3),
            xytext=(main_x + main_w, main_y + 2.5),
            arrowprops=dict(arrowstyle='->', color=SCOPE_ACTIVE_COLOR,
                          connectionstyle='arc3,rad=0.2', linewidth=2))

# ============================================
# CONTEXT WINDOW INDICATOR
# ============================================
# Box showing what's "in context"
ctx_box = FancyBboxPatch((main_x - 0.3, main_y - 0.3), main_w + 0.6 + scope2_w + 2.3, main_h + 0.6,
                         boxstyle="round,pad=0.02,rounding_size=0.2",
                         facecolor='none', edgecolor='#ef4444',
                         linewidth=2, linestyle=':')
ax.add_patch(ctx_box)

ax.text(10.5, main_y + main_h + 0.5, "Context Window (what LLM sees)",
        ha='center', fontsize=9, color='#ef4444', fontweight='bold')

# ============================================
# LEGEND
# ============================================
legend_elements = [
    mpatches.Patch(facecolor=MESSAGE_ACTIVE, edgecolor='#6b7280', label='Active Message'),
    mpatches.Patch(facecolor=MESSAGE_INACTIVE, edgecolor='#d1d5db', label='Deactivated Message'),
    mpatches.Patch(facecolor=NOTE_COLOR, edgecolor='#f59e0b', label='Note (Episodic)'),
    mpatches.Patch(facecolor=INSIGHT_COLOR, edgecolor='#7c3aed', label='Insight (Semantic)'),
    Line2D([0], [0], color=MAIN_COLOR, linewidth=3, label='main (Hub)'),
    Line2D([0], [0], color=SCOPE_ACTIVE_COLOR, linewidth=2, label='Active Scope'),
    Line2D([0], [0], color=SCOPE_CLOSED_COLOR, linewidth=2, linestyle='--', label='Closed Scope'),
]

ax.legend(handles=legend_elements, loc='upper left', fontsize=8,
          framealpha=0.95, edgecolor='#e5e7eb')

# ============================================
# TITLE
# ============================================
ax.text(7, 9.7, "SPACE: Self-Partitioned Agent Context Environment",
        ha='center', fontsize=14, fontweight='bold', color=TEXT_COLOR)
ax.text(7, 9.35, "Radial Navigation with Three-Tier Memory",
        ha='center', fontsize=10, color='#6b7280')

# ============================================
# ANNOTATIONS
# ============================================
# Annotation for deactivated messages
ax.annotate('Messages cleared\non return',
            xy=(scope1_x + scope1_w/2, scope1_y + 2),
            xytext=(0.3, 3.5),
            fontsize=8, color='#6b7280',
            arrowprops=dict(arrowstyle='->', color='#9ca3af',
                          connectionstyle='arc3,rad=0.3'))

# Annotation for notes persistence
ax.annotate('Notes persist\n(queryable via `notes`)',
            xy=(scope1_x + scope1_w/2, scope1_y + 0.5),
            xytext=(0.3, 2.2),
            fontsize=8, color='#92400e',
            arrowprops=dict(arrowstyle='->', color='#f59e0b',
                          connectionstyle='arc3,rad=-0.2'))

# Annotation for insights
ax.annotate('Insights available\nin ALL scopes',
            xy=(7, insight_y + 0.5),
            xytext=(7, 2.5),
            ha='center',
            fontsize=8, color='#5b21b6',
            arrowprops=dict(arrowstyle='->', color='#7c3aed',
                          connectionstyle='arc3,rad=0'))

plt.tight_layout()
plt.savefig('/home/vilson-neto/Documents/msg-projects/ctx-cli/paper/figures/space_architecture.png',
            dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig('/home/vilson-neto/Documents/msg-projects/ctx-cli/paper/figures/space_architecture.pdf',
            bbox_inches='tight', facecolor='white')
print("Saved: space_architecture.png and space_architecture.pdf")
