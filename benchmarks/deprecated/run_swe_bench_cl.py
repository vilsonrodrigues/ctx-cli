#!/usr/bin/env python3
"""
SWE-Bench-CL (Continual Learning) Benchmark for ECM.

SWE-Bench-CL tests agents on sequences of related software engineering tasks.
Unlike standard SWE-Bench, it evaluates:
- Continual learning: Does the agent improve over the sequence?
- Forward transfer: Does knowledge from task N help with task N+1?
- Context retention: Can the agent recall relevant info from earlier tasks?

Dataset Structure:
- Each sequence contains 10-50 related tasks on the same repository
- Tasks are ordered chronologically (easier → harder, or by git history)
- Ground truth includes which files were modified and test results

Metrics:
- Task Success Rate: % of tasks completed correctly
- Forward Transfer: Performance gain from prior tasks
- Token Efficiency: Context usage across the sequence
- Knowledge Retention: Accuracy on callback questions about earlier tasks

Usage:
    # Run on sample sequence
    uv run benchmarks/longhorizon/run_swe_bench_cl.py --sequence django-1

    # Compare ECM vs baselines
    uv run benchmarks/longhorizon/run_swe_bench_cl.py --agents ecm longcontext --max-tasks 20

    # Full evaluation
    uv run benchmarks/longhorizon/run_swe_bench_cl.py --all-sequences --output results/swe_cl/

References:
- SWE-Bench: https://www.swebench.com/
- Continual Learning extension concept from ECM paper
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from tqdm import tqdm

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from benchmarks.common.base_agent import BaseAgent, AgentResult
from benchmarks.memory.agents import AVAILABLE_AGENTS, ECMAgent, LongContextAgent


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class SWETask:
    """A single SWE-Bench task."""
    task_id: str
    instance_id: str
    repo: str
    problem_statement: str
    hints: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)
    test_patch: str = ""
    gold_patch: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class SWESequence:
    """A sequence of related SWE tasks for continual learning."""
    sequence_id: str
    repo: str
    description: str
    tasks: list[SWETask]
    total_tasks: int = 0

    def __post_init__(self):
        self.total_tasks = len(self.tasks)


@dataclass
class TaskResult:
    """Result from a single task attempt."""
    task_id: str
    success: bool
    prediction: str
    ground_truth: str
    input_tokens: int
    output_tokens: int
    latency: float
    files_identified: list[str] = field(default_factory=list)
    knowledge_used: list[str] = field(default_factory=list)


@dataclass
class SequenceResult:
    """Results from running a full sequence."""
    sequence_id: str
    agent_name: str
    task_results: list[TaskResult]
    success_rate: float
    forward_transfer: float  # Improvement over baseline
    avg_tokens: float
    total_time: float
    retention_score: float  # Score on callback questions


# =============================================================================
# Dataset Loading
# =============================================================================

def load_swe_bench_cl_sequences(
    data_dir: Optional[str] = None,
    max_sequences: int = 5,
    max_tasks_per_sequence: int = 50,
) -> list[SWESequence]:
    """
    Load SWE-Bench-CL sequences.

    For now, uses synthetic sequences based on SWE-Bench structure.
    Full implementation requires SWE-Bench dataset setup.
    """
    sequences = []

    # Check for local data
    if data_dir and Path(data_dir).exists():
        data_path = Path(data_dir)
        for seq_file in sorted(data_path.glob("sequence_*.json"))[:max_sequences]:
            with open(seq_file) as f:
                seq_data = json.load(f)
            tasks = [SWETask(**t) for t in seq_data.get("tasks", [])[:max_tasks_per_sequence]]
            sequences.append(SWESequence(
                sequence_id=seq_data.get("sequence_id", seq_file.stem),
                repo=seq_data.get("repo", "unknown"),
                description=seq_data.get("description", ""),
                tasks=tasks,
            ))
        return sequences

    # Try loading from HuggingFace SWE-Bench
    try:
        from datasets import load_dataset
        print("Loading SWE-Bench from HuggingFace...")
        ds = load_dataset("princeton-nlp/SWE-bench", split="test")

        # Group by repo to create sequences
        repo_tasks = {}
        for item in ds:
            repo = item.get("repo", "unknown")
            if repo not in repo_tasks:
                repo_tasks[repo] = []
            repo_tasks[repo].append(SWETask(
                task_id=item.get("instance_id", ""),
                instance_id=item.get("instance_id", ""),
                repo=repo,
                problem_statement=item.get("problem_statement", ""),
                hints=item.get("hints_text", "").split("\n") if item.get("hints_text") else [],
                gold_patch=item.get("patch", ""),
                test_patch=item.get("test_patch", ""),
                metadata={
                    "base_commit": item.get("base_commit", ""),
                    "created_at": item.get("created_at", ""),
                },
            ))

        # Create sequences from repos with multiple tasks
        for repo, tasks in sorted(repo_tasks.items(), key=lambda x: -len(x[1]))[:max_sequences]:
            if len(tasks) >= 3:  # Only repos with enough tasks
                sequences.append(SWESequence(
                    sequence_id=f"swe_{repo.replace('/', '_')}",
                    repo=repo,
                    description=f"Continual learning sequence for {repo}",
                    tasks=tasks[:max_tasks_per_sequence],
                ))

        return sequences

    except ImportError:
        print("Warning: datasets not installed. Using synthetic data.")
    except Exception as e:
        print(f"Warning: Could not load SWE-Bench: {e}. Using synthetic data.")

    # Fallback: synthetic sequences for testing
    print("Generating synthetic SWE-Bench-CL sequences for testing...")
    for i in range(min(3, max_sequences)):
        tasks = []
        repo = f"test/repo-{i+1}"
        for j in range(min(10, max_tasks_per_sequence)):
            tasks.append(SWETask(
                task_id=f"task_{i}_{j}",
                instance_id=f"test__{repo.replace('/', '__')}__{j}",
                repo=repo,
                problem_statement=f"[Task {j+1}] Fix the bug in module_{j}.py that causes incorrect output when handling edge case {j}.",
                hints=[f"Look at the validation logic in line {50+j*10}"],
                files_to_modify=[f"src/module_{j}.py"],
                gold_patch=f"diff --git a/src/module_{j}.py\n+# Fixed edge case {j}",
            ))
        sequences.append(SWESequence(
            sequence_id=f"synthetic_{i+1}",
            repo=repo,
            description=f"Synthetic sequence {i+1} for testing",
            tasks=tasks,
        ))

    return sequences


# =============================================================================
# Long-Horizon Agent Wrapper
# =============================================================================

class LongHorizonAgentWrapper:
    """
    Wrapper that adapts memory agents for long-horizon task sequences.

    Provides:
    - Task context injection
    - Memory persistence across tasks
    - Callback question injection for retention testing
    """

    def __init__(self, agent: BaseAgent, agent_name: str):
        self.agent = agent
        self.agent_name = agent_name
        self.task_history: list[dict] = []
        self.current_sequence_id: str = ""

    def start_sequence(self, sequence: SWESequence):
        """Initialize for a new sequence."""
        self.current_sequence_id = sequence.sequence_id
        self.task_history = []

        # Memorize sequence context
        context = f"""Starting task sequence for repository: {sequence.repo}
Description: {sequence.description}
Total tasks in sequence: {sequence.total_tasks}

This is a continual learning evaluation. Knowledge from earlier tasks should help with later tasks.
"""
        self.agent.memorize(context, context_id=0)

    def process_task(self, task: SWETask, task_index: int) -> TaskResult:
        """Process a single task and return results."""
        start_time = time.time()

        # Build task prompt
        task_prompt = f"""
[Task {task_index + 1}] {task.task_id}

Repository: {task.repo}

Problem Statement:
{task.problem_statement}

"""
        if task.hints:
            task_prompt += f"Hints:\n" + "\n".join(f"- {h}" for h in task.hints) + "\n\n"

        if task.files_to_modify:
            task_prompt += f"Files that may need modification:\n" + "\n".join(f"- {f}" for f in task.files_to_modify) + "\n\n"

        task_prompt += """
Please analyze this task and provide:
1. Your understanding of the problem
2. The approach you would take
3. Key files/functions to modify
4. Any relevant knowledge from previous tasks in this sequence
"""

        # Memorize task context
        self.agent.memorize(f"Starting task {task_index + 1}: {task.problem_statement[:200]}...", context_id=0)

        # Query for solution
        result = self.agent.query(task_prompt, context_id=0)

        latency = time.time() - start_time

        # Analyze response
        response = result.get("answer", "")
        files_identified = self._extract_files_from_response(response)
        knowledge_used = self._extract_knowledge_references(response)

        # Determine success (simplified - full version would run tests)
        success = self._evaluate_response(response, task)

        # Store in history for retention testing
        self.task_history.append({
            "task_id": task.task_id,
            "task_index": task_index,
            "problem": task.problem_statement[:100],
            "response_summary": response[:200],
            "success": success,
        })

        # Memorize outcome for future tasks
        outcome_note = f"Task {task_index + 1} completed. Success: {success}. Approach: {response[:100]}..."
        self.agent.memorize(outcome_note, context_id=0)

        return TaskResult(
            task_id=task.task_id,
            success=success,
            prediction=response,
            ground_truth=task.gold_patch,
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            latency=latency,
            files_identified=files_identified,
            knowledge_used=knowledge_used,
        )

    def test_retention(self, num_questions: int = 3) -> float:
        """Test retention of knowledge from earlier tasks."""
        if len(self.task_history) < 2:
            return 1.0  # Not enough history to test

        correct = 0
        total = min(num_questions, len(self.task_history) - 1)

        for i in range(total):
            task_info = self.task_history[i]
            question = f"In task {task_info['task_index'] + 1} ({task_info['task_id']}), what was the main problem to solve?"

            result = self.agent.query(question, context_id=0)
            response = result.get("answer", "").lower()

            # Simple check: does response contain key terms from the problem?
            problem_terms = set(task_info["problem"].lower().split())
            response_terms = set(response.split())
            overlap = len(problem_terms & response_terms) / (len(problem_terms) + 1)

            if overlap > 0.2:  # At least 20% term overlap
                correct += 1

        return correct / total if total > 0 else 1.0

    def _extract_files_from_response(self, response: str) -> list[str]:
        """Extract mentioned file paths from response."""
        import re
        # Simple pattern matching for file paths
        patterns = [
            r'[\w/]+\.py',
            r'[\w/]+\.js',
            r'[\w/]+\.ts',
            r'src/[\w/]+',
            r'tests?/[\w/]+',
        ]
        files = set()
        for pattern in patterns:
            matches = re.findall(pattern, response)
            files.update(matches)
        return list(files)

    def _extract_knowledge_references(self, response: str) -> list[str]:
        """Extract references to prior tasks/knowledge."""
        import re
        refs = []
        # Look for references to earlier tasks
        patterns = [
            r'task \d+',
            r'earlier',
            r'previous',
            r'similar to',
            r'as we saw',
            r'learned from',
        ]
        for pattern in patterns:
            if re.search(pattern, response.lower()):
                refs.append(pattern)
        return refs

    def _evaluate_response(self, response: str, task: SWETask) -> bool:
        """
        Evaluate if response is successful.

        Full implementation would:
        1. Apply the generated patch
        2. Run the test suite
        3. Check if tests pass

        For now, uses heuristic based on file mention and approach quality.
        """
        response_lower = response.lower()

        # Check if target files are mentioned
        files_mentioned = sum(
            1 for f in task.files_to_modify
            if f.lower() in response_lower or f.split('/')[-1].lower() in response_lower
        )

        # Check for substantive response
        has_approach = any(term in response_lower for term in [
            "modify", "change", "fix", "update", "add", "remove",
            "function", "method", "class", "variable",
        ])

        # Simple heuristic: success if files mentioned and has approach
        return files_mentioned > 0 and has_approach and len(response) > 200


# =============================================================================
# Evaluation
# =============================================================================

def run_sequence_evaluation(
    agent: BaseAgent,
    agent_name: str,
    sequence: SWESequence,
    verbose: bool = True,
) -> SequenceResult:
    """Run evaluation on a single sequence."""
    wrapper = LongHorizonAgentWrapper(agent, agent_name)
    wrapper.start_sequence(sequence)

    task_results = []
    total_tokens = 0

    start_time = time.time()

    iterator = enumerate(sequence.tasks)
    if verbose:
        iterator = tqdm(list(iterator), desc=f"{agent_name} on {sequence.sequence_id}")

    for i, task in iterator:
        result = wrapper.process_task(task, i)
        task_results.append(result)
        total_tokens += result.input_tokens + result.output_tokens

    total_time = time.time() - start_time

    # Calculate metrics
    success_rate = sum(1 for r in task_results if r.success) / len(task_results) if task_results else 0

    # Forward transfer: compare first half vs second half performance
    mid = len(task_results) // 2
    first_half_success = sum(1 for r in task_results[:mid] if r.success) / mid if mid > 0 else 0
    second_half_success = sum(1 for r in task_results[mid:] if r.success) / (len(task_results) - mid) if len(task_results) > mid else 0
    forward_transfer = second_half_success - first_half_success

    # Test retention
    retention_score = wrapper.test_retention()

    return SequenceResult(
        sequence_id=sequence.sequence_id,
        agent_name=agent_name,
        task_results=task_results,
        success_rate=success_rate * 100,
        forward_transfer=forward_transfer * 100,
        avg_tokens=total_tokens / len(task_results) if task_results else 0,
        total_time=total_time,
        retention_score=retention_score * 100,
    )


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="SWE-Bench-CL evaluation for ECM")

    parser.add_argument("--agents", nargs="+", default=["ecm", "longcontext"],
                        help="Agents to evaluate")
    parser.add_argument("--sequence", default=None, help="Specific sequence ID to run")
    parser.add_argument("--all-sequences", action="store_true", help="Run all sequences")
    parser.add_argument("--max-sequences", type=int, default=3, help="Max sequences to run")
    parser.add_argument("--max-tasks", type=int, default=20, help="Max tasks per sequence")
    parser.add_argument("--data-dir", default=None, help="Directory with sequence data")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model to use")
    parser.add_argument("--output-dir", default="benchmarks/results/swe_cl", help="Output directory")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    # Load sequences
    print("Loading SWE-Bench-CL sequences...")
    sequences = load_swe_bench_cl_sequences(
        data_dir=args.data_dir,
        max_sequences=args.max_sequences,
        max_tasks_per_sequence=args.max_tasks,
    )

    if args.sequence:
        sequences = [s for s in sequences if s.sequence_id == args.sequence]
        if not sequences:
            print(f"Error: Sequence '{args.sequence}' not found")
            sys.exit(1)

    print(f"Loaded {len(sequences)} sequences")
    for seq in sequences:
        print(f"  - {seq.sequence_id}: {seq.total_tasks} tasks ({seq.repo})")

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize agents
    agents = {}
    for agent_key in args.agents:
        if agent_key not in AVAILABLE_AGENTS:
            print(f"Warning: Unknown agent '{agent_key}', skipping")
            continue
        info = AVAILABLE_AGENTS[agent_key]
        if agent_key == "ecm":
            agents[info["name"]] = info["class"](model=args.model)
        else:
            agents[info["name"]] = info["class"](model=args.model)

    # Run evaluations
    all_results = []

    for sequence in sequences:
        print(f"\n{'='*60}")
        print(f"Sequence: {sequence.sequence_id}")
        print(f"Repository: {sequence.repo}")
        print(f"Tasks: {sequence.total_tasks}")
        print(f"{'='*60}")

        for name, agent in agents.items():
            print(f"\nEvaluating: {name}")
            result = run_sequence_evaluation(
                agent, name, sequence,
                verbose=not args.quiet
            )
            all_results.append(result)
            agent.reset()

            # Print result
            print(f"\n{name} Results:")
            print(f"  Success Rate: {result.success_rate:.1f}%")
            print(f"  Forward Transfer: {result.forward_transfer:+.1f}%")
            print(f"  Retention Score: {result.retention_score:.1f}%")
            print(f"  Avg Tokens: {result.avg_tokens:.0f}")
            print(f"  Total Time: {result.total_time:.1f}s")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = output_dir / f"swe_cl_results_{timestamp}.json"

    results_data = {
        "timestamp": timestamp,
        "config": {
            "agents": args.agents,
            "max_tasks": args.max_tasks,
            "model": args.model,
        },
        "results": [
            {
                "sequence_id": r.sequence_id,
                "agent_name": r.agent_name,
                "success_rate": r.success_rate,
                "forward_transfer": r.forward_transfer,
                "retention_score": r.retention_score,
                "avg_tokens": r.avg_tokens,
                "total_time": r.total_time,
                "num_tasks": len(r.task_results),
            }
            for r in all_results
        ],
    }

    with open(results_path, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\nSaved results: {results_path}")

    # Print summary table
    print(f"\n{'='*70}")
    print("Summary: SWE-Bench-CL Results")
    print(f"{'='*70}")
    print(f"{'Agent':<15} {'Sequence':<20} {'Success%':>10} {'Transfer':>10} {'Retention':>10}")
    print("-" * 70)
    for r in all_results:
        print(f"{r.agent_name:<15} {r.sequence_id:<20} {r.success_rate:>9.1f}% {r.forward_transfer:>+9.1f}% {r.retention_score:>9.1f}%")


if __name__ == "__main__":
    main()
