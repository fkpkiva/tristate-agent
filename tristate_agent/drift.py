"""
drift.py — Phi-decay weighted drift scoring.
S step of the SWORD pipeline.
Orchestrator uses this to detect topic shifts.
"""

import math
from typing import List, Optional

PHI = 1.6180339887  # golden ratio


def cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two embedding vectors."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def phi_decay_drift_score(
    recent_embeddings: List[list],
    anchor_embedding: list,
    decay_rate: float = PHI,
) -> float:
    """
    Compute phi-decay weighted drift score.

    More recent turns have higher weight.
    drift_score = sum( (1/phi)^i * cosine_distance(turn_i, anchor) )
    where i=0 is most recent.

    Returns a float in [0, 1]. Higher = more drift from anchor topic.
    """
    if not recent_embeddings or not anchor_embedding:
        return 0.0

    total_weight = 0.0
    weighted_distance = 0.0

    for i, emb in enumerate(reversed(recent_embeddings)):
        weight = (1.0 / decay_rate) ** i
        similarity = cosine_similarity(emb, anchor_embedding)
        distance = 1.0 - similarity
        weighted_distance += weight * distance
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return weighted_distance / total_weight


def compute_drift(
    new_embedding: list,
    anchor_embedding: list,
    recent_embeddings: Optional[List[list]] = None,
    decay_rate: float = PHI,
) -> float:
    """
    Compute drift score for a new message.
    Includes the new embedding in the recent window.
    """
    window = list(recent_embeddings or [])
    window.append(new_embedding)
    return phi_decay_drift_score(window, anchor_embedding, decay_rate)
