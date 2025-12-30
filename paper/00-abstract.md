# Abstract

Long-running language model agents face a fundamental limitation: context windows are finite, but tasks can require unbounded reasoning. As agents execute multi-step tasks, their context grows linearly with each message, eventually exceeding model limits or degrading performance through attention dilution. Current approaches address this through learned compression (requiring fine-tuning) or reinforcement learning (requiring reward engineering), adding significant complexity to agent development.

We introduce **explicit context management**, a lightweight approach that treats conversation context as versioned state. Our method provides agents with four commands—`scope`, `goto`, `note`, and inspection commands—that enable deliberate control over what information persists across reasoning steps. The key insight is **scope isolation**: by partitioning messages into isolated scopes and preserving only compressed episodic notes, agents maintain bounded context while retaining accumulated knowledge.

The architecture implements an attention mask mechanism where only messages from the current scope are visible to the model, while notes from all scopes remain accessible. This creates a two-tier memory system: ephemeral working memory (messages) and persistent episodic memory (notes). Transitions between scopes require explicit notes, preventing reasoning gaps when context switches.

We evaluate our approach on multi-step coding tasks comparing against linear conversation baselines. Results show **68% reduction in total input tokens** and **73% lower peak context** while completing identical tasks. The approach requires no model fine-tuning, no reinforcement learning, and integrates with any language model through standard tool-use interfaces.

Our implementation is available as an open-source library, demonstrating that effective context management for long-running agents can be achieved through simple, explicit mechanisms rather than learned compression.
