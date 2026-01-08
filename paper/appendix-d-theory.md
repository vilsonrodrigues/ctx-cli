# Appendix D: Theoretical Foundations

## D.1 Cognitive Science Parallels

Our architectural choices are not arbitrary but draw explicit inspiration from cognitive psychology, specifically Endel Tulving's taxonomy of long-term memory systems [21].

| SPACE Component | Cognitive Analog | Function |
| :--- | :--- | :--- |
| **Scopes** | Episodic Contexts | Frames of reference for specific time-bound events. |
| **Notes** | Episodic Encoding | Crystallization of high-entropy experiences. |
| **Insights** | Semantic Consolidation | Abstraction of general rules from specific instances. |
| **Transitions** | Context Switching | The cognitive cost of changing task focus. |

This isomorphism suggests that the three-tier architecture (Working, Episodic, Semantic) is a robust pattern for intelligence systems, whether biological or artificial.

## D.2 The "Test-Time Compute" Paradigm

The prevailing paradigm for enhancing model performance—**Test-Time Compute (TTC)** [41]—suggests that allowing models to "think longer" improves reasoning. However, current implementations (e.g., Chain-of-Thought) often suffer from unstructured expansion, where the model generates vast amounts of "cognitive waste."

SPACE reframes TTC as **Structured Cognitive Allocation**:

1.  **Scopes as Compute Budgets**: Each `scope` represents a deliberate allocation of tokens to a sub-problem. It acts as a container for thought.
2.  **Returns as Cognitive Commits**: The `return` command forces a **crystallization** of reasoning. It requires the agent to synthesize exploration into decision, effectively performing "Garbage Collection" on its own thought process.
3.  **Graph as Externalized Reasoning**: The resulting structure of scopes and notes forms a high-level representation of the problem-solving process, more robust than a linear stream of tokens.

In this view, SPACE acts as a **Cognitive Controller**, allowing agents to scale compute without paying the quadratic attention penalty associated with linear context growth.

## D.3 Convergence with Recursive Architectures

The emergence of **Recursive Language Models (RLM)** [31] validates the paradigm of "context management via code execution." RLM demonstrates that LLMs can handle inputs orders of magnitude larger than their context window by treating the prompt as an external environment.

### D.3.1 SPACE as High-Level RLM

SPACE can be formalized as a high-level abstraction over RLM primitives:

| RLM Primitive | SPACE Equivalent |
| :--- | :--- |
| `context` variable | Current scope's message history |
| `llm_query(snippet)` | `scope` $\rightarrow$ work $\rightarrow$ `return` |
| `buffer.append(result)` | `note` |
| Global variables | `insight` |

The key distinction is **Abstraction Level**. RLM requires the model to write correct Python code to manage its memory (High Flexibility, High Risk). SPACE provides validated tools for the same operations (Constrained Flexibility, High Reliability).

### D.3.2 The Synthesis

We propose that future architectures will converge on a hybrid:
*   **SPACE for Macro-Structure**: Managing high-level task navigation and memory tiers.
*   **RLM for Micro-Reasoning**: Allowing code-based manipulation of context *within* a specific scope.

This hybrid approach would combine the reliability of SPACE's navigation topology with the unbounded expressivity of RLM's code-driven reasoning.
