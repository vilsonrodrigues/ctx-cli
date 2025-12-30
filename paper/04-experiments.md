# 4. Experiments

We evaluate explicit context management across three experimental scenarios designed to measure token economics and knowledge retention capabilities.

## 4.1 Experimental Setup

### 4.1.1 Model and Infrastructure

All experiments use **GPT-4.1-mini** via the OpenAI API. We chose this model for:
- Tool-use capability required for command interface
- Moderate context window (128K tokens) representative of current deployments
- Cost efficiency for multiple experimental runs

Token counting uses **tiktoken** with the cl100k_base encoding for accurate measurement.

### 4.1.2 Baseline: Linear Conversation

The baseline represents traditional agent architecture:
- All messages accumulate in a single conversation history
- No context management tools available
- Standard system prompt (~30 tokens)

### 4.1.3 Treatment: Scope-Based Context

The treatment provides explicit context management:
- Four commands available as tools (scope, goto, note, scopes/notes)
- Extended system prompt explaining commands and workflow (~800 tokens)
- Same underlying model and API

### 4.1.4 Metrics

We measure:

| Metric | Description |
|--------|-------------|
| **Base Input** | First-call tokens (system + tools + user) — cacheable by providers |
| **Peak Input** | Maximum tokens in any single API call |
| **Growth** | Peak minus base — represents actual context growth |
| **Total Input** | Sum of all input tokens across all API calls |
| **Total Output** | Sum of all output tokens |
| **Iterations** | Number of API calls to complete task |

We separate base from growth because modern API providers cache system prompts and tool definitions. The actual incremental cost is better represented by growth.

## 4.2 Task 1: Multi-Step Coding Task

### 4.2.1 Task Description

Design a blog platform through 12 sequential steps:

1. Design data model for posts, comments, users
2. Add categories and tags
3. Design authentication system
4. Add notification system
5. Add search feature
6. Add analytics tracking
7. Design API endpoints
8. Summarize architecture
9. (continued iterations as needed)

Each step builds on previous decisions, requiring the agent to maintain coherent context.

### 4.2.2 Expected Behavior

**Linear baseline**: Context grows with each step. By step 8, context includes all previous 7 exchanges plus current.

**Scope treatment**: Agent should:
1. Create scopes for related work (e.g., "data-model", "auth", "api")
2. Take notes on key decisions within each scope
3. Return to main with summaries
4. Access notes from previous scopes as needed

## 4.3 Task 2: Cross-Project Knowledge Transfer

### 4.3.1 Task Description

Two sequential projects simulating separate development efforts:

**Project A**: Create a User model with:
- Dataclass with id, email, name, password_hash, created_at, is_active
- Email validation (must contain @)
- Password validation (min 8 chars)
- is_valid() aggregating validations
- to_dict() for serialization

**Project B**: Create a Product model with:
- Dataclass with id, name, price, stock, created_at, is_available
- Price validation (must be positive)
- Stock validation (must be >= 0)
- is_valid() aggregating validations
- to_dict() for serialization

### 4.3.2 Expected Behavior

**Linear baseline**: Project B starts fresh. The agent must rediscover patterns (validation structure, to_dict implementation) from scratch.

**Scope treatment**:
1. Project A creates notes documenting patterns
2. Between projects, working messages are cleared but notes persist
3. Project B queries notes from Project A
4. Agent applies same patterns, reducing exploration

### 4.3.3 Measurement

Between projects, we clear working messages in both conditions to simulate session boundaries. Only the scope treatment retains episodic memory (notes).

## 4.4 Task 3: Alternative Exploration

### 4.4.1 Task Description

Design a real-time collaborative document editor (similar to Google Docs) with requirements:
- Multiple users editing simultaneously
- Changes visible in real-time
- Offline support
- Version history
- Scale to 100 concurrent editors

The agent must explore two architectural approaches:
1. **Operational Transformation (OT)**: Transform-based conflict resolution
2. **CRDTs**: Conflict-free replicated data types

### 4.4.2 Expected Behavior

**Linear baseline**: All exploration in single context. OT analysis pollutes CRDT analysis and vice versa.

**Scope treatment**:
1. Create scope for OT exploration
2. Take notes on OT pros/cons, tech stack
3. Return to main with summary
4. Create scope for CRDT exploration
5. Take notes on CRDT pros/cons, tech stack
6. Return to main with summary
7. Compare using notes from both scopes

### 4.4.3 Measurement

We measure whether the agent can recall specific details from each approach when making the final comparison, indicating successful knowledge isolation and retrieval.

## 4.5 Task 4: SWE-Bench-CL Continual Learning

### 4.5.1 Task Description

We adapt the SWE-Bench-CL benchmark [20] to evaluate knowledge transfer across sequential GitHub issue resolution tasks. SWE-Bench-CL organizes 273 tasks from 8 repositories into chronologically ordered sequences, simulating realistic software evolution.

For our evaluation, we use a simplified version that measures context window growth rather than actual code correctness:

- **Dataset**: Django sequence (50 tasks available, we use 15)
- **Task format**: Each task provides a problem statement and files to modify
- **Evaluation**: Agent analyzes issue and proposes solution approach

### 4.5.2 Expected Behavior

**Linear baseline**: Context grows with each task as previous analyses accumulate. After 15 tasks, context includes all prior exchanges.

**Scope treatment**:
1. Create scope for each task
2. Analyze problem, identify patterns
3. Note reusable patterns (file structures, Django idioms)
4. Return to main with summary
5. Future tasks can reference accumulated patterns

### 4.5.3 Metrics

We focus on context window metrics (relevant with prompt caching):

| Metric | Description |
|--------|-------------|
| **Peak Context** | Maximum context window size |
| **Final Task Context** | Context size on last task |
| **Context Growth** | Total tokens added across all tasks |
| **API Calls** | Number of model invocations |
| **Cached Tokens** | Prompt tokens served from cache |
| **Execution Time** | Wall-clock time for completion |

### 4.5.4 Relevance to Real-World Agents

This task models a common pattern: an agent processing a queue of related tasks where knowledge from earlier tasks could benefit later ones. Examples include:
- CI/CD agents processing multiple PRs on the same repository
- Support agents handling tickets for the same product
- Code review agents analyzing related changes

## 4.6 Controlled Variables

To ensure fair comparison:

1. **Same model**: GPT-4.1-mini for all conditions
2. **Same tasks**: Identical task descriptions
3. **Same evaluation**: Automated token counting via tiktoken
4. **Multiple runs**: Results averaged across 3 runs per condition
5. **Temperature**: Set to 0.7 for all runs
6. **Max iterations**: Capped at 20 per task to prevent runaway execution

## 4.6 Limitations

Our experimental design has limitations:

1. **Single model**: Results may not generalize to other models
2. **Synthetic tasks**: Real-world agent tasks may differ in structure
3. **Prompted behavior**: Scope treatment success depends on agent following workflow
4. **No human evaluation**: We measure tokens, not output quality

We address output quality in Section 6 through task completion metrics.
