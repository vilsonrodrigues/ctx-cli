# 4. Experimental Setup

We evaluate SPACE across four experimental scenarios designed to isolate specific cognitive capabilities and measure token economics under controlled conditions. This section details the benchmark selection rationale, experimental infrastructure, and specific task protocols.

## 4.1 Benchmark Selection Rationale

Recent benchmarks for long-horizon agents include **OdysseyBench** [32] (office workflows), **AppWorld** [33] (interactive coding), **TheAgentCompany** [34] (enterprise tasks), and **MemoryBench** [35] (long-term retrieval). We selected **SWE-Bench-CL** [30] as our primary evaluation platform for the following reasons:

1.  **Continual Learning Focus**: Unlike episodic benchmarks, SWE-Bench-CL tasks are chronologically ordered, enabling the measurement of both forward transfer (applying past knowledge to new tasks) and backward transfer (updating general understanding based on new evidence).
2.  **Sequential Context Accumulation**: The benchmark simulates a realistic development lifecycle where each task builds upon the codebase state of previous tasks—precisely the scenario where linear context accumulation becomes prohibitive.
3.  **Established Baseline**: It provides a standard for comparison against both linear conversation agents and recent learned compression approaches.
4.  **Reproducibility**: The dataset offers well-defined evaluation metrics and deterministic task environments.

We complement SWE-Bench-CL with targeted synthetic tasks (Multi-Step Design, Knowledge Transfer, Alternative Exploration) to isolate specific mechanical properties of the SPACE architecture that might be obscured in aggregate benchmarks.

## 4.2 Infrastructure and Methodology

### 4.2.1 Model Specification
All experiments utilize **GPT-4o-mini** [42] (version `2024-07-18`) accessed via the OpenAI API. We selected this model to demonstrate that SPACE's architectural benefits are realizable with cost-effective, mid-tier models, not just frontier-class reasoning models. The model was configured with `temperature=0.7` to balance creativity with deterministic tool usage.

### 4.2.2 Token Metrology
Token usage was quantified using `tiktoken` with the `o200k_base` encoding scheme. We report metrics across six dimensions:

| Metric | Definition | Significance |
| :--- | :--- | :--- |
| **Base Input** | Initial prompt size (System + Tools + User) | Represents the fixed overhead of the architecture. |
| **Peak Input** | Maximum tokens in a single inference call | Proxy for latency and attention dilution risk. |
| **Growth** | Peak Input minus Base Input | Measures the actual accumulation of dynamic context. |
| **Total Input** | Cumulative tokens processed | Direct proxy for financial cost. |
| **Total Output** | Cumulative tokens generated | Measures generation overhead. |
| **Iterations** | Count of model inference turns | Measures algorithmic efficiency. |

### 4.2.3 Experimental Conditions

**Baseline Condition (Linear)**:
*   Standard chat completion loop.
*   Full history retention (no truncation).
*   Standard system prompt ($\sim$30 tokens).
*   No explicit memory tools.

**Treatment Condition (SPACE)**:
*   SPACE loop (Algorithm 2).
*   Context managed via explicit commands.
*   Extended system prompt defining memory semantics ($\sim$800 tokens).
*   Full toolset: `scope`, `return`, `note`, `insight`, `notes`, `insights`, `status`.

## 4.3 Task 1: Multi-Step Coding (Design)

### 4.3.1 Protocol
The agent is tasked with designing a blog platform architecture through 12 sequential steps, ranging from data modeling to API design. This task evaluates the system's ability to manage context during a long, coherent reasoning chain without external interruptions.

### 4.3.2 Hypotheses
*   **H1 (Linear)**: Context will grow linearly ($O(t)$), eventually polluting the window with obsolete reasoning from early steps.
*   **H2 (SPACE)**: The agent will segment the task into logical scopes (e.g., `design/auth`, `design/api`), resulting in a sawtooth context profile with significantly lower peak usage.

## 4.4 Task 2: Cross-Project Knowledge Transfer

### 4.4.1 Protocol
This task simulates two distinct but related projects executed sequentially:
1.  **Project A (Source)**: Implement a `User` class with specific validation logic (e.g., email format, password strength).
2.  **Project B (Target)**: Implement a `Product` class requiring analogous validation patterns.

Between projects, the working memory is explicitly cleared. In the SPACE condition, the agent retains access to its Episodic Memory (Notes) and Semantic Memory (Insights).

### 4.4.2 Measurement
We measure **Transfer Efficiency**, defined as the reduction in iterations and tokens required for Project B compared to Project A. A reduction indicates successful retrieval and application of learned patterns.

## 4.5 Task 3: Alternative Exploration (Branching)

### 4.5.1 Protocol
The agent must evaluate two architectural candidates for a real-time collaborative editor:
1.  **Operational Transformation (OT)**
2.  **Conflict-free Replicated Data Types (CRDTs)**

### 4.5.2 Hypotheses
*   **H1 (Linear)**: The exploration of CRDTs will be polluted by the preceding OT analysis, potentially leading to hallucinated hybrid features.
*   **H2 (SPACE)**: The agent will create distinct scopes for each analysis (`explore/ot`, `explore/crdt`). The final comparison will utilize retrieved notes, ensuring clean separation of concerns.

## 4.6 Task 4: SWE-Bench-CL (Continual Learning)

### 4.6.1 Protocol
We adapt **SWE-Bench-CL** [30] to evaluate context scalability. The agent faces a sequence of 15 chronologically ordered GitHub issues from the Django repository.
*   **Input**: Issue description and codebase access.
*   **Output**: Analysis and proposed solution.
*   **Constraint**: The agent is not reset between tasks; it must maintain a continuous identity.

### 4.6.2 Relevance
This setup models a "Lifelong Agent" scenario (e.g., a dedicated repository maintainer). It tests the critical failure mode of linear architectures: the "Context Explosion" where the history of Task 1 dominates the attention mechanism during Task 15.

### 4.6.3 Controlled Variables
To ensure rigorous comparison:
1.  **Fixed Model**: GPT-4o-mini for all runs.
2.  **Fixed Task Order**: Chronological sequence preserved.
3.  **Iteration Cap**: Maximum 20 turns per task to prevent infinite loops.
4.  **Replication**: Results averaged over $n=3$ independent runs.

## 4.7 Limitations of Design

We acknowledge several limitations in our experimental design:
1.  **Model Specificity**: Results are derived from a single model family (GPT-4). While SPACE is architecturally agnostic, agent compliance may vary with model capability.
2.  **Synthetic vs. Wild**: Tasks 1-3 are synthetic. While designed to isolate specific mechanics, they lack the noise and ambiguity of in-the-wild interactions.
3.  **Proxy Metrics**: In the SWE-Bench-CL task, we focus on *context dynamics* rather than *code correctness*. Future work will incorporate full correctness evaluation using the official Docker-based harness.
