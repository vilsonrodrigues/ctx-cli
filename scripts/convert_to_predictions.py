#!/usr/bin/env python3
"""
Convert ctx-cli benchmark results to SWE-bench prediction format.
Works for both single tasks and sequential CL tasks.
"""

import json
import sys
from pathlib import Path

def convert_results_to_predictions(results_file, output_file):
    """Convert ctx-cli results to SWE-bench prediction format."""
    results_path = Path(results_file)
    if not results_path.exists():
        print(f"Error: Results file {results_file} not found.")
        return

    with open(results_path) as f:
        data = json.load(f)

    predictions = []
    
    # Handle both SWE-bench Lite and CL formats
    if "results" in data:
        # Lite format
        raw_results = data["results"]
    elif "linear" in data or "scope" in data:
        # CL format (sequential tasks)
        raw_results = []
        for approach in ["linear", "scope"]:
            if data.get(approach) and "task_results" in data[approach]:
                for task_res in data[approach]["task_results"]:
                    # Ensure we label the approach in the model name
                    task_res["approach"] = approach
                    raw_results.append(task_res)
    else:
        print("Error: Unknown result format.")
        return

    for result in raw_results:
        instance_id = result.get("instance_id") or result.get("task_id")
        patch = result.get("patch")
        
        if instance_id and patch:
            approach = result.get("approach", "unknown")
            predictions.append({
                "instance_id": instance_id,
                "model_patch": patch,
                "model_name_or_path": f"ctx-cli-{approach}"
            })

    if not predictions:
        print("No valid patches found in the results file.")
        return

    with open(output_file, 'w') as f:
        json.dump(predictions, f, indent=2)

    print(f"Successfully converted {len(predictions)} predictions to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/convert_to_predictions.py <results_json> <output_json>")
    else:
        convert_results_to_predictions(sys.argv[1], sys.argv[2])