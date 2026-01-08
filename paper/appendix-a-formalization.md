# Appendix A: Formal Specification of SPACE

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
$$S = \langle \text{id}, M_S, N_S, h_S, t_S, \sigma_S \rangle$$
where:
- $\text{id}$ is the unique scope identifier (e.g., "main", "fix/auth-bug")
- $M_S = [m_1, m_2, \ldots, m_k]$ is the ordered list of working messages
- $N_S = [n_1, n_2, \ldots, n_j]$ is the list of episodic notes
- $h_S$ is the head note (departure context from main)
- $t_S$ is the creation timestamp
- $\sigma_S \in \{\text{active}, \text{closed}\}$ is the scope state

**Definition 5 (Context Store).** The context store $\mathcal{C}$ is a tuple:
$$\mathcal{C} = \langle \mathcal{S}, \mathcal{I}, s_{\text{current}} \rangle$$
where:
- $\mathcal{S} = \{S_1, S_2, \ldots, S_n\}$ is the set of all scopes
- $\mathcal{I} = [i_1, i_2, \ldots, i_m]$ is the list of global insights
- $s_{\text{current}} \in \mathcal{S}$ is the current active scope

### A.1.2 Memory Tiers

SPACE implements three memory tiers with distinct properties:

| Tier | Container | Scope | Lifetime | Access | Token Cost |
|------|-----------|-------|----------|--------|------------|
| Working | $M_S$ | Local | Ephemeral (cleared on return) | Automatic | Per-call |
| Episodic | $N_S$ | Local | Persistent | Pull (`notes`) | On-demand |
| Semantic | $\mathcal{I}$ | Global | Persistent | Pull (`insights`) | On-demand |

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

## A.4 Context Growth Analysis

This section provides a rigorous mathematical analysis of how context size evolves during task execution, comparing linear accumulation with SPACE's bounded approach.

### A.4.1 Notation

Let:
- $t \in \mathbb{N}$ be the turn number (total interactions)
- $\tau_i = (a_i, o_i)$ be the $i$-th interaction (action + observation)
- $|\tau_i|$ be the token count of interaction $i$
- $\bar{\tau}$ be the average tokens per interaction
- $P_{\text{sys}}$ be the system prompt
- $n$ be the number of sequential tasks/scopes
- $k_j$ be the number of turns in scope $j$

### A.4.2 Linear Agent: Monotonic Growth

In a standard ReAct agent, context accumulates all interactions:

**Definition 6 (Linear Context).** The context at turn $t$ is:
$$C_{\text{linear}}(t) = P_{\text{sys}} \oplus \bigoplus_{i=1}^{t} \tau_i$$

where $\oplus$ denotes concatenation.

**Theorem 1 (Linear Context Size).**
$$|C_{\text{linear}}(t)| = |P_{\text{sys}}| + \sum_{i=1}^{t} |\tau_i|$$

With uniform interaction size:
$$|C_{\text{linear}}(t)| \approx |P_{\text{sys}}| + t \cdot \bar{\tau} = O(t)$$

**Corollary 1.** For $n$ sequential tasks with average $\bar{t}$ turns each:
$$|C_{\text{linear}}(n \cdot \bar{t})| = |P_{\text{sys}}| + n \cdot \bar{t} \cdot \bar{\tau} = O(n)$$

Context grows linearly with both turn count and task count.

### A.4.3 SPACE Agent: Bounded Growth with Sawtooth Pattern

SPACE partitions interactions into scopes, with only the current scope in context.

**Definition 7 (SPACE Context).** The context at turn $t$ within scope $S_j$ is:
$$C_{\text{SPACE}}(t) = P_{\text{sys}} \oplus M_{S_j}$$

where $M_{S_j}$ contains only messages since entering $S_j$.

**Theorem 2 (SPACE Context Size).**
$$|C_{\text{SPACE}}(t)| = |P_{\text{sys}}| + |M_{S_{\text{current}}}| = |P_{\text{sys}}| + \sum_{i=t_{\text{enter}}}^{t} |\tau_i|$$

where $t_{\text{enter}}$ is the turn when the current scope was entered.

**Theorem 3 (Bounded Peak Context).** Let $k_{\max} = \max_j |M_{S_j}|$ be the maximum scope size. Then:
$$\max_t |C_{\text{SPACE}}(t)| = |P_{\text{sys}}| + k_{\max} \cdot \bar{\tau}$$

This is independent of total turn count $t$ and task count $n$.

**Definition 8 (Sawtooth Pattern).** SPACE context follows a sawtooth pattern:

$$|C_{\text{SPACE}}(t)| = \begin{cases}
|P_{\text{sys}}| + (t - t_{\text{enter}}) \cdot \bar{\tau} & \text{within scope} \\
|P_{\text{sys}}| + |m_{\text{summary}}| & \text{after return}
\end{cases}$$

Each `return` resets working memory to main, creating periodic drops.

### A.4.4 Memory Accumulation Model

While context is bounded, total memory (notes + insights) grows with usage.

**Definition 9 (Total Memory).** The total memory footprint at time $t$ is:
$$|\mathcal{M}(t)| = \underbrace{|M_{S_{\text{current}}}|}_{\text{Working}} + \underbrace{\sum_{S \in \mathcal{S}} |N_S|}_{\text{Episodic (Notes)}} + \underbrace{|\mathcal{I}|}_{\text{Semantic (Insights)}}$$

**Theorem 4 (Memory Growth Rates).**

Let $\alpha_n$ be the note creation rate (notes per turn) and $\alpha_i$ be the insight creation rate.

- **Working memory**: $O(k)$ — bounded by scope size, reset on return
- **Episodic memory (Notes)**: $|N_{\text{total}}(t)| = \sum_{\tau=1}^{t} \alpha_n(\tau) \cdot \bar{n}$ — grows with note-taking
- **Semantic memory (Insights)**: $|\mathcal{I}(t)| = \sum_{\tau=1}^{t} \alpha_i(\tau) \cdot \bar{i}$ — grows with insight extraction

where $\bar{n}$ and $\bar{i}$ are average note and insight sizes in tokens.

**Corollary 2 (Context vs Memory Separation).**
$$|C_{\text{SPACE}}(t)| = O(k) \quad \text{while} \quad |\mathcal{M}(t)| = O(t \cdot (\alpha_n + \alpha_i))$$

Memory grows but context remains bounded—the key SPACE invariant.

### A.4.5 Token Economics: Detailed Analysis

**Definition 10 (API Call Token Cost).** For a single LLM call at turn $t$:
$$\text{Cost}(t) = |C(t)| \cdot c_{\text{input}} + |r_t| \cdot c_{\text{output}}$$

where $c_{\text{input}}$, $c_{\text{output}}$ are per-token costs and $|r_t|$ is response length.

**Theorem 5 (Cumulative Token Cost).**

**Linear Agent** (over $T$ turns):
$$\text{Total}_{\text{linear}} = \sum_{t=1}^{T} |C_{\text{linear}}(t)| \cdot c_{\text{input}}$$
$$= c_{\text{input}} \sum_{t=1}^{T} \left(|P_{\text{sys}}| + t \cdot \bar{\tau}\right) = c_{\text{input}} \left(T \cdot |P_{\text{sys}}| + \bar{\tau} \cdot \frac{T(T+1)}{2}\right) = O(T^2)$$

**SPACE Agent** (over $T$ turns across $n$ scopes):
$$\text{Total}_{\text{SPACE}} = \sum_{j=1}^{n} \sum_{t=1}^{k_j} |C_{\text{SPACE}}^{(j)}(t)| \cdot c_{\text{input}}$$

With average scope size $\bar{k}$:
$$\text{Total}_{\text{SPACE}} \approx c_{\text{input}} \cdot n \left(\bar{k} \cdot |P_{\text{sys}}| + \bar{\tau} \cdot \frac{\bar{k}(\bar{k}+1)}{2}\right) = O(n \cdot \bar{k}^2)$$

**Theorem 6 (Token Savings Ratio).**
$$\text{Savings} = 1 - \frac{\text{Total}_{\text{SPACE}}}{\text{Total}_{\text{linear}}} \approx 1 - \frac{n \cdot \bar{k}^2}{T^2}$$

For $T = n \cdot \bar{k}$ (same total turns distributed across scopes):
$$\text{Savings} \approx 1 - \frac{1}{n}$$

With $n = 15$ tasks: $\text{Savings} \approx 93\%$ — matching our empirical ~88-93%.

### A.4.6 Memory Query Cost Model

When the agent queries notes or insights, additional tokens are injected into context.

**Definition 11 (Query-Augmented Context).**
$$C_{\text{query}}(t) = C_{\text{SPACE}}(t) \oplus Q_{\text{notes}} \oplus Q_{\text{insights}}$$

where:
$$|Q_{\text{notes}}| = \begin{cases}
\sum_{n \in N_S} |n| & \text{if querying scope } S \\
\sum_{S \in \mathcal{S}} \sum_{n \in N_S} |n| & \text{if querying all notes}
\end{cases}$$

$$|Q_{\text{insights}}| = \sum_{i \in \mathcal{I}} |i|$$

**Theorem 7 (Query Cost Bound).** With bounded note/insight sizes ($|n| \leq \bar{n}_{\max}$, $|i| \leq \bar{i}_{\max}$):
$$|C_{\text{query}}(t)| \leq |P_{\text{sys}}| + k_{\max} \cdot \bar{\tau} + |\mathcal{N}_{\text{total}}| \cdot \bar{n}_{\max} + |\mathcal{I}| \cdot \bar{i}_{\max}$$

This grows with total notes/insights but is **under agent control** — queries are explicit decisions, not automatic injection.

### A.4.7 The Three-Tier Cost Model

SPACE's memory tiers have distinct cost characteristics:

| Tier | Creation Cost | Storage Cost | Retrieval Cost |
|------|---------------|--------------|----------------|
| Working ($M_S$) | 0 (automatic) | $O(k)$ per call | 0 (automatic) |
| Episodic ($N_S$) | $O(\|n\|)$ output | $O(1)$ storage | $O(\sum\|N_S\|)$ on query |
| Semantic ($\mathcal{I}$) | $O(\|i\|)$ output | $O(1)$ storage | $O(\sum\|\mathcal{I}\|)$ on query |

**Key insight**: Notes and insights have **deferred cost** — they consume tokens only when explicitly retrieved, enabling selective knowledge loading.

### A.4.8 Comparative Complexity Summary

| Metric | Linear | SPACE | Context-Folding | AgentFold | CaT |
|--------|--------|-------|-----------------|-----------|-----|
| Context per call | $O(t)$ | $O(k)$ | $O(k)$ | $O(\log t)$* | $O(k)$ |
| Peak context | $O(T)$ | $O(k_{\max})$ | $O(k_{\max})$ | ~7K | ~4.7K |
| Cumulative cost | $O(T^2)$ | $O(n \cdot \bar{k}^2)$ | $O(n \cdot \bar{k}^2)$ | $O(T \log T)$* | $O(n \cdot \bar{k}^2)$ |
| Notes/Insights | ✗ | ✓ (3-tier) | ✗ | ✗ | ✗ |
| Cross-scope transfer | ✗ | ✓ (insights) | ✗ | ✗ | ✗ |

*With learned multi-scale compression

### A.4.9 Empirical Validation

Our preliminary experiments on SWE-Bench-CL (15 sequential tasks) show:

| Metric | Linear (Measured) | SPACE (Measured) | Theoretical Prediction |
|--------|-------------------|------------------|------------------------|
| Peak context | 12,059 tokens | 1,402 tokens | $O(k_{\max})$ ✓ |
| Final task context | 12,059 tokens | 801 tokens | Independent of $n$ ✓ |
| Reduction | — | ~88% | $1 - 1/n \approx 93\%$ ✓ |
| Growth pattern | Monotonic | Sawtooth | As predicted ✓ |

The slight discrepancy (88% vs 93%) is attributed to:
1. System prompt overhead (~800 tokens for SPACE commands)
2. Return summaries persisting in main context
3. Occasional note/insight queries adding to context

## A.5 Comparison with Related Approaches

### A.5.1 vs. Context-Folding

| Property | Context-Folding | SPACE |
|----------|-----------------|-------|
| Navigation | Stack (LIFO) | Radial (hub-and-spoke) |
| Compression | Learned (RL) | Explicit (notes) |
| Training | Required (FoldGRPO) | None |
| Memory Tiers | 1 (compressed history) | 3 (working, episodic, semantic) |

### A.5.2 vs. MemGPT

| Property | MemGPT | SPACE |
|----------|--------|-------|
| Storage | External (DB) | In-process |
| Retrieval | Learned paging | Explicit pull |
| Infrastructure | Vector DB required | None |

### A.5.3 vs. CaT

| Property | CaT | SPACE |
|----------|-----|-------|
| Compression | Learned (SFT on 20K samples) | Explicit (agent decides) |
| Model | Specific (SWE-Compressor) | Any tool-use model |
| Structure | Linear with checkpoints | Radial with isolated scopes |
