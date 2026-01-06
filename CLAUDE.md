# ctx-cli: Explicit Context Management (ECM)

## Overview

Git-like CLI for explicit context management in LLM agents.
Focus: **continual learning for real tasks** (not book QA, not synthetic).

## Project Structure

```
ctx-cli/
├── ctx_store.py      # Core ECM implementation (Notes, Insights, Scopes)
├── ctx_cli.py        # CLI interface (ctx_cli tool for agents)
├── agent.py          # Example agent with ECM integration
├── metrics.py        # Token tracking utilities
├── benchmarks/       # Evaluation with official harnesses
│   ├── core/         # Shared infrastructure
│   ├── harnesses/    # Official benchmark integrations
│   ├── retrieval/    # Retrieval benchmarks (NOT continual learning)
│   └── runners/      # Unified CLI runners
├── paper/            # Academic manuscript
└── demos/            # Usage demonstrations
```

## Core Concepts

### ECM Memory Types
- **Notes**: Explicit facts/observations (semantic memory)
- **Insights**: Patterns/learnings extracted from experience (episodic → semantic)
- **Scopes**: Hierarchical context organization (like git branches)

### Key Operations
```python
# Save a note
ctx_cli.note("User prefers dark mode")

# Save an insight (learned pattern)
ctx_cli.insight("API errors usually need retry with backoff")

# Create/switch scope
ctx_cli.scope("project/auth", note="Working on authentication")

# Pull relevant context
context = ctx_cli.pull(query="authentication patterns")
```

## Benchmarks

### Critical Rules

1. **NEVER use synthetic data** - Always load from official datasets
2. **NEVER reset agent between CL tasks** - Memory must persist across sequence
3. **ALWAYS run official correctness checks** - Tests must pass, not just similarity
4. **ALWAYS track tokens** - Use `CumulativeTokenReport` for every run
5. **DO reset between sequences** - New episode = fresh agent state

### Benchmark Categories

| Category | Benchmarks | Purpose |
|----------|------------|---------|
| **CL-Focused** | SWE-Bench-CL, LifelongAgentBench | Test knowledge retention across tasks |
| **Long-Horizon** | AppWorld, OSWorld | Test multi-step task completion |
| **Retrieval** | MemoryAgentBench | Baseline comparisons (NOT CL!) |

### Running Benchmarks

```bash
# Single benchmark (mini for dev, full for paper)
uv run benchmarks/runners/run_benchmark.py --benchmark swe-bench-cl --size mini

# All benchmarks
uv run benchmarks/runners/run_all.py --size full --output results/
```

### Official Harnesses

| Benchmark | Repository | Status |
|-----------|------------|--------|
| SWE-Bench-CL | `thomasjoshi/agents-never-forget` | Priority 1 |
| LifelongAgentBench | `caixd-220529/LifelongAgentBench` | Priority 1 |
| AppWorld | `StonyBrookNLP/appworld` | Priority 2 |
| OSWorld | `xlang-ai/OSWorld` | Priority 3 |

## Code Conventions

### Style
- Python 3.9+
- Formatter: `ruff format`
- Linter: `ruff check`
- Type hints required on public interfaces

### Testing
```bash
uv run pytest tests/ -v
```

### Dependencies
```bash
# Install all dependencies
uv sync --all-groups

# Run with dependencies
uv run python script.py
```

## Paper Claims

The paper (`paper/`) makes these key claims about ECM:

1. **88% context reduction** on SWE-Bench-CL (12,059 → 1,402 tokens)
2. **34% faster execution** (121.5s → 80.5s)
3. **O(1) base + O(m) growth** vs O(n) linear accumulation
4. **Works with any tool-use capable model** - no fine-tuning required

## Common Tasks

### Adding a New Benchmark

1. Create harness directory: `benchmarks/harnesses/{name}/`
2. Implement `OfficialHarness` protocol in `adapter.py`
3. Create runner in `runner.py`
4. Add config to `configs/{name}.yaml`
5. Register in `runners/run_benchmark.py`
6. Add setup instructions to `SETUP.md`

### Debugging Token Usage

```python
from benchmarks.core.metrics import CumulativeTokenReport

report = CumulativeTokenReport(agent_type="ecm", model="gpt-4o", benchmark="test")
# ... run tasks ...
print(report.summary())
```

### Comparing ECM vs Linear

```python
from benchmarks.core.ecm_agent import ECMAgent
from benchmarks.core.linear_agent import LinearAgent

# Run same tasks with both agents, compare token trajectories
```

## Environment Variables

```bash
OPENAI_API_KEY=...          # Required for OpenAI models
ANTHROPIC_API_KEY=...       # Required for Claude models
ECM_DEBUG=1                 # Enable verbose logging
```

## Troubleshooting

### "Harness not found"
Run setup script: `bash benchmarks/scripts/setup_harnesses.sh`

### "Token limit exceeded"
ECM should prevent this. Check if agent is using `ctx_cli.pull()` instead of accumulating.

### "Tests not passing"
Ensure Docker is running for SWE-Bench-CL test execution.
