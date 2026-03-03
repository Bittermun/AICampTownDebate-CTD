import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.run_phase1_batch import _build_jobs


def test_build_jobs_round_robin_for_openai_models() -> None:
    jobs = _build_jobs(
        seeds=[101, 202, 303],
        labels=["set01"],
        openai_base_urls=["http://arc:8000", "http://npu:8000"],
        model_id="openai:Qwen/Qwen2.5-1.5B-Instruct",
        judge_model="openai:Qwen/Qwen2.5-1.5B-Instruct",
    )

    assert jobs == [
        (101, "set01", "http://arc:8000"),
        (202, "set01", "http://npu:8000"),
        (303, "set01", "http://arc:8000"),
    ]


def test_build_jobs_ignores_endpoint_roster_for_non_openai_models() -> None:
    jobs = _build_jobs(
        seeds=[101],
        labels=["set01", "set02"],
        openai_base_urls=["http://arc:8000", "http://npu:8000"],
        model_id="ollama:qwen2.5:7b",
        judge_model="ollama:qwen2.5:7b",
    )

    assert jobs == [
        (101, "set01", None),
        (101, "set02", None),
    ]


if __name__ == "__main__":
    test_build_jobs_round_robin_for_openai_models()
    test_build_jobs_ignores_endpoint_roster_for_non_openai_models()
    print("test_phase1_batch_endpoint_assignment: PASS")
