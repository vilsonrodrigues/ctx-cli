# Figure 1: System Architecture

## ContextStore Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CONTEXT STORE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌───────────────┐      ┌───────────────┐      ┌───────────────┐          │
│   │     main      │      │    step-1     │      │    step-2     │          │
│   │   (scope)     │      │   (scope)     │      │   (scope)     │          │
│   ├───────────────┤      ├───────────────┤      ├───────────────┤          │
│   │               │      │               │      │               │          │
│   │ ┌───────────┐ │      │ ┌───────────┐ │      │ ┌───────────┐ │          │
│   │ │  NOTES    │ │      │ │  NOTES    │ │      │ │  NOTES    │ │          │
│   │ │ (episodic)│ │      │ │ (episodic)│ │      │ │ (episodic)│ │          │
│   │ ├───────────┤ │      │ ├───────────┤ │      │ ├───────────┤ │          │
│   │ │ [→step-1] │ │      │ │ [abc123]  │ │      │ │ [def456]  │ │          │
│   │ │ [←step-1] │ │      │ │ Found bug │ │      │ │ Created   │ │          │
│   │ │ [→step-2] │ │      │ │           │ │      │ │ model     │ │          │
│   │ │ [←step-2] │ │      │ └───────────┘ │      │ └───────────┘ │          │
│   │ └───────────┘ │      │               │      │               │          │
│   │               │      │ ┌───────────┐ │      │ ┌───────────┐ │          │
│   │ ┌───────────┐ │      │ │ MESSAGES  │ │      │ │ MESSAGES  │ │          │
│   │ │ MESSAGES  │ │      │ │ (working) │ │      │ │ (working) │ │          │
│   │ │ (working) │ │      │ ├───────────┤ │      │ ├───────────┤ │          │
│   │ ├───────────┤ │      │ │ (cleared) │ │      │ │ (cleared) │ │          │
│   │ │ User: ... │ │      │ │           │ │      │ │           │ │          │
│   │ │ Asst: ... │ │      │ └───────────┘ │      │ └───────────┘ │          │
│   │ └───────────┘ │      │               │      │               │          │
│   └───────┬───────┘      └───────────────┘      └───────────────┘          │
│           │                                                                  │
│           ▼                                                                  │
│     current_scope                                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Memory Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                     TWO-TIER MEMORY MODEL                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              EPISODIC MEMORY (Persistent)                │   │
│   │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │   │
│   │  │ Note 1  │  │ Note 2  │  │ Note 3  │  │ Note N  │    │   │
│   │  │ [hash]  │  │ [hash]  │  │ [hash]  │  │ [hash]  │    │   │
│   │  │ message │  │ message │  │ message │  │ message │    │   │
│   │  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │   │
│   │                                                          │   │
│   │  Properties: Compressed, Survives scope switches,        │   │
│   │              Always visible in scope, O(k) tokens        │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              │ Transition                        │
│                              ▼                                   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              WORKING MEMORY (Ephemeral)                  │   │
│   │  ┌──────────────────────────────────────────────────┐   │   │
│   │  │  Message 1  │  Message 2  │  ...  │  Message M   │   │   │
│   │  │  (user)     │  (assistant)│       │  (tool)      │   │   │
│   │  └──────────────────────────────────────────────────┘   │   │
│   │                                                          │   │
│   │  Properties: Full detail, Cleared on scope switch,       │   │
│   │              Only current scope visible, O(n) tokens     │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## LaTeX/TikZ Description

For generating a publication-quality figure:

```latex
% Figure 1: ContextStore Architecture
% Use TikZ with fit library for scope boxes
% Main elements:
% - Outer rectangle: ContextStore
% - Inner rectangles: Scopes (main, step-1, step-2)
% - Within each scope: Notes box (persistent), Messages box (ephemeral)
% - Arrow pointing to current_scope
% - Color coding: Notes in blue, Messages in orange
```
