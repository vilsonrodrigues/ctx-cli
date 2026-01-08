# Appendix D: Theoretical Foundations

## D.1 Relationship to Human Memory

Our approach draws explicit parallels to Tulving's memory taxonomy [21]:

| SPACE Concept | Cognitive Analog |
|---------------|------------------|
| Scopes | Episodic contexts |
| Notes | Episodic encoding |
| Insights | Semantic memory consolidation |
| Transitions | Context shifts |

The three-tier architecture (working, episodic, semantic) maps directly to cognitive science models, suggesting that effective memory systems—whether biological or artificial—may share structural principles.

## D.2 Future-Proofing for Next-Generation Models

As the field anticipates million-token context windows, the trend towards larger contexts continues. However, larger windows do not solve the *attention dilution* problem—performance on reasoning tasks typically degrades as context fills with noise [4, 5]. Furthermore, the computational cost and latency of processing massive contexts remain prohibitive for real-time agent loops.

SPACE provides a crucial architectural layer for future models, ensuring that their superior reasoning capabilities are applied to high-signal, self-curated contexts rather than diluted by raw interaction logs.

## D.3 Structured Test-Time Compute

The prevailing paradigm for enhancing model performance at inference time—**Test-Time Compute (TTC)** [41]—often relies on brute-force strategies like generating multiple Chain-of-Thought (CoT) paths [38] or deepening search trees (Tree of Thoughts) [39]. While effective, these approaches suffer from unstructured expansion: the model generates vast amounts of tokens that may be repetitive, circular, or irrelevant, with no mechanism to "garbage collect" bad reasoning paths.

SPACE reframes TTC from unstructured token expenditure into **Structured Cognitive Allocation**:

1. **Scopes as Compute Budgets**: Each `scope` represents a deliberate allocation of computational resources to a specific sub-problem. Unlike unbounded CoT, a scope is a "container" for thought that must eventually be closed.

2. **Returns as Cognitive Commits**: The `return` command forces a **crystallization** of reasoning. It requires the agent to synthesize its exploration into a concrete decision and discard the noisy process that led to it. This prevents the "cognitive drift" common in long CoT traces.

3. **Externalized Reasoning**: While CoT externalizes reasoning in *text*, SPACE externalizes it in *structure*. The graph of scopes and notes forms a high-level representation of the problem-solving process that is more robust than a linear stream of tokens.

In this view, SPACE acts as a **Test-Time Compute Controller**, allowing agents to "think longer" about complex problems without paying the quadratic attention cost usually associated with long-context reasoning.

### D.3.1 Stabilization vs. Planning

It is crucial to distinguish SPACE from a hierarchical planner. In planning algorithms (like ToT), branches often represent individual *ideas* or atomic steps. In SPACE, scopes represent **stable lines of reasoning**. Planning is inherently turbulent exploration; SPACE provides the **containment** for this turbulence.

By isolating the messy process of trial-and-error within a scope and only propagating the stabilized conclusion (via `return`), SPACE acts as a **Cognitive Stabilization System**. It does not tell the agent *what* to think (planning), but *where* to think to maintain coherence (containment).

## D.4 Convergence with Recursive Architectures

The emergence of Recursive Language Models (RLM) [31] validates the paradigm of "context management via code execution." RLM demonstrates that LLMs can handle inputs up to **10M+ tokens**—two orders of magnitude beyond their native context windows—by treating the prompt as an external environment the model can programmatically examine.

### D.4.1 The RLM Mechanism

RLM provides models with:
1. A Python REPL where the prompt is stored as a variable (`context`)
2. A `llm_query` function for recursive self-calls on filtered snippets
3. Execution feedback to iteratively refine reasoning

This enables patterns like:
```python
# RLM approach: Model writes arbitrary code
chunks = [context[i:i+1000] for i in range(0, len(context), 1000)]
for chunk in chunks:
    result = llm_query(f"Extract key facts from: {chunk}")
    buffer.append(result)
final_answer = llm_query(f"Synthesize: {buffer}")
```

### D.4.2 SPACE as High-Level RLM

SPACE can be understood as a **high-level abstraction over RLM's principles**:

| RLM Primitive | SPACE Equivalent |
|---------------|------------------|
| `context` variable | Current scope's message history |
| `llm_query(snippet)` | `scope` + work + `return` |
| `buffer.append(result)` | `note -m "..."` |
| Global variables | `insight -m "..."` |
| REPL state | Context store |

The key insight is that SPACE **pre-structures** the patterns RLM models must discover:
- RLM: "Figure out how to chunk and process"
- SPACE: "Use `scope` to isolate, `note` to persist, `return` to consolidate"

### D.4.3 Tradeoffs

**RLM advantages:**
- Maximum flexibility (arbitrary Python)
- Can handle truly novel patterns
- Scales to 10M+ tokens

**SPACE advantages:**
- Works with any tool-use model (not just frontier 400B+)
- Predictable latency (~1.5s vs multi-minute trajectories)
- Lower failure rate (validated commands vs code errors)
- Human-readable audit trail

The fundamental tradeoff is **expressiveness vs. reliability**. RLM's raw code generation offers unbounded capability but requires frontier models and accepts high variance. SPACE's structured commands sacrifice some flexibility for consistency and portability.

### D.4.4 Potential Synthesis

A promising direction combines both approaches:
1. **SPACE for structure**: Enforce scope/return discipline and memory tiers
2. **RLM for content**: Within scopes, allow code-based context manipulation

This would preserve SPACE's cognitive discipline while enabling RLM's powerful symbolic interaction for specific sub-tasks requiring complex filtering or transformation.
