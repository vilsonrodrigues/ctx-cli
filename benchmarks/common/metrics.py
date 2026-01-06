"""
Metrics and Scoring Utilities for ECM Benchmarks.

Provides evaluation metrics commonly used in memory and QA benchmarks:
- Exact Match: Strict string equality (case-insensitive, normalized)
- Contains Match: Whether the answer contains the expected value
- F1 Score: Token-level F1 between prediction and ground truth
"""

import re
from typing import Union


def normalize_answer(answer: str) -> str:
    """
    Normalize answer for comparison.

    Performs:
    - Lowercase conversion
    - Whitespace normalization
    - Punctuation removal
    - Article removal (a, an, the)

    Args:
        answer: The answer string to normalize

    Returns:
        Normalized answer string
    """
    # Lowercase
    answer = answer.lower()

    # Remove punctuation
    answer = re.sub(r'[^\w\s]', ' ', answer)

    # Remove articles
    answer = re.sub(r'\b(a|an|the)\b', ' ', answer)

    # Normalize whitespace
    answer = ' '.join(answer.split())

    return answer.strip()


def compute_exact_match(prediction: str, ground_truth: Union[str, list[str]]) -> float:
    """
    Compute exact match score.

    Args:
        prediction: Model's predicted answer
        ground_truth: Expected answer(s) - can be string or list of acceptable answers

    Returns:
        1.0 if exact match, 0.0 otherwise
    """
    pred_normalized = normalize_answer(prediction)

    # Handle list of acceptable answers
    if isinstance(ground_truth, list):
        for gt in ground_truth:
            if normalize_answer(gt) == pred_normalized:
                return 1.0
        return 0.0

    return 1.0 if normalize_answer(ground_truth) == pred_normalized else 0.0


def compute_contains_match(prediction: str, ground_truth: Union[str, list[str]]) -> float:
    """
    Compute contains match score.

    Checks if the prediction contains the ground truth answer.

    Args:
        prediction: Model's predicted answer
        ground_truth: Expected answer(s) - can be string or list of acceptable answers

    Returns:
        1.0 if contains match, 0.0 otherwise
    """
    pred_normalized = normalize_answer(prediction)

    # Handle list of acceptable answers
    if isinstance(ground_truth, list):
        for gt in ground_truth:
            if normalize_answer(gt) in pred_normalized:
                return 1.0
        return 0.0

    return 1.0 if normalize_answer(ground_truth) in pred_normalized else 0.0


def compute_f1(prediction: str, ground_truth: Union[str, list[str]]) -> float:
    """
    Compute token-level F1 score.

    Calculates precision and recall based on token overlap.

    Args:
        prediction: Model's predicted answer
        ground_truth: Expected answer(s) - can be string or list of acceptable answers

    Returns:
        F1 score between 0.0 and 100.0
    """
    pred_tokens = set(normalize_answer(prediction).split())

    # Handle list of acceptable answers - take max F1
    if isinstance(ground_truth, list):
        return max(
            _compute_f1_single(pred_tokens, normalize_answer(gt).split())
            for gt in ground_truth
        )

    gt_tokens = normalize_answer(ground_truth).split()
    return _compute_f1_single(pred_tokens, gt_tokens)


def _compute_f1_single(pred_tokens: set, gt_tokens: list) -> float:
    """Compute F1 for a single prediction-groundtruth pair."""
    gt_set = set(gt_tokens)

    if len(pred_tokens) == 0 or len(gt_set) == 0:
        return 0.0

    common = pred_tokens & gt_set
    num_common = len(common)

    if num_common == 0:
        return 0.0

    precision = num_common / len(pred_tokens)
    recall = num_common / len(gt_set)

    f1 = (2 * precision * recall) / (precision + recall)
    return f1 * 100  # Return as percentage


# =============================================================================
# Aggregate Metrics
# =============================================================================

def compute_aggregate_metrics(
    predictions: list[str],
    ground_truths: list[Union[str, list[str]]],
) -> dict:
    """
    Compute aggregate metrics over a list of predictions.

    Args:
        predictions: List of model predictions
        ground_truths: List of expected answers

    Returns:
        dict with exact_match, contains_match, f1_score (all as percentages)
    """
    assert len(predictions) == len(ground_truths), "Mismatched lengths"

    n = len(predictions)
    if n == 0:
        return {"exact_match": 0.0, "contains_match": 0.0, "f1_score": 0.0}

    exact_matches = sum(
        compute_exact_match(pred, gt)
        for pred, gt in zip(predictions, ground_truths)
    )
    contains_matches = sum(
        compute_contains_match(pred, gt)
        for pred, gt in zip(predictions, ground_truths)
    )
    f1_scores = sum(
        compute_f1(pred, gt)
        for pred, gt in zip(predictions, ground_truths)
    )

    return {
        "exact_match": (exact_matches / n) * 100,
        "contains_match": (contains_matches / n) * 100,
        "f1_score": f1_scores / n,
    }
