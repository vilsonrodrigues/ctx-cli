# 1. Introduction

Language model agents have emerged as a compelling paradigm for automating complex, multi-step tasks. Unlike traditional prompt-response interactions, agents operate in extended loops—observing environments, taking actions, and reasoning over trajectories that may span hours or days [12]. From software development assistants to research copilots, these agents promise to transform how humans interact with AI systems.

However, a fundamental tension undermines this promise: while agentic tasks require potentially unbounded reasoning, the underlying context windows are finite. As agents execute multi-step tasks, every interaction—user requests, assistant responses, tool invocations, and their results—accumulates in the conversation history. This creates a linear growth in context size that eventually degrades performance through attention dilution and exceeds model limits [4, 5].

## 1.1 The Stability Barrier

Consider an agent tasked with resolving a sequence of GitHub issues in a codebase. Each issue builds on knowledge from previous fixes: code patterns discovered, API conventions learned, architectural constraints identified. In a traditional agent loop, every interaction persists in context. For a sequence of 15 coding tasks from SWE-Bench-CL [20], we observe context growing to over 12,000 tokens by the final task, with linear approaches accumulating context at $\sim$780 tokens per task.

This unbounded accumulation creates a fundamental **stability barrier**. It is not merely a question of cost, but of operational viability. As context grows, agents face:
1.  **Attention Collapse**: The model's ability to retrieve specific, relevant information degrades as the ratio of noise (past history) to signal (current task) increases [4, 5].
2.  **Context Amnesia**: When the window limit is reached, arbitrary truncation severs reasoning chains, forcing the agent to rediscover information it "knows" but can no longer "see."
3.  **Latency Spikes**: Inference latency grows super-linearly, rendering the agent unresponsive in real-time loops.

The Cognitive Architectures for Language Agents (CoALA) framework [12] identifies this as a structural limitation: most contemporary agents conflate *working memory* (active reasoning) with *long-term memory* (accumulated knowledge) within the same finite context window. To achieve true longevity, an agent must be able to **discard** the process of learning while **retaining** the lesson learned.

## 1.2 The Memory Imperative

Recent surveys on memory mechanisms in LLM-based agents [4, 5] frame context management as the critical bottleneck for agent capability. The consensus is that effective long-term agents require differentiated memory systems analogous to human cognition:

*   **Working Memory**: Active reasoning state (the context window).
*   **Episodic Memory**: Records of specific experiences and events.
*   **Semantic Memory**: General knowledge and learned facts.
*   **Procedural Memory**: Skills and behavioral patterns.

A recent position paper [6] argues that episodic memory is "the missing piece" for long-term agents. Unlike semantic memory, which captures general facts, episodic memory encodes *what happened, when, and why*—the experiential grounding that enables agents to learn from specific interactions. Crucially, episodic memory supports *single-exposure learning*: encoding experiences from one occurrence rather than requiring repeated training [6]. This reframes the context management problem: the goal is not merely to compress context, but to create appropriate memory structures that preserve episodic knowledge while bounding working memory.

## 1.3 The Reasoning Model Paradox

The recent advent of **Reasoning Models** (e.g., OpenAI o1) exacerbates this issue. These models achieve high performance by generating extensive "Chain-of-Thought" (CoT) traces [38]—often thousands of tokens of internal monologue—before producing a final answer. While this "Test-Time Compute" [41] boosts single-turn accuracy, it is catastrophic for multi-step agents. If an agent retains these verbose reasoning traces in its history, the context window fills exponentially faster with irrelevant intermediate states. Without a mechanism to discard this ephemeral reasoning while preserving the conclusion, reasoning models in agentic loops suffer from rapid performance degradation.

## 1.4 Existing Approaches and Their Tradeoffs

The research community has proposed diverse solutions to context limitations, each with distinct tradeoffs.

**Virtual context management** systems like MemGPT [13] draw analogies to operating system memory hierarchies. By "paging" information between main context (RAM) and external storage (disk), these systems provide unbounded effective context. However, they require external infrastructure and introduce retrieval latency and coherence challenges.

**Learned compression** approaches train models to compress context intelligently. Context-Folding [2] uses reinforcement learning to learn when to branch and collapse context, achieving 10$\times$ reduction. AgentFold [1] fine-tunes models to perform micro- and macro-folding operations. CaT [28] trains a dedicated SWE-Compressor model on 20,000 trajectories to learn when and how to compress. While effective, these approaches require significant training overhead and produce models that are not transferable across domains.

**Agentic memory** systems like Mem0 [16] and A-MEM [17] actively manage memory through extraction, linking, and consolidation. These systems achieve impressive results but require sophisticated infrastructure including vector databases and graph stores.

Table 1 summarizes how SPACE compares to these approaches:

**Table 1: Comparison of Context Management Approaches**

| Approach | Training | Navigation | Semantic Memory | Model Portable |
| :--- | :--- | :--- | :--- | :--- |
| MemGPT [13] | None | Linear | External DB | Yes |
| Context-Folding [2] | RL | Stack (LIFO) | No | No |
| AgentFold [1] | SFT | Linear | No | No |
| CaT [28] | SFT (20K) | Linear | No | No |
| **SPACE (Ours)** | **None** | **Radial** | **Yes (insights)** | **Yes** |

What these approaches share is a commitment to **implicit** context management—policies learned through training or derived from task structure. The agent does not explicitly decide what to remember; this is determined by algorithms operating on the context.

## 1.5 SPACE: Self-Partitioned Agent Context Environment

We propose a fundamentally different approach: give agents **explicit control** over their context through deliberate operations. Rather than learning when to compress or relying on automatic extraction, agents declare what matters through structured commands. We call this architecture **SPACE (Self-Partitioned Agent Context Environment)**.

Our insight is that conversation context can be treated as **versioned state**, analogous to version control systems for code. Just as developers create branches to isolate work and commits to checkpoint progress, agents can create scopes to isolate reasoning and notes to preserve learnings.

This leads to a minimal interface organized around three operations: **navigation** (`scope`, `return`), **persistence** (`note`, `insight`), and **inspection** (`notes`, `insights`, `status`).

| Command | Semantics | Memory Tier |
| :--- | :--- | :--- |
| `scope <name>` | Create and enter new context | Working |
| `return` | Finalize scope and return to main | Working |
| `note` | Record scope-local event | Episodic |
| `insight` | Record global knowledge | Semantic |
| `notes` / `insights` | Retrieve memories | — |
| `status` | Inspect current state | Meta |

The key mechanism is **scope isolation with radial navigation**. Messages are partitioned into scopes, and only messages from the current scope are visible to the model during API calls. SPACE implements a **hub-and-spoke topology**: the `main` context serves as a stable hub, while temporary scopes branch off for specific subtasks and must return with summarized conclusions. This enforces cognitive discipline—agents cannot drift between arbitrary contexts but must consolidate their reasoning before switching tasks.

This design creates a **three-tier memory system** without external infrastructure:
*   **Working memory**: Messages in the current scope (ephemeral, cleared on return).
*   **Episodic memory**: Notes local to each scope (persistent, queryable via `notes`).
*   **Semantic memory**: Insights global across all scopes (persistent, queryable via `insights`).

## 1.6 Contributions

This paper makes the following contributions:

1.  **SPACE: A Minimal, Training-Free Architecture**: We demonstrate that a small set of commands (navigation, persistence, inspection) suffices for effective context control, requiring no model fine-tuning or reinforcement learning.
2.  **Radial Scope Navigation**: Unlike stack-based approaches that enforce LIFO ordering, SPACE implements radial navigation where agents branch from a stable `main` context and must return with consolidated summaries, preventing arbitrary context drift.
3.  **Three-Tier Memory Architecture**: We introduce a system differentiating working memory (ephemeral), episodic memory (scope-local notes), and semantic memory (global insights), enabling knowledge transfer patterns impossible with pure compression.
4.  **Cognitive Commit Semantics**: The `return` command forces explicit summarization before context switching, transforming context management into active attention control.
5.  **Empirical Validation**: Experiments on SWE-Bench-CL [30] demonstrate an **88% reduction in peak context** and **34% faster execution** compared to linear baselines, with $O(1)$ context growth for sequential tasks.
6.  **Open-Source Implementation**: We provide a model-agnostic implementation that integrates with any tool-use capable model.

## 1.7 Paper Organization

Section 2 surveys related work. Section 3 presents our method, including data structures and command semantics. Section 4 describes the experimental setup. Section 5 presents results. Section 6 discusses limitations and design implications. Section 7 concludes.
