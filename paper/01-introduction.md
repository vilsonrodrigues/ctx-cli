# 1. Introduction

Language model agents have emerged as a compelling paradigm for automating complex, multi-step tasks. Unlike traditional prompt-response interactions, agents operate in extended loops—observing environments, taking actions, and reasoning over trajectories that may span hours or days [12]. From software development assistants to research copilots, these agents promise to transform how humans interact with AI systems.

However, a fundamental tension undermines this promise: while agentic tasks require potentially unbounded reasoning, the underlying context windows are finite. As agents execute multi-step tasks, every interaction—user requests, assistant responses, tool invocations, and their results—accumulates in the conversation history. This creates a linear growth in context size that eventually degrades performance through attention dilution and exceeds model limits [4, 5].

## 1.1 The Stability Barrier

Consider an agent tasked with resolving a sequence of GitHub issues in a codebase. Each issue builds on knowledge from previous fixes: code patterns discovered, API conventions learned, architectural constraints identified. In a traditional agent loop, every interaction persists in context. Prior work on cognitive architectures for language agents [12] identifies this cumulative growth as a fundamental structural limitation, with context expanding linearly as tasks accumulate.

This unbounded accumulation creates a fundamental **stability barrier**. It is not merely a question of cost, but of operational viability. As context grows, agents face:
1.  **Attention Collapse**: The model's ability to retrieve specific, relevant information degrades as the ratio of noise (past history) to signal (current task) increases [4, 5].
2.  **Context Amnesia**: When the window limit is reached, truncation or aggressive summarization severs reasoning chains, forcing the agent to rediscover information it "knows" but can no longer "see."
3.  **Latency Spikes**: Inference latency grows with context length, rendering the agent unresponsive in real-time loops.

This structural limitation stems from a design conflation: most contemporary agents use the same finite context window for both *working memory* (active reasoning) and *long-term memory* (accumulated knowledge) [12]. Existing approaches often conflate *reasoning history* with *knowledge retention*, leading to inefficiencies and instability during long-horizon tasks. To achieve true longevity, an agent must be able to **discard** the process of learning while **retaining** the lesson learned—a clear separation between *thinking* and *knowing*.

## 1.2 The Memory Imperative

Recent surveys on memory mechanisms in LLM-based agents [4, 5] frame context management as the critical bottleneck for agent capability. A recurring theme in this literature is that effective long-term agents require differentiated memory systems analogous to human cognition:

*   **Working Memory**: Active reasoning state (the context window).
*   **Episodic Memory**: Records of specific experiences and events.
*   **Semantic Memory**: General knowledge and learned facts.

A recent position paper [6] argues that episodic memory is "the missing piece" for long-term agents. Unlike semantic memory, which captures general facts, episodic memory encodes *what happened, when, and why*—the experiential grounding that enables agents to learn from specific interactions. Crucially, episodic memory enables encoding experiences from a single occurrence rather than requiring repeated training, a property the cognitive science literature terms *one-shot episodic encoding* [6]. This reframes the context management problem: the goal is not merely to compress context, but to create appropriate memory structures that preserve episodic knowledge while bounding working memory.

## 1.3 The Test-Time Compute Paradox

Recent advances demonstrate that allocating additional computation at inference time—commonly referred to as *test-time compute* (TTC)—significantly improves performance on complex reasoning tasks [41]. Techniques such as chain-of-thought prompting, self-consistency, tree-of-thoughts, and graph-of-thoughts leverage extended deliberation to explore alternatives and refine answers. The advent of **token-level reasoning models** (e.g., OpenAI o-series [38]) institutionalizes this pattern: these models generate extensive reasoning traces before producing final answers, achieving high single-turn accuracy through TTC scaling.

However, this paradigm creates a fundamental tension for multi-step agents. If an agent retains verbose reasoning traces in its history, the context window fills significantly faster with intermediate states irrelevant for subsequent tasks. More critically, most TTC approaches suffer from three structural limitations:

1. **Undirected Compute**: More thinking does not guarantee better thinking. Models may repeat ideas, drift into tangents, or rationalize decisions already implicitly made.
2. **No Semantic Commit**: Even after extensive deliberation, there is no clear demarcation between exploratory reasoning and committed decisions. Reflections may contradict earlier conclusions without resolution.
3. **Superlinear Cost Growth**: Tree-based approaches explode combinatorially, expending tokens on paths that never influence the final result.

Without a mechanism to discard ephemeral reasoning while preserving conclusions, reasoning models in agentic loops suffer the same stability barrier as simpler agents—exacerbated by their verbose deliberation style.

## 1.4 Existing Approaches

Prior work has addressed context limitations through diverse mechanisms: virtual paging between active context and external storage [13], learned compression policies trained via reinforcement learning or supervised fine-tuning [1, 2, 28], and agentic memory systems with extraction and consolidation pipelines [16, 17]. These approaches achieve impressive results but typically require either external infrastructure (vector databases, graph stores), model-specific training that limits transferability, or implicit management policies where the agent does not explicitly decide what to remember.

Section 2 surveys this landscape in detail. Our contribution is an *explicit*, *training-free* alternative: agents declare what matters through structured commands rather than relying on learned or automatic policies.

## 1.5 SPACE: Self-Partitioned Agent Context Environment

We propose a fundamentally different approach: give agents **explicit control** over their context through deliberate operations. Rather than learning when to compress or relying on automatic extraction, agents declare what matters through structured commands. We call this architecture **SPACE (Self-Partitioned Agent Context Environment)**.

The core idea is to explicitly separate *disposable reasoning traces* from *persistent knowledge artifacts*, while enforcing a disciplined execution flow that constrains how and when reasoning branches may be created or discarded. This design enforces a clear distinction between *thinking* and *knowing*, aligning the agent's operational structure with cognitive principles while enabling scalable test-time computation.

Our approach draws on Tulving's theory of episodic memory [21], which distinguishes between *remembering* (re-experiencing past events) and *knowing* (accessing general facts). In SPACE, agents record significant events during task execution (episodic traces) and can later perform *mental time travel*—selectively revisiting relevant past experiences rather than maintaining the entire trajectory in working memory. This allows agents to discard the verbose process of problem-solving while retaining the distilled conclusions.

This leads to a minimal interface organized around three operations: **navigation** (`scope`, `return`), **persistence** (`note`, `insight`), and **inspection** (`notes`, `insights`, `status`).

| Command | Semantics | Memory Tier |
| :--- | :--- | :--- |
| `scope <name>` | Create and enter new context | Working |
| `return` | Finalize scope and return to main | Working |
| `note` | Record scope-local event | Episodic |
| `insight` | Record global knowledge | Semantic |
| `notes` / `insights` | Retrieve memories | — |
| `status` | Inspect current state | Meta |

The key mechanism is **scope isolation with layered hub-and-spoke navigation**. Messages are partitioned into scopes, and only messages from the current scope are visible to the model during API calls. The `main` context serves as a stable hub, while temporary scopes branch off for specific subtasks. Upon returning, intermediate reasoning is discarded while conclusions are preserved—the agent explicitly chooses what to persist via `note` and `insight` commands, making the compression policy interpretable and transferable across domains.

Critically, this architecture reframes test-time compute: each scope represents an **explicit allocation of deliberation budget**. The agent must decide when to open a scope, how long to reason within it, and what merits consolidation. By forcing all durable information through `return`, SPACE transforms TTC from an implicit byproduct of token generation into a **controllable, bounded resource**.

This design creates a **three-tier memory system** grounded in Tulving's cognitive taxonomy [21], without external infrastructure:
*   **Working memory**: Messages in the current scope (ephemeral, cleared on return).
*   **Episodic memory**: Notes local to each scope (persistent, queryable via `notes`).
*   **Semantic memory**: Insights global across all scopes, forming a growing **semantic substrate** that shapes behavior across tasks and sessions (persistent, queryable via `insights`).

Additionally, a **project-based session management** mechanism addresses a critical deployment requirement: developers often need to reset agent state for new tasks while preserving learned knowledge. When a new project begins, previous scopes are archived (e.g., `debug-auth@v1`) but their episodic memories remain accessible via `@project` notation, while semantic memory (insights) persists universally. This enables **cross-session knowledge transfer**: patterns discovered in one project immediately benefit subsequent projects without explicit retrieval.

**Hypothesis.** We hypothesize that explicit context control through structured commands enables agents to maintain stable performance across extended task sequences, achieving bounded context growth while preserving task-relevant knowledge. This should manifest as (1) sublinear context growth with respect to the number of tasks, and (2) maintained task success rates as sequences lengthen.

## 1.6 Contributions

This paper makes the following contributions:

1.  **SPACE: A Minimal, Training-Free Architecture**: We demonstrate that a small set of commands (navigation, persistence, inspection) suffices for effective context control, requiring no model retraining.
2.  **Test-Time Compute Control**: Unlike graph-based or chain-of-thought methods that treat TTC as implicit token expenditure, SPACE structures deliberation into explicit, irreversible cycles with mandatory consolidation, making compute allocation controllable and predictable.
3.  **Layered Hub-and-Spoke Navigation**: SPACE implements a layered hub-and-spoke topology where agents branch from a stable `main` context into isolated scopes, returning with consolidated summaries. Strict transition rules prevent reentry, nesting, or arbitrary navigation.
4.  **Three-Tier Memory Architecture**: We introduce a system grounded in cognitive science, differentiating working memory (ephemeral), episodic memory (scope-local notes), and semantic memory (global insights). A complementary project mechanism enables cross-session episodic retrieval.
5.  **Cross-Session Knowledge Transfer**: Insights persist across project boundaries, enabling lifelong learning where knowledge from previous sessions benefits new tasks without retrieval overhead.
6.  **Empirical Validation**: Experiments on SWE-Bench-CL [30] and LifelongAgentBench demonstrate bounded context growth and maintained performance compared to linear baselines.

## 1.7 Paper Organization

Section 2 surveys related work. Section 3 presents our method, including data structures and command semantics. Section 4 describes the experimental setup. Section 5 presents results. Section 6 discusses limitations and design implications. Section 7 concludes.
