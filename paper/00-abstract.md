# SPACE: Self-Partitioned Agent Context Environment for Long-Horizon Agents

We introduce **SPACE**, a training-free architecture that enables LLM agents to manage their own working memory through explicit commands. Unlike learned compression approaches—Context-Folding requires reinforcement learning, AgentFold and CaT require supervised fine-tuning on thousands of trajectories—SPACE achieves comparable context reduction using only standard tool-use interfaces, deployable immediately with any frontier model.

SPACE treats conversation context as versioned state rather than a linear log. The architecture provides a minimal command interface organized around three operations: **navigation** (`scope`, `return`), **persistence** (`note`, `insight`), and **inspection** (`notes`, `insights`, `status`). Agents work in isolated scopes—temporary reasoning environments—and return to a stable main context with summarized conclusions, implementing a **radial navigation** pattern (hub-and-spoke) that prevents cognitive drift.

The core innovation is a **three-tier memory system** without external infrastructure:
- **Working memory**: Ephemeral messages in current scope (cleared on return)
- **Episodic memory**: Scope-local notes capturing specific events (persistent)
- **Semantic memory**: Global insights encoding reusable patterns (persistent across all scopes)

This architecture enables knowledge transfer patterns impossible with pure compression: an insight discovered in `fix/auth-bug` becomes immediately available in `feature/new-endpoint` without explicit retrieval.

Preliminary experiments on sequential coding tasks from SWE-Bench-CL show **~88% reduction in peak context** and **~34% faster execution** compared to linear conversation baselines—approaching learned compression results without training overhead. The key finding: SPACE provides value specifically when context accumulates across multiple related steps; for isolated single-turn tasks, simpler approaches suffice.

Our open-source implementation demonstrates that effective context management can be achieved through explicit mechanisms rather than learned policies, shifting complexity from model training to agent architecture.