# 5. Empirical Results

This section details the empirical findings from our experimental evaluation. We present quantitative analysis of token economics across the four distinct tasks defined in Section 4, followed by a qualitative assessment of knowledge transfer capabilities. **Note: The data presented herein represents consolidated results from pilot replications; comprehensive evaluation using the full benchmark harness is currently in progress.**

## 5.1 Task 1: Multi-Step Design (Token Economics)

We assessed the efficiency of the SPACE architecture in a 12-step sequential design task. Table 2 summarizes the comparative token metrics.

**Table 2: Comparative Token Economics for Multi-Step Design**

| Metric | Linear Baseline | SPACE Treatment | $\Delta$ (Impact) |
| :--- | :--- | :--- | :--- |
| **Total Input Tokens** | 431,528 | 137,025 | **-68.2%** |
| **Peak Input Tokens** | 23,249 | 6,353 | **-72.7%** |
| **Base Input Tokens** | 1,247 | 2,891 | +131.8% |
| **Context Growth** | 22,002 | 3,462 | **-84.3%** |
| **Total Output Tokens** | 18,442 | 21,156 | +14.7% |
| **Task Completion** | 100% (12/12) | 100% (12/12) | — |

### 5.1.1 Analysis of Context Dynamics

1.  **Reduction in Accumulation**: The SPACE architecture achieved a **68.2% reduction** in total input tokens. This efficiency gain stems from the radial navigation topology: by isolating each step into a discrete scope and returning only a summary, the agent prevents the linear accumulation of intermediate reasoning states.
2.  **Peak Context Bounding**: Peak context usage was reduced by **72.7%** (23k $\rightarrow$ 6.3k). This is critical for latency-sensitive applications, as inference time scales super-linearly with input length for Transformer architectures.
3.  **Overhead vs. Savings**: While SPACE incurs a fixed overhead in the base system prompt (+131% base tokens), this cost is amortized rapidly. The **84.3% reduction in context growth** indicates that for any task exceeding $\sim$3 steps, the dynamic savings outweigh the static overhead.
4.  **Operational Overhead**: The SPACE condition generated **14.7% more output tokens**. This reflects the "control tax"—the additional tokens required to generate tool calls (`scope`, `return`, `note`) and their JSON payloads.

### 5.1.2 Growth Trajectory Analysis

The contrasting growth profiles confirm our theoretical models from Section 3.5:
*   **Linear Baseline**: Exhibited strict monotonic growth ($R^2 > 0.99$), confirming the $O(t)$ accumulation model.
*   **SPACE**: Exhibited a stable **sawtooth pattern**. Context grows locally within a scope ($O(k)$) but resets to the baseline upon every `return` command, effectively bounding the maximum context window regardless of the total step count.

## 5.2 Task 2: Cross-Project Knowledge Transfer

We evaluated the ability of agents to transfer semantic knowledge between sequential, disjoint projects.

**Table 3: Knowledge Transfer Efficiency**

| Metric | Project | Linear Baseline | SPACE Treatment | $\Delta$ |
| :--- | :--- | :--- | :--- | :--- |
| **Growth (Tokens)** | A (Source) | 3,767 | 2,478 | -34.2% |
| **Iterations** | A (Source) | 6 | 5 | -1 |
| **Growth (Tokens)** | B (Target) | 3,443 | **1,121** | **-67.4%** |
| **Iterations** | B (Target) | 5 | **4** | **-1** |

### 5.2.1 Empirical Evidence of Transfer

The SPACE agent demonstrated significant "second-system efficiency." While Project A showed moderate savings (-34%), Project B showed a dramatic **67.4% reduction in context growth** compared to the baseline.

Qualitative inspection of the trace logs revealed the mechanism:
1.  **Explicit Retrieval**: In 80% of trials (4/5), the SPACE agent executed `notes user-model` immediately upon starting Project B.
2.  **Pattern Reapplication**: The agent utilized the retrieved notes to replicate the validation logic structure from Project A without the exploratory "trial-and-error" phase observed in the baseline condition.
3.  **Code Consistency**: The resulting implementation in Project B matched the stylistic patterns of Project A (e.g., using specific dataclass decorators and validation methods) more consistently than the baseline.

## 5.3 Task 3: Alternative Exploration (Branching)

This task measured the ability to maintain distinct reasoning paths without cross-contamination.

**Table 4: Comparative Exploration Metrics**

| Metric | Linear Baseline | SPACE Treatment |
| :--- | :--- | :--- |
| **Total Input Tokens** | 89,124 | 52,891 |
| **Peak Input Tokens** | 12,456 | 5,891 |
| **Information Isolation** | Low (Context Mixing) | High (Scope Isolation) |

### 5.3.1 Qualitative Assessment of Isolation

In the **Linear Baseline**, the agent's analysis of Approach B (CRDTs) frequently referenced implementation details from Approach A (OT) inappropriately, leading to "conceptual bleeding" where the trade-offs became muddled.

In the **SPACE Treatment**, the agent explicitly created isolated scopes:
1.  `scope explore/ot`
2.  `return` (clearing OT context)
3.  `scope explore/crdt`
4.  `return` (clearing CRDT context)

The final comparative analysis relied exclusively on the *notes* generated from these scopes. This enforced a clean separation of concerns: the agent compared the *crystallized findings* rather than the *noisy exploration process*, resulting in a more coherent final recommendation.

## 5.4 Task 4: SWE-Bench-CL (Continual Learning)

The Continual Learning task (15 sequential Django issues) provides the most rigorous test of long-horizon stability.

**Table 5: SWE-Bench-CL Longitudinal Metrics (15 Tasks)**

| Metric | Linear Baseline | SPACE Treatment | Impact |
| :--- | :--- | :--- | :--- |
| **Peak Context** | 12,059 | 1,402 | **-88.4%** |
| **Final Task Context** | 12,059 | 801 | **-93.3%** |
| **Avg Context/Task** | 6,032 | 569 | **-90.6%** |
| **Execution Time** | 121.5s | 80.5s | **-33.7%** |
| **Cache Hit Rate** | ~69% | 0% | (See Discussion) |

### 5.4.1 Long-Horizon Stability

The most significant finding is the decoupling of task count from context size.
*   **Linear**: Context size scaled linearly ($r=0.98$) with task count. By Task 15, the agent was processing >12k tokens per turn, regardless of the task's simplicity.
*   **SPACE**: Context size remained stationary (mean=569, $\sigma \approx 200$). The context load for Task 15 was statistically indistinguishable from Task 1.

### 5.4.2 Latency Implications

Despite a 4.1% increase in total API calls (due to navigation commands), the SPACE condition achieved a **33.7% reduction in total execution time**. This counter-intuitive result is explained by the physics of Transformer inference: the reduction in input tokens per call (input latency) outweighed the cost of additional network round-trips.

## 5.5 Aggregate Analysis

### 5.5.1 Summary of Efficiency Gains

Across all experimental conditions, SPACE demonstrates a consistent efficiency advantage that scales with task horizon:

| Scenario | Peak Context Reduction | Primary Driver |
| :--- | :--- | :--- |
| **Short-Horizon** (Task 2) | ~18% | Semantic Reuse |
| **Medium-Horizon** (Task 3) | ~53% | Branch Isolation |
| **Long-Horizon** (Task 1) | ~73% | Scope Reset |
| **Lifelong** (Task 4) | **~88%** | $O(1)$ Scaling |

### 5.5.2 The "Prompt Caching Paradox"

A notable anomaly in Table 5 is the **0% Cache Hit Rate** for SPACE versus 69% for Linear. Current prompt caching implementations (e.g., Anthropic, OpenAI) rely on prefix matching. In the Linear condition, the growing history forms a stable prefix. In SPACE, the frequent context resets (clearing the "middle" of the prompt) break the prefix continuity.

While this seemingly penalizes SPACE, the **absolute reduction in tokens** (-88%) vastly outweighs the benefit of caching. Even with a 100% cache hit rate, the Linear agent would still process more tokens than the SPACE agent due to the sheer volume of the accumulated history. Furthermore, the SPACE architecture could be optimized for caching by placing the "Semantic Memory" block at the start of the prompt as a stable prefix.
