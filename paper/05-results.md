# 5. Results

This section presents empirical findings from our evaluation on SWE-Bench-CL and LifelongAgentBench. We report results for both GPT-4o-mini and GPT-5-mini to assess generalization across model capabilities.

## 5.1 SWE-Bench-CL

### 5.1.1 Context Dynamics

Table 2 summarizes context metrics across the full task sequence.

**Table 2: SWE-Bench-CL Context Metrics**

| Metric | Linear (GPT-4o-mini) | SPACE (GPT-4o-mini) | Linear (GPT-5-mini) | SPACE (GPT-5-mini) |
| :--- | :--- | :--- | :--- | :--- |
| **Peak Context (tokens)** | [TBD] | [TBD] | [TBD] | [TBD] |
| **Context at Task 15** | [TBD] | [TBD] | [TBD] | [TBD] |
| **Avg Context/Task** | [TBD] | [TBD] | [TBD] | [TBD] |
| **Cumulative Tokens** | [TBD] | [TBD] | [TBD] | [TBD] |
| **Execution Time** | [TBD] | [TBD] | [TBD] | [TBD] |

**Key findings**:
- [TBD: Describe context growth patterns]
- [TBD: Compare linear vs bounded growth]
- [TBD: Sawtooth pattern observation]

### 5.1.2 Task Success Rate

Table 3 reports task completion metrics.

**Table 3: SWE-Bench-CL Task Performance**

| Metric | Linear (GPT-4o-mini) | SPACE (GPT-4o-mini) | Linear (GPT-5-mini) | SPACE (GPT-5-mini) |
| :--- | :--- | :--- | :--- | :--- |
| **Success Rate** | [TBD]% | [TBD]% | [TBD]% | [TBD]% |
| **Partial Success** | [TBD]% | [TBD]% | [TBD]% | [TBD]% |
| **Success @Task 1-5** | [TBD]% | [TBD]% | [TBD]% | [TBD]% |
| **Success @Task 11-15** | [TBD]% | [TBD]% | [TBD]% | [TBD]% |

**Key findings**:
- [TBD: Performance preservation across sequence]
- [TBD: Degradation in linear condition]
- [TBD: Stability in SPACE condition]

### 5.1.3 Growth Trajectory Analysis

Figure 1 illustrates the contrasting context growth profiles.

[TBD: Figure 1 - Context size vs task number for Linear and SPACE conditions]

The linear baseline exhibits monotonic growth consistent with $O(T)$ accumulation. The SPACE condition exhibits a characteristic **sawtooth pattern**: context grows within each scope but resets upon `return`, maintaining bounded peak context independent of task count.

## 5.2 LifelongAgentBench

### 5.2.1 Forward Transfer

Table 4 reports forward transfer metrics—whether knowledge from early tasks improves performance on later tasks.

**Table 4: LifelongAgentBench Forward Transfer**

| Metric | Linear | SPACE | $\Delta$ |
| :--- | :--- | :--- | :--- |
| **Early Task Performance (1-5)** | [TBD]% | [TBD]% | [TBD] |
| **Late Task Performance (N-5 to N)** | [TBD]% | [TBD]% | [TBD] |
| **Transfer Gain** | [TBD] | [TBD] | [TBD] |

**Key findings**:
- [TBD: Evidence of knowledge transfer via insights]
- [TBD: Comparison with linear baseline]

### 5.2.2 Backward Interference

Table 5 reports whether performance on early task types degrades as the agent accumulates experience.

**Table 5: LifelongAgentBench Backward Interference**

| Task Type | Linear (Early) | Linear (Late) | SPACE (Early) | SPACE (Late) |
| :--- | :--- | :--- | :--- | :--- |
| **Coding** | [TBD]% | [TBD]% | [TBD]% | [TBD]% |
| **Reasoning** | [TBD]% | [TBD]% | [TBD]% | [TBD]% |
| **Retrieval** | [TBD]% | [TBD]% | [TBD]% | [TBD]% |

**Key findings**:
- [TBD: Catastrophic forgetting in linear condition]
- [TBD: Stability in SPACE condition]

## 5.3 Cross-Model Analysis

Table 6 compares the effectiveness of SPACE across model generations.

**Table 6: Model Comparison Summary**

| Metric | GPT-4o-mini | GPT-5-mini | Observation |
| :--- | :--- | :--- | :--- |
| **Context Reduction** | [TBD]% | [TBD]% | [TBD] |
| **Success Rate Improvement** | [TBD]% | [TBD]% | [TBD] |
| **Command Compliance** | [TBD]% | [TBD]% | [TBD] |

**Key findings**:
- [TBD: Whether SPACE benefits generalize to reasoning models]
- [TBD: Differences in scope utilization patterns]

## 5.4 Hypothesis Evaluation

We evaluate the four hypotheses from §4.5:

### H1: Stability (Context Growth)

| Condition | Expected | Observed | Supported? |
| :--- | :--- | :--- | :--- |
| Linear | $O(T)$ growth | [TBD] | [TBD] |
| SPACE | $O(k_{\max})$ bounded | [TBD] | [TBD] |

### H2: Performance Preservation

| Condition | Expected | Observed | Supported? |
| :--- | :--- | :--- | :--- |
| Linear | Degradation over sequence | [TBD] | [TBD] |
| SPACE | Stable performance | [TBD] | [TBD] |

### H3: Knowledge Transfer (Within-Session)

| Condition | Expected | Observed | Supported? |
| :--- | :--- | :--- | :--- |
| SPACE (with insights) | Improved late-task performance | [TBD] | [TBD] |
| SPACE (fresh) | Baseline late-task performance | [TBD] | [TBD] |

### H4: Cross-Session Transfer (Across Projects)

| Condition | Expected | Observed | Supported? |
| :--- | :--- | :--- | :--- |
| SPACE (new project, inherited insights) | Improved initial performance | [TBD] | [TBD] |
| SPACE (new project, empty insights) | Baseline initial performance | [TBD] | [TBD] |

**Table 7: Cross-Project Transfer Metrics**

| Metric | Fresh Start | With Inherited Insights | $\Delta$ |
| :--- | :--- | :--- | :--- |
| **First 5 Tasks Success Rate** | [TBD]% | [TBD]% | [TBD] |
| **Insight Retrieval Rate** | N/A | [TBD]% | — |
| **Novel Insights Generated** | [TBD] | [TBD] | [TBD] |

**Key findings**:
- [TBD: Whether insights from project-v1 benefit project-v2]
- [TBD: Insight retrieval patterns across project boundaries]
- [TBD: Comparison of convergence speed with/without prior knowledge]

## 5.5 Ablation Studies

### 5.5.1 Component Ablations

**Table 8: Component Ablation Results (SWE-Bench-CL)**

| Condition | Peak Context | Context Reduction | Success Rate | Forward Transfer |
| :--- | :--- | :--- | :--- | :--- |
| **Full SPACE** | [TBD] | [TBD]% | [TBD]% | [TBD] |
| **No Insights** | [TBD] | [TBD]% | [TBD]% | [TBD] |
| **No Notes** | [TBD] | [TBD]% | [TBD]% | [TBD] |
| **No Scopes** | [TBD] | [TBD]% | [TBD]% | [TBD] |
| **Linear Baseline** | [TBD] | — | [TBD]% | [TBD] |

**Key findings**:
- [TBD: Relative contribution of each component]
- [TBD: Which component is most critical for context efficiency?]
- [TBD: Which component is most critical for knowledge transfer?]

### 5.5.2 Scope Granularity Analysis

**Table 9: Scope Usage Patterns**

| Metric | GPT-4o-mini | GPT-5-mini |
| :--- | :--- | :--- |
| **Avg Scope Length (turns)** | [TBD] | [TBD] |
| **Scopes per Task** | [TBD] | [TBD] |
| **Return Rate** | [TBD]% | [TBD]% |
| **Abandoned Scopes** | [TBD] | [TBD] |

**Key findings**:
- [TBD: Correlation between scope length and task success]
- [TBD: Differences in scoping behavior between models]
- [TBD: Evidence of micro-scoping or degenerate linearity]

### 5.5.3 Memory Utilization Analysis

**Table 10: Memory Tier Utilization**

| Metric | GPT-4o-mini | GPT-5-mini |
| :--- | :--- | :--- |
| **Notes Created (total)** | [TBD] | [TBD] |
| **Notes Retrieved (total)** | [TBD] | [TBD] |
| **Note Retrieval Rate** | [TBD]% | [TBD]% |
| **Insights Created (total)** | [TBD] | [TBD] |
| **Insight Retrieval Rate** | [TBD]% | [TBD]% |
| **"Write-Only" Notes** | [TBD]% | [TBD]% |

**Key findings**:
- [TBD: What fraction of notes are actually useful?]
- [TBD: Are insights generalizing or remaining task-specific?]
- [TBD: Evidence of effective knowledge consolidation]

## 5.6 Summary

[TBD: 2-3 paragraph summary of key findings]

**Primary result**: [TBD]

**Secondary findings**: [TBD]

**Unexpected observations**: [TBD]
