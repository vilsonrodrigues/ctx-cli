# 2. Related Work

The challenge of maintaining coherent long-term behavior in language model agents has catalyzed a rich body of research spanning cognitive architectures, memory systems, and context management techniques. We organize this literature along six dimensions, situating our contribution within the broader landscape.

## 2.1 Cognitive Architectures for Language Agents

The Cognitive Architectures for Language Agents (CoALA) framework [12] provides a foundational taxonomy for understanding agent memory systems. Drawing on classical cognitive science and symbolic AI traditions—particularly the SOAR architecture—CoALA organizes agent cognition along three axes: information storage, action space, and decision-making procedures.

CoALA distinguishes between **working memory** (the active context window) and **long-term memory**, further subdividing the latter into semantic (facts and concepts), episodic (specific experiences), and procedural (skills and behaviors) components [12]. This taxonomy has become the de facto standard for describing memory in language agents, and we adopt its terminology throughout this work.

Critically, CoALA identifies that most contemporary agents conflate working and long-term memory within the context window—a design that inherently limits agent longevity. Our work addresses this limitation through explicit scope isolation, creating distinct memory tiers without requiring external databases.

## 2.2 Virtual Context Management

MemGPT [13] introduced the paradigm of **virtual context management**, drawing an analogy between LLM context windows and operating system memory hierarchies. Just as operating systems provide the illusion of unlimited memory through paging between RAM and disk, MemGPT enables LLMs to operate beyond their native context limits through intelligent data movement.

The MemGPT architecture divides memory into:
- **Main context**: Active tokens within the LLM's window (analogous to RAM)
- **External context**: Archival and recall storage (analogous to disk)

The LLM manages these tiers through function calls, "paging" information in and out as tasks demand. When required information is absent from main context—analogous to a page fault—the agent issues retrieval commands to external storage [13].

This operating systems metaphor is powerful but introduces complexity: agents must learn when to page, what to evict, and how to maintain coherence across memory tiers. Our approach shares MemGPT's goal of bounded context but achieves it through simpler means—explicit scope boundaries rather than learned paging policies.

## 2.3 Episodic Memory and Reflection

The seminal work on Generative Agents [14] established the importance of episodic memory for believable long-term agent behavior. By equipping 25 simulated characters with memory streams, reflection capabilities, and planning modules, Park et al. demonstrated that explicit memory mechanisms transform LLMs into entities capable of coherent multi-day behavior.

The Generative Agents architecture comprises three components:

1. **Memory stream**: A comprehensive log of observations in natural language
2. **Reflection**: Periodic synthesis of raw memories into higher-level insights
3. **Retrieval**: Selection of relevant memories based on recency, importance, and relevance

The reflection mechanism is particularly significant—agents periodically analyze their experiences to form generalizations ("Klaus is interested in art") that guide future behavior [14]. This creates a self-reinforcing cycle where experiences inform beliefs, which shape actions, which generate new experiences.

Reflexion [15] extends this paradigm to task-oriented agents through **verbal reinforcement learning**. Rather than updating model weights, Reflexion agents maintain an episodic buffer of self-critiques that inform subsequent attempts. When a coding task fails, the agent reflects on the failure mode and stores this reflection for future reference—achieving learning through linguistic feedback rather than gradient updates [15].

Our note-taking mechanism shares philosophical roots with these systems: notes are explicit reflections that persist across reasoning episodes. However, while Generative Agents and Reflexion focus on *what* to remember, our work addresses *when* memories should be visible—the attention mask dimension that determines which context is active at any moment.

## 2.4 Agentic Memory Systems

Recent work has moved beyond passive memory storage toward **agentic memory**—systems that actively manage their own memory lifecycle [16, 17].

**Mem0** [16] exemplifies this approach through a two-phase pipeline:

1. **Extraction**: An LLM analyzes conversation turns to identify candidate memories
2. **Update**: Each candidate is compared against existing memories, with an LLM resolver determining the appropriate operation (ADD, UPDATE, DELETE, or NOOP)

The graph-enhanced variant, Mem0g, represents memories as directed graphs where nodes are entities and edges encode semantic relations [16]. This structure enables multi-hop reasoning over temporal and relational queries that flat vector stores struggle to answer.

**A-MEM** [17] draws inspiration from the Zettelkasten method of knowledge management, organizing memories as atomic notes with dynamic inter-linkages. Each memory $m_i$ comprises:

$$m_i = \{c_i, t_i, K_i, G_i, X_i, e_i, L_i\}$$

where $c_i$ is content, $t_i$ is timestamp, $K_i, G_i, X_i$ are LLM-generated metadata (keywords, tags, context), $e_i$ is a vector embedding, and $L_i$ represents links to related memories [17].

A-MEM's distinguishing feature is autonomous link generation: when a new memory is created, the system identifies semantically related existing memories and establishes bidirectional connections. This creates an evolving knowledge graph that surfaces emergent relationships.

These systems demonstrate sophisticated memory management but require external infrastructure (vector databases, graph stores) and introduce retrieval latency. Our approach trades sophistication for simplicity: rather than intelligent extraction and linking, we rely on explicit agent decisions about what to preserve.

## 2.5 Skill Libraries and Procedural Memory

**Voyager** [18] addresses long-term learning in embodied agents through a novel form of procedural memory: executable code. Operating in Minecraft, Voyager maintains a **skill library** of JavaScript functions representing learned behaviors.

When Voyager discovers how to perform a task (e.g., mining iron), it:
1. Generates executable code through iterative prompting
2. Verifies correctness through environment feedback
3. Stores the skill in a retrievable library

This approach solves catastrophic forgetting—skills persist as code rather than weights—and enables zero-shot transfer to new environments [18]. Voyager achieves milestones 15.3× faster than prior methods by reusing previously learned skills.

While Voyager focuses on procedural knowledge (how to do things), our work addresses episodic knowledge (what happened and why). The approaches are complementary: an agent could use scope isolation for reasoning while maintaining a Voyager-style skill library for actions.

## 2.6 Context Compression and Folding

A parallel research thread addresses context limits through **compression** rather than memory externalization.

**Context-Folding** [2] frames context management as a reinforcement learning problem. Agents learn policies for two operations:
- **Branch**: Create isolated context for focused reasoning
- **Collapse**: Merge contexts back with summarization

Through RL training, agents learn when these operations maximize task success. The approach achieves 10× context reduction on long-horizon tasks [2]. However, the requirement for reward engineering and RL training limits accessibility.

**AgentFold** [1] introduces folding operations at two granularities:
- **Micro-folding**: Compressing individual reasoning steps
- **Macro-folding**: Collapsing entire reasoning branches

AgentFold requires fine-tuning the underlying model to learn folding policies, adding deployment complexity.

**HiAgent** [3] takes a hierarchical approach, decomposing tasks into subgoals with associated context chunks. Memory boundaries emerge from task structure rather than learned policies. HiAgent achieves 2× higher success rates with 35% less context without requiring fine-tuning [3].

Table 1 summarizes these approaches:

| Approach | Mechanism | Training Required | Context Reduction |
|----------|-----------|-------------------|-------------------|
| MemGPT [13] | Virtual paging | No | Unbounded (external) |
| Mem0 [16] | Extraction + graphs | No | ~90% token savings |
| Context-Folding [2] | RL-learned branch/collapse | RL training | 10× |
| AgentFold [1] | Learned folding | Fine-tuning | High |
| HiAgent [3] | Subgoal chunking | No | 35% |
| **Ours** | Explicit scope isolation | **No** | **68%** |

## 2.7 Positioning Our Contribution

Our work occupies a distinct position in this landscape. We share MemGPT's goal of bounded context but achieve it without external storage. We share Context-Folding's branching metaphor but implement it through explicit commands rather than learned policies. We share HiAgent's training-free philosophy but allow arbitrary scope organization rather than task-derived hierarchies.

The key differentiators of explicit context management are:

1. **No training requirements**: Works with any tool-use capable model
2. **No external infrastructure**: All state maintained in-process
3. **Explicit control**: Agents decide what to preserve through deliberate commands
4. **Minimal interface**: Four commands cover all operations

Perhaps most importantly, our approach makes context management **legible**. When an agent creates a scope or takes a note, these operations are visible in the conversation trace. Failures in memory management—forgotten notes, poorly chosen scope boundaries—can be diagnosed and corrected through prompt engineering rather than retraining.

This legibility comes at a cost: the agent must correctly use the commands. Learned approaches may achieve better policies through optimization, while our approach depends on prompt-induced behavior. We view this as a reasonable tradeoff for applications where simplicity and interpretability are valued over peak performance.

## 2.8 The Episodic Memory Hypothesis

Recent position papers [6] argue that episodic memory is "the missing piece" for long-term LLM agents. Drawing parallels to biological memory systems, Nuxoll and Laird [6] note that episodic memory enables **single-exposure learning**—the ability to encode experiences from one occurrence rather than requiring multiple training examples.

This capability is crucial for agents operating in non-stationary environments where specific events cannot be replicated. An agent that debugs a production incident must remember the specific error context; an agent assisting with a research project must recall which approaches were tried and why they failed.

Our note mechanism operationalizes this hypothesis. Each note captures a specific episodic memory—what was discovered, decided, or learned in a particular context. The scope structure provides the "when and where" anchoring that distinguishes episodic from semantic memory. And the asymmetric placement semantics (origin for departure notes, destination for arrival notes) maintain the causal chain that makes episodic recall meaningful.

In this sense, explicit context management is an implementation of the episodic memory hypothesis for practical agent deployment: a minimal architecture that provides fast, single-exposure encoding of task-relevant experiences without requiring architectural modifications or additional training.
