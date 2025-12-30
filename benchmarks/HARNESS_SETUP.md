# SWE-bench Harness Setup for ctx-cli Evaluation

This guide explains how to set up and run the SWE-bench Docker harness to validate patch correctness from ctx-cli experiments.

## Overview

The SWE-bench harness evaluates generated patches by:
1. Building Docker containers with the exact repository state
2. Applying the generated patch
3. Running the repository's test suite
4. Reporting pass/fail results

## Prerequisites

- **Docker**: Version 29.1+ installed and running
- **System Resources**:
  - 120GB free storage
  - 16GB RAM minimum
  - 8 CPU cores recommended
- **Python**: 3.9+

## Installation

### 1. Install SWE-bench Harness

```bash
# Clone the official SWE-bench repository
git clone https://github.com/princeton-nlp/SWE-bench.git
cd SWE-bench
pip install -e .
```

### 2. Prepare Predictions File

The harness expects predictions in a specific format. Convert our results to the required schema:

```python
# scripts/convert_to_predictions.py
import json
from pathlib import Path

def convert_results_to_predictions(results_file, output_file):
    """Convert ctx-cli results to SWE-bench prediction format."""
    with open(results_file) as f:
        data = json.load(f)

    predictions = []
    for result in data["results"]:
        if result["success"] and result["patch"]:
            predictions.append({
                "instance_id": result["instance_id"],
                "model_patch": result["patch"],
                "model_name_or_path": f"ctx-cli-{result['approach']}"
            })

    with open(output_file, 'w') as f:
        json.dump(predictions, f, indent=2)

    print(f"Converted {len(predictions)} predictions to {output_file}")

# Usage
convert_results_to_predictions(
    "benchmarks/results/swe_bench_lite_20251230_173212.json",
    "benchmarks/predictions_lite.json"
)
```

### 3. Run Evaluation

```bash
# From SWE-bench directory
python -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-bench_Lite \
  --predictions_path ../ctx-cli/benchmarks/predictions_lite.json \
  --max_workers 4 \
  --cache_level instance \
  --output_dir ../ctx-cli/benchmarks/harness_results/
```

**Parameters:**
- `--dataset_name`: Which benchmark (SWE-bench, SWE-bench_Lite, etc.)
- `--predictions_path`: Path to converted predictions
- `--max_workers`: Number of parallel evaluations
- `--cache_level`: Docker caching strategy (none/base/env/instance)
- `--output_dir`: Where to save evaluation results

### 4. Optimized Setup (Optional)

For faster evaluations, use Epoch AI's optimized Docker images:

```bash
# Pull pre-built images
docker pull ghcr.io/swe-bench/swe-bench-env:latest

# Run with optimized images
python -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-bench_Lite \
  --predictions_path ../ctx-cli/benchmarks/predictions_lite.json \
  --max_workers 8 \
  --use_cached_images \
  --output_dir ../ctx-cli/benchmarks/harness_results/
```

## Evaluation Workflow

### For SWE-Bench Lite (Single Tasks)

1. **Generate patches** with `run_swe_bench_lite.py`
2. **Convert results** to prediction format
3. **Run harness** on subset of instances
4. **Analyze pass@1** for LINEAR vs SCOPE

Expected workflow:
```bash
# Generate patches
OPENAI_API_KEY="..." uv run python benchmarks/run_swe_bench_lite.py \
  --tasks 10 \
  --approach both \
  --max-iterations 30

# Convert to predictions
python scripts/convert_to_predictions.py

# Evaluate with harness
cd ../SWE-bench
python -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-bench_Lite \
  --predictions_path ../ctx-cli/benchmarks/predictions_lite.json \
  --max_workers 4
```

### For SWE-Bench-CL (Sequential Tasks)

**Note**: SWE-Bench-CL is designed for continual learning evaluation. The harness is less relevant here because:

1. Our benchmark measures **context growth**, not patch correctness
2. Tasks are analyzed but not fully implemented (simplified version)
3. The value is in demonstrating bounded context, not perfect solutions

For full validation of SWE-Bench-CL, we would need to:
- Modify `run_swe_cl.py` to actually implement fixes (not just analyze)
- Generate patches for each task
- Run harness on the full sequence

This is future work if we want to measure both context efficiency AND solution quality.

## Results Interpretation

The harness outputs a report with:

```json
{
  "instance_id": "django__django-10914",
  "resolved": true,  // Did the patch fix the issue?
  "test_results": {
    "passed": 42,
    "failed": 0,
    "errors": 0
  }
}
```

**Key Metrics:**
- **pass@1**: Percentage of instances where patch passes all tests
- **resolution_rate**: Percentage of issues fully resolved

**For our paper:**
- Compare LINEAR vs SCOPE pass@1 rates
- Check if context efficiency comes at quality cost
- Validate that both approaches generate correct solutions

## Expected Results

Based on our Django task (django__django-10914):
- Both LINEAR and SCOPE generated **identical patches** (modulo formatting)
- Both should achieve **100% pass@1** on this specific task
- This validates that SCOPE preserves solution quality while reducing context

For broader evaluation (10-20 tasks):
- Expect similar pass@1 for both approaches
- SCOPE may have slightly lower pass@1 on isolated tasks (due to overhead)
- But for sequential tasks, SCOPE should match or exceed LINEAR quality

## Storage Management

Docker images can consume significant space:

```bash
# Check Docker space usage
docker system df

# Clean up after evaluation
docker system prune -a

# Or use cache_level=none and clean=True
python -m swebench.harness.run_evaluation \
  --cache_level none \
  --clean True \
  ...
```

## Troubleshooting

### Docker Permission Errors
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Out of Memory
Reduce `--max_workers` to 2 or 1

### Image Build Failures
Some tasks have complex dependencies. Use `--skip_existing` to continue after failures.

## References

- [SWE-bench Docker Setup](https://www.swebench.com/SWE-bench/guides/docker_setup/)
- [SWE-bench Evaluation Guide](https://www.swebench.com/SWE-bench/guides/evaluation/)
- [Epoch AI Optimized Docker](https://epoch.ai/blog/swebench-docker)
- [GitHub: SWE-bench](https://github.com/SWE-bench/SWE-bench)

## Next Steps

1. **Immediate**: Convert existing SWE-Bench Lite results to prediction format
2. **Short-term**: Run harness on 10-20 Lite tasks to validate quality
3. **Future**: Extend SWE-Bench-CL runner to generate full patches for harness evaluation
