# Appendix B: Evaluation Metrics

## B.1 Token Economics Metrics

### B.1.1 Primary Definitions

**Definition 6 (Context Size at Step t).**
$$C(t) = |P_{\text{sys}}| + |M_{\text{active}}(t)|$$
where $P_{\text{sys}}$ denotes the system prompt and $M_{\text{active}}(t)$ denotes the active message buffer at step $t$.

**Definition 7 (Peak Context).**
$$C_{\text{peak}} = \max_{t \in [1, T]} C(t)$$
This metric serves as a proxy for maximum inference latency and VRAM requirements.

**Definition 8 (Context Growth).**
$$\Delta C = C_{\text{peak}} - C_{\text{base}}$$
where $C_{\text{base}} = C(1)$ represents the static overhead. This metric isolates the dynamic accumulation of context.

**Definition 9 (Context Reduction Ratio).**
$$R = 1 - \frac{C_{\text{peak}}^{\text{SPACE}}}{C_{\text{peak}}^{\text{linear}}}$$
A value of $R=0.88$ indicates an 88% reduction in peak context requirements.

### B.1.2 Growth Rate Analysis

**Definition 10 (Per-Task Growth Rate).**
For a sequence of $T$ tasks:
$$\gamma = \frac{C(T) - C(1)}{T - 1}$$
*   **Linear Agent**: $\gamma_{\text{linear}} \approx 780$ tokens/task (Empirically Observed).
*   **SPACE Agent**: $\gamma_{\text{SPACE}} \approx 36$ tokens/task (Empirically Observed).

This differential confirms the $O(t)$ vs. $O(1)$ scaling characteristics.

## B.2 Memory Effectiveness Metrics

### B.2.1 Knowledge Retention

**Definition 11 (Knowledge Retention Test - KRT).**
Given a sequence of tasks $[t_1, \ldots, t_T]$, at task $t_T$ we define the retention indicator function:
$$\text{KRT}(k) = \mathbb{1}[\text{Agent successfully recalls key decision from task } t_k]$$
Aggregate retention score:
$$\text{KRT}_{\text{avg}} = \frac{1}{T-1} \sum_{k=1}^{T-1} \text{KRT}(k)$$

### B.2.2 Forward Transfer

**Definition 12 (Forward Transfer Score - FWT).**
Adapted from Continual Learning literature [30]:
$$\text{FWT} = \frac{1}{T-1} \sum_{i=2}^{T} (A_{i} - b_i)$$
where:
*   $A_i$ is the performance on task $i$ given the history of tasks $1..i-1$.
*   $b_i$ is the baseline performance on task $i$ in isolation.
Positive FWT indicates that the accumulated context (notes/insights) is effectively aiding new tasks.

### B.2.3 Note Utility

**Definition 13 (Note Utility Score).**
For each note $n \in N$, we define its utility as:
$$U(n) = \frac{\text{Retrievals of } n}{\text{Opportunities to retrieve } n}$$
Notes with $U(n)=0$ represent "Write-Only Memory"—information that was persisted but never utilized, indicating potential inefficiencies in the agent's summarization strategy.

## B.3 Navigation Topology Metrics

### B.3.1 Graph Metrics

**Definition 14 (Return Rate).**
$$r_{\text{return}} = \frac{|\{\texttt{return}\}|}{|\{\texttt{scope}\}|}$$
A return rate of $1.0$ indicates perfect adherence to the hub-and-spoke topology. Lower rates suggest "abandoned" scopes or context drift.

**Definition 15 (Navigation Entropy).**
Let $p(s_i \rightarrow s_j)$ be the transition probability between scopes:
$$H_{\text{nav}} = -\sum_{i,j} p(s_i \rightarrow s_j) \log p(s_i \rightarrow s_j)$$
Low entropy implies highly structured, predictable navigation (ideal for routine tasks). High entropy implies unstructured exploration.

## B.4 Comparative Benchmarking Protocol

### B.4.1 Baseline Comparison
We evaluate performance relative to the **Linear Baseline** using three key indicators:
1.  **Context Reduction**: $1 - C_{\text{peak}}^{\text{SPACE}} / C_{\text{peak}}^{\text{linear}}$ (Target: $>50\%$)
2.  **Speed Improvement**: $1 - T_{\text{exec}}^{\text{SPACE}} / T_{\text{exec}}^{\text{linear}}$ (Target: $>0\%$)
3.  **Task Success Parity**: $\text{Success}_{\text{SPACE}} / \text{Success}_{\text{linear}}$ (Target: $\ge 1.0$)

### B.4.2 Learned Comparison
We compare against **Context-Folding** and **AgentFold** along qualitative dimensions:
1.  **Training Requirement**: Zero-shot vs. RL/SFT.
2.  **Model Portability**: Universal vs. Model-Specific.
3.  **Memory Persistence**: Cross-session (Notes) vs. Session-only (Summaries).
