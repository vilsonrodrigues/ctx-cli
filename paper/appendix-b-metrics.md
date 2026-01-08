# Appendix B: Evaluation Metrics

## B.1 Token Economics Metrics

### B.1.1 Primary Metrics

**Definition 6 (Context Size at Step t).**
$$C(t) = |P_{\text{sys}}| + |M_{\text{active}}(t)|$$

where $P_{\text{sys}}$ is the system prompt and $M_{\text{active}}(t)$ is the active message buffer at step $t$.

**Definition 7 (Peak Context).**
$$C_{\text{peak}} = \max_{t \in [1, T]} C(t)$$

**Definition 8 (Base Context).**
$$C_{\text{base}} = C(1) = |P_{\text{sys}}| + |m_{\text{initial}}|$$

This represents the cacheable portion (system prompt + tool definitions).

**Definition 9 (Context Growth).**
$$\Delta C = C_{\text{peak}} - C_{\text{base}}$$

This is the non-cacheable context accumulation.

**Definition 10 (Context Reduction Ratio).**
$$R = 1 - \frac{C_{\text{peak}}^{\text{ECM}}}{C_{\text{peak}}^{\text{linear}}}$$

Our reported 88% reduction corresponds to $R = 0.88$.

### B.1.2 Growth Rate Analysis

**Definition 11 (Per-Task Growth Rate).**

For a sequence of $T$ tasks:

$$\gamma = \frac{C(T) - C(1)}{T - 1}$$

- Linear agent: $\gamma_{\text{linear}} \approx 780$ tokens/task (observed)
- ECM agent: $\gamma_{\text{ECM}} \approx 36$ tokens/task (observed)

**Definition 12 (Growth Complexity).**
- Linear: $C(t) = O(t)$ — monotonic growth
- ECM: $C(t) = O(1)$ — sawtooth pattern (grows within scope, resets on transition)

### B.1.3 Total Token Metrics

**Definition 13 (Total Input Tokens).**
$$T_{\text{in}} = \sum_{i=1}^{N} C(t_i)$$

where $N$ is the total number of API calls.

**Definition 14 (Total Output Tokens).**
$$T_{\text{out}} = \sum_{i=1}^{N} |r_i|$$

where $r_i$ is the response at call $i$.

**Definition 15 (Token Efficiency).**
$$\eta = \frac{\text{Tasks Completed}}{T_{\text{in}} + T_{\text{out}}}$$

Higher is better.

## B.2 Memory Effectiveness Metrics

### B.2.1 Knowledge Retention

**Definition 16 (Knowledge Retention Test).**

Given a sequence of tasks $[t_1, \ldots, t_T]$, at task $t_T$ we query:
$$\text{KRT}(k) = \mathbb{1}[\text{agent recalls key decision from task } t_k]$$

Aggregate:
$$\text{KRT}_{\text{avg}} = \frac{1}{T-1} \sum_{k=1}^{T-1} \text{KRT}(k)$$

For linear agents, KRT degrades as $T$ increases (context amnesia).
For ECM agents, KRT should remain stable (notes preserve decisions).

### B.2.2 Forward Transfer

**Definition 17 (Forward Transfer Score).**

Adapted from continual learning literature [30]:

$$\text{FWT} = \frac{1}{T-1} \sum_{i=2}^{T} (A_{i} - b_i)$$

where:
- $A_i$ = performance on task $i$ after learning tasks $1, \ldots, i-1$
- $b_i$ = baseline performance on task $i$ without prior context

Positive FWT indicates knowledge from earlier tasks helps later tasks.

### B.2.3 Note Quality

**Definition 18 (Note Utility Score).**

For each note $n$ created:
$$U(n) = \frac{\text{Retrievals of } n}{\text{Opportunities to retrieve } n}$$

Aggregate:
$$\bar{U} = \frac{1}{|N|} \sum_{n \in N} U(n)$$

Notes with $U(n) = 0$ are "dead notes" (created but never used).
Notes with $U(n) > 0$ indicate successful knowledge transfer.

**Definition 19 (Note Compression Ratio).**
$$\rho_n = \frac{|M_{\text{scope}}|}{|n|}$$

where $|M_{\text{scope}}|$ is the working memory size when the note was created.
Higher $\rho_n$ indicates more aggressive compression.

### B.2.4 Insight Utility

**Definition 20 (Insight Coverage).**
$$\text{Coverage}(i) = \frac{\text{Scopes where } i \text{ was retrieved}}{|\mathcal{S}|}$$

High coverage indicates globally useful knowledge.

## B.3 Navigation Metrics

### B.3.1 Scope Structure

**Definition 21 (Scope Count).**
$$|\mathcal{S}| = \text{Number of scopes created}$$

**Definition 22 (Average Scope Lifetime).**
$$\bar{L} = \frac{1}{|\mathcal{S}|} \sum_{S \in \mathcal{S}} |M_S|$$

where $|M_S|$ is the number of messages in scope $S$ before transition.

**Definition 23 (Scope Depth).**

For tree-like scope creation patterns:
$$d_{\max} = \max_{S \in \mathcal{S}} \text{depth}(S)$$

where depth is the number of `scope` operations from `main`.

### B.3.2 Navigation Patterns

**Definition 24 (Transition Count).**
$$|\mathcal{T}| = |\{\texttt{scope}\}| + |\{\texttt{goto}\}|$$

**Definition 25 (Return Rate).**
$$r_{\text{return}} = \frac{|\{\texttt{goto main}\}|}{|\mathcal{T}|}$$

High return rate indicates disciplined "hub-and-spoke" pattern.

**Definition 26 (Navigation Entropy).**

Let $p(s_i \rightarrow s_j)$ be the probability of transitioning from $s_i$ to $s_j$:
$$H_{\text{nav}} = -\sum_{i,j} p(s_i \rightarrow s_j) \log p(s_i \rightarrow s_j)$$

Low entropy = predictable navigation (e.g., always return to main)
High entropy = complex navigation patterns

## B.4 Comparative Metrics

### B.4.1 vs. Linear Baseline

| Metric | Formula | Target |
|--------|---------|--------|
| Context Reduction | $1 - C_{\text{peak}}^{\text{ECM}} / C_{\text{peak}}^{\text{linear}}$ | > 50% |
| Speed Improvement | $1 - T_{\text{exec}}^{\text{ECM}} / T_{\text{exec}}^{\text{linear}}$ | > 0% |
| Task Completion | $\text{Tasks}_{\text{ECM}} / \text{Tasks}_{\text{linear}}$ | $\geq 1$ |

### B.4.2 vs. Stack-Based (Context-Folding)

| Metric | What it measures | ECM Advantage |
|--------|------------------|---------------|
| Navigation Flexibility | Can goto non-parent scope? | Yes (graph) vs No (stack) |
| Training Requirement | Training data needed | 0 vs RL training |
| Model Portability | Works on any model? | Yes vs No (model-specific) |

### B.4.3 Continual Learning Metrics (from SWE-Bench-CL)

**Definition 27 (Average Accuracy).**
$$\bar{A} = \frac{1}{T} \sum_{i=1}^{T} A_i$$

**Definition 28 (Forgetting).**
$$F = \frac{1}{T-1} \sum_{i=1}^{T-1} \max_{j \leq i} (A_j^{(i)} - A_j^{(T)})$$

where $A_j^{(i)}$ is performance on task $j$ after learning task $i$.

**Definition 29 (Backward Transfer).**
$$\text{BWT} = \frac{1}{T-1} \sum_{i=1}^{T-1} (A_i^{(T)} - A_i^{(i)})$$

Positive BWT = later learning improves earlier task performance.

## B.5 Proposed Evaluation Protocol

### B.5.1 Token Economics Evaluation

```
For each task sequence [t_1, ..., t_T]:
    For each agent in [LINEAR, ECM]:
        Record: C(t) for all t
        Compute: C_peak, C_base, ΔC, γ
        Compute: T_in, T_out, η

    Report: R (reduction ratio)
    Plot: C(t) over time (sawtooth vs linear)
```

### B.5.2 Knowledge Transfer Evaluation

```
For each task sequence:
    For ECM agent:
        At task t_T:
            Query agent about decisions from t_1, t_5, t_10
            Score: KRT(1), KRT(5), KRT(10)

        For each task t_i:
            Record: Notes created, insights created
            Record: Notes retrieved from previous tasks

    Compute: FWT, U_avg, Coverage
```

### B.5.3 Navigation Analysis

```
For each ECM execution:
    Build navigation graph G = (V, E)
    Compute: |S|, L_avg, d_max
    Compute: |T|, r_return, H_nav
    Visualize: Scope tree / graph
```

## B.6 Benchmark-Specific Metrics

### B.6.1 SWE-Bench-CL

| Metric | Description |
|--------|-------------|
| Pass@1 | Fraction of tasks solved correctly |
| Context at Task T | $C(T)$ for final task |
| Forward Transfer | FWT across task sequence |

### B.6.2 MemoryBench

| Metric | Description |
|--------|-------------|
| Episodic Recall | Accuracy on "what happened?" queries |
| Semantic Recall | Accuracy on "what rule applies?" queries |
| Procedural Recall | Accuracy on "how to do X?" queries |

### B.6.3 AppWorld

| Metric | Description |
|--------|-------------|
| Task Success Rate | Fraction of 750 tasks completed |
| API Efficiency | Tokens per successful task |
| Cross-App Transfer | Knowledge used across different apps |
