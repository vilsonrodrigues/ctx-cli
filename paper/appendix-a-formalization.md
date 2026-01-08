# Appendix A: Formal Specification of ECM

## A.1 Data Structures

### A.1.1 Core Definitions

**Definition 1 (Message).** A message $m$ is a tuple:
$$m = \langle \rho, c, \tau \rangle$$
where $\rho \in \{\text{system}, \text{user}, \text{assistant}, \text{tool}\}$ is the role, $c$ is the content string, and $\tau$ is the timestamp.

**Definition 2 (Note - Episodic Memory).** A note $n$ is a tuple:
$$n = \langle c, \tau, s \rangle$$
where $c$ is the content, $\tau$ is the timestamp, and $s$ is the scope identifier where it was created.

**Definition 3 (Insight - Semantic Memory).** An insight $i$ is a tuple:
$$i = \langle c, \tau \rangle$$
where $c$ is the content and $\tau$ is the timestamp. Insights are global (not scoped).

**Definition 4 (Scope).** A scope $S$ is a tuple:
$$S = \langle \text{id}, M_S, N_S, h_S, t_S \rangle$$
where:
- $\text{id}$ is the unique scope identifier (e.g., "main", "fix/auth-bug")
- $M_S = [m_1, m_2, \ldots, m_k]$ is the ordered list of working messages
- $N_S = [n_1, n_2, \ldots, n_j]$ is the list of episodic notes
- $h_S$ is the head note (transition context)
- $t_S$ is the creation timestamp

**Definition 5 (Context Store).** The context store $\mathcal{C}$ is a tuple:
$$\mathcal{C} = \langle \mathcal{S}, \mathcal{I}, s_{\text{current}} \rangle$$
where:
- $\mathcal{S} = \{S_1, S_2, \ldots, S_n\}$ is the set of all scopes
- $\mathcal{I} = [i_1, i_2, \ldots, i_m]$ is the list of global insights
- $s_{\text{current}} \in \mathcal{S}$ is the current active scope

### A.1.2 Memory Tiers

ECM implements three memory tiers with distinct properties:

| Tier | Container | Scope | Lifetime | Access |
|------|-----------|-------|----------|--------|
| Working | $M_S$ | Local | Ephemeral (cleared on scope change) | Automatic |
| Episodic | $N_S$ | Local | Persistent | Pull (`notes`) |
| Semantic | $\mathcal{I}$ | Global | Persistent | Pull (`insights`) |

## A.2 Operations

### A.2.1 Navigation Operations

**Operation: scope** (Create and Enter)
$$\texttt{scope}(s_{\text{new}}, m_{\text{note}}) : \mathcal{C} \rightarrow \mathcal{C}'$$

Precondition: $s_{\text{new}} \notin \mathcal{S}$

Effect:
1. Create departure note in origin: $N_{s_{\text{current}}} \leftarrow N_{s_{\text{current}}} \cup \{n_{\text{departure}}\}$
2. Create new scope: $S_{\text{new}} = \langle s_{\text{new}}, [], [], h_{\text{new}}, \tau_{\text{now}} \rangle$
3. Add to store: $\mathcal{S} \leftarrow \mathcal{S} \cup \{S_{\text{new}}\}$
4. Switch: $s_{\text{current}} \leftarrow s_{\text{new}}$

**Operation: goto** (Navigate to Existing)
$$\texttt{goto}(s_{\text{target}}, m_{\text{note}}) : \mathcal{C} \rightarrow \mathcal{C}'$$

Precondition: $s_{\text{target}} \in \mathcal{S}$

Effect:
1. Create arrival note in target: $N_{s_{\text{target}}} \leftarrow N_{s_{\text{target}}} \cup \{n_{\text{arrival}}\}$
2. Switch: $s_{\text{current}} \leftarrow s_{\text{target}}$

Note: Working memory $M_{s_{\text{current}}}$ of the origin is **not** transferred.

### A.2.2 Persistence Operations

**Operation: note** (Record Episodic)
$$\texttt{note}(c) : \mathcal{C} \rightarrow \mathcal{C}'$$

Effect: $N_{s_{\text{current}}} \leftarrow N_{s_{\text{current}}} \cup \{\langle c, \tau_{\text{now}}, s_{\text{current}} \rangle\}$

**Operation: insight** (Record Semantic)
$$\texttt{insight}(c) : \mathcal{C} \rightarrow \mathcal{C}'$$

Effect: $\mathcal{I} \leftarrow \mathcal{I} \cup \{\langle c, \tau_{\text{now}} \rangle\}$

### A.2.3 Retrieval Operations

**Operation: notes** (Pull Episodic)
$$\texttt{notes}(s?) : \mathcal{C} \rightarrow \text{String}$$

Effect:
- If $s$ specified: Return formatted $N_s$
- If $s$ omitted: Return formatted $\bigcup_{S \in \mathcal{S}} N_S$

**Operation: insights** (Pull Semantic)
$$\texttt{insights}() : \mathcal{C} \rightarrow \text{String}$$

Effect: Return formatted $\mathcal{I}$

### A.2.4 Context Composition (API Call)

**Algorithm 1: GetContext**

```
function GetContext(C, P_sys):
    S_active ← C.current_scope
    P ← [P_sys]                           // System prompt
    M_valid ← ValidateToolSequence(S_active.M)  // Fix incomplete tool calls
    P ← P + M_valid
    return P
```

The key property: **Only messages from $S_{\text{current}}$ are included**. Notes and insights are NOT automatically injected.

## A.3 Graph Structure

### A.3.1 Navigation Graph

The set of scopes $\mathcal{S}$ forms a directed graph $G = (V, E)$ where:
- $V = \mathcal{S}$ (vertices are scopes)
- $E = \{(s_i, s_j) : \exists \text{ transition from } s_i \text{ to } s_j\}$

**Property 1 (Graph Navigation).** For any $s_i, s_j \in \mathcal{S}$, the agent can execute $\texttt{goto}(s_j)$ regardless of the current position. There is no LIFO constraint.

**Contrast with Stack-Based (Context-Folding):**
- Context-Folding: $\texttt{branch}$ pushes, $\texttt{return}$ pops → Stack (LIFO)
- ECM: $\texttt{scope}$ creates, $\texttt{goto}$ navigates → Graph (arbitrary traversal)

### A.3.2 Asymmetric Note Placement

**Theorem 1 (Causal Preservation).** The asymmetric placement of notes preserves causal narrative:
- Departure notes ($\texttt{scope}$) answer: "Why am I leaving?"
- Arrival notes ($\texttt{goto}$) answer: "What am I bringing back?"

This ensures that each scope's episodic memory tells a coherent story of events that occurred within that scope.

## A.4 Complexity Analysis

### A.4.1 Context Size

**Linear Agent:**
$$|C_{\text{linear}}(t)| = |P_{\text{sys}}| + \sum_{i=1}^{t} |m_i| = O(t)$$

**ECM Agent:**
$$|C_{\text{ECM}}(t)| = |P_{\text{sys}}| + |M_{s_{\text{current}}}| = O(k)$$

where $k = |M_{s_{\text{current}}}|$ is bounded by scope lifetime, typically $k \ll t$.

**Theorem 2 (Bounded Context).** For an ECM agent executing $t$ tasks across $s$ scopes with average scope size $\bar{k}$:
$$|C_{\text{ECM}}| \leq |P_{\text{sys}}| + \bar{k}$$

This is independent of $t$, achieving O(1) context growth.

### A.4.2 Memory Overhead

Total memory stored:
$$|\mathcal{M}_{\text{ECM}}| = \sum_{S \in \mathcal{S}} (|M_S| + |N_S|) + |\mathcal{I}|$$

This grows with usage but is not loaded into context automatically.

## A.5 Comparison with Related Approaches

### A.5.1 vs. Context-Folding

| Property | Context-Folding | ECM |
|----------|-----------------|-----|
| Navigation | Stack (LIFO) | Graph (arbitrary) |
| Compression | Learned (RL) | Explicit (notes) |
| Training | Required (FoldGRPO) | None |
| Memory Tiers | 1 (compressed history) | 3 (working, episodic, semantic) |

### A.5.2 vs. MemGPT

| Property | MemGPT | ECM |
|----------|--------|-----|
| Storage | External (DB) | In-process |
| Retrieval | Learned paging | Explicit pull |
| Infrastructure | Vector DB required | None |

### A.5.3 vs. CaT

| Property | CaT | ECM |
|----------|-----|-----|
| Compression | Learned (SFT on 20K samples) | Explicit (agent decides) |
| Model | Specific (SWE-Compressor) | Any tool-use model |
| Structure | Linear with checkpoints | Graph with isolated scopes |
