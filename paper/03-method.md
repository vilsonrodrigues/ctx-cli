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

## 3.4 Command Interface

The model interacts with C through a structured tool interface implementing radial navigation.

| Command | Logical Operation | Tier | Effect |
|---------|-------------------|------|--------|
| `scope <name> -m "..."` | Create S_new, enter S_new | Working | Creates and enters a new reasoning space |
| `return -m "..."` | Finalize S, goto Main | Working | Closes scope, saves summary, returns to main |
| `note -m "..."` | N_S ← n_new | Episodic | Records event in current scope |
| `insight -m "..."` | I ← i_new | Semantic | Records global knowledge |
| `notes [scope]` | Output N_scope or N_all | Episodic | Retrieves episodic memory |
| `insights` | Output I | Semantic | Retrieves semantic memory |
| `status` | Output state | Meta | Shows current scope, message count, memory stats |
| `scopes` | Output all S | Meta | Lists all existing scopes |

### 3.4.1 Radial Scope Navigation

SPACE implements a **radial navigation topology** (Hub-and-Spoke). The `main` scope acts as the stable center of cognition, while temporary scopes branch off to handle specific sub-tasks.

```
        ┌─── research/approach-A
main ───┼─── research/approach-B
        └─── implement/chosen
```

This topology enforces **Cognitive Discipline**:
- **Strict Isolation:** Scopes cannot communicate directly. All information transfer must pass through `main` via `return` summaries.
- **Cognitive Reset:** Returning to `main` clears the working memory, preventing "rumination" on the messy details of the sub-task.
- **Forced Consolidation:** The agent cannot simply jump between tasks; it must explicitly summarize (commit) its findings before switching contexts.

### 3.4.2 Transition Semantics

Transitions follow a strict protocol to ensure causal continuity:

**On `scope` (Departure):** The `-m` message becomes a **departure note** stored in the `main` scope, documenting the *intent* of the new branch (e.g., "Investigating auth bug").

**On `return` (Arrival):** The `-m` message becomes a **summary note** stored in the `main` scope, documenting the *outcome* of the closed branch (e.g., "Fixed auth bug by adding null check").

This ensures that the `main` scope contains a high-level log of intents and outcomes, while the detailed execution history is encapsulated (and eventually discarded) within the sub-scopes.

### 3.4.3 The Planning Workflow

To maintain cognitive continuity without context pollution, ECM agents utilize **Planning Scopes** (e.g., `plan/new-task`). The workflow:

1. **Open thinking space:** `scope plan/task-x -m "Reasoning about task X"`
2. **Pull knowledge:** `insights` and `notes` to load relevant context
3. **Synthesize plan:** Reasoning occurs in isolated working memory
4. **Commit result:** `goto main -m "Plan complete: [summary]"`
5. **Execute:** `scope implement/task-x -m "Implementing plan"`

This pattern ensures that planning complexity does not bloat implementation context, while preserving the plan's conclusions in the main scope's episodic memory.

## 3.5 Token Economics

- **Linear Complexity**: Tokens ~ O(n), where n is the total interaction count.
- **ECM Complexity**: Tokens ~ O(1) + O(m), where m is the current sub-task size.

This architecture enables agents to operate in large-scale repositories for indefinite periods, as the cost of a new task is decoupled from the history of previous tasks.