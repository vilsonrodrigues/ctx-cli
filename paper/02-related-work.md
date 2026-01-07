# 2. Related Work

The challenge of maintaining coherent long-term behavior in language model agents has catalyzed a rich body of research spanning cognitive architectures, memory systems, and context management techniques. Recent literature distinguishes between **Semantic Memory**—the storage of general facts and world knowledge—and **Episodic Memory**—the recall of specific past events and their contexts [5, 10]. In LLM agents, semantic memory is often implemented via Retrieval-Augmented Generation (RAG) using vector databases. However, pure RAG approaches often struggle with "Context Drift" where irrelevant episodic history pollutes the reasoning space.

This section surveys the landscape of memory and context management for LLM agents, positioning ECM relative to cognitive architectures (§2.1), episodic memory systems (§2.3-2.4), virtual context management (§2.5), agentic memory (§2.6), learned compression (§2.7), and domain-specific challenges (§2.8).

## 2.1 Cognitive Architectures for Language Agents

The Cognitive Architectures for Language Agents (CoALA) framework [12] provides a foundational taxonomy for understanding agent memory systems. Drawing on classical cognitive science and symbolic AI traditions—particularly the SOAR architecture—CoALA organizes agent cognition along three axes: information storage, action space, and decision-making procedures.

CoALA distinguishes between **working memory** (the active context window) and **long-term memory**, further subdividing the latter into semantic (facts and concepts), episodic (specific experiences), and procedural (skills and behaviors) components [12]. This taxonomy has become the de facto standard for describing memory in language agents, and we adopt its terminology throughout this work.

Critically, CoALA identifies that most contemporary agents conflate working and long-term memory within the context window—a design that inherently limits agent longevity. Our work addresses this limitation through explicit scope isolation, creating distinct memory tiers without requiring external databases.

## 2.2 Version Control as Cognitive Metaphor

While not typically cited in agent literature, software version control systems (VCS) like Git represent the most successful engineered systems for managing complex, non-linear text history. Concepts such as **branching** (isolating work), **committing** (checkpointing state), and **merging** (reintegrating knowledge) provide a mature vocabulary for managing state evolution.

Our work explicitly adopts these metaphors. Where Git manages code, our system manages *reasoning*. By treating the agent's context as a versioned artifact, we gain powerful primitives for handling the "forking paths" of complex problem solving—primitives that are absent in linear conversation models.

## 2.3 Episodic Memory: Foundations and Retrieval

The theoretical basis for episodic memory traces back to Tulving [21], who distinguished it from semantic memory by its "autonoetic" quality—the ability to mentally travel back in time to re-experience specific events defined by *what*, *where*, and *when*.

### 2.3.1 Retrieval-Augmented Approaches
Most contemporary agents implement episodic memory via **Retrieval-Augmented Generation (RAG)** over raw interaction logs. Systems like **MemoryBank** [22] enforce biological realism by implementing the Ebbinghaus forgetting curve, where memories decay over time unless reinforced. **TiM (Think-in-Memory)** [23] creates an evolving memory store where agents can iteratively curate their own history.

However, standard RAG approaches suffer from **narrative fragmentation**. Retrieving the top-$k$ distinct log chunks based on semantic similarity often destroys the causal chain of reasoning. The agent retrieves *what* happened, but loses the *why*—the transition logic that links state A to state B. ECM addresses this by storing synthesized notes rather than raw logs, and by enforcing transition notes that explicitly preserve causality.

### 2.3.2 Experience Replay
In Reinforcement Learning, **Experience Replay** buffers allow agents to learn from past transitions. **REMEMBERER** [24] adapts this for LLMs, training a dedicated memory model to select high-value experiences for storage. Unlike these systems, which often require training or separate retriever models, ECM relies on the agent's own in-context reasoning to decide what is memorable at the moment of creation.

## 2.4 Generative Agents and Reflection

The seminal work on **Generative Agents** [14] established the structural implementation of episodic memory for believable behavior. By equipping simulated characters with memory streams, reflection capabilities, and planning modules, Park et al. demonstrated that explicit memory mechanisms transform LLMs into entities capable of coherent multi-day behavior.

The Generative Agents architecture comprises three components:
1. **Memory stream**: A comprehensive log of observations.
2. **Reflection**: Periodic synthesis of raw memories into higher-level insights.
3. **Retrieval**: Selection of relevant memories based on recency, importance, and relevance.

**Reflexion** [15] extends this to task-oriented agents through **verbal reinforcement learning**, maintaining an episodic buffer of self-critiques (e.g., "I failed specifically because I imported the wrong library") to inform future attempts.

Our note-taking mechanism shares the "Reflection" DNA of these systems: notes are explicit syntheses of experience rather than raw logs. However, while Generative Agents focuses on *background* simulation, ECM focuses on *active* workflow management. Our "Scope" mechanism adds a spatial dimension (memory isolation) that these linear-stream systems lack.

## 2.5 Virtual Context Management

**MemGPT** [13] introduced the paradigm of **virtual context management**, drawing an analogy between LLM context windows and operating system memory hierarchies. Just as operating systems provide the illusion of unlimited memory through paging between RAM and disk, MemGPT enables LLMs to operate beyond their native context limits through intelligent data movement.

The MemGPT architecture divides memory into:
- **Main context**: Active tokens within the LLM's window (analogous to RAM).
- **External context**: Archival and recall storage (analogous to disk).

The LLM manages these tiers through function calls, "paging" information in and out. This operating systems metaphor is powerful but introduces complexity: agents must learn paging policies. Our approach shares MemGPT's goal of bounded context but achieves it through simpler means—explicit scope boundaries rather than learned paging policies.

## 2.6 Agentic Memory Systems

Recent work has moved beyond passive storage toward **agentic memory**—systems that actively manage their own memory lifecycle.

**Mem0** [16] employs a two-phase pipeline (Extraction + Resolution) to maintain a consistent user profile. **A-MEM** [17] draws inspiration from the Zettelkasten method, organizing memories as atomic notes with dynamic inter-linkages generated by the model.

These systems represent the state-of-the-art in *implicit* management—the system organizes memory for the agent. ECM represents the alternative *explicit* pole: the agent organizes memory for itself. This shifts the burden from complex backend infrastructure (vector DBs, graph stores) to the agent's reasoning capabilities.

## 2.7 Context Compression and Folding

A parallel research thread addresses context limits through **learned compression**—training models to autonomously decide when and how to compress their context.

### 2.7.1 Context-Folding

**Context-Folding** [2] introduces an agentic mechanism where models actively manage their working context through two operations: `branch(description, prompt)` creates a temporary sub-trajectory for a localized subtask, and `return(message)` rejoins the main thread while "folding" away intermediate steps. The key innovation is **FoldGRPO**, a reinforcement learning algorithm with dense, token-level process rewards including an "Unfolded Token Penalty" (discouraging token-heavy operations in the main context) and an "Out-of-Scope Penalty" (maintaining focus within sub-tasks).

Context-Folding achieves 62.0% on BrowseComp-Plus and 58.0% on SWE-Bench Verified using only a 32K token budget—surpassing ReAct baselines requiring 327K contexts. However, the approach implements **stack-based navigation**: branches must return in LIFO (Last-In-First-Out) order, limiting exploration patterns to strictly hierarchical decomposition.

### 2.7.2 AgentFold

**AgentFold** [1] extends folding with two complementary operations at different scales. **Micro-folding** (granular condensation) targets single steps, converting verbose interactions into compact summaries. **Macro-folding** (deep consolidation) fuses multiple prior summaries into coarser abstractions, enabling the system to "retract entire verbose sequences and replace them with a single, conclusive summary."

AgentFold frames context as "a dynamic cognitive workspace to be actively sculpted, rather than a passive log to be filled." Using supervised fine-tuning on trajectory data from a Fold-Generator pipeline, AgentFold-30B achieves 36.2% on BrowseComp—outperforming DeepSeek-V3.1-671B (30.0%) and OpenAI's o4-mini (28.3%)—while maintaining only ~7K tokens after 100 interaction turns.

### 2.7.3 Context as a Tool (CaT)

**CaT** [28] formalizes a structured context workspace with three components: stable task semantics $Q$, condensed long-term memory $M(t)$, and high-fidelity short-term interactions $I^{(k)}(t)$. The agent proactively triggers compression at strategic milestones identified by three signals: context expansion (sustained growth), structural boundaries (subtask completion), and error-correction moments.

Using **CaT-Generator**, an offline pipeline that injects context-management actions into complete interaction trajectories, the authors train **SWE-Compressor** (Qwen2.5-Coder 32B) achieving 57.6% on SWE-Bench-Verified while maintaining bounded context. CaT demonstrates that context management can be elevated from "a passive heuristic to a callable and plannable capability."

### 2.7.4 Comparative Analysis

Table 2 contrasts these learned compression approaches with ECM:

| Dimension | Context-Folding | AgentFold | CaT | **ECM (Ours)** |
|-----------|-----------------|-----------|-----|----------------|
| Training Required | RL (FoldGRPO) | SFT | SFT (20K samples) | **None** |
| Navigation Structure | Stack (branch/return) | Linear | Linear | **Graph (scope/goto)** |
| Compression Timing | Learned | Learned | Learned (3 signals) | **Explicit (transitions)** |
| Semantic Memory | No | No | No | **Yes (insights)** |
| Memory Persistence | Session-only | Session-only | Session-only | **Cross-session** |
| Model-Agnostic | No | No | No | **Yes** |

Three fundamental differences distinguish ECM from learned compression:

**Stack vs. Graph Navigation.** Context-Folding's `branch/return` enforces LIFO ordering—an agent exploring alternatives A and B must complete B before returning to A. ECM's `scope/goto` implements **graph-based navigation**: an agent can freely move between `research/A`, `research/B`, and `main`, enabling non-linear exploration essential for comparing alternatives.

**Learned vs. Explicit Compression.** Folding approaches learn *when* to compress through training signals. ECM makes compression **explicit and deliberate**: the agent declares what matters at scope transitions through mandatory notes. This prospective approach captures the agent's current understanding rather than retrospectively summarizing what a compression model deems important.

**Ephemeral vs. Persistent Memory.** When Context-Folding executes `return(message)`, intermediate steps are destroyed—only the summary survives. ECM's notes remain **permanently accessible** via `notes [scope]`, enabling retrospective analysis and cross-task knowledge transfer. Furthermore, ECM's `insights` provide a semantic memory tier absent in all folding approaches.

### 2.7.5 Other Compression Approaches

**HiAgent** [3] decomposes tasks into subgoals with associated context chunks, achieving 35% context reduction without training. **ACON** [29] provides a universal agent context optimization framework supporting both history and observation compression, reducing memory usage by 26-54% while preserving task success. These approaches focus on compression mechanics rather than the navigation and memory structures that ECM provides.

## 2.8 Challenges in Long-Running Coding Agents

The specific domain of software engineering magnifies context challenges due to the iterative nature of development. Benchmarks like **SWE-bench** [20] require agents to navigate large repositories, reproduce bugs, and verify fixes through repeated **Edit-Run-Debug loops**.

State-of-the-art agents like **SWE-agent** [25] and **OpenDevin** [26] employ specialized interfaces to mitigate context usage (e.g., limiting file viewer output). However, they typically rely on aggressive context truncation or sliding windows. This creates a specific failure mode: **"Context Amnesia" during debugging**. When an agent runs a test suite that generates 5,000 lines of output, a sliding window might evict the *code change* that caused the error, leaving the agent with the symptom but no memory of the cause [25].

**AutoCodeRover** [27] attempts to solve this via program analysis (AST parsing) to retrieve only relevant code slices. While effective for *code* retrieval, it does not solve the *reasoning* continuity problem. ECM addresses this gap: by isolating the "Debug" scope, an agent can generate massive test logs, extract the relevant error into a note, and return to the "Edit" scope with a clean context and a clear objective, preventing the test output from polluting the reasoning history.

Table 1 summarizes the landscape of context management approaches:

| Approach | Mechanism | Training | Reduction | Navigation | Persistent Memory |
|----------|-----------|----------|-----------|------------|-------------------|
| MemoryBank [22] | Ebbinghaus Decay | No | Variable | Linear | External |
| MemGPT [13] | Virtual paging | No | Unbounded | Linear | External DB |
| Context-Folding [2] | branch/return + RL | RL | 10× | Stack | No |
| AgentFold [1] | micro/macro-fold | SFT | ~7K@100t | Linear | No |
| CaT [28] | Learned compression | SFT | 70% | Linear | No |
| HiAgent [3] | Subgoal chunking | No | 35% | Hierarchical | No |
| ACON [29] | History+Obs compression | No | 26-54% | Linear | No |
| **ECM (Ours)** | **Scope Isolation** | **No** | **88%** | **Graph** | **Yes** |

## 2.9 Positioning Our Contribution

ECM occupies a unique position in the design space of context management systems, distinguished by three orthogonal dimensions:

### Training Requirements

The recent wave of learned compression approaches—Context-Folding [2], AgentFold [1], and CaT [28]—achieve impressive results but require either reinforcement learning or supervised fine-tuning on thousands of trajectories. ECM demonstrates that **comparable context reduction (88%) is achievable with zero training**, making it immediately deployable with any tool-use capable model. This training-free property is shared only with MemGPT [13] and HiAgent [3], but ECM achieves superior reduction without external infrastructure.

### Navigation Topology

Context-Folding's `branch/return` implements stack-based (LIFO) navigation—branches must complete before returning to parent contexts. AgentFold and CaT maintain linear context with periodic compression. ECM uniquely provides **graph-based navigation** through `scope/goto`, enabling non-linear exploration where an agent can freely traverse between any existing scopes. This topology mirrors how developers use Git branches: creating `research/approach-A` and `research/approach-B`, exploring each independently, and comparing findings without one polluting the other.

### Memory Semantics

All compression approaches—whether learned (Context-Folding, AgentFold, CaT) or heuristic (HiAgent, ACON)—focus exclusively on **episodic compression**: summarizing what happened. ECM introduces a **two-tier memory system**:
- **Episodic (notes)**: Scope-local records of specific events, preserved across transitions
- **Semantic (insights)**: Global knowledge transcending individual scopes

This distinction enables knowledge transfer patterns impossible with pure compression: an insight discovered in `fix/auth-bug` ("all endpoints require @authenticated decorator") becomes immediately available in `feature/new-endpoint` without explicit retrieval.

### Prospective vs. Retrospective

The fundamental philosophical difference is **when** memory curation occurs:
- **Retrospective (RAG/Mem0/Folding):** "After the fact, determine what was important."
- **Prospective (ECM):** "At the moment of transition, declare what matters going forward."

This prospective approach leverages the agent's current understanding of its goals to create high-quality episodic markers *in the moment*, avoiding the information loss inherent in retrospective summarization. When an agent executes `goto main -m "Found root cause: missing null check in parser.py:142"`, it captures precisely the insight that motivated the transition—context that a compression model operating on raw logs might not preserve.

### Design Tradeoffs

ECM's simplicity comes with explicit tradeoffs. Learned approaches can potentially achieve better compression ratios by identifying subtle redundancies humans might miss. Stack-based navigation (Context-Folding) enforces structured decomposition that may prevent certain errors. ECM accepts these tradeoffs in exchange for:
1. **Zero training overhead**: Deploy immediately with any model
2. **Interpretable state**: All memory is human-readable and auditable
3. **Flexible navigation**: Support exploration patterns beyond hierarchical decomposition
4. **Persistent knowledge**: Notes and insights survive beyond individual sessions