# LifelongAgentBench Setup

## Overview

LifelongAgentBench evaluates agents on skill reuse across multiple environments:
Database (SQL), Operating System (Bash), and Knowledge Graph (SPARQL).

**Repository**: https://github.com/caixd-220529/LifelongAgentBench
**Website**: https://caixd-220529.github.io/LifelongAgentBench/

## Installation

```bash
# Clone official harness
git clone https://github.com/caixd-220529/LifelongAgentBench.git /tmp/lifelong-agent-bench

# Install dependencies
cd /tmp/lifelong-agent-bench
pip install -r requirements.txt

# Setup Docker environments
docker-compose up -d
```

## Environments

### Database (db)
- MySQL tasks with 22 SQL skills
- Tasks: CREATE, INSERT, SELECT, UPDATE, DELETE, JOINs, subqueries
- Verification: Query execution and result comparison

### Operating System (os)
- Linux bash tasks with 29 skills
- Tasks: File operations, process management, text processing
- Verification: Command execution and filesystem state

### Knowledge Graph (kg)
- SPARQL queries over RDF data
- Tasks: Pattern matching, filtering, aggregation
- Verification: Query execution and result sets

## Running with ECM

```bash
# Mini evaluation (10 tasks, DB only)
uv run benchmarks/runners/run_benchmark.py \
    --benchmark lifelong-agent-bench \
    --size mini \
    --environment db

# Full evaluation (100 tasks, all environments)
uv run benchmarks/runners/run_benchmark.py \
    --benchmark lifelong-agent-bench \
    --size full
```

## Metrics

- **Skill Reuse Rate**: How often agent applies learned skills
- **Cross-Environment Transfer**: Knowledge transfer between DB/OS/KG
- **Context Efficiency**: Token usage vs task completion
- **Dependency Accuracy**: Success on dependent task chains

## Docker Requirements

Each environment runs in isolated containers:

```bash
# Start all environments
docker-compose -f /tmp/lifelong-agent-bench/docker-compose.yml up -d

# Verify containers
docker ps | grep lifelong
```

## Task Dependencies

Tasks are structured with explicit dependencies:
- Task T_n may depend on results from T_{n-1}, T_{n-2}, etc.
- Agent must remember table names, file paths, or graph nodes created earlier
- Forgetting leads to task failures

## Key Files

- `adapter.py`: ECM adapter for the harness
- `runner.py`: Main evaluation script
- `config/`: Environment configurations
