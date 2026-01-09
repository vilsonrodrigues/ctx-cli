# SWE-Bench Verified Setup

## Overview

SWE-Bench Verified is a curated subset of ~500 tasks from SWE-Bench that have been:
- Manually verified to be solvable
- Have reliable, deterministic test suites
- Cover diverse repositories and issue types

Reference: https://github.com/princeton-nlp/SWE-bench

## Requirements

### 1. Python Dependencies

```bash
uv pip install datasets huggingface_hub
```

### 2. Docker (for test execution)

The official evaluation requires Docker:

```bash
# Install Docker
sudo apt install docker.io

# Add user to docker group
sudo usermod -aG docker $USER

# Verify
docker --version
```

### 3. HuggingFace Access

The dataset is publicly available:
- Dataset: `princeton-nlp/SWE-bench_Verified`
- No authentication required

## Running the Benchmark

### Quick Start (Mini)

```bash
uv run benchmarks/runners/run_benchmark.py \
    --benchmark swe-bench-verified \
    --size mini
```

### With Repository Filter

```bash
uv run benchmarks/runners/run_benchmark.py \
    --benchmark swe-bench-verified \
    --size small \
    --repo django/django
```

### Full Evaluation

```bash
uv run benchmarks/runners/run_benchmark.py \
    --benchmark swe-bench-verified \
    --size full \
    --max-tasks 100
```

## Dataset Structure

Each task contains:
- `instance_id`: Unique identifier (e.g., `django__django-12345`)
- `repo`: Repository name (e.g., `django/django`)
- `base_commit`: Git commit to apply patch to
- `problem_statement`: GitHub issue description
- `hints_text`: Optional hints for solving
- `patch`: Gold standard solution
- `FAIL_TO_PASS`: Tests that should pass after the fix
- `PASS_TO_PASS`: Tests that should remain passing

## Evaluation Modes

### Simulated Mode (Development)
- Used when Docker is not available
- Compares patch similarity (NOT for production)
- Fast iteration during development

### Docker Mode (Production)
- Uses official SWE-bench evaluation harness
- Runs actual test suites in containers
- Required for accurate results

## Comparison with SWE-Bench-CL

| Aspect | SWE-Bench Verified | SWE-Bench-CL |
|--------|-------------------|--------------|
| Tasks | ~500 | 273 |
| Organization | Independent | Chronological sequences |
| Focus | General evaluation | Continual learning |
| Memory reset | Optional | Never (within sequence) |

## Troubleshooting

### "datasets not installed"
```bash
uv pip install datasets
```

### "Permission denied" on Docker
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

### "Rate limit exceeded" on HuggingFace
The dataset is cached locally after first download at:
`benchmarks/harnesses/swe_bench_verified/data/tasks.json`
