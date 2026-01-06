"""
MemoryBench Adapter for ECM Evaluation.

MemoryBench: Comprehensive benchmark for memory and continual learning in LLMs.
- 11 diverse datasets
- Declarative + Procedural memory
- User feedback simulation

Paper: https://arxiv.org/abs/2410.xxxxx
"""

import os
import sys
import json
import time
from dataclasses import dataclass
from typing import Optional, Iterator
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from metrics import (
    MetricsCollector, 
    TaskTokenRecord, 
    CumulativeTokenReport,
    count_context_tokens,
)
from benchmarks.configs.benchmark_sizes import get_config, BenchmarkConfig


@dataclass
class MemoryBenchSample:
    """A single MemoryBench sample."""
    sample_id: str
    dataset: str
    feedback_type: str  # "declarative" or "procedural"
    context: str
    query: str
    expected_answer: str
    user_feedback: Optional[str] = None


class MemoryBenchAdapter:
    """
    Adapter for MemoryBench benchmark.
    
    Evaluates:
    - Declarative memory (facts, preferences)
    - Procedural memory (workflows, rules)
    - Learning from user feedback
    """
    
    DATASETS = [
        "personachat",
        "wizard_of_wikipedia", 
        "empathetic_dialogues",
        "daily_dialog",
        "convai2",
        "blended_skill_talk",
        "multiwoz",
        "taskmaster",
        "schema_guided",
        "meta_woz",
        "simulated_feedback",
    ]
    
    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or get_config("memorybench", "mini")
        self.samples: list[MemoryBenchSample] = []
        
    def load_dataset(self) -> list[MemoryBenchSample]:
        """
        Load MemoryBench samples.
        
        For now, generates synthetic samples matching MemoryBench format.
        TODO: Integrate with HuggingFace datasets when available.
        """
        samples = []
        datasets_to_use = self.DATASETS[:self.config.datasets_count]
        samples_per_dataset = self.config.max_samples // len(datasets_to_use)
        
        for dataset in datasets_to_use:
            for i in range(samples_per_dataset):
                # Generate synthetic samples matching MemoryBench format
                sample = self._generate_synthetic_sample(dataset, i)
                samples.append(sample)
                
        self.samples = samples
        return samples
    
    def _generate_synthetic_sample(self, dataset: str, idx: int) -> MemoryBenchSample:
        """Generate a synthetic sample for testing the harness."""
        feedback_type = "declarative" if idx % 2 == 0 else "procedural"
        
        if feedback_type == "declarative":
            context = f"User previously mentioned they prefer {dataset}_preference_{idx}."
            query = f"What preference did the user mention about {dataset}?"
            expected = f"{dataset}_preference_{idx}"
            feedback = f"Remember: I prefer {dataset}_preference_{idx}"
        else:
            context = f"User taught the system: When asked about {dataset}, respond with rule_{idx}."
            query = f"Apply the learned rule for {dataset}."
            expected = f"rule_{idx}"
            feedback = f"When asked about {dataset}, always respond with rule_{idx}"
            
        return MemoryBenchSample(
            sample_id=f"{dataset}_{idx}",
            dataset=dataset,
            feedback_type=feedback_type,
            context=context,
            query=query,
            expected_answer=expected,
            user_feedback=feedback,
        )
    
    def iterate_samples(self) -> Iterator[MemoryBenchSample]:
        """Iterate over loaded samples."""
        for sample in self.samples:
            yield sample
    
    def run_with_tracking(
        self,
        agent,
        collector: MetricsCollector,
    ) -> CumulativeTokenReport:
        """
        Run benchmark with per-task token tracking.
        
        Args:
            agent: Agent with send_message() interface
            collector: MetricsCollector for detailed tracking
            
        Returns:
            CumulativeTokenReport with per-task I/O data
        """
        report = CumulativeTokenReport(
            agent_type=collector.metrics.agent_type,
            model=collector.metrics.model,
            benchmark="memorybench",
        )
        
        if not self.samples:
            self.load_dataset()
        
        collector.set_total_tasks(len(self.samples))
        
        for i, sample in enumerate(self.samples):
            task_start = time.time()
            context_start = collector.token_tracker.current_context_tokens
            input_tokens = 0
            output_tokens = 0
            api_calls = 0
            
            # Phase 1: Learn from feedback
            if sample.user_feedback:
                result = agent.send_message(sample.user_feedback, memorizing=True)
                input_tokens += result.get("input_len", 0) if isinstance(result, dict) else 0
                output_tokens += result.get("output_len", 0) if isinstance(result, dict) else 0
                api_calls += 1
            
            # Phase 2: Query
            result = agent.send_message(sample.query, memorizing=False)
            input_tokens += result.get("input_len", 0)
            output_tokens += result.get("output_len", 0)
            api_calls += 1
            
            # Evaluate
            answer = result.get("output", "")
            success = sample.expected_answer.lower() in answer.lower()
            
            # Record task
            context_end = collector.token_tracker.current_context_tokens
            record = TaskTokenRecord(
                task_id=sample.sample_id,
                task_name=f"{sample.dataset}:{sample.feedback_type}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                context_at_start=context_start,
                context_at_end=context_end,
                api_calls=api_calls,
                execution_time_seconds=time.time() - task_start,
                success=success,
            )
            report.add_task(record)
            collector.record_task_completed()
            
        return report


class LTMBenchmarkAdapter:
    """
    Adapter for GoodAI LTM Benchmark.
    
    Tests long-term memory in extended conversations.
    Paper: https://github.com/GoodAI/LTMBench
    """
    
    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or get_config("ltm_benchmark", "mini")
        self.sessions: list[dict] = []
        
    def load_dataset(self) -> list[dict]:
        """Load LTM benchmark sessions."""
        sessions = []
        
        for i in range(self.config.max_sessions):
            session = self._generate_synthetic_session(i)
            sessions.append(session)
            
        self.sessions = sessions
        return sessions
    
    def _generate_synthetic_session(self, idx: int) -> dict:
        """Generate synthetic session for testing."""
        num_turns = 10 + (idx % 5) * 5  # 10-30 turns
        
        turns = []
        facts = []
        
        for t in range(num_turns):
            if t % 3 == 0:
                # Information sharing turn
                fact = f"fact_{idx}_{t}"
                facts.append(fact)
                turns.append({
                    "role": "user",
                    "content": f"Remember that {fact} is important.",
                    "type": "information",
                })
            else:
                # Regular conversation
                turns.append({
                    "role": "user", 
                    "content": f"Let's discuss topic {t}.",
                    "type": "conversation",
                })
        
        # Add recall questions
        for fact in facts[:3]:  # Test first 3 facts
            turns.append({
                "role": "user",
                "content": f"What did I tell you about {fact}?",
                "type": "recall",
                "expected": fact,
            })
            
        return {
            "session_id": f"session_{idx}",
            "turns": turns,
            "num_facts": len(facts),
        }
    
    def run_with_tracking(
        self,
        agent,
        collector: MetricsCollector,
    ) -> CumulativeTokenReport:
        """Run LTM benchmark with token tracking."""
        report = CumulativeTokenReport(
            agent_type=collector.metrics.agent_type,
            model=collector.metrics.model,
            benchmark="ltm_benchmark",
        )
        
        if not self.sessions:
            self.load_dataset()
            
        collector.set_total_tasks(len(self.sessions))
        
        for session in self.sessions:
            task_start = time.time()
            context_start = collector.token_tracker.current_context_tokens
            input_tokens = 0
            output_tokens = 0
            api_calls = 0
            recall_correct = 0
            recall_total = 0
            
            for turn in session["turns"]:
                if turn["type"] == "information":
                    result = agent.send_message(turn["content"], memorizing=True)
                else:
                    result = agent.send_message(turn["content"], memorizing=False)
                    
                if isinstance(result, dict):
                    input_tokens += result.get("input_len", 0)
                    output_tokens += result.get("output_len", 0)
                api_calls += 1
                
                if turn["type"] == "recall":
                    recall_total += 1
                    answer = result.get("output", "") if isinstance(result, dict) else ""
                    if turn["expected"].lower() in answer.lower():
                        recall_correct += 1
            
            success = (recall_correct / max(recall_total, 1)) >= 0.5
            
            record = TaskTokenRecord(
                task_id=session["session_id"],
                task_name=f"ltm_session_{session['num_facts']}_facts",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                context_at_start=context_start,
                context_at_end=collector.token_tracker.current_context_tokens,
                api_calls=api_calls,
                execution_time_seconds=time.time() - task_start,
                success=success,
            )
            report.add_task(record)
            collector.record_task_completed()
            
        return report


class LifelongAgentBenchAdapter:
    """
    Adapter for LifelongAgentBench.
    
    Tests lifelong learning with interdependent tasks across:
    - Databases (DB)
    - Operating Systems (OS)  
    - Knowledge Graphs (KG)
    
    Paper: https://github.com/LifelongAgentBench
    """
    
    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or get_config("lifelong_agent_bench", "mini")
        self.tasks: list[dict] = []
        
    def load_dataset(self) -> list[dict]:
        """Load LifelongAgentBench tasks."""
        tasks = []
        environments = self.config.environments or ["db"]
        tasks_per_env = self.config.max_tasks // len(environments)
        
        for env in environments:
            for i in range(tasks_per_env):
                task = self._generate_synthetic_task(env, i)
                tasks.append(task)
                
        self.tasks = tasks
        return tasks
    
    def _generate_synthetic_task(self, env: str, idx: int) -> dict:
        """Generate synthetic task for testing."""
        if env == "db":
            return {
                "task_id": f"db_task_{idx}",
                "environment": "db",
                "skill": f"sql_query_type_{idx % 5}",
                "instruction": f"Execute SQL query pattern {idx % 5} on table users.",
                "dependencies": [f"db_task_{max(0, idx-1)}"] if idx > 0 else [],
                "expected_skill_reuse": idx > 0,
            }
        elif env == "os":
            return {
                "task_id": f"os_task_{idx}",
                "environment": "os", 
                "skill": f"file_operation_{idx % 3}",
                "instruction": f"Perform file operation type {idx % 3}.",
                "dependencies": [],
                "expected_skill_reuse": idx > 0,
            }
        else:  # kg
            return {
                "task_id": f"kg_task_{idx}",
                "environment": "kg",
                "skill": f"graph_query_{idx % 4}",
                "instruction": f"Query knowledge graph with pattern {idx % 4}.",
                "dependencies": [],
                "expected_skill_reuse": idx > 0,
            }
    
    def run_with_tracking(
        self,
        agent,
        collector: MetricsCollector,
    ) -> CumulativeTokenReport:
        """Run LifelongAgentBench with token tracking."""
        report = CumulativeTokenReport(
            agent_type=collector.metrics.agent_type,
            model=collector.metrics.model,
            benchmark="lifelong_agent_bench",
        )
        
        if not self.tasks:
            self.load_dataset()
            
        collector.set_total_tasks(len(self.tasks))
        learned_skills: set[str] = set()
        
        for task in self.tasks:
            task_start = time.time()
            context_start = collector.token_tracker.current_context_tokens
            
            # Build instruction with skill context
            instruction = task["instruction"]
            if task["skill"] in learned_skills:
                instruction = f"[Reuse skill: {task['skill']}] " + instruction
            
            result = agent.send_message(instruction, memorizing=False)
            
            input_tokens = result.get("input_len", 0)
            output_tokens = result.get("output_len", 0)
            
            # Mark skill as learned
            learned_skills.add(task["skill"])
            
            # Determine success (simplified)
            success = True  # Would need actual execution in real benchmark
            
            record = TaskTokenRecord(
                task_id=task["task_id"],
                task_name=f"{task['environment']}:{task['skill']}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                context_at_start=context_start,
                context_at_end=collector.token_tracker.current_context_tokens,
                api_calls=1,
                execution_time_seconds=time.time() - task_start,
                success=success,
            )
            report.add_task(record)
            collector.record_task_completed()
            
        return report
