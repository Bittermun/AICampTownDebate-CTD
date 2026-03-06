"""Judge variance analysis helpers."""
from dataclasses import dataclass
import statistics
from typing import Dict, List, Optional

from ..models.judge import BaseJudge


@dataclass
class JudgeVarianceResult:
    runs: int
    mean_confidence_a: float
    stdev_confidence_a: float
    synthesis_pass: bool  # True if mean_a >= min_mean_a (or min_mean_a disabled)
    variance_pass: bool   # True if stdev_a <= max_stdev (always checked)
    min_mean_a_used: Optional[float]  # None = synthesis gate disabled
    confidences_a: List[float]

    @property
    def passed(self) -> bool:
        return self.synthesis_pass and self.variance_pass

    def to_dict(self) -> Dict:
        return {
            "runs": self.runs,
            "mean_confidence_a": self.mean_confidence_a,
            "stdev_confidence_a": self.stdev_confidence_a,
            "synthesis_pass": self.synthesis_pass,
            "variance_pass": self.variance_pass,
            "passed": self.passed,
            "confidences_a": self.confidences_a,
            "min_mean_a_used": self.min_mean_a_used,
        }


def evaluate_judge_variance(
    judge: BaseJudge,
    topic: str,
    argument_a: str,
    argument_b: str,
    runs: int = 10,
    max_stdev: float = 0.05,
    min_mean_a: Optional[float] = None,
    round_id: int = 1,
) -> JudgeVarianceResult:
    """Evaluate judge consistency by scoring the same arguments repeatedly.

    Args:
        max_stdev: Maximum allowed standard deviation (always enforced).
        min_mean_a: Optional minimum mean score for Argument A. When None
            (default) the synthesis gate is disabled — use only when you have
            a deliberately stronger Argument A as a calibration probe.
    """
    if runs < 2:
        raise ValueError("runs must be >= 2")

    confidences_a: list[float] = []
    for _ in range(runs):
        judgment = judge.evaluate(
            topic=topic,
            argument_a=argument_a,
            argument_b=argument_b,
            round_id=round_id,
        )
        confidences_a.append(judgment.confidence_a)

    mean_a = statistics.mean(confidences_a)
    stdev_a = statistics.stdev(confidences_a)

    synthesis_pass = (min_mean_a is None) or (mean_a >= min_mean_a)

    return JudgeVarianceResult(
        runs=runs,
        mean_confidence_a=mean_a,
        stdev_confidence_a=stdev_a,
        synthesis_pass=synthesis_pass,
        variance_pass=stdev_a <= max_stdev,
        min_mean_a_used=min_mean_a,
        confidences_a=confidences_a,
    )
