"""Judge variance analysis helpers."""
from dataclasses import dataclass
import statistics
from typing import Dict, List

from ..models.judge import BaseJudge


@dataclass
class JudgeVarianceResult:
    runs: int
    mean_confidence_a: float
    stdev_confidence_a: float
    synthesis_pass: bool
    variance_pass: bool
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
        }


def evaluate_judge_variance(
    judge: BaseJudge,
    topic: str,
    argument_a: str,
    argument_b: str,
    runs: int = 10,
    max_stdev: float = 0.05,
    min_mean_a: float = 0.55,
    round_id: int = 1,
) -> JudgeVarianceResult:
    """Evaluate variance by scoring the same arguments repeatedly."""
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

    return JudgeVarianceResult(
        runs=runs,
        mean_confidence_a=mean_a,
        stdev_confidence_a=stdev_a,
        synthesis_pass=mean_a >= min_mean_a,
        variance_pass=stdev_a <= max_stdev,
        confidences_a=confidences_a,
    )
