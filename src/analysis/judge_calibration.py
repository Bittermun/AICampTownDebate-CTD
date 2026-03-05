"""Judge calibration utilities using fixed benchmark cases."""
from dataclasses import dataclass
from typing import Dict, List, Literal

from ..models.judge import BaseJudge


@dataclass
class CalibrationCase:
    topic: str
    argument_a: str
    argument_b: str
    expected_winner: Literal["A", "B"]
    min_margin: float = 0.01


@dataclass
class JudgeCalibrationResult:
    total_cases: int
    passed_cases: int
    pass_rate: float
    pass_threshold: float
    case_results: List[Dict]

    @property
    def passed(self) -> bool:
        return self.pass_rate >= self.pass_threshold

    def to_dict(self) -> Dict:
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "pass_rate": self.pass_rate,
            "pass_threshold": self.pass_threshold,
            "passed": self.passed,
            "case_results": self.case_results,
        }


DEFAULT_CALIBRATION_CASES: List[CalibrationCase] = [
    CalibrationCase(
        topic="Should schools require students to wear helmets in class to reduce injury risk?",
        argument_a=(
            "No. Classrooms are low-risk settings, and universal helmet rules add cost and discomfort "
            "without meaningful safety gain. Focus on targeted protections in actual high-risk activities."
        ),
        argument_b=(
            "Yes because everything is dangerous. Helmets should be mandatory everywhere always. "
            "There is no downside and no need for evidence."
        ),
        expected_winner="A",
    ),
    CalibrationCase(
        topic="Should a city replace all traffic lights with AI-controlled adaptive signals?",
        argument_a=(
            "Yes, but only with phased rollout, fail-safe fallback, and independent audits. "
            "Adaptive control can reduce congestion if reliability and safety controls are explicit."
        ),
        argument_b=(
            "No system should ever change because old methods are tradition. "
            "Any AI is automatically unsafe regardless of safeguards."
        ),
        expected_winner="A",
    ),
    CalibrationCase(
        topic="Should hospitals share patient data publicly to speed research?",
        argument_a=(
            "Yes, publish all raw records with names and addresses. Privacy concerns are exaggerated "
            "and consent is unnecessary if research might be useful."
        ),
        argument_b=(
            "No to public raw release. Use consented, de-identified, governed data-sharing pipelines "
            "so research advances without violating patient privacy."
        ),
        expected_winner="B",
    ),
]


def evaluate_judge_calibration(
    judge: BaseJudge,
    cases: List[CalibrationCase] | None = None,
    pass_threshold: float = 0.67,
    round_id: int = 1,
) -> JudgeCalibrationResult:
    """Evaluate if judge decisions match expected winners on fixed benchmark cases."""
    cases = cases or DEFAULT_CALIBRATION_CASES
    case_results: List[Dict] = []
    passed = 0

    for idx, c in enumerate(cases, start=1):
        judgment = judge.evaluate(
            topic=c.topic,
            argument_a=c.argument_a,
            argument_b=c.argument_b,
            round_id=round_id + idx,
        )
        margin = judgment.confidence_a - judgment.confidence_b
        predicted = "A" if margin >= 0 else "B"
        pass_case = predicted == c.expected_winner and abs(margin) >= c.min_margin
        if pass_case:
            passed += 1
        case_results.append(
            {
                "index": idx,
                "expected_winner": c.expected_winner,
                "predicted_winner": predicted,
                "confidence_a": judgment.confidence_a,
                "confidence_b": judgment.confidence_b,
                "margin": margin,
                "min_margin": c.min_margin,
                "passed": pass_case,
            }
        )

    total = len(cases)
    pass_rate = (passed / total) if total else 0.0
    return JudgeCalibrationResult(
        total_cases=total,
        passed_cases=passed,
        pass_rate=pass_rate,
        pass_threshold=pass_threshold,
        case_results=case_results,
    )
