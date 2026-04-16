"""United Agents — Condition scorer (deterministic).

Per ALGORITHMS.md §2. Currently dormant — LLM-judge prompt used instead.
Preserved per GOTCHAS §4.4 with config flag; default = LLM judgement.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger("heartbeat.sources.scorer")


def calculate(
    current_values: dict,
    baseline: dict,
    previous_score: Optional[float] = None,
) -> Tuple[float, str]:
    """Returns (score 0-100, trend: 'improving'|'stable'|'declining'|'critical').

    baseline config shape:
    {
      "<param_name>": {
          "value": <float>,           # known-healthy reference value
          "weight": <float>,          # importance for composite score
          "direction": "deviation_bad" | "high_bad" | "low_bad",
      },
    }
    """
    if not baseline or not current_values:
        return 50.0, "stable"

    total_weight = 0.0
    weighted_score = 0.0

    for param, cfg in baseline.items():
        if param not in current_values:
            continue

        current = current_values[param]
        if not isinstance(current, (int, float)):
            continue

        ref = cfg.get("value", 0)
        weight = cfg.get("weight", 1.0)
        direction = cfg.get("direction", "deviation_bad")

        if abs(ref) < 1e-10:
            # Avoid division by zero
            deviation = abs(current) if abs(current) > 0.01 else 0.0
        else:
            if direction == "deviation_bad":
                deviation = abs(current - ref) / abs(ref)
            elif direction == "high_bad":
                deviation = max(0.0, (current - ref) / abs(ref))
            elif direction == "low_bad":
                deviation = max(0.0, (ref - current) / abs(ref))
            else:
                deviation = abs(current - ref) / abs(ref)

        param_score = max(0.0, min(100.0, 100.0 * (1.0 - deviation)))
        weighted_score += param_score * weight
        total_weight += weight

    if total_weight == 0:
        score = 50.0
    else:
        score = weighted_score / total_weight

    score = max(0.0, min(100.0, score))

    # Trend classification
    if score <= 10:
        trend = "critical"
    elif previous_score is not None:
        delta = score - previous_score
        if delta > 5:
            trend = "improving"
        elif delta < -5:
            trend = "declining"
        else:
            trend = "stable"
    else:
        if score >= 70:
            trend = "stable"
        elif score >= 40:
            trend = "declining"
        else:
            trend = "critical"

    return round(score, 1), trend
