#!/usr/bin/env python3
"""
Setup script for ECM benchmarks.

Downloads and configures all benchmark datasets:
- MemoryBench (supermemoryai)
- MemoryAgentBench (HUST-AI)
- Episodic Memory Benchmark (ICLR 2025)
- SWE-Bench-CL

Usage:
    uv run benchmarks/setup_benchmarks.py --all
    uv run benchmarks/setup_benchmarks.py --benchmark memorybench
"""

import argparse
import os
import subprocess
import sys
import json
import shutil
from pathlib import Path
from typing import Optional

# Try to import requests for downloads
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# =============================================================================
# Configuration
# =============================================================================

BENCHMARKS_DIR = Path(__file__).parent
DATA_DIR = BENCHMARKS_DIR / "data"
REPOS_DIR = BENCHMARKS_DIR / "repos"

BENCHMARKS = {
    "memorybench": {
        "name": "MemoryBench (supermemoryai)",
        "description": "Unified benchmark for conversational memory and RAG",
        "repo": "https://github.com/supermemoryai/memorybench.git",
        "paper": "https://github.com/supermemoryai/memorybench",
        "type": "git",
    },
    "memoryagentbench": {
        "name": "MemoryAgentBench (HUST-AI)",
        "description": "Evaluating memory in LLM agents via incremental multi-turn interactions",
        "repo": "https://github.com/HUST-AI-HYZ/MemoryAgentBench.git",
        "paper": "https://arxiv.org/abs/2503.00234",
        "type": "git",
    },
    "episodic-memory": {
        "name": "Episodic Memory Benchmark (ICLR 2025)",
        "description": "Synthetic episodic memory datasets (10K-1M tokens)",
        "repo": "https://github.com/ahstat/episodic-memory-benchmark.git",
        "paper": "https://arxiv.org/abs/2501.13121",
        "type": "git",
    },
    "swe-bench-cl": {
        "name": "SWE-Bench-CL",
        "description": "Continual learning benchmark for coding agents",
        "huggingface": "princeton-nlp/SWE-bench_Lite",
        "paper": "https://arxiv.org/abs/2507.00014",
        "type": "huggingface",
        "local_data": "swe-bench-cl.json",
    },
    "longmem": {
        "name": "LongMemEval",
        "description": "Long-context memory evaluation",
        "repo": "https://github.com/xiaowu0162/LongMemEval.git",
        "paper": "https://arxiv.org/abs/2410.10813",
        "type": "git",
    },
}


# =============================================================================
# Helper Functions
# =============================================================================

def run_command(cmd: list[str], cwd: Optional[Path] = None) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def check_git() -> bool:
    """Check if git is available."""
    success, _ = run_command(["git", "--version"])
    return success


def check_uv() -> bool:
    """Check if uv is available."""
    success, _ = run_command(["uv", "--version"])
    return success


def clone_repo(repo_url: str, target_dir: Path) -> bool:
    """Clone a git repository."""
    if target_dir.exists():
        print(f"  Already exists: {target_dir}")
        # Pull latest
        success, output = run_command(["git", "pull"], cwd=target_dir)
        if success:
            print(f"  Updated to latest")
        return True

    print(f"  Cloning {repo_url}...")
    success, output = run_command(["git", "clone", "--depth", "1", repo_url, str(target_dir)])

    if success:
        print(f"  Cloned to {target_dir}")
    else:
        print(f"  Failed: {output[:200]}")

    return success


def download_file(url: str, target_path: Path) -> bool:
    """Download a file from URL."""
    if not REQUESTS_AVAILABLE:
        # Fallback to curl
        success, output = run_command(["curl", "-L", "-o", str(target_path), url])
        return success

    try:
        print(f"  Downloading {url}...")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"  Saved to {target_path}")
        return True

    except Exception as e:
        print(f"  Failed: {e}")
        return False


def setup_huggingface_dataset(dataset_id: str, target_dir: Path) -> bool:
    """Download a HuggingFace dataset."""
    try:
        # Try using huggingface_hub
        from huggingface_hub import snapshot_download

        print(f"  Downloading {dataset_id} from HuggingFace...")
        snapshot_download(
            repo_id=dataset_id,
            repo_type="dataset",
            local_dir=target_dir,
        )
        print(f"  Downloaded to {target_dir}")
        return True

    except ImportError:
        print("  huggingface_hub not installed. Installing...")
        success, _ = run_command(["uv", "pip", "install", "huggingface_hub"])
        if success:
            return setup_huggingface_dataset(dataset_id, target_dir)
        return False

    except Exception as e:
        print(f"  Failed: {e}")
        return False


# =============================================================================
# Benchmark Setup Functions
# =============================================================================

def setup_memorybench() -> bool:
    """Setup MemoryBench benchmark."""
    print("\n[MemoryBench]")
    config = BENCHMARKS["memorybench"]

    repo_dir = REPOS_DIR / "memorybench"
    success = clone_repo(config["repo"], repo_dir)

    if success:
        # Check for requirements and install
        req_file = repo_dir / "requirements.txt"
        if req_file.exists():
            print("  Installing dependencies...")
            run_command(["uv", "pip", "install", "-r", str(req_file)])

    return success


def setup_memoryagentbench() -> bool:
    """Setup MemoryAgentBench benchmark."""
    print("\n[MemoryAgentBench]")
    config = BENCHMARKS["memoryagentbench"]

    repo_dir = REPOS_DIR / "memoryagentbench"
    success = clone_repo(config["repo"], repo_dir)

    if success:
        # Check for data directory
        data_dir = repo_dir / "data"
        if data_dir.exists():
            print(f"  Data directory found: {data_dir}")
            # List available datasets
            for item in data_dir.iterdir():
                print(f"    - {item.name}")

    return success


def setup_episodic_memory() -> bool:
    """Setup Episodic Memory Benchmark."""
    print("\n[Episodic Memory Benchmark]")
    config = BENCHMARKS["episodic-memory"]

    repo_dir = REPOS_DIR / "episodic-memory-benchmark"
    success = clone_repo(config["repo"], repo_dir)

    if success:
        # Install dependencies
        print("  Installing dependencies...")
        run_command(["uv", "pip", "install", "-e", str(repo_dir)])

    return success


def setup_swe_bench_cl() -> bool:
    """Setup SWE-Bench-CL benchmark."""
    print("\n[SWE-Bench-CL]")

    # Check if local data exists
    local_data = DATA_DIR / "swe-bench-cl.json"
    if local_data.exists():
        print(f"  Local data found: {local_data}")
        return True

    # Try to download from HuggingFace
    config = BENCHMARKS["swe-bench-cl"]

    # For SWE-Bench-CL, we need to create a custom dataset
    # Since it's based on SWE-Bench, let's create a sample structure
    print("  Creating sample SWE-Bench-CL structure...")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    sample_data = {
        "name": "SWE-Bench-CL",
        "description": "Continual learning sequences from SWE-Bench",
        "sequences": [
            {
                "repo": "django/django",
                "tasks": [
                    {
                        "metadata": {
                            "instance_id": f"django__django-{10000 + i}",
                            "repo": "django/django",
                            "base_commit": "main",
                        },
                        "task": {
                            "problem_statement": f"Sample task {i + 1} for Django"
                        }
                    }
                    for i in range(50)
                ]
            }
        ]
    }

    with open(local_data, "w") as f:
        json.dump(sample_data, f, indent=2)

    print(f"  Created sample data: {local_data}")
    print("  NOTE: Replace with real SWE-Bench-CL data for actual benchmarking")

    return True


def setup_longmem() -> bool:
    """Setup LongMemEval benchmark."""
    print("\n[LongMemEval]")
    config = BENCHMARKS["longmem"]

    repo_dir = REPOS_DIR / "longmemeval"
    success = clone_repo(config["repo"], repo_dir)

    return success


# =============================================================================
# Main Setup
# =============================================================================

def setup_benchmark(name: str) -> bool:
    """Setup a specific benchmark."""
    if name not in BENCHMARKS:
        print(f"Unknown benchmark: {name}")
        print(f"Available: {', '.join(BENCHMARKS.keys())}")
        return False

    setup_funcs = {
        "memorybench": setup_memorybench,
        "memoryagentbench": setup_memoryagentbench,
        "episodic-memory": setup_episodic_memory,
        "swe-bench-cl": setup_swe_bench_cl,
        "longmem": setup_longmem,
    }

    if name in setup_funcs:
        return setup_funcs[name]()

    return False


def setup_all() -> dict[str, bool]:
    """Setup all benchmarks."""
    results = {}
    for name in BENCHMARKS:
        results[name] = setup_benchmark(name)
    return results


def list_benchmarks() -> None:
    """List available benchmarks."""
    print("\nAvailable Benchmarks:")
    print("-" * 60)

    for key, config in BENCHMARKS.items():
        status = "✓" if (REPOS_DIR / key).exists() or (DATA_DIR / f"{key}.json").exists() else "○"
        print(f"  [{status}] {key}")
        print(f"      {config['name']}")
        print(f"      {config['description']}")
        print(f"      Paper: {config.get('paper', 'N/A')}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Setup ECM benchmarks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    uv run benchmarks/setup_benchmarks.py --list
    uv run benchmarks/setup_benchmarks.py --all
    uv run benchmarks/setup_benchmarks.py --benchmark memorybench
    uv run benchmarks/setup_benchmarks.py --benchmark memoryagentbench episodic-memory
        """
    )

    parser.add_argument("--list", action="store_true", help="List available benchmarks")
    parser.add_argument("--all", action="store_true", help="Setup all benchmarks")
    parser.add_argument("--benchmark", nargs="+", help="Setup specific benchmark(s)")
    parser.add_argument("--clean", action="store_true", help="Clean benchmark repos")

    args = parser.parse_args()

    # Create directories
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    # Check prerequisites
    if not check_git():
        print("Error: git is required but not found")
        sys.exit(1)

    if args.list:
        list_benchmarks()
        return

    if args.clean:
        print("Cleaning benchmark repos...")
        if REPOS_DIR.exists():
            shutil.rmtree(REPOS_DIR)
            print(f"  Removed {REPOS_DIR}")
        return

    if args.all:
        print("=" * 60)
        print("Setting up all benchmarks")
        print("=" * 60)

        results = setup_all()

        print("\n" + "=" * 60)
        print("Setup Summary")
        print("=" * 60)
        for name, success in results.items():
            status = "✓" if success else "✗"
            print(f"  [{status}] {name}")

    elif args.benchmark:
        for name in args.benchmark:
            setup_benchmark(name)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
