# 2. Related Work

The challenge of maintaining coherent long-term behavior in language model agents has catalyzed a rich body of research spanning cognitive architectures, memory systems, and context management techniques. Recent literature distinguishes between **Semantic Memory**—the storage of general facts and world knowledge—and **Episodic Memory**—the recall of specific past events and their contexts [5, 10]. In LLM agents, semantic memory is often implemented via Retrieval-Augmented Generation (RAG) using vector databases [1, 3]. However, pure RAG approaches often struggle with "Context Drift" where irrelevant episodic history pollutes the reasoning space. ECM addresses this by providing a deliberate interface for the agent to transition between these memory tiers.

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

A parallel research thread addresses context limits through **compression**.

**Context-Folding** [2] and **AgentFold** [1] use reinforcement learning or fine-tuning to teach models when to "fold" (compress) their context. **HiAgent** [3] decomposes tasks into subgoals with associated context chunks.

## 2.8 Challenges in Long-Running Coding Agents

The specific domain of software engineering magnifies context challenges due to the iterative nature of development. Benchmarks like **SWE-bench** [20] require agents to navigate large repositories, reproduce bugs, and verify fixes through repeated **Edit-Run-Debug loops**.

State-of-the-art agents like **SWE-agent** [25] and **OpenDevin** [26] employ specialized interfaces to mitigate context usage (e.g., limiting file viewer output). However, they typically rely on aggressive context truncation or sliding windows. This creates a specific failure mode: **"Context Amnesia" during debugging**. When an agent runs a test suite that generates 5,000 lines of output, a sliding window might evict the *code change* that caused the error, leaving the agent with the symptom but no memory of the cause [25].

**AutoCodeRover** [27] attempts to solve this via program analysis (AST parsing) to retrieve only relevant code slices. While effective for *code* retrieval, it does not solve the *reasoning* continuity problem. ECM addresses this gap: by isolating the "Debug" scope, an agent can generate massive test logs, extract the relevant error into a note, and return to the "Edit" scope with a clean context and a clear objective, preventing the test output from polluting the reasoning history.

Table 1 summarizes these approaches:

| Approach | Mechanism | Training Required | Context Reduction |
|----------|-----------|-------------------|-------------------|
| MemoryBank [22] | Ebbinghaus Decay | No | Variable |
| MemGPT [13] | Virtual paging | No | Unbounded (external) |
| Context-Folding [2] | RL-learned branch/collapse | RL training | 10× |
| HiAgent [3] | Subgoal chunking | No | 35% |
| **ECM (Ours)** | **Scope Isolation** | **No** | **88%** |

## 2.9 Positioning Our Contribution

Our work occupies a distinct position in this landscape. We share MemGPT's goal of bounded context but achieve it without external storage. We share the "Reflection" concept of Generative Agents but apply it to workflow control.

The key differentiator is **prospective vs. retrospective memory management**.
- **Retrospective (RAG/Mem0):** "Look back at what I did and find what's important."
- **Prospective (ECM):** "I am changing context now, so I will define what is important to carry forward."

This prospective approach leverages the agent's current understanding of its goals to create high-quality episodic markers (notes) *in the moment*, avoiding the loss of nuance that occurs when summarizing raw logs after the fact.