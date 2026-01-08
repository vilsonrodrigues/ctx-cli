# 3. Method

We present **SPACE (Self-Partitioned Agent Context Environment)**, a training-free framework that provides agents with deliberate control over their working memory. Section 3.1 defines the core data structures. Section 3.2 details the tiered memory architecture. Section 3.3 describes the pull-based context composition. Section 3.4 formalizes the command interface and navigation topology.

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

SPACE implements a three-tier memory system inspired by Endel Tulving's theory of human memory:

1.  **Working Memory (ephemeral):** Messages in the current scope. Cleared on `return`.
2.  **Episodic Memory (`note`):** Captures high-entropy, localized events. These are the "events" of the reasoning process—what was tried, what failed, and what files were changed. Persists within the scope and is queryable via `notes`.
3.  **Semantic Memory (`insight`):** Captures low-entropy, global patterns. These are the "rules" of the codebase—naming conventions, architectural constraints, and reusable logic patterns. Persists globally across all scopes.

## 3.3 Pull-Based Context Composition

Unlike traditional memory systems that inject history automatically, SPACE adopts a **Pull-Based Strategy**.

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
| `return -m "..."` | Finalize S, return to Main | Working | Closes scope permanently, saves summary to main |
| `note -m "..."` | N_S ← n_new | Episodic | Records event in current scope |
| `insight -m "..."` | I ← i_new | Semantic | Records global knowledge |
| `notes [scope]` | Output N_scope or N_all | Episodic | Retrieves episodic memory |
| `insights` | Output I | Semantic | Retrieves semantic memory |
| `status` | Output state | Meta | Shows current scope, message count, memory stats |

### 3.4.1 Radial Scope Navigation (Hub-and-Spoke)

SPACE implements a **radial navigation topology** with strict constraints:

```
main → scope → return → main → scope → return → main
```

The `main` context acts as the **stable hub** of cognition, while temporary scopes branch off as **spokes** to handle specific sub-tasks. Unlike graph-based navigation where agents can jump between arbitrary scopes, SPACE enforces:

1. **Scopes only from main**: The `scope` command is only valid from `main`
2. **Return only from scopes**: The `return` command is only valid from within a scope
3. **No nesting**: Scopes cannot create sub-scopes
4. **No reentry**: Closed scopes cannot be reopened

```
        ┌─── fix/auth-bug (closed)
main ───┼─── plan/migration (closed)
        └─── implement/feature (active)
```

This topology enforces **Cognitive Discipline**:
- **Strict Isolation:** Scopes cannot communicate directly. All information transfer must pass through `main` via `return` summaries.
- **Cognitive Reset:** Returning to `main` clears the working memory, preventing "rumination" on messy details.
- **Forced Consolidation:** The agent must explicitly summarize its findings before switching contexts.

### 3.4.2 Transition Semantics

Transitions follow a strict protocol to ensure causal continuity:

**On `scope` (Departure from main):** The `-m` message documents the *intent* of the new branch (e.g., "Investigating auth bug"). This is stored as a departure note in `main`.

**On `return` (Arrival back to main):** The `-m` message documents the *outcome* of the closed branch (e.g., "Fixed auth bug by adding null check"). This summary becomes the permanent record—the detailed execution history within the scope is discarded.

This ensures that `main` contains a high-level log of intents and outcomes, while detailed reasoning is encapsulated and eventually discarded.

### 3.4.3 The Planning Workflow

To maintain cognitive continuity without context pollution, SPACE agents utilize **Planning Scopes** (e.g., `plan/new-task`). The workflow:

1. **Open thinking space:** `scope plan/task-x -m "Reasoning about task X"`
2. **Pull knowledge:** `insights` and `notes` to load relevant context
3. **Synthesize plan:** Reasoning occurs in isolated working memory
4. **Commit result:** `return -m "[SUMMARY]...[DECISION]...[NEXT]..."`
5. **Execute:** `scope implement/task-x -m "Implementing plan"`

This pattern ensures that planning complexity does not bloat implementation context, while preserving the plan's conclusions in main's memory.

## 3.5 Token Economics

### 3.5.1 Context Growth Models

**Linear Agent**: Context grows monotonically with turn count $t$:
$$|C_{\text{linear}}(t)| = |P_{\text{sys}}| + \sum_{i=1}^{t} |\tau_i| = O(t)$$

**SPACE Agent**: Context is bounded by current scope size $k$:
$$|C_{\text{SPACE}}(t)| = |P_{\text{sys}}| + |M_{S_{\text{current}}}| = O(k)$$

### 3.5.2 The Sawtooth Pattern

SPACE context follows a characteristic sawtooth pattern:

$$|C_{\text{SPACE}}(t)| = \begin{cases}
|P_{\text{sys}}| + (t - t_{\text{enter}}) \cdot \bar{\tau} & \text{within scope (growing)} \\
|P_{\text{sys}}| + |m_{\text{summary}}| & \text{after return (reset)}
\end{cases}$$

Each `return` clears working memory, creating periodic drops that bound peak context.

### 3.5.3 Memory Tiers and Token Cost

SPACE's three-tier architecture separates context cost from memory storage:

| Tier | Growth | In Context | Token Cost |
|------|--------|------------|------------|
| Working ($M_S$) | Resets each scope | Always | $O(k)$ per call |
| Episodic ($N_S$) | Accumulates | On `notes` query | Deferred |
| Semantic ($\mathcal{I}$) | Accumulates | On `insights` query | Deferred |

**Total Memory**:
$$|\mathcal{M}(t)| = |M_{S_{\text{current}}}| + \sum_{S \in \mathcal{S}} |N_S| + |\mathcal{I}|$$

Memory grows with note/insight creation, but **context remains bounded** because notes and insights are only loaded on explicit query.

### 3.5.4 Cumulative Cost Analysis

**Linear Agent** (quadratic):
$$\text{Total}_{\text{linear}} = O(T^2) \quad \text{where } T = \text{total turns}$$

**SPACE Agent** (linear in tasks):
$$\text{Total}_{\text{SPACE}} = O(n \cdot \bar{k}^2) \quad \text{where } n = \text{number of scopes}$$

**Token Savings**: For $n$ sequential tasks:
$$\text{Savings} \approx 1 - \frac{1}{n}$$

With 15 tasks: theoretical ~93% savings, empirical ~88% (accounting for prompt overhead).

### 3.5.5 Complexity Summary

| Metric | Linear | SPACE |
|--------|--------|-------|
| Context per call | $O(t)$ | $O(k)$ |
| Peak context | $O(T)$ | $O(k_{\max})$ |
| Cumulative cost | $O(T^2)$ | $O(n \cdot \bar{k}^2)$ |
| Notes/Insights cost | N/A | Deferred (on query) |

This architecture enables agents to operate indefinitely, as the cost of a new task is decoupled from the history of previous tasks. Full mathematical derivations are provided in Appendix A.4.

## 3.6 Algorithm: SPACE Agent Loop

```
Algorithm 2: SPACE Agent Main Loop

Input: Task T, ContextStore C
Output: Result R

1. C.current_scope ← "main"
2. C.add_message("user", T)
3. while not done:
4.     context ← ComposeContext(C)  // Algorithm 1
5.     response ← LLM(context)
6.
7.     if response.has_tool_call("scope"):
8.         if C.current_scope ≠ "main":
9.             ERROR: "scope only valid from main"
10.        name ← response.tool_args.name
11.        message ← response.tool_args.message
12.        C.create_scope(name, departure_note=message)
13.        C.current_scope ← name
14.
15.    elif response.has_tool_call("return"):
16.        if C.current_scope = "main":
17.            ERROR: "return only valid from scope"
18.        message ← response.tool_args.message
19.        C.close_scope(summary=message)  // Clears working memory
20.        C.current_scope ← "main"
21.
22.    elif response.has_tool_call("note"):
23.        C.add_note(response.tool_args.message)
24.
25.    elif response.has_tool_call("insight"):
26.        C.add_insight(response.tool_args.message)  // Global
27.
28.    elif response.has_tool_call("notes"):
29.        scope ← response.tool_args.scope or "all"
30.        return C.get_notes(scope)
31.
32.    elif response.has_tool_call("insights"):
33.        return C.get_insights()
34.
35.    elif response.is_final:
36.        R ← response.content
37.        done ← true
38.
39. return R
```

The key invariant is that `C.current_scope` alternates between `main` and exactly one active scope, never allowing nesting or arbitrary graph traversal.