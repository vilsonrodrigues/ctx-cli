"""
Dataset Loaders for ECM Benchmarks.

Provides utilities to load and preprocess benchmark datasets:
- MemoryAgentBench: Memory-based QA benchmark
- Future: LoCoMo, LongMemEval, etc.
"""

import re
from typing import Optional
from dataclasses import dataclass, field


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class BenchmarkSample:
    """A single benchmark sample with context chunks, questions, and answers."""
    context_id: int
    chunks: list[str]
    questions: list[str]
    answers: list[str]  # Each answer can be a single string or list of acceptable answers
    metadata: dict = field(default_factory=dict)


@dataclass
class BenchmarkDataset:
    """A complete benchmark dataset."""
    name: str
    split: str
    samples: list[BenchmarkSample]
    total_chunks: int = 0
    total_questions: int = 0


# =============================================================================
# MemoryAgentBench
# =============================================================================

MEMORYAGENTBENCH_SPLITS = {
    "AR": "Accurate_Retrieval",
    "TTL": "Test_Time_Learning",
    "LRU": "Long_Range_Understanding",
    "CR": "Conflict_Resolution",
}


def chunk_context(
    context: str,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> list[str]:
    """
    Split context into chunks.

    First tries to split by paragraphs/sections, then falls back to
    character-based chunking for very long paragraphs.

    Args:
        context: The context text to chunk
        chunk_size: Target size for each chunk (in characters)
        overlap: Overlap between chunks (in characters)

    Returns:
        List of context chunks
    """
    # Try splitting by double newlines first (paragraphs)
    paragraphs = re.split(r'\n\n+', context)

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If paragraph itself is too long, split it
        if len(para) > chunk_size * 2:
            # Split long paragraph into smaller pieces
            words = para.split()
            temp_chunk = ""
            for word in words:
                if len(temp_chunk) + len(word) + 1 > chunk_size:
                    if temp_chunk:
                        chunks.append(temp_chunk.strip())
                    temp_chunk = word
                else:
                    temp_chunk = f"{temp_chunk} {word}" if temp_chunk else word
            if temp_chunk:
                if len(current_chunk) + len(temp_chunk) < chunk_size:
                    current_chunk = f"{current_chunk}\n\n{temp_chunk}" if current_chunk else temp_chunk
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = temp_chunk
        else:
            # Normal paragraph
            if len(current_chunk) + len(para) + 2 > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def load_memoryagentbench(
    split: str = "AR",
    max_contexts: int = 10,
    max_queries_per_context: int = 10,
    max_chunks_per_context: int = 50,
    chunk_size: int = 1000,
) -> BenchmarkDataset:
    """
    Load MemoryAgentBench dataset from HuggingFace.

    The dataset has 4 splits:
    - AR: Accurate_Retrieval (22 samples) - Tests precise fact retrieval
    - TTL: Test_Time_Learning (6 samples) - Tests learning during inference
    - LRU: Long_Range_Understanding (110 samples) - Tests understanding across long contexts
    - CR: Conflict_Resolution (8 samples) - Tests handling conflicting information

    Args:
        split: Dataset split (AR, TTL, LRU, CR)
        max_contexts: Maximum number of contexts to load
        max_queries_per_context: Maximum queries per context
        max_chunks_per_context: Maximum chunks per context (0 = unlimited)
        chunk_size: Target chunk size in characters

    Returns:
        BenchmarkDataset with loaded samples
    """
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError("Please install datasets: pip install datasets")

    # Map short name to full split name
    split_name = MEMORYAGENTBENCH_SPLITS.get(split, split)

    print(f"Loading MemoryAgentBench/{split_name}...")
    ds = load_dataset("WeiminXiong/MemoryAgentBench", split=split_name)

    samples = []
    total_chunks = 0
    total_questions = 0

    for idx, item in enumerate(ds):
        if idx >= max_contexts:
            break

        context = item.get("context", "") or item.get("document", "")
        questions = item.get("questions", [])
        answers = item.get("answers", [])
        metadata = item.get("metadata", {})

        if not context or not questions:
            continue

        # Limit questions per context
        if max_queries_per_context > 0 and len(questions) > max_queries_per_context:
            questions = questions[:max_queries_per_context]
            answers = answers[:max_queries_per_context]

        # Chunk the context
        chunks = chunk_context(context, chunk_size=chunk_size)

        # Limit chunks if specified
        if max_chunks_per_context > 0 and len(chunks) > max_chunks_per_context:
            chunks = chunks[:max_chunks_per_context]

        # Normalize answers (they can be lists)
        normalized_answers = []
        for a in answers:
            if isinstance(a, list):
                normalized_answers.append(a[0] if a else "")
            else:
                normalized_answers.append(a)

        sample = BenchmarkSample(
            context_id=idx,
            chunks=chunks,
            questions=questions,
            answers=normalized_answers,
            metadata=metadata if isinstance(metadata, dict) else {},
        )
        samples.append(sample)

        total_chunks += len(chunks)
        total_questions += len(questions)

    print(f"Loaded {len(samples)} contexts, {total_chunks} chunks, {total_questions} questions")

    return BenchmarkDataset(
        name="MemoryAgentBench",
        split=split,
        samples=samples,
        total_chunks=total_chunks,
        total_questions=total_questions,
    )


# =============================================================================
# Long-Horizon Dataset Loaders (Stubs)
# =============================================================================

def load_swe_bench_cl(
    max_sequences: int = 10,
    max_tasks_per_sequence: int = 50,
) -> BenchmarkDataset:
    """
    Load SWE-Bench-CL (Continual Learning) dataset.

    SWE-Bench-CL contains sequences of related code tasks that test
    an agent's ability to maintain context across multiple code changes.

    NOTE: This is a stub - full implementation requires SWE-Bench setup.
    """
    raise NotImplementedError(
        "SWE-Bench-CL loader not yet implemented. "
        "Use benchmarks/longhorizon/run_swe_bench_cl.py for full evaluation."
    )


def load_appworld(
    max_tasks: int = 10,
) -> BenchmarkDataset:
    """
    Load AppWorld benchmark dataset.

    AppWorld tests agents on multi-step tasks across 9 different apps
    with realistic state and dependencies.

    NOTE: This is a stub - full implementation requires AppWorld setup.
    """
    raise NotImplementedError(
        "AppWorld loader not yet implemented. "
        "Use benchmarks/longhorizon/run_appworld.py for full evaluation."
    )


def load_agentcompany(
    max_tasks: int = 10,
) -> BenchmarkDataset:
    """
    Load TheAgentCompany benchmark dataset.

    TheAgentCompany simulates realistic work environments with
    complex multi-step tasks.

    NOTE: This is a stub - full implementation requires TheAgentCompany setup.
    """
    raise NotImplementedError(
        "TheAgentCompany loader not yet implemented. "
        "Use benchmarks/longhorizon/run_agentcompany.py for full evaluation."
    )
