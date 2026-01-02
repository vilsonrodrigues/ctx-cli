# 3. Method

We present **Explicit Context Management (ECM)**, a framework that provides agents with deliberate control over their working memory. Section 3.1 defines the core data structures. Section 3.2 details the tiered memory architecture. Section 3.3 describes the pull-based context composition. Section 3.4 formalizes the command interface and planning workflow.

## 3.1 Data Structures

The system relies on a **ContextStore** (C) that manages isolated reasoning contexts and tiered memories.

### 3.1.1 Scope (Reasoning Path)
A scope S is a distinct memory partition defined as:
$$ S = \langle M_S, N_S, H_S \rangle $$
Where:
- M_S is the **Working Memory**: A list of ephemeral messages (User, Assistant, Tool).
- N_S is the **Episodic Memory**: A stack of immutable technical notes representing progress.
- H_S is the **Head Note**: A semantic pointer situating the scope's origin.

### 3.1.2 Semantic Memory (Insights)
A global repository I stores universal truths or architectural patterns discovered by the agent:
$$ I = \{i_1, i_2, ..., i_n\} $$
Each insight i contains a content string and a timestamp, providing a durable knowledge base that persists across all scopes.

## 3.2 Tiered Memory Architecture

ECM implements a dual-tier memory system inspired by Endel Tulving's theory of human memory:

1.  **Episodic Memory (`note`):** Captures high-entropy, localized events. These are the "events" of the reasoning process—what was tried, what failed, and what files were changed.
2.  **Semantic Memory (`insight`):** Captures low-entropy, global patterns. These are the "rules" of the codebase—naming conventions, architectural constraints, and reusable logic patterns.

## 3.3 Pull-Based Context Composition

Unlike traditional memory systems that inject history automatically, ECM adopts a **Pull-Based Strategy**.

### Algorithm 1: Context Composition
**Input**: ContextStore C, SystemPrompt P_sys
**Output**: Message sequence P

1. P <- [P_sys]
2. S_active <- C.current_scope
3. M_clean <- ValidateToolSequence(S_active.messages)
4. P <- P + M_clean
5. **Return** P

*Rationale*: By removing automatic injection, the working memory remains constant regardless of the total history size. Knowledge is only loaded into the prompt when the agent explicitly requests it via tools (e.g., `ctx_cli insights`).

## 3.4 Command Interface and Planning Workflow

The model interacts with C through a structured tool interface.

| Command | Logical Operation | Tier | Effect |
|---------|-------------------|------|--------|
| `scope <name> -m "..."` | S_origin -> S_new | Working | Creates a clean reasoning space. |
| `note -m "..."` | N_S <- n_new | Episodic | Records a technical event in current scope. |
| `insight -m "..."` | I <- i_new | Semantic | Records a global rule or pattern. |
| `notes` | Output N_all | Episodic | Returns global history from all scopes. |
| `insights` | Output I | Semantic | Returns all global project truths. |

### 3.4.1 The Planning Workflow
To maintain cognitive continuity without context pollution, ECM agents utilize **Planning Scopes** (e.g., `plan/new-task`). The agent opens a clean scope, pulls relevant insights and notes, synthesizes a plan, and returns to `main` with only the conclusion. This "thinking space" ensures that the complexity of planning does not bloat the implementation context.

## 3.5 Token Economics

- **Linear Complexity**: Tokens ~ O(n), where n is the total interaction count.
- **ECM Complexity**: Tokens ~ O(1) + O(m), where m is the current sub-task size.

This architecture enables agents to operate in large-scale repositories for indefinite periods, as the cost of a new task is decoupled from the history of previous tasks.