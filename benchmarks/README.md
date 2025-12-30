# Benchmarks

Experimental evaluation of explicit context management.

## Benchmark Suite

### 1. Token Economics (Internal)

Compare LINEAR vs SCOPE approaches on controlled tasks:

| Task | Description | Metrics |
|------|-------------|---------|
| `multi_step_coding` | 12-step blog platform design | Peak tokens, total tokens, growth |
| `knowledge_transfer` | Cross-project pattern reuse | Notes accessed, patterns applied |
| `alternative_exploration` | OT vs CRDT architecture | Scope isolation, comparison quality |

```bash
uv run python benchmarks/run_internal.py
```

### 2. LOCOMO (Long-term Conversation Memory)

Evaluate on subset of LOCOMO benchmark:
- Single-hop QA (factual recall)
- Multi-hop QA (reasoning across turns)
- Temporal QA (time-based reasoning)

```bash
uv run python benchmarks/run_locomo.py
```

### 3. SWE-Bench-CL Style (Continual Learning)

Evaluate knowledge transfer across sequential coding tasks:
- Task 1: Create User model
- Task 2: Create Product model (should reuse patterns)
- Task 3: Create Order model (should reuse patterns)

```bash
uv run python benchmarks/run_swe_cl.py
```

## Metrics

### Token Metrics
- **Base Input**: System + tools + user (cacheable)
- **Peak Input**: Maximum tokens per API call
- **Growth**: Peak - Base (actual context growth)
- **Total Input**: Sum across all API calls
- **Total Output**: Generation tokens

### Memory Metrics
- **Notes Created**: Number of episodic memories
- **Notes Accessed**: Cross-scope memory retrieval
- **Pattern Transfer**: Successful pattern reuse rate

### Task Metrics
- **Completion Rate**: Tasks successfully completed
- **Accuracy**: Correctness of output
- **Iterations**: API calls to completion

## Running Benchmarks

```bash
# Install dependencies
uv sync

# Run all benchmarks
uv run python benchmarks/run_all.py

# Run specific benchmark
uv run python benchmarks/run_internal.py --task multi_step_coding
```

## Results

Results are saved to `benchmarks/results/` in JSON format.
