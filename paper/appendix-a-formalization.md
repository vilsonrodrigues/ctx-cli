# Appendix A: Formal Specification of SPACE

## A.1 Data Structures

### A.1.1 Core Definitions

**Definition 1 (Message).** A message $m$ is defined as a tuple:
$$m = \langle \rho, c, \tau \rangle$$
where $\rho \in \{\text{system}, \text{user}, \text{assistant}, \text{tool}\}$ denotes the role, $c \in \Sigma^*$ is the content string over alphabet $\Sigma$, and $\tau \in \mathbb{R}^+$ is the logical timestamp.

**Definition 2 (Note - Episodic Memory).** A note $n$ is a tuple:
$$n = \langle c, \tau, s_{id} \rangle$$
where $c$ is the content, $\tau$ is the creation timestamp, and $s_{id}$ is the identifier of the scope in which the note was created.

**Definition 3 (Insight - Semantic Memory).** An insight $i$ is a tuple:
$$i = \langle c, \tau \rangle$$
where $c$ is the universal content and $\tau$ is the timestamp. Insights are global and scope-agnostic.

**Definition 4 (Scope).** A scope $S$ is a tuple:
$$S = \langle \text{id}, M_S, N_S, h_S, t_{start}, \sigma \rangle$$
where:
*   $\text{id}$ is the unique scope identifier.
*   $M_S = [m_1, m_2, \ldots, m_k]$ is the ordered sequence of working memory messages.
*   $N_S = [n_1, n_2, \ldots, n_j]$ is the ordered sequence of episodic notes.
*   $h_S$ is the head note (departure context from parent).
*   $t_{start}$ is the initialization timestamp.
*   $\sigma \in \{\text{active}, \text{closed}\}$ is the state flag.

**Definition 5 (Context Store).** The global context store $\mathcal{C}$ is defined as:
$$\mathcal{C} = \langle \mathcal{S}, \mathcal{I}, s_{\text{current}} \rangle$$
where:
*   $\mathcal{S} = \{S_1, S_2, \ldots, S_n\}$ is the set of all scopes.
*   $\mathcal{I} = [i_1, i_2, \ldots, i_m]$ is the global insight repository.
*   $s_{\text{current}} \in \mathcal{S}$ identifies the currently active reasoning partition.

### A.1.2 Memory Tiers

SPACE implements three memory tiers with distinct properties:

| Tier | Container | Scope | Lifetime | Access Pattern | Token Cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Working** | $M_S$ | Local | Ephemeral | Automatic | $O(k)$ per call |
| **Episodic** | $N_S$ | Local | Persistent | Pull (`notes`) | On-demand |
| **Semantic** | $\mathcal{I}$ | Global | Persistent | Pull (`insights`) | On-demand |

## A.2 Operations

### A.2.1 Navigation Operations

**Operation: scope** (Create and Enter)
$$\texttt{scope}(s_{\text{new}}, m_{\text{note}}) : \mathcal{C} \rightarrow \mathcal{C}'$$
*Precondition*: $s_{\text{new}} \notin \mathcal{S} \land s_{\text{current}} = \text{"main"}$
*Effect*:
1.  **Record Departure**: $N_{s_{\text{current}}} \leftarrow N_{s_{\text{current}}} \cup \{n_{\text{departure}}\}$
2.  **Initialize**: $S_{\text{new}} = \langle s_{\text{new}}, [], [], h_{\text{new}}, \tau_{\text{now}}, \text{active} \rangle$
3.  **Store**: $\mathcal{S} \leftarrow \mathcal{S} \cup \{S_{\text{new}}\}$
4.  **Transition**: $s_{\text{current}} \leftarrow s_{\text{new}}$

**Operation: return** (Finalize and Exit)
$$\texttt{return}(m_{\text{summary}}) : \mathcal{C} \rightarrow \mathcal{C}'$$
*Precondition*: $s_{\text{current}} \neq \text{"main"}$
*Effect*:
1.  **Close**: $S_{\text{current}}.\sigma \leftarrow \text{closed}$
2.  **Transition**: $s_{\text{current}} \leftarrow \text{"main"}$
3.  **Consolidate**: $N_{\text{main}} \leftarrow N_{\text{main}} \cup \{\langle m_{\text{summary}}, \tau_{\text{now}}, \text{main} \rangle\}$
4.  **Purge**: $M_{S_{\text{prev}}}$ is now inaccessible to the prompt construction algorithm.

### A.2.2 Persistence Operations

**Operation: note** (Record Episodic)
$$\texttt{note}(c) : \mathcal{C} \rightarrow \mathcal{C}'$$
*Effect*: $N_{s_{\text{current}}} \leftarrow N_{s_{\text{current}}} \cup \{\langle c, \tau_{\text{now}}, s_{\text{current}} \rangle\}$

**Operation: insight** (Record Semantic)
$$\texttt{insight}(c) : \mathcal{C} \rightarrow \mathcal{C}'$$
*Effect*: $\mathcal{I} \leftarrow \mathcal{I} \cup \{\langle c, \tau_{\text{now}} \rangle\}$

## A.3 Context Growth Analysis

This section provides a rigorous mathematical analysis of context evolution.

### A.3.1 Notation

Let:
*   $t \in \mathbb{N}$ be the cumulative turn count.
*   $\tau_i$ be the $i$-th interaction tuple $(a_i, o_i)$.
*   $|\tau_i|$ be the token count of interaction $i$.
*   $P_{\text{sys}}$ be the system prompt.
*   $n$ be the number of sequential tasks.

### A.3.2 Linear Agent: Monotonic Growth

**Theorem 1 (Linear Context).** The context size for a linear agent grows monotonically:
$$|C_{\text{linear}}(t)| = |P_{\text{sys}}| + \sum_{i=1}^{t} |\tau_i|$$
Assuming uniform interaction size $\bar{\tau}$:
$$|C_{\text{linear}}(t)| \approx |P_{\text{sys}}| + t \cdot \bar{\tau} = O(t)$$

### A.3.3 SPACE Agent: Bounded Growth

**Theorem 2 (SPACE Context).** The context size for a SPACE agent is bounded by the current scope's duration:
$$|C_{\text{SPACE}}(t)| = |P_{\text{sys}}| + \sum_{i=t_{\text{enter}}}^{t} |\tau_i|$$
where $t_{\text{enter}}$ is the turn index when the current scope was initialized.

**Theorem 3 (Bounded Peak Context).** Let $k_{\max} = \max_{j} |M_{S_j}|$ be the maximum size of any single scope. Then:
$$\max_t |C_{\text{SPACE}}(t)| = |P_{\text{sys}}| + k_{\max} \cdot \bar{\tau}$$
This bound is independent of total history length $T$.

### A.3.4 Cumulative Cost Analysis

**Theorem 4 (Total Token Consumption).**

For a **Linear Agent** over $T$ turns:
$$\text{Total}_{\text{linear}} = c_{\text{input}} \sum_{t=1}^{T} \left(|P_{\text{sys}}| + t \cdot \bar{\tau}\right) \approx O(T^2)$$

For a **SPACE Agent** executing $n$ tasks of length $\bar{k}$:
$$\text{Total}_{\text{SPACE}} \approx c_{\text{input}} \cdot n \sum_{k=1}^{\bar{k}} \left(|P_{\text{sys}}| + k \cdot \bar{\tau}\right) \approx O(n \cdot \bar{k}^2)$$

**Corollary (Savings Ratio).** The asymptotic token savings approach:
$$\lim_{n \to \infty} \left( 1 - \frac{\text{Total}_{\text{SPACE}}}{\text{Total}_{\text{linear}}} \right) = 1$$
For finite $n$, assuming $T = n \cdot \bar{k}$:
$$\text{Savings} \approx 1 - \frac{1}{n}$$
For $n=15$ tasks, theoretical savings are $\approx 93.3\%$.

## A.4 Memory Query Cost Model

While working memory is bounded, the *potential* context (accessible via retrieval) grows.

**Definition (Query-Augmented Context).**
$$C_{\text{query}}(t) = C_{\text{SPACE}}(t) \oplus Q_{\text{notes}} \oplus Q_{\text{insights}}$$

**Theorem 5 (Controlled Retrieval).** The size of retrieved context is strictly controlled by the agent:
$$|Q| \le \sum_{n \in \text{SelectedNotes}} |n|$$
Unlike RAG systems that may automatically inject top-$k$ chunks, SPACE incurs retrieval costs *only* when the agent explicitly judges that historical information is required for the current reasoning step.
