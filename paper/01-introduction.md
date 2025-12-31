# 1. Introduction

Language model agents have emerged as a compelling paradigm for automating complex, multi-step tasks. Unlike traditional prompt-response interactions, agents operate in extended loops—observing environments, taking actions, and reasoning over trajectories that may span hours or days [12]. From software development assistants to research copilots, these agents promise to transform how humans interact with AI systems.

Yet a fundamental tension undermines this promise: **context windows are finite, but agent tasks can require unbounded reasoning**. As agents execute multi-step tasks, every message—user requests, assistant responses, tool invocations, and their results—accumulates in the conversation history. This creates linear context growth that eventually exceeds model limits or degrades performance through attention dilution [4, 5].

## 1.1 The Context Growth Problem

Consider an agent tasked with resolving a sequence of GitHub issues in a codebase. Each issue builds on knowledge from previous fixes: code patterns discovered, API conventions learned, architectural constraints identified. In a traditional agent loop, every interaction persists in context.

For a sequence of 15 coding tasks from SWE-Bench-CL [20], we observe context growing to over 12,000 tokens by the final task, with linear approaches accumulating context at ~780 tokens per task. As context grows:

1. **Token costs scale** linearly with context size.
2. **Latency increases** as models process longer inputs.
3. **Attention dilutes** across increasingly irrelevant historical content.
4. **Overflow risk** emerges as context approaches model limits.

When context is eventually truncated—whether by model limits or explicit pruning—the agent loses track of what it learned, what decisions it made, and why. This "context amnesia" forces agents to rediscover information or make inconsistent decisions, undermining the coherence that distinguishes agents from stateless models.

The Cognitive Architectures for Language Agents (CoALA) framework [12] identifies this as a structural limitation: most contemporary agents conflate working memory (active reasoning) with long-term memory (accumulated knowledge) within the same context window. This conflation means that retaining knowledge requires retaining all the messages that produced it—an unsustainable design for long-horizon tasks.

## 1.2 The Memory Imperative

Recent surveys on memory mechanisms in LLM-based agents [4, 5] frame context management as the critical bottleneck for agent capability. The consensus emerging from this literature is that effective long-term agents require differentiated memory systems analogous to human cognition:

- **Working memory**: Active reasoning state (the context window).
- **Episodic memory**: Records of specific experiences and events.
- **Semantic memory**: General knowledge and learned facts.
- **Procedural memory**: Skills and behavioral patterns.

A recent position paper [6] argues that episodic memory is "the missing piece" for long-term agents. Unlike semantic memory, which captures general facts, episodic memory encodes **what happened, when, and why**—the experiential grounding that enables agents to learn from specific interactions. Crucially, episodic memory supports **single-exposure learning**: encoding experiences from one occurrence rather than requiring repeated training [6].

This insight reframes the context management problem. The goal is not merely to compress context, but to create appropriate memory structures that preserve episodic knowledge while bounding working memory.

## 1.3 Existing Approaches and Their Tradeoffs

The research community has proposed diverse solutions to context limitations, each with distinct tradeoffs.

**Virtual context management** systems like MemGPT [13] draw analogies to operating system memory hierarchies. By "paging" information between main context (RAM) and external storage (disk), these systems provide unbounded effective context. However, they require external infrastructure and introduce retrieval latency and coherence challenges.

**Learned compression** approaches train models to compress context intelligently. Context-Folding [2] uses reinforcement learning to learn when to branch and collapse context, achieving 10× reduction. AgentFold [1] fine-tunes models to perform micro- and macro-folding operations. While effective, these approaches require significant training overhead.

**Agentic memory** systems like Mem0 [16] and A-MEM [17] actively manage memory through extraction, linking, and consolidation. These systems achieve impressive results but require sophisticated infrastructure including vector databases and graph stores.

What these approaches share is a commitment to **implicit** context management—policies learned through training or derived from task structure. The agent does not explicitly decide what to remember; this is determined by algorithms operating on the context.

## 1.4 Explicit Context Management

We propose a fundamentally different approach: give agents **explicit control** over their context through deliberate operations. Rather than learning when to compress or relying on automatic extraction, agents declare what matters through structured commands.

Our insight is that conversation context can be treated as **versioned state**, analogous to version control systems for code. Just as developers create branches to isolate work and commits to checkpoint progress, agents can create scopes to isolate reasoning and notes to preserve learnings.

This leads to a minimal interface of four commands:

| Command | Semantics |
|---------|-----------|
| `scope <name> -m "..."` | Create isolated reasoning context |
| `goto <name> -m "..."` | Navigate between contexts |
| `note -m "..."` | Preserve episodic memory |
| `scopes` / `notes` | Inspect state |

The key mechanism is **scope isolation**. Messages are partitioned into scopes, and only messages from the current scope are visible to the model during API calls. Notes provide compressed episodic memory that persists within scopes, enabling knowledge retention without unbounded context growth.

This design creates a two-tier memory system without external infrastructure:
- **Working memory**: Messages in the current scope (ephemeral).
- **Episodic memory**: Notes in the current scope (persistent).

## 1.5 Contributions

This paper makes the following contributions:

1. **A minimal command interface for explicit context management.** We demonstrate that four commands suffice for effective context control, requiring no model modifications or external infrastructure.

2. **Application-Layer Context Partitioning.** We formalize a mechanism where message visibility is determined by scope membership, implementing bounded context through message filtering rather than architectural changes.

3. **Asymmetric Note Placement Semantics.** We introduce a novel transition protocol where "departure notes" stay in the origin scope and "arrival notes" go to the destination scope. This preserves the causal narrative of the agent's journey across disjoint memory spaces.

4. **Empirical validation of token economics.** We demonstrate **88% reduction in peak context** (12,059 → 1,402 tokens) and **34% faster execution** on sequential coding tasks from SWE-Bench-CL [20], while identifying that isolated tasks favor linear approaches.

5. **An open-source implementation** that integrates with any tool-use capable model and includes robust handling of API-specific constraints (such as tool call consistency).

Our approach occupies a distinct position in the design space: simpler than learned compression, more flexible than hierarchical decomposition, and more transparent than agentic memory systems. The tradeoff is explicit dependence on agent compliance—the model must correctly use the commands. We view this as acceptable for applications where interpretability and simplicity are valued alongside performance.

## 1.6 Paper Organization

Section 2 surveys related work in cognitive architectures, memory systems, and context compression. Section 3 presents our method, including data structures, the context partitioning mechanism, and command semantics. Section 4 describes experimental setup. Section 5 presents results on multi-step tasks. Section 6 discusses limitations, design decisions, and implications. Section 7 concludes.