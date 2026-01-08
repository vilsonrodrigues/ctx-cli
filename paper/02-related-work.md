# 2. Related Work

The challenge of maintaining coherent long-term behavior in language model agents has catalyzed a rich body of research spanning cognitive architectures, memory systems, and context management techniques. Recent literature distinguishes between **Semantic Memory**—the storage of general facts and world knowledge—and **Episodic Memory**—the recall of specific past events and their contexts [5, 10]. In LLM agents, semantic memory is often implemented via Retrieval-Augmented Generation (RAG) using vector databases. However, pure RAG approaches often struggle with "Context Drift" where irrelevant episodic history pollutes the reasoning space.

This section surveys the landscape of memory and context management for LLM agents, positioning SPACE relative to cognitive architectures (§2.1), episodic memory systems (§2.3-2.4), virtual context management (§2.5), agentic memory (§2.6), learned compression (§2.7), and domain-specific challenges (§2.8).

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

However, standard RAG approaches suffer from **narrative fragmentation**. Retrieving the top-$k$ distinct log chunks based on semantic similarity often destroys the causal chain of reasoning. The agent retrieves *what* happened, but loses the *why*—the transition logic that links state A to state B. SPACE addresses this by storing synthesized notes rather than raw logs, and by enforcing transition summaries that explicitly preserve causality.

### 2.3.2 Experience Replay
In Reinforcement Learning, **Experience Replay** buffers allow agents to learn from past transitions. **REMEMBERER** [24] adapts this for LLMs, training a dedicated memory model to select high-value experiences for storage. Unlike these systems, which often require training or separate retriever models, SPACE relies on the agent's own in-context reasoning to decide what is memorable at the moment of creation.

## 2.4 Generative Agents and Reflection

The seminal work on **Generative Agents** [14] established the structural implementation of episodic memory for believable behavior. By equipping simulated characters with memory streams, reflection capabilities, and planning modules, Park et al. demonstrated that explicit memory mechanisms transform LLMs into entities capable of coherent multi-day behavior.

The Generative Agents architecture comprises three components:
1. **Memory stream**: A comprehensive log of observations.
2. **Reflection**: Periodic synthesis of raw memories into higher-level insights.
3. **Retrieval**: Selection of relevant memories based on recency, importance, and relevance.

**Reflexion** [15] extends this to task-oriented agents through **verbal reinforcement learning**, maintaining an episodic buffer of self-critiques (e.g., "I failed specifically because I imported the wrong library") to inform future attempts.

Our note-taking mechanism shares the "Reflection" DNA of these systems: notes are explicit syntheses of experience rather than raw logs. However, while Generative Agents focuses on *background* simulation, SPACE focuses on *active* workflow management. Our "Scope" mechanism adds a spatial dimension (memory isolation) that these linear-stream systems lack.

## 2.5 Recursive Language Models (RLM)

**Recursive Language Models** [31] introduce a paradigm shift: instead of feeding long prompts directly into the neural network, the prompt becomes part of an **external environment** that the model can programmatically examine. The core mechanism provides the model with a Python REPL where the prompt is stored as a variable (`context`), and a special `llm_query` function allows the model to recursively call itself on filtered snippets.

Key innovations of RLM:
- **Symbolic interaction**: The model uses regex, chunking, and filtering to selectively view context rather than ingesting every token
- **Unbounded reasoning chains**: Models can iteratively refine their recursion via execution feedback
- **Self-managed context**: All context window management is handled implicitly by the LLM itself through code generation

RLM achieves remarkable scale, handling inputs **up to 10M+ tokens**—two orders of magnitude beyond model context windows—while being up to 3× cheaper than summarization approaches. On benchmarks like BrowseComp+ and OOLONG, RLM shows double-digit percentage gains over baselines.

However, RLM has significant limitations:
- **Latency**: Multi-minute trajectories due to synchronous blocking calls
- **Model requirements**: Requires frontier-class models (>400B parameters) to reliably generate correct Python code
- **High variance**: Trajectory lengths vary significantly, leading to unpredictable costs
- **Failure modes**: Models make "strange decisions" (e.g., outputting plans as final answers) or redundant verification steps

### SPACE vs RLM: Abstraction Level Tradeoff

RLM and SPACE represent different points on the **abstraction spectrum** for context management:

| Dimension | RLM | SPACE |
|-----------|-----|-------|
| Interface | Raw Python code generation | High-level CLI commands |
| Flexibility | Maximum (arbitrary code) | Constrained (7 commands) |
| Latency | High (code execution) | Low (~1.5s per transition) |
| Model Requirements | Frontier (>400B) | Any tool-use capable |
| Failure Risk | High (code errors) | Low (validated commands) |
| Learning Curve | Complex (write Python) | Simple (call tools) |

**RLM's approach**: "Let the model write arbitrary memory management code"
**SPACE's approach**: "Give the model a structured memory API"

SPACE can be viewed as a **high-level abstraction over RLM's principles**. Where RLM requires the model to write code like:
```python
chunks = [context[i:i+1000] for i in range(0, len(context), 1000)]
for chunk in chunks:
    result = llm_query(f"Extract key facts: {chunk}")
    buffer.append(result)
```

SPACE provides equivalent capability through:
```
scope extract-facts -m "Processing document section"
[... work ...]
note -m "Key facts: X, Y, Z"
return -m "Completed extraction"
```

This shifts complexity from **generation** (writing correct Python) to **selection** (choosing the right command), dramatically reducing failure modes while preserving the core benefit of agent-controlled context management.

## 2.6 Virtual Context Management

**MemGPT** [13] introduced the paradigm of **virtual context management**, drawing an analogy between LLM context windows and operating system memory hierarchies. Just as operating systems provide the illusion of unlimited memory through paging between RAM and disk, MemGPT enables LLMs to operate beyond their native context limits through intelligent data movement.

The MemGPT architecture divides memory into:
- **Main context**: Active tokens within the LLM's window (analogous to RAM).
- **External context**: Archival and recall storage (analogous to disk).

The LLM manages these tiers through function calls, "paging" information in and out. This operating systems metaphor is powerful but introduces complexity: agents must learn paging policies. Our approach shares MemGPT's goal of bounded context but achieves it through simpler means—explicit scope boundaries rather than learned paging policies.

## 2.6 Agentic Memory Systems

Recent work has moved beyond passive storage toward **agentic memory**—systems that actively manage their own memory lifecycle.

**Mem0** [16] employs a two-phase pipeline (Extraction + Resolution) to maintain a consistent user profile. **A-MEM** [17] draws inspiration from the Zettelkasten method, organizing memories as atomic notes with dynamic inter-linkages generated by the model.

### 2.6.1 Confucius Code Agent (CCA)

**Confucius Code Agent** [37] presents a particularly relevant comparison, achieving 54.3% Resolve@1 on SWE-Bench-Pro through sophisticated scaffolding. CCA introduces several mechanisms that parallel SPACE:

**Hierarchical Working Memory**: CCA uses "configurable visibility scopes" (session, entry, runnable) to retain essential state during context pruning. This parallels SPACE's scope isolation, though CCA's scopes are implicitly managed by the framework rather than explicitly commanded by the agent.

**Adaptive Context Compression**: When prompt length approaches configurable thresholds, a separate "Architect" agent generates structured summaries preserving task goals, decisions made, and open TODOs. This achieves **over 40% prompt reduction** and reduces token costs from 104K to 93K tokens.

**Hindsight Notes**: CCA introduces "persistent notes for failures" documenting unproductive strategies and compilation errors. This enables "durable knowledge" across sessions, preventing agents from "repeatedly rediscovering information."

**Memory Differentiation**: CCA explicitly separates "transient hierarchical working memory" (active sessions) from "persistent knowledge" (file-system-like tree)—mapping closely to SPACE's working/episodic/semantic tiers.

### CCA vs SPACE: Implicit vs Explicit Control

| Dimension | CCA | SPACE |
|-----------|-----|-------|
| Compression Trigger | Automatic (threshold) | Explicit (`return -m`) |
| Scope Management | Implicit (visibility rules) | Explicit (`scope`/`return`) |
| Note Creation | Automatic (hindsight) | Explicit (`note`/`insight`) |
| Summarization | Separate Architect LLM | Agent's own synthesis |
| Training Required | No | No |

The key philosophical difference: **CCA automates context management decisions** (when to compress, what to note), while **SPACE makes these decisions explicit agent actions**. CCA's approach reduces cognitive burden but sacrifices transparency; SPACE's approach requires more discipline but produces auditable, interpretable memory trails.

CCA's "hindsight notes" are complementary to SPACE's prospective notes: hindsight captures *what went wrong* after the fact, while SPACE's notes capture *what matters* at the moment of transition. A hybrid could combine both patterns.

### 2.6.2 Positioning

These systems (Mem0, A-MEM, CCA) represent varying degrees of *implicit* vs *explicit* management. CCA moves closest to explicit management but offloads the cognitive burden to specialized sub-agents (Architect, Note-Taker). SPACE represents the fully *explicit* pole: the primary agent organizes memory for itself as a core part of its reasoning loop. This shifts the burden from orchestration overhead (multi-agent swarms) to the single agent's reasoning capabilities.

## 2.7 Context Compression and Folding

A parallel research thread addresses context limits through **learned compression**—training models to autonomously decide when and how to compress their context.

### 2.7.1 Context-Folding

**Context-Folding** [2] introduces an agentic mechanism where models actively manage their working context through two operations: `branch(description, prompt)` creates a temporary sub-trajectory for a localized subtask, and `return(message)` rejoins the main thread while "folding" away intermediate steps. The key innovation is **FoldGRPO**, a reinforcement learning algorithm with dense, token-level process rewards including an "Unfolded Token Penalty" (discouraging token-heavy operations in the main context) and an "Out-of-Scope Penalty" (maintaining focus within sub-tasks).

Context-Folding achieves 62.0% on BrowseComp-Plus and 58.0% on SWE-Bench Verified using only a 32K token budget—surpassing ReAct baselines requiring 327K contexts. The authors report **over 90% context compression**, reducing full 100K+ token trajectories to ~8K tokens in the main thread.

Critically, Context-Folding implements a **plan-execution framework** where the agent alternates between: (i) a *Planning State* in the main thread for high-level reasoning, where token-intensive tool use is discouraged; and (ii) an *Execution State* within branches for completing sub-tasks, where creating new branches is disabled. This mirrors SPACE's radial topology with enforced discipline.

However, Context-Folding employs **stack-based navigation**: branches must return in LIFO (Last-In-First-Out) order, limiting exploration patterns to strictly hierarchical decomposition. The approach also requires training a 36B parameter model (Seed-OSS-36B) with RL, making it non-portable to other models.

### 2.7.2 AgentFold

**AgentFold** [1] introduces a sophisticated two-scale folding mechanism that treats context as "a dynamic cognitive workspace to be actively sculpted, rather than a passive log to be filled."

**Micro-folding (Granular Condensation)**: Targets single interactions, converting verbose tool calls into fine-grained summaries while maintaining high resolution. Applied during incremental steps to preserve detail.

**Macro-folding (Deep Consolidation)**: Fuses the latest interaction with a chain of prior summaries into coarser abstractions. Preferred when sub-tasks complete, "abstracting away noisy, intermediate steps."

The key innovation is a **flexible look-back mechanism**: the agent outputs a JSON folding directive `ft={"range":[k, t-1], "summary":"σt"}` specifying which interaction range to consolidate. This allows the model to "delay consolidation until a sub-task's outcome is clear"—discarding failed attempts only after a successful path is found.

**Context Structure**: The workspace at step t is defined as `Ct=(Q, T, St-2, It-1)` where:
- Q: Invariant user question
- T: Task description
- St: Multi-Scale State Summaries (ordered sequence of summary blocks at different scales)
- It: High-fidelity Latest Interaction

**Training**: AgentFold uses the **Fold-Generator** pipeline with rejection sampling—excluding steps with format violations or excessive environmental errors. The resulting AgentFold-30B (fine-tuned Qwen3-30B-A3B) achieves:
- **36.2% on BrowseComp** (surpassing DeepSeek-V3.1-671B at 30.0%)
- **~7K tokens after 100 turns** (vs. linear growth to context limits)
- Scales to **500+ interaction turns**

### 2.7.3 Context as a Tool (CaT)

**CaT** [28] elevates context management from a passive heuristic to "a callable and plannable capability." The framework formalizes a structured context workspace:

$$C(t) = (Q, M(t), I^{(k)}(t))$$

Where:
- **Q**: Non-compressible stable task semantics (system prompt, task description)
- **M(t)**: Evolvable long-term memory containing condensed historical trajectories
- **I(k)(t)**: High-fidelity short-term interactions (recent k steps)

**Three Compression Signals**: Unlike fixed thresholds, CaT uses heuristic triggers:
1. **Context Expansion**: Sustained growth in context length
2. **Structural Boundary**: Subtask completion or milestone achievement
3. **Error-Correction**: New feasible directions emerging after failures

**CaT-Generator Pipeline**: A two-stage process:
1. **Base ReAct Trajectory Generation**: Collect successful trajectories
2. **Trajectory Refactoring**: Inject context-management actions at appropriate milestones

**Training**: CaT uses **CaT-Instruct**, a curated set of **20K supervised fine-tuning instances**. The resulting **SWE-Compressor** (Qwen2.5-Coder 32B) achieves:
- **57.6% on SWE-Bench-Verified**
- **~70% compression ratio** (15,585 → 4,676 tokens average)
- Bounded context growth regardless of task length

**Key Distinction from Static Compression**: CaT is "execution-driven and active"—the model learns *when* to compress based on task dynamics, unlike Context-Folding's stack-based triggers or LLMLingua's static compression.

### 2.7.4 Comparative Analysis: Learned Compression Approaches

Table 2 contrasts these learned compression approaches with SPACE:

| Dimension | Context-Folding | AgentFold | CaT | **SPACE (Ours)** |
|-----------|-----------------|-----------|-----|------------------|
| Training | RL (FoldGRPO) | SFT (Fold-Generator) | SFT (20K CaT-Instruct) | **None** |
| Base Model | Seed-OSS-36B | Qwen3-30B-A3B | Qwen2.5-Coder-32B | **Any** |
| Compression Trigger | Learned (branch/return) | Learned (JSON directive) | Learned (3 signals) | **Explicit (`return -m`)** |
| Folding Granularity | Branch-level | Multi-scale (micro/macro) | Milestone-based | **Scope-level** |
| Look-back | Fixed (current branch) | Flexible (agent-chosen range) | Fixed (recent k steps) | **Explicit (notes query)** |
| Context @100 turns | ~8K (main thread) | ~7K | ~4.7K | **~1.4K (preliminary)** |
| Semantic Memory | No | No | No | **Yes (insights)** |
| Model Portability | No | No | No | **Yes** |

### Key Architectural Differences

**Compression Granularity**:
- **Context-Folding**: Branch-level (entire sub-trajectories folded at once)
- **AgentFold**: Multi-scale (micro for single steps, macro for sequences)
- **CaT**: Milestone-based (triggered by 3 heuristic signals)
- **SPACE**: Scope-level with explicit agent control

**Look-back Mechanism**:
- **AgentFold's flexible look-back** is particularly sophisticated: the agent outputs `{"range":[k, t-1], "summary":"σt"}` to specify exactly which steps to consolidate. This allows retrospective pruning of failed attempts.
- **SPACE's explicit notes** achieve similar functionality but prospectively: the agent declares what matters at transition time via `note -m`, rather than retrospectively deciding what to discard.

**Memory Tiers**:
All three learned approaches operate on a **two-tier model** (active context + compressed summaries). SPACE uniquely introduces a **three-tier model**:
1. Working memory (ephemeral, cleared on return)
2. Episodic memory (notes, scope-local, persistent)
3. Semantic memory (insights, global, persistent)

This enables knowledge patterns impossible with compression alone: an insight discovered in `fix/auth-bug` immediately benefits `feature/new-endpoint` without retrieval.

**Training vs Architecture**:
The fundamental tradeoff remains: learned approaches achieve tighter compression through optimized policies (CaT's 70% ratio, AgentFold's 7K@100 turns), while SPACE achieves comparable results (~88% on sequential tasks) through architectural constraints alone.

### 2.7.5 The Folding Paradigm: A Unified View

Context-Folding, AgentFold, and CaT represent a coherent **folding paradigm** with shared principles:

1. **Active over Passive**: Agents actively manage context rather than passively accumulating
2. **Summarize at Boundaries**: Compression occurs at meaningful transition points
3. **Preserve Decisions**: Summaries retain key decisions and outcomes, discarding intermediate noise
4. **Bounded Growth**: Context size stabilizes regardless of task length

SPACE shares these principles but diverges in implementation:

| Principle | Folding Paradigm | SPACE |
|-----------|------------------|-------|
| Active management | Learned skill | Architectural constraint |
| Boundary detection | Model decides | Agent commands |
| Summary content | Model decides | Agent writes |
| Memory persistence | Summaries only | Notes + Insights |

**The key question**: Should context management be a **learned skill** (folding) or an **explicit interface** (SPACE)?

Arguments for learned (folding):
- Higher compression ceiling (models learn optimal policies)
- Lower cognitive burden (automatic decisions)
- Can capture subtle patterns humans might miss

Arguments for explicit (SPACE):
- Zero training overhead (deploy immediately)
- Model-agnostic (works with any tool-use LLM)
- Interpretable (all decisions are observable)
- Persistent memory (notes survive beyond summaries)

### 2.7.6 Other Compression Approaches

**HiAgent** [3] decomposes tasks into subgoals with associated context chunks, achieving 35% context reduction without training. **ACON** [29] provides a universal agent context optimization framework supporting both history and observation compression, reducing memory usage by 26-54% while preserving task success. These approaches focus on compression mechanics rather than the navigation and memory structures that SPACE provides.

## 2.8 Challenges in Long-Running Coding Agents

The specific domain of software engineering magnifies context challenges due to the iterative nature of development. Benchmarks like **SWE-bench** [20] require agents to navigate large repositories, reproduce bugs, and verify fixes through repeated **Edit-Run-Debug loops**.

State-of-the-art agents like **SWE-agent** [25] and **OpenDevin** [26] employ specialized interfaces to mitigate context usage (e.g., limiting file viewer output). However, they typically rely on aggressive context truncation or sliding windows. This creates a specific failure mode: **"Context Amnesia" during debugging**. When an agent runs a test suite that generates 5,000 lines of output, a sliding window might evict the *code change* that caused the error, leaving the agent with the symptom but no memory of the cause [25].

**AutoCodeRover** [27] attempts to solve this via program analysis (AST parsing) to retrieve only relevant code slices. While effective for *code* retrieval, it does not solve the *reasoning* continuity problem. SPACE addresses this gap: by isolating the "Debug" scope, an agent can generate massive test logs, extract the relevant error into a note, and return to the "Edit" scope with a clean context and a clear objective, preventing the test output from polluting the reasoning history.

Table 1 summarizes the landscape of context management approaches:

| Approach | Mechanism | Training | Reduction | Navigation | Persistent Memory |
|----------|-----------|----------|-----------|------------|-------------------|
| MemGPT [13] | Virtual paging | No | Unbounded | Linear | External DB |
| RLM [31] | REPL + llm_query | No | 10M+ tokens | Recursive | REPL state |
| CCA [37] | Architect + Hindsight | No | 40%+ | Hierarchical | Hindsight notes |
| Context-Folding [2] | branch/return + RL | RL | 90% | Stack | No |
| AgentFold [1] | micro/macro-fold | SFT | ~7K@100t | Linear | No |
| CaT [28] | 3-signal compression | SFT (20K) | 70% | Linear | No |
| HiAgent [3] | Subgoal chunking | No | 35% | Hierarchical | No |
| ACON [29] | History+Obs compression | No | 26-54% | Linear | No |
| **SPACE (Ours)** | **Scope + Notes + Insights** | **No** | **~88%** | **Radial** | **Yes (3-tier)** |

## 2.9 Positioning Our Contribution

SPACE occupies a unique position in the design space of context management systems. Having analyzed nine contemporary approaches, we identify four orthogonal dimensions that distinguish SPACE:

### Training Requirements

| Approach | Training | Deployment |
|----------|----------|------------|
| Context-Folding | RL (FoldGRPO) | Model-specific |
| AgentFold | SFT (Fold-Generator) | Model-specific |
| CaT | SFT (20K trajectories) | Model-specific |
| RLM | None | Frontier models only (>400B) |
| CCA | None | Framework-specific |
| **SPACE** | **None** | **Any tool-use model** |

SPACE is the only approach achieving high compression (~88%) with **zero training** and **universal model compatibility**.

### Abstraction Level

```
Low-level ←————————————————————————————→ High-level
     │                                       │
    RLM          CaT/AgentFold    CCA      SPACE
 (raw Python)   (learned tools)  (multi-agent) (CLI commands)
```

RLM offers maximum flexibility but requires frontier models. SPACE offers maximum accessibility—any model that can call tools can use SPACE.

### Memory Architecture

| Approach | Memory Tiers | Persistence |
|----------|--------------|-------------|
| Context-Folding | 1 (active context) | Session only |
| AgentFold | 2 (active + summaries) | Session only |
| CaT | 2 (M(t) + I(k)) | Session only |
| CCA | 2 (transient + hindsight) | Cross-session |
| **SPACE** | **3 (working/episodic/semantic)** | **Cross-session** |

SPACE's three-tier architecture enables knowledge patterns impossible with compression:
- **Working → Episodic**: `note -m` captures task-specific events
- **Episodic → Semantic**: `insight -m` elevates patterns to global knowledge
- **Cross-scope transfer**: Insights from `fix/auth-bug` benefit `feature/new-endpoint`

### Prospective vs. Retrospective

| Approach | When decisions are made |
|----------|------------------------|
| AgentFold | Retrospective (flexible look-back) |
| CaT | Retrospective (milestone triggers) |
| CCA | Retrospective (hindsight notes) |
| **SPACE** | **Prospective (transition declarations)** |

SPACE's prospective approach captures the agent's understanding *in the moment* rather than retrospectively deciding what to preserve. When an agent executes `return -m "Found root cause: missing null check in parser.py:142"`, it captures precisely the insight that motivated the transition—context that a compression model operating on raw logs might not preserve.

### Design Tradeoffs

SPACE's simplicity comes with explicit tradeoffs. Learned approaches can potentially achieve better compression ratios by identifying subtle redundancies humans might miss. Stack-based navigation (Context-Folding) enforces structured decomposition that may prevent certain errors. SPACE accepts these tradeoffs in exchange for:
1. **Zero training overhead**: Deploy immediately with any model
2. **Interpretable state**: All memory is human-readable and auditable
3. **Flexible navigation**: Support exploration patterns beyond hierarchical decomposition
4. **Persistent knowledge**: Notes and insights survive beyond individual sessions