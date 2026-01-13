# 3. Method

We present **SPACE (Self-Partitioned Agent Context Environment)**, a training-free framework that empowers agents with explicit architectural control over their working memory. This section formalizes the architecture: Section 3.1 defines the core data structures; Section 3.2 details the tiered memory hierarchy; Section 3.3 describes the pull-based context composition strategy; Section 3.4 specifies the command interface and navigation topology; and Section 3.5 provides a formal analysis of token economics.

## 3.1 Data Structures

The architecture is predicated on a **ContextStore** ($\mathcal{C}$) that manages isolated reasoning contexts and hierarchical memory tiers across multiple sessions.

### 3.1.1 Scope (Reasoning Partition)
A scope $S$ constitutes a distinct memory partition defined as a tuple:
$$ S = \langle M_S, N_S, m_{\text{intent}} \rangle $$
Where:
*   $M_S$ is the **Working Memory**: An ordered sequence of ephemeral messages (User, Assistant, Tool) representing the immediate reasoning context.
*   $N_S$ is the **Episodic Memory**: An ordered sequence of notes representing crystallized observations within the scope.
*   $m_{\text{intent}}$ is the **Intent Message**: A string documenting the scope's purpose, recorded in the parent context upon creation.

### 3.1.2 Project (Session Container)
A project $\Pi$ represents a logical session boundary, grouping related scopes:
$$ \Pi = \langle \text{name}, \{S_1, S_2, ..., S_m\}, t_{\text{created}} \rangle $$

When a new project is initiated, all scopes from the previous project are archived with a disambiguating suffix. For a scope $S$ in project $\Pi_{\text{old}}$ transitioning to project $\Pi_{\text{new}}$, the archived scope is referenced as:
$$ S@\Pi_{\text{old}} $$

This notation enables cross-project episodic retrieval: notes from `debug-auth@project-v1` remain accessible after transitioning to `project-v2`.

### 3.1.3 Semantic Memory (Insights)
A global repository $\mathcal{I}$ stores universal patterns and architectural knowledge discovered by the agent:
$$ \mathcal{I} = [i_1, i_2, ..., i_n] $$
Each insight $i$ comprises a content string and temporal metadata. This sequence forms a growing **semantic substrate**—a durable knowledge base that persists across all scopes and **all projects**, shaping agent behavior without reintroducing the full reasoning history that generated each insight. This enables cross-session knowledge transfer without retrieval overhead.

## 3.2 Tiered Memory Architecture

SPACE implements a three-tier memory system theoretically grounded in Tulving's taxonomy of human memory [21]:

1.  **Working Memory (Ephemeral)**: Corresponds to messages ($M_S$) within the active scope. This tier is volatile and is explicitly cleared upon executing a `return` command.
2.  **Episodic Memory (Persistent, Scope-Local)**: Managed via the `note` command, this tier captures task-specific observations—implementation details, error analyses, and state changes. These memories persist within the scope structure and are retrievable via `notes`.
3.  **Semantic Memory (Persistent, Global)**: Managed via the `insight` command, this tier captures generalized patterns—architectural invariants, API contracts, and reusable heuristics. These memories persist globally, enabling lifelong learning without retrieval overhead.

### 3.2.1 Session Management via Projects

Orthogonal to the memory tiers, SPACE provides a **project-based session management** mechanism that governs the lifecycle and accessibility of episodic memories across sessions:

*   **Active Project**: All scopes created belong to the current project. Episodic memories are directly accessible via `notes <scope>`.
*   **Archived Projects**: When a new project is initiated, all scopes from the previous project are archived with `@project` notation. Their episodic memories remain accessible via `notes <scope>@<project>`.
*   **Semantic Memory Persistence**: Insights are unaffected by project transitions—they persist globally across all sessions.

This separation ensures that the memory *type* (working/episodic/semantic) remains conceptually distinct from the *organizational scope* (current project vs. archived projects).

Figure 1 illustrates the memory hierarchy and session boundaries.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SEMANTIC MEMORY (Global)                     │
│                   insights persist forever                      │
├─────────────────────────────────────────────────────────────────┤
│                    EPISODIC MEMORY (Scope-Local)                │
│  ┌─────────────────────────┐  ┌─────────────────────────────┐  │
│  │   PROJECT: current      │  │  PROJECT: archived@old      │  │
│  │  ┌─────┐ ┌─────┐       │  │  ┌───────────────────────┐  │  │
│  │  │main │ │scope│ ...   │  │  │ main@old, scope@old   │  │  │
│  │  │notes│ │notes│       │  │  │   (notes accessible)  │  │  │
│  │  └─────┘ └─────┘       │  │  └───────────────────────┘  │  │
│  └─────────────────────────┘  └─────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    WORKING MEMORY (Ephemeral)                   │
│                 messages in current scope only                  │
└─────────────────────────────────────────────────────────────────┘
```

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

The agent interacts with $\mathcal{C}$ through a structured tool interface implementing a **Layered Hub-and-Spoke Navigation Topology**.

| Command | Logical Operation | Tier | Effect |
| :--- | :--- | :--- | :--- |
| `scope <name>` | Create $S_{new}$, enter $S_{new}$ | Working | Initializes and activates a new reasoning partition. |
| `return` | Finalize $S$, return to Main | Working | Terminates scope; synthesizes summary to parent; clears $M_S$. |
| `note` | $N_S \leftarrow N_S \oplus n_{new}$ | Episodic | Persists a localized observation. |
| `insight` | $\mathcal{I} \leftarrow \mathcal{I} \oplus i_{new}$ | Semantic | Persists a global axiom. |
| `notes` | Output $N_{scope}$ or $N_{all}$ | Episodic | Retrieves episodic traces. |
| `insights` | Output $\mathcal{I}$ | Semantic | Retrieves semantic knowledge. |
| `status` | Output state metadata | Meta | Reports current scope, token usage, and memory stats. |

### 3.4.1 Layered Hub-and-Spoke Navigation

SPACE enforces a **Layered Hub-and-Spoke** topology defined by strict transition constraints:

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

Transitions follow a protocol ensuring causal continuity between scopes:

**Scope Initiation**: The `-m` argument documents the *intent* (e.g., "Investigating authentication failure"). This message is recorded in `main` before entering the scope.

**Scope Termination**: The `-m` argument documents the *outcome* (e.g., "Resolved via null-check in auth.py"). This summary becomes the permanent record in `main`.

This protocol ensures `main` retains a causal log of *Intents* and *Outcomes*, while detailed reasoning remains encapsulated within scopes. When transitioning between scopes, the agent can chain commands to declare the next intent before the previous scope's context is cleared, preserving continuity.

### 3.4.3 Example Usage Pattern

A typical workflow follows a **plan-execute pattern**: the agent creates a planning scope, retrieves relevant context via `insights` or `notes`, synthesizes a plan, returns with a summary, then creates an execution scope with clean context. This pattern leverages scope isolation to separate deliberation from execution.

### 3.4.4 Session Management via Projects

While scopes manage context *within* a conversation, **projects** manage context *across* conversations. This separation addresses a key deployment reality: developers need to reset agent state for new tasks while preserving learned knowledge.

**Project Lifecycle**:
1.  **Active Project**: All scopes created belong to the current project. The `status` command displays them without qualification.
2.  **Project Transition**: When a new project is initiated (developer API, not agent command), all current scopes are archived with `@{project-name}` suffix.
3.  **Archived Projects**: Previous scopes remain accessible via explicit reference (e.g., `notes debug-auth@v1`).

**Cross-Project Knowledge Access**:
*   **Notes**: Accessible via `notes <scope>@<project>`. Enables selective retrieval of episodic memories from previous sessions.
*   **Insights**: Automatically available. No retrieval required—insights persist globally and are included in system prompt context.

**Status Display**:
```
On scope: main
Current Project: v2
  Scopes:
    ● main
    - feature-auth (3 notes)

Previous Projects:
  [v1]
    Scopes:
      - main@v1 (5 notes)
      - debug-api@v1 (2 notes)

Memory:
  Insights: 12 (global)
  Notes: 10 (current project) + 7 (archived)
```

This design enables **lifelong learning**: insights discovered in `project-v1` immediately benefit `project-v2` without explicit retrieval, while episodic memories remain accessible for selective recall when needed.

### 3.4.5 Command Composability

SPACE supports **atomic multi-command sequences** within a single inference pass. This capability addresses a critical continuity challenge: when an agent returns to `main`, the working memory of the previous scope is purged, potentially disrupting agentic momentum.

**Supported Patterns**:
*   `return -m "summary"; scope <name> -m "intent"`: Terminates the current scope and immediately enters a new one. The summary and intent are generated in the same inference pass, preserving reasoning continuity.
*   `note -m "observation"; return -m "summary"`: Records a final observation before scope termination.
*   `insight -m "pattern"; note -m "instance"`: Captures both a generalized pattern and a specific instance simultaneously.

**Mechanism**: The agent outputs multiple tool calls in sequence. The runtime executes them atomically, ensuring that the agent's "future self" (in the new scope) receives both the consolidated summary and the declared intent without an intermediate disoriented state.

**Rationale**: Early experiments revealed that agents often entered repetitive loops upon returning to `main`, struggling to re-orient in the clean context. Multi-command sequences act as a **cognitive bridge**: the agent "passes the baton" to its future self by generating both the conclusion of the past and the plan for the future in a single pass.

### 3.4.6 Scope Conventions: Planning vs Execution

SPACE distinguishes between two classes of scopes by naming convention:

**Planning Scopes (`plan/*`)**: Used for exploratory reasoning, alternative generation, and structural thinking. These scopes are intentionally noisy—the agent may consider multiple approaches, evaluate trade-offs, and discard failed paths. Planning scopes are expected to produce high-level decisions rather than concrete artifacts.

**Execution Scopes (`task/*` or `fix/*`)**: Used for directed problem-solving that follows an established plan. These scopes produce evidence, local decisions, and concrete results. Execution scopes should be focused and goal-directed.

This convention is not enforced by the architecture but emerges as a best practice:
*   Only planning scopes should generate multiple alternatives.
*   Task creation follows from returning from a planning scope, ensuring execution is grounded in prior deliberation.
*   The separation prevents "planning in execution" (scope creep) and "executing in planning" (premature commitment).

### 3.4.7 Relation to Test-Time Compute

Within SPACE, test-time compute is realized through **controlled scope creation**. Rather than increasing token budgets or recursively expanding prompts, additional computation is allocated by opening explicit reasoning scopes that: (1) are contextually rich (full access to insights and notes), (2) are isolated from prior noise, and (3) have a clear termination condition.

This transforms test-time compute from an implicit, unstructured process into a **first-class, inspectable operation**. The agent can perform arbitrarily complex planning or analysis while maintaining a clean and stable main context.

| TTC Dimension | Traditional Approaches | SPACE |
| :--- | :--- | :--- |
| **Compute Allocation** | Implicit (token generation) | Explicit (`scope` creates budget) |
| **Deliberation Boundary** | None (continuous stream) | Clear (`return` terminates) |
| **Commit Mechanism** | None (implicit in final answer) | Explicit (`return -m` forces synthesis) |
| **Exploration Control** | Unbounded (tree/graph expansion) | Bounded (non-nesting, non-reentry) |
| **Cost Predictability** | Low (combinatorial growth) | High (scope count × avg length) |

**Key Insight**: In SPACE, "thinking more" requires opening more scopes. Each scope is a conscious decision to allocate compute, and each return is a forced consolidation. This creates **cognitive friction** that aligns with cognitive economy: more deliberation requires more organization, making compute cost explicit and controllable.

By enforcing disposability of reasoning and persistence of distilled knowledge, SPACE enables scalable long-horizon reasoning without context collapse, making it particularly suitable for continual learning and multi-session agentic workflows.

This design enables new metrics for TTC efficiency:
*   **Compute per decision**: Tokens spent per committed insight or note.
*   **Scope efficiency**: Ratio of useful conclusions to total scope tokens.
*   **Discard rate**: Fraction of scope content not preserved in return summary.

## 3.5 Token Economics

### 3.5.1 Context Growth Models

**Linear Agent**: Context grows monotonically with turn count $t$:
$$|C_{\text{linear}}(t)| = |P_{\text{sys}}| + \sum_{i=1}^{t} |\tau_i| = O(t)$$

**SPACE Agent**: Context is bounded by the current scope's message count $k$:
$$|C_{\text{SPACE}}(t)| = |P_{\text{sys}}| + |M_{S_{\text{current}}}| = O(k)$$

Since scopes are reset upon return, the maximum context size is bounded by the longest scope: $O(k_{\max})$, independent of total conversation length $T$.

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

**Token Savings**: For $n$ sequential tasks with similar scope lengths, the asymptotic savings approach:
$$\text{Savings} \approx 1 - \frac{1}{n}$$
As $n$ grows, savings approach unity. We evaluate this prediction empirically in §5.

### 3.5.4 Complexity Summary

| Metric | Linear | SPACE |
| :--- | :--- | :--- |
| Context per call | $O(t)$ | $O(k)$ |
| Peak context | $O(T)$ | $O(k_{\max})$ |
| Cumulative cost | $O(T^2)$ | $O(n \cdot \bar{k}^2)$ |

This analysis demonstrates that SPACE effectively decouples the cost of a new task from the history of prior tasks. While context within a scope grows linearly with scope length, the total cost scales with the number of scopes rather than total conversation length.

### 3.5.5 Cross-Project Token Economics

When multiple projects are used sequentially (e.g., $p$ projects with $n$ scopes each):

**Linear Agent**: Each new project inherits the full history, leading to:
$$\text{Total}_{\text{linear}} = O(p \cdot n \cdot T^2)$$

**SPACE Agent**: Project boundaries reset working memory while preserving insights:
$$\text{Total}_{\text{SPACE}} = O(p \cdot n \cdot \bar{k}^2) + O(|\mathcal{I}|)$$

The insight overhead $O(|\mathcal{I}|)$ grows slowly as insights are curated generalizations, not raw logs. Empirically, we observe $|\mathcal{I}| \ll T$ (see §5).

**Key Property**: Unlike approaches that discard all memory between sessions, SPACE preserves semantic knowledge (insights) while resetting episodic context (working memory + notes). This enables **bounded cost per session** with **cumulative knowledge transfer**.

## 3.6 Algorithm: SPACE Agent Loop

```
Algorithm 2: SPACE Agent Main Loop

Input: Task T, ContextStore C
Output: Result R

1.  C.current_scope ← "main"
2.  C.add_message("user", T)
3.  done ← false
4.  while not done:
5.      context ← ComposeContext(C)
6.      response ← LLM(context)
7.
8.      if response.has_tool_call("scope"):
9.          name, message ← response.tool_args
10.         C.create_scope(name, intent=message)
11.
12.     else if response.has_tool_call("return"):
13.         message ← response.tool_args
14.         C.close_scope(summary=message)
15.
16.     else if response.has_tool_call("note"):
17.         C.add_note(response.tool_args.message)
18.
19.     else if response.has_tool_call("insight"):
20.         C.add_insight(response.tool_args.message)
21.
22.     else if response.is_final:
23.         R ← response.content
24.         done ← true
25.
26. return R
```

**Invariants**: (1) `scope` is only valid when `C.current_scope = "main"`; (2) `return` is only valid when `C.current_scope ≠ "main"`. These constraints enforce hub-and-spoke navigation.
