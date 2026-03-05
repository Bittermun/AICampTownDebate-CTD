import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts import run_phase1_batch
from scripts.run_phase1_batch import _build_jobs
from src.benchmark.batch_utils import BatchRunRecord, encode_checkpoint_row, load_checkpoint_jsonl


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


def test_build_jobs_round_robin_for_vllm_models() -> None:
    jobs = _build_jobs(
        seeds=[101, 202, 303],
        labels=["set01"],
        openai_base_urls=["http://arc:8000", "http://npu:8000"],
        model_id="vllm:Qwen/Qwen2.5-1.5B-Instruct",
        judge_model="vllm:Qwen/Qwen2.5-1.5B-Instruct",
    )

    assert jobs == [
        (101, "set01", "http://arc:8000"),
        (202, "set01", "http://npu:8000"),
        (303, "set01", "http://arc:8000"),
    ]


def test_build_jobs_ignores_endpoint_roster_for_non_endpoint_models() -> None:
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


def _write_summary_rows(path: Path, rows: list[BatchRunRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")


def _read_summary_rows(path: Path) -> list[dict]:
    rows, _ = load_checkpoint_jsonl(str(path), schema_name=run_phase1_batch.PHASE1_SUMMARY_SCHEMA_NAME)
    return rows


def _phase1_fingerprint(
    *,
    model_id: str,
    judge_model: str | None,
    seeds: list[int],
    labels: list[str],
) -> str:
    args = SimpleNamespace(
        config="configs/benchmark_phase1.yaml",
        tournament_config="configs/ollama_tournament_recommended.yaml",
        model_id=model_id,
        judge_model=judge_model,
        offline_fixtures_dir="benchmarks/fixtures",
        source_mode="core_live_stretch_fixture",
        allow_stub=False,
        bankruptcy_retries=1,
        replacement_mode="off",
        replacement_roster="",
        replacement_judge_model=None,
        max_replacements_per_run=1,
    )
    return run_phase1_batch._config_fingerprint(
        args=args,
        seeds=seeds,
        labels=labels,
        openai_base_urls=[],
    )


def _write_checkpoint(path: Path, *, batch_id: str, fingerprint: str, schema_version: int | None = None) -> None:
    payload = run_phase1_batch._checkpoint_payload(batch_id=batch_id, fingerprint=fingerprint)
    if schema_version is not None:
        payload["schema_version"] = schema_version
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_main_resume_requires_batch_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["run_phase1_batch.py", "--model-id", "stub", "--resume"])
    with pytest.raises(ValueError, match="--resume requires --batch-id"):
        run_phase1_batch.main()


def test_load_checkpoint_records_skips_malformed_lines(tmp_path: Path) -> None:
    summary_jsonl = tmp_path / "batch_summary.jsonl"
    valid_row = BatchRunRecord(
        run_id="seed101_set01",
        attempt=1,
        seed=101,
        topic_set="set01",
        summary_path="attempt_1/benchmark_summary.json",
        registry_path="attempt_1/champion_registry.json",
        return_code=0,
        bankrupt=False,
        terminal_bankrupt=False,
        original_model_id="stub",
        effective_model_id="stub",
    )
    wrapped_row = BatchRunRecord(
        run_id="seed202_set01",
        attempt=1,
        seed=202,
        topic_set="set01",
        summary_path="attempt_1/benchmark_summary.json",
        registry_path="attempt_1/champion_registry.json",
        return_code=0,
        bankrupt=False,
        terminal_bankrupt=False,
        original_model_id="stub",
        effective_model_id="stub",
    )
    summary_jsonl.write_text(
        "\n".join(
            [
                json.dumps(valid_row.to_dict(), sort_keys=True),
                json.dumps(
                    encode_checkpoint_row(
                        wrapped_row.to_dict(),
                        schema_name=run_phase1_batch.PHASE1_SUMMARY_SCHEMA_NAME,
                    ),
                    sort_keys=True,
                ),
                "{broken json",
            ]
        ),
        encoding="utf-8",
    )

    loaded = run_phase1_batch._load_checkpoint_records(summary_jsonl)
    assert len(loaded) == 2
    assert {record.run_id for record in loaded} == {"seed101_set01", "seed202_set01"}


def test_main_resume_skips_completed_jobs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "batches"
    batch_id = "resume-batch-001"
    batch_root = output_dir / batch_id
    summary_jsonl = batch_root / "batch_summary.jsonl"

    completed = BatchRunRecord(
        run_id="seed101_set01",
        attempt=1,
        seed=101,
        topic_set="set01",
        summary_path="attempt_1/benchmark_summary.json",
        registry_path="attempt_1/champion_registry.json",
        return_code=0,
        bankrupt=False,
        terminal_bankrupt=False,
        original_model_id="stub",
        effective_model_id="stub",
    )
    incomplete = BatchRunRecord(
        run_id="seed202_set01",
        attempt=1,
        seed=202,
        topic_set="set01",
        summary_path="",
        registry_path="",
        return_code=9,
        bankrupt=False,
        terminal_bankrupt=False,
        original_model_id="stub",
        effective_model_id="stub",
    )
    _write_summary_rows(summary_jsonl, [completed, incomplete])
    checkpoint = batch_root / run_phase1_batch.CHECKPOINT_FILENAME
    _write_checkpoint(
        checkpoint,
        batch_id=batch_id,
        fingerprint=_phase1_fingerprint(model_id="stub", judge_model=None, seeds=[101, 202], labels=["set01"]),
    )

    called_jobs: list[tuple[int, str, str]] = []

    def _fake_run_job(args, current_batch_id: str, seed: int, matrix_label: str, openai_base_url):
        called_jobs.append((seed, matrix_label, current_batch_id))
        return [
            BatchRunRecord(
                run_id=f"seed{seed}_{matrix_label}",
                attempt=1,
                seed=seed,
                topic_set=matrix_label,
                summary_path="attempt_1/benchmark_summary.json",
                registry_path="attempt_1/champion_registry.json",
                return_code=0,
                bankrupt=False,
                terminal_bankrupt=False,
                original_model_id=args.model_id,
                effective_model_id=args.model_id,
                openai_base_url=openai_base_url,
            )
        ]

    monkeypatch.setattr(run_phase1_batch, "_run_job", _fake_run_job)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_phase1_batch.py",
            "--model-id",
            "stub",
            "--seeds",
            "101,202",
            "--matrix-labels",
            "set01",
            "--output-dir",
            str(output_dir),
            "--batch-id",
            batch_id,
            "--resume",
            "--concurrency",
            "1",
        ],
    )

    rc = run_phase1_batch.main()
    assert rc == 0
    assert called_jobs == [(202, "set01", batch_id)]

    rows = _read_summary_rows(summary_jsonl)
    assert {(row["seed"], row["topic_set"]) for row in rows} == {(101, "set01"), (202, "set01")}
    assert all(int(row["return_code"]) != 9 for row in rows)
    raw_payloads = [json.loads(line) for line in summary_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert all(payload.get("__schema__") == run_phase1_batch.PHASE1_SUMMARY_SCHEMA_NAME for payload in raw_payloads)


def test_main_non_resume_runs_all_jobs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "batches"
    batch_id = "no-resume-batch-001"
    batch_root = output_dir / batch_id
    summary_jsonl = batch_root / "batch_summary.jsonl"

    old_row = BatchRunRecord(
        run_id="seed101_set01",
        attempt=1,
        seed=101,
        topic_set="set01",
        summary_path="attempt_1/benchmark_summary.json",
        registry_path="attempt_1/champion_registry.json",
        return_code=0,
        bankrupt=False,
        terminal_bankrupt=False,
        original_model_id="old-model",
        effective_model_id="old-model",
    )
    _write_summary_rows(summary_jsonl, [old_row])

    called_jobs: list[tuple[int, str, str]] = []

    def _fake_run_job(args, current_batch_id: str, seed: int, matrix_label: str, openai_base_url):
        called_jobs.append((seed, matrix_label, current_batch_id))
        return [
            BatchRunRecord(
                run_id=f"seed{seed}_{matrix_label}",
                attempt=1,
                seed=seed,
                topic_set=matrix_label,
                summary_path="attempt_1/benchmark_summary.json",
                registry_path="attempt_1/champion_registry.json",
                return_code=0,
                bankrupt=False,
                terminal_bankrupt=False,
                original_model_id=args.model_id,
                effective_model_id=args.model_id,
                openai_base_url=openai_base_url,
            )
        ]

    monkeypatch.setattr(run_phase1_batch, "_run_job", _fake_run_job)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_phase1_batch.py",
            "--model-id",
            "stub",
            "--seeds",
            "101,202",
            "--matrix-labels",
            "set01",
            "--output-dir",
            str(output_dir),
            "--batch-id",
            batch_id,
            "--concurrency",
            "1",
        ],
    )

    rc = run_phase1_batch.main()
    assert rc == 0
    assert sorted(called_jobs) == [(101, "set01", batch_id), (202, "set01", batch_id)]

    rows = _read_summary_rows(summary_jsonl)
    assert len(rows) == 2
    assert all(row["effective_model_id"] == "stub" for row in rows)


def test_main_returns_nonzero_on_fatal_job(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "batches"
    batch_id = "fatal-batch-001"

    def _fake_run_job(args, current_batch_id: str, seed: int, matrix_label: str, openai_base_url):
        return [
            BatchRunRecord(
                run_id=f"seed{seed}_{matrix_label}",
                attempt=1,
                seed=seed,
                topic_set=matrix_label,
                summary_path="",
                registry_path="",
                return_code=9,
                bankrupt=False,
                terminal_bankrupt=False,
                original_model_id=args.model_id,
                effective_model_id=args.model_id,
                openai_base_url=openai_base_url,
            )
        ]

    monkeypatch.setattr(run_phase1_batch, "_run_job", _fake_run_job)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_phase1_batch.py",
            "--model-id",
            "stub",
            "--seeds",
            "101",
            "--matrix-labels",
            "set01",
            "--output-dir",
            str(output_dir),
            "--batch-id",
            batch_id,
            "--concurrency",
            "1",
        ],
    )

    rc = run_phase1_batch.main()
    assert rc == 1


def test_resume_rejects_incompatible_checkpoint_schema(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "batches"
    batch_id = "schema-mismatch-batch"
    batch_root = output_dir / batch_id
    checkpoint = batch_root / run_phase1_batch.CHECKPOINT_FILENAME
    _write_checkpoint(
        checkpoint,
        batch_id=batch_id,
        fingerprint=_phase1_fingerprint(model_id="stub", judge_model=None, seeds=[101], labels=["set01"]),
        schema_version=999,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_phase1_batch.py",
            "--model-id",
            "stub",
            "--seeds",
            "101",
            "--matrix-labels",
            "set01",
            "--output-dir",
            str(output_dir),
            "--batch-id",
            batch_id,
            "--resume",
        ],
    )
    with pytest.raises(RuntimeError, match="schema_version"):
        run_phase1_batch.main()


def test_resume_rejects_config_fingerprint_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "batches"
    batch_id = "fingerprint-mismatch-batch"
    batch_root = output_dir / batch_id
    checkpoint = batch_root / run_phase1_batch.CHECKPOINT_FILENAME
    _write_checkpoint(checkpoint, batch_id=batch_id, fingerprint="deadbeefdeadbeef")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_phase1_batch.py",
            "--model-id",
            "stub",
            "--seeds",
            "101",
            "--matrix-labels",
            "set01",
            "--output-dir",
            str(output_dir),
            "--batch-id",
            batch_id,
            "--resume",
        ],
    )
    with pytest.raises(RuntimeError, match="configuration mismatch"):
        run_phase1_batch.main()


if __name__ == "__main__":
    test_build_jobs_round_robin_for_openai_models()
    test_build_jobs_round_robin_for_vllm_models()
    test_build_jobs_ignores_endpoint_roster_for_non_endpoint_models()
    print("test_phase1_batch_endpoint_assignment: PASS")
