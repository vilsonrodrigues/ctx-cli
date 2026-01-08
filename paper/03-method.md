# 3. Method

We present **SPACE (Self-Partitioned Agent Context Environment)**, a training-free framework that empowers agents with explicit architectural control over their working memory. This section formalizes the architecture: Section 3.1 defines the core data structures; Section 3.2 details the tiered memory hierarchy; Section 3.3 describes the pull-based context composition strategy; Section 3.4 specifies the command interface and navigation topology; and Section 3.5 provides a formal analysis of token economics.

## 3.1 Data Structures

The architecture is predicated on a **ContextStore** ($\mathcal{C}$) that manages isolated reasoning contexts and hierarchical memory tiers.

### 3.1.1 Scope (Reasoning Path)
A scope $S$ constitutes a distinct memory partition defined as a tuple:
$$ S = \langle M_S, N_S, H_S \rangle $$
Where:
*   $M_S$ is the **Working Memory**: An ordered sequence of ephemeral messages (User, Assistant, Tool) representing the immediate reasoning context.
*   $N_S$ is the **Episodic Memory**: A stack of immutable technical notes representing crystallized progress within the scope.
*   $H_S$ is the **Head Note**: A semantic pointer situating the scope's origin and intent relative to the parent context.

### 3.1.2 Semantic Memory (Insights)
A global repository $\mathcal{I}$ stores universal axioms and architectural patterns discovered by the agent:
$$ \mathcal{I} = \{i_1, i_2, ..., i_n\} $$
Each insight $i$ comprises a content string and temporal metadata, providing a durable knowledge base that persists across all scopes and sessions.

## 3.2 Tiered Memory Architecture

SPACE implements a three-tier memory system theoretically grounded in Tulving's taxonomy of human memory:

1.  **Working Memory (Ephemeral)**: Corresponds to messages ($M_S$) within the active scope. This tier is volatile and is explicitly cleared upon executing a `return` command, enforcing a "cognitive reset."
2.  **Episodic Memory (Persistent, Local)**: Managed via the `note` command, this tier captures high-entropy, localized events—specific implementation details, error analyses, and state changes. These memories persist within the scope structure and are retrievable via `notes`.
3.  **Semantic Memory (Persistent, Global)**: Managed via the `insight` command, this tier captures low-entropy, generalized patterns—architectural invariants, API contracts, and heuristic rules. These memories persist globally, accessible to all future scopes.

## 3.3 Pull-Based Context Composition

In contrast to conventional memory systems that proactively inject history into the context window, SPACE adopts a **Pull-Based Strategy** to minimize token consumption.

### Algorithm 1: Context Composition
**Input**: ContextStore $\mathcal{C}$, SystemPrompt $P_{sys}$
**Output**: Message sequence $P$

1.  $P \leftarrow [P_{sys}]$
2.  $S_{active} \leftarrow \mathcal{C}.current\_scope$
3.  $M_{clean} \leftarrow \text{ValidateToolSequence}(S_{active}.messages)$
4.  $P \leftarrow P \oplus M_{clean}$
5.  **Return** $P$

*Rationale*: By eliminating automatic history injection, the working memory size remains bounded by the current scope's duration ($O(k)$), independent of the total conversation history ($O(T)$). Historical knowledge is loaded into the prompt only upon explicit agent request (e.g., via `ctx_cli notes`), effectively shifting the retrieval burden from the architecture to the agent's reasoning process.

## 3.4 Command Interface

The agent interacts with $\mathcal{C}$ through a structured tool interface implementing a **Radial Navigation Topology**.

| Command | Logical Operation | Tier | Effect |
| :--- | :--- | :--- | :--- |
| `scope <name>` | Create $S_{new}$, enter $S_{new}$ | Working | Initializes and activates a new reasoning partition. |
| `return` | Finalize $S$, return to Main | Working | Terminates scope; synthesizes summary to parent; clears $M_S$. |
| `note` | $N_S \leftarrow N_S \oplus n_{new}$ | Episodic | Persists a localized observation. |
| `insight` | $\mathcal{I} \leftarrow \mathcal{I} \oplus i_{new}$ | Semantic | Persists a global axiom. |
| `notes` | Output $N_{scope}$ or $N_{all}$ | Episodic | Retrieves episodic traces. |
| `insights` | Output $\mathcal{I}$ | Semantic | Retrieves semantic knowledge. |
| `status` | Output state metadata | Meta | Reports current scope, token usage, and memory stats. |

### 3.4.1 Radial Scope Navigation (Hub-and-Spoke)

SPACE enforces a **Hub-and-Spoke** topology defined by strict transition constraints:

```
main → scope → return → main → scope → return → main
```

The `main` context serves as the **stable cognitive hub**, while temporary scopes act as **spokes** for isolated sub-tasks. Unlike graph-based navigation which permits arbitrary traversal, SPACE enforces:

1.  **Hub-Centric Branching**: The `scope` command is valid *only* from `main`.
2.  **Mandatory Convergence**: The `return` command is valid *only* from a scope.
3.  **Non-Nesting**: Scopes cannot spawn child scopes (depth $\le$ 1).
4.  **Non-Reentry**: Terminated scopes are immutable and inaccessible, except via their summaries.

This topology imposes **Cognitive Discipline**:
*   **Isolation**: Scopes are hermetically sealed; information transfer occurs solely via `main` through synthesized summaries.
*   **Reset**: Returning to `main` purges working memory, preventing "rumination" on irrelevant intermediate states.
*   **Consolidation**: The requirement to summarize upon return forces the agent to crystallize understanding before context switching.

### 3.4.2 Transition Semantics

Transitions follow a strict protocol to ensure causal continuity:

**Departure (Scope Initiation)**: The `-m` argument documents the *intent* (e.g., "Investigating authentication failure"). This intention is recorded in `main`.

**Arrival (Scope Termination)**: The `-m` argument documents the *outcome* (e.g., "Resolved via null-check in auth.py"). This summary becomes the permanent record in `main`, while the granular execution trace is discarded.

This protocol ensures `main` retains a high-level causal log of *Intents* and *Outcomes*, while detailed *Reasoning* is encapsulated and ephemeral.

### 3.4.3 The Planning Workflow

To maintain cognitive continuity, SPACE agents employ a **Plan-Execute Pattern**:

1.  **Ideation**: `scope plan/task-x` $\rightarrow$ Reasoning occurs in isolation.
2.  **Retrieval**: `insights` / `notes` $\rightarrow$ Load relevant context.
3.  **Synthesis**: Generate plan within working memory.
4.  **Commit**: `return` $\rightarrow$ Plan is summarized to `main`.
5.  **Execution**: `scope implement/task-x` $\rightarrow$ Execute plan with clean context.

## 3.5 Token Economics

### 3.5.1 Context Growth Models

**Linear Agent**: Context grows monotonically with turn count $t$:
$$|C_{\text{linear}}(t)| = |P_{\text{sys}}| + \sum_{i=1}^{t} |\tau_i| = O(t)$$

**SPACE Agent**: Context is bounded by the current scope size $k$:
$$|C_{\text{SPACE}}(t)| = |P_{\text{sys}}| + |M_{S_{\text{current}}}| = O(k)$$

### 3.5.2 The Sawtooth Pattern

The SPACE context profile exhibits a characteristic **sawtooth wave**:

$$|C_{\text{SPACE}}(t)| = \begin{cases}
|P_{\text{sys}}| + (t - t_{\text{enter}}) \cdot \bar{\tau} & \text{within scope (accumulation)} \\
|P_{\text{sys}}| + |m_{\text{summary}}| & \text{after return (reset)}
\end{cases}$$

Each `return` operation purges working memory, resetting the context floor and bounding peak consumption.

### 3.5.3 Cumulative Cost Analysis

**Linear Agent** (Quadratic Scaling):
$$\text{Total}_{\text{linear}} \approx \sum_{t=1}^{T} t \cdot \bar{\tau} = O(T^2)$$

**SPACE Agent** (Linear Scaling):
$$\text{Total}_{\text{SPACE}} \approx n \cdot \sum_{k=1}^{\bar{k}} k \cdot \bar{\tau} = O(n \cdot \bar{k}^2)$$
Where $n$ is the number of scopes and $\bar{k}$ is average scope length.

**Token Savings**: For $n$ sequential tasks, the asymptotic savings approach:
$$\text{Savings} \approx 1 - \frac{1}{n}$$
For $n=15$, theoretical savings are $\sim$93%, consistent with our empirical findings.

### 3.5.4 Complexity Summary

| Metric | Linear | SPACE |
| :--- | :--- | :--- |
| Context per call | $O(t)$ | $O(k)$ |
| Peak context | $O(T)$ | $O(k_{\max})$ |
| Cumulative cost | $O(T^2)$ | $O(n \cdot \bar{k}^2)$ |

This analysis demonstrates that SPACE effectively decouples the cost of a new task from the history of prior tasks, enabling $O(1)$ scaling for lifelong agents.

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
8.         Assert(C.current_scope == "main")
9.         C.create_scope(name, departure_note=message)
10.
11.    elif response.has_tool_call("return"):
12.        Assert(C.current_scope != "main")
13.        C.close_scope(summary=message)  // Clears working memory
14.
15.    elif response.has_tool_call("note"):
16.        C.add_note(response.tool_args.message)
17.
18.    elif response.has_tool_call("insight"):
19.        C.add_insight(response.tool_args.message)
20.
21.    elif response.has_tool_call("notes"):
22.        return C.get_notes(scope)
23.
24.    elif response.is_final:
25.        R ← response.content
26.        done ← true
27.
28. return R
```
The invariant `C.current_scope \in \{ \text{"main"}, S_{active} \}` guarantees strict radial navigation.
