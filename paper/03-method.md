# 3. Method

We present **Explicit Context Management (ECM)**, a framework that provides agents with deliberate control over their working memory. Section 3.1 defines the core data structures. Section 3.2 details the context partitioning and inheritance strategy. Section 3.3 describes the command interface. Section 3.4 formalizes the asymmetric note placement and cognitive continuity. Section 3.5 presents the context composition algorithm and consistency guarantees.

## 3.1 Data Structures

The system relies on a **ContextStore** (C) that manages isolated reasoning contexts.

### 3.1.1 Scope (Reasoning Path)
A scope S is a distinct memory partition defined as:
$$ S = \langle M_S, N_S, H_S \rangle $$
Where:
- M_S is the **Working Memory**: A list of ephemeral messages (User, Assistant, Tool).
- N_S is the **Episodic Memory**: A stack of immutable notes representing high-level progress.
- H_S is the **Head Note**: A semantic pointer that situates the scope's origin.

### 3.1.2 Note (Episodic Unit)
A note n is a discrete summary of state, achieving a compression ratio of approximately 10:1 compared to raw logs. It preserves the "why" of a reasoning path while discarding the "how" (the specific tool interactions).

## 3.2 Context Partitioning and Inheritance

Unlike linear memory systems that suffer from O(n) token growth, ECM implements **Application-Layer Context Partitioning**.

### 3.2.1 The Main-as-Anchor Policy
A critical design choice in ECM is the **Inheritance Policy**. When a new scope S_new is created from an origin S_origin, it does not inherit M_origin. Instead, it inherits from S_main:
$$ M_{S_{new}} \leftarrow M_{S_{main}} $$

*Rationale*: This prevents "ancestry pollution," where errors or irrelevant logs from a previous sub-task leak into a new one. The `main` scope acts as the **Semantic Anchor**, accumulating only validated progress, while "leaf" scopes remain computationally lean.

## 3.3 Command Interface (Tool Schema)

The model interacts with C through a structured tool interface. The mandatory use of the -m (message) flag forces the model to perform **on-the-fly reflection** before every context switch.

| Command | Logical Operation | Transition Effect |
|---------|-------------------|-------------------|
| `scope <name> -m "..."` | S_origin -> S_new | Snapshot origin; Clear working memory |
| `goto <name> -m "..."` | S_origin -> S_target | Preserve tool chain; Restore target state |
| `note -m "..."` | N_S <- n_new | Checkpoint working memory |

## 3.4 Cognitive Continuity and Asymmetric Notes

To mitigate "cognitive lapses" during transitions—where an agent loses its objective after a context switch—ECM employs **Asymmetric Note Placement**.

Let T(A, B, m) be a transition from scope A to B with message m.
1. **Departure Logic**: For `scope B`, the note m is appended to N_A. This answers: *"Where did I go and why?"*
2. **Arrival Logic**: For `goto B`, the note m is appended to N_B. This answers: *"I am back; what did I bring from the other scope?"*

This creates a **narrative bridge** (B) that ensures the model's system prompt in the new context is grounded in the results of the previous one:
$$ \mathcal{B} = \text{last}(N_{origin}) \cup \text{head}(S_{target}) $$

## 3.5 Context Composition Algorithm

The final prompt P sent to the LLM is a non-linear composition of the store's state.

### Algorithm 1: Context Composition
**Input**: ContextStore C, SystemPrompt P_sys
**Output**: Message sequence P

1. P <- [P_sys]
2. S_active <- C.current_scope
3. **If** S_active.notes **is not empty**:
   - E <- Format last k notes as "Episodic Memory"
   - P <- P + [Message(role="system", content=E)]
4. M_clean <- ValidateToolSequence(S_active.messages)
5. P <- P + M_clean
6. **Return** P

### 3.5.1 Tool Call Consistency Guarantee
To maintain compatibility with APIs like OpenAI's, which enforce strict Assistant -> Tool sequences, ECM implements a **State Carry-Over** mechanism. If a transition is invoked while a tool response is pending, the system identifies the "orphaned" `tool_call_id` and carries the corresponding `assistant` message into the new scope's working memory. This prevents the "Incomplete Tool Chain" error that would otherwise crash the agent loop during non-linear transitions.

## 3.6 Token Economics

Let n be the total number of interactions, s the number of scopes, and k the average notes per scope.
- **Linear Complexity**: Tokens ~ O(n)
- **ECM Complexity**: Tokens ~ O(n/s + k)

Given that k << n, the ECM approach bounds the context window used in any single reasoning episode, enabling arbitrarily long task executions.
