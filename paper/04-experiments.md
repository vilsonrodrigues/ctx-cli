# 4. Experimental Setup

We evaluate SPACE on continual learning benchmarks designed to stress-test context management over extended task sequences. This section describes our benchmark selection, model configurations, evaluation metrics, and experimental conditions.

## 4.1 Benchmarks

We focus on **continual learning** benchmarks where agents must maintain coherent performance across sequential tasks without resetting between episodes. This setting directly tests the stability barrier identified in §1.1.

### 4.1.1 SWE-Bench-CL

**SWE-Bench-CL** [30] adapts the SWE-Bench dataset for continual learning evaluation. The agent faces a sequence of chronologically ordered GitHub issues from real-world repositories (e.g., Django, Flask).

**Key properties**:
- **Sequential dependency**: Tasks are ordered chronologically; later issues may reference or build upon earlier fixes.
- **No reset**: The agent maintains continuous identity across the full sequence.
- **Realistic complexity**: Issues range from bug fixes to feature implementations.

**Evaluation protocol**:
- **Task success**: Measured via the official Docker-based test harness.
- **Context dynamics**: Token usage tracked per task and cumulatively.

### 4.1.2 LifelongAgentBench

**LifelongAgentBench** [35] provides a complementary evaluation focusing on knowledge retention and transfer across diverse task types. Unlike SWE-Bench-CL which focuses on a single domain (software engineering), LifelongAgentBench tests generalization across heterogeneous tasks.

**Key properties**:
- **Heterogeneous tasks**: Combines coding, reasoning, and information retrieval tasks in interleaved sequences.
- **Explicit transfer tests**: Includes probe tasks that measure whether knowledge from early tasks benefits later ones.
- **Forgetting detection**: Re-tests task types seen earlier in the sequence to detect catastrophic forgetting.
- **Configurable sequences**: Allows controlled evaluation of sequence length and task diversity.

**Evaluation protocol**:
- **Forward transfer**: Performance improvement on later tasks due to earlier learning, measured as $\text{FWT} = \frac{1}{T-1} \sum_{i=2}^{T} (A_i - b_i)$ where $A_i$ is performance with history and $b_i$ is baseline performance in isolation.
- **Backward interference**: Performance degradation on task types seen earlier, measured by re-testing initial task types at sequence end.

## 4.2 Models

We evaluate SPACE with two models to test generalization across model capabilities:

| Model | Parameters | Context Window | Reasoning Style |
| :--- | :--- | :--- | :--- |
| GPT-4o-mini | ~8B (est.) | 128K | Standard |
| GPT-5-mini | TBD | TBD | Extended reasoning |

**Rationale**: GPT-4o-mini represents current cost-effective deployment. GPT-5-mini tests whether SPACE benefits extend to next-generation reasoning models with longer internal chains-of-thought.

All models accessed via OpenAI API with `temperature=0` for reproducibility.

## 4.3 Metrics

We report metrics across two dimensions:

### 4.3.1 Task Performance

| Metric | Definition |
| :--- | :--- |
| **Success Rate** | Percentage of tasks passing official test suites |
| **Partial Success** | Tasks with correct approach but incomplete implementation |

### 4.3.2 Context Economics

| Metric | Definition |
| :--- | :--- |
| **Peak Context** | Maximum tokens in a single inference call |
| **Cumulative Tokens** | Total tokens processed across all tasks |
| **Growth Rate** | Tokens per task as sequence progresses |
| **Context at Task N** | Snapshot of context size at task boundaries |

Token counts measured using `tiktoken` with model-appropriate encoding.

## 4.4 Experimental Conditions

### 4.4.1 Baseline: Linear Agent

- Standard chat completion loop
- Full history retention (no truncation within context limit)
- Minimal system prompt (~50 tokens)
- No explicit memory management tools

### 4.4.2 Treatment: SPACE Agent

- SPACE agent loop (Algorithm 2 from §3.6)
- Context managed via explicit commands
- Extended system prompt with memory semantics (~800 tokens)
- Full command set: `scope`, `return`, `note`, `insight`, `notes`, `insights`, `status`

### 4.4.3 Project Configuration

For experiments requiring multiple task sequences, we use the project mechanism:
- Each benchmark run initializes a new project
- Previous project scopes are archived with `@project` notation
- Insights persist across project boundaries (cross-session knowledge transfer)
- Notes remain accessible via explicit scope reference (e.g., `notes debug@run1`)

**Cross-Project Condition**: To evaluate H4 (Cross-Session Transfer), we run a second sequence with insights from the first sequence preserved but working memory reset.

### 4.4.4 Controlled Variables

| Variable | Setting |
| :--- | :--- |
| Task order | Fixed (chronological for SWE-Bench-CL) |
| Maximum turns per task | 30 |
| Runs per condition | 5 (for statistical significance) |
| Random seed | Fixed per run |

## 4.5 Hypotheses

**H1 (Stability)**: SPACE agents maintain bounded context growth ($O(k_{\max})$) independent of task count, while linear agents exhibit linear growth ($O(T)$).

**H2 (Performance Preservation)**: SPACE agents maintain stable task success rates as sequences lengthen, while linear agents show degradation due to attention dilution.

**H3 (Knowledge Transfer)**: SPACE agents with populated semantic memory (insights) show improved performance on later tasks compared to agents starting fresh.

**H4 (Cross-Session Transfer)**: SPACE agents starting a new project with insights from a previous project outperform agents starting with empty semantic memory, demonstrating cross-session knowledge transfer.

## 4.6 Ablation Studies

To isolate the contribution of each SPACE component, we design the following ablation conditions:

### 4.6.1 Component Ablations

| Condition | Scopes | Notes | Insights | Description |
| :--- | :---: | :---: | :---: | :--- |
| **Full SPACE** | ✓ | ✓ | ✓ | Complete architecture |
| **No Insights** | ✓ | ✓ | ✗ | Episodic memory only; no semantic generalization |
| **No Notes** | ✓ | ✗ | ✓ | No within-scope persistence; only summaries on return |
| **No Scopes** | ✗ | ✓ | ✓ | Linear context with note/insight commands |
| **Linear Baseline** | ✗ | ✗ | ✗ | Standard chat completion |

**Expected outcomes**:
- **No Insights**: Should show reduced forward transfer (H3) but maintain context efficiency (H1).
- **No Notes**: Should show increased "context amnesia" within scopes; return summaries must carry all information.
- **No Scopes**: Should show linear context growth but potentially better knowledge retention than pure linear (notes/insights still available).

### 4.6.2 Scope Granularity Analysis

We analyze the relationship between scope usage patterns and performance:

| Metric | Definition |
| :--- | :--- |
| **Avg Scope Length** | Mean turns per scope before return |
| **Scope Count** | Number of scopes created per task |
| **Return Rate** | Ratio of `return` commands to `scope` commands (ideal: 1.0) |

**Research questions**:
- Does shorter scope length correlate with better context efficiency?
- Is there an optimal scope granularity for different task types?
- Do agents naturally converge on consistent scoping patterns?

### 4.6.3 Memory Utilization Analysis

We track how agents use the memory tiers:

| Metric | Definition |
| :--- | :--- |
| **Note Creation Rate** | Notes created per scope |
| **Insight Creation Rate** | Insights created per task |
| **Note Retrieval Rate** | Fraction of notes accessed via `notes` command |
| **Insight Retrieval Rate** | Fraction of tasks where `insights` command is used |

**Research questions**:
- What fraction of created notes are actually retrieved? (Write-only memory detection)
- Do insights generalize across task types or remain domain-specific?
- How does memory utilization change as sequences lengthen?

## 4.7 Limitations

1. **Model coverage**: Primary results from OpenAI models. Replication with open-source models (Qwen, Llama) is left for future work.
2. **Benchmark scope**: Two continual learning benchmarks. Additional domains (e.g., long-horizon GUI tasks via OSWorld) would strengthen generalization claims.
3. **Insight quality**: We do not separately evaluate the quality of agent-generated insights; this is measured indirectly through task performance.
