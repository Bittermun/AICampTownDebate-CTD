import json
import sys
from pathlib import Path
from types import SimpleNamespace

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import scripts.run_tournament_batch as run_tournament_batch
from src.benchmark.batch_utils import encode_checkpoint_row, load_checkpoint_jsonl


def _write_checkpoint(path: Path, *, batch_id: str, fingerprint: str, schema_version: int | None = None) -> None:
    payload = run_tournament_batch._checkpoint_payload(batch_id, fingerprint)
    if schema_version is not None:
        payload["schema_version"] = schema_version
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_load_and_index_summary_records_filters_invalid_lines(tmp_path: Path) -> None:
    summary_path = tmp_path / "batch_summary.jsonl"
    summary_path.write_text(
        "\n".join(
            [
                json.dumps({"run_no": 1, "success": True}),
                json.dumps(
                    encode_checkpoint_row(
                        {"run_no": 2, "success": True},
                        schema_name=run_tournament_batch.TOURNAMENT_SUMMARY_SCHEMA_NAME,
                    )
                ),
                "{not-json",
                json.dumps({"run_no": "2", "success": True}),
                json.dumps({"run_no": 2, "success": False}),
                json.dumps({"run_no": 6, "success": True}),
            ]
        ),
        encoding="utf-8",
    )

    loaded = run_tournament_batch._load_summary_records(summary_path)
    indexed = run_tournament_batch._index_records_by_run_no(loaded, runs_requested=5)

    assert sorted(indexed.keys()) == [1, 2]
    assert indexed[2]["success"] is False


def test_build_jobs_skips_completed_runs_and_preserves_seed_mapping() -> None:
    jobs = run_tournament_batch._build_jobs(
        runs=5,
        start_seed=100,
        seed_step=10,
        base_urls=["http://e1", "http://e2"],
        skip_run_nos={2, 4},
    )

    assert jobs == [
        (1, 100, "http://e1"),
        (3, 120, "http://e1"),
        (5, 140, "http://e1"),
    ]


def test_main_resume_only_schedules_missing_run_numbers(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "batches"
    batch_id = "resume_batch"
    batch_root = output_root / batch_id
    batch_root.mkdir(parents=True, exist_ok=True)
    (batch_root / "batch_summary.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"run_no": 1, "success": True, "rounds_completed": 1, "trace_count": 1}),
                json.dumps({"run_no": 3, "success": True, "rounds_completed": 1, "trace_count": 1}),
            ]
        ),
        encoding="utf-8",
    )
    checkpoint = batch_root / run_tournament_batch.CHECKPOINT_FILENAME

    scheduled: list[tuple[int, int, str | None]] = []

    def _fake_load_config(_: str):
        return SimpleNamespace(judges=[SimpleNamespace(model="judge:test")])

    def _fake_run_job(
        run_no,
        seed,
        _batch_root,
        _batch_id,
        _args,
        _gate_variance,
        _gate_calibration,
        _judge_model,
        _summary_jsonl,
        _write_lock,
        endpoint,
    ):
        scheduled.append((run_no, seed, endpoint))
        return {
            "run_no": run_no,
            "seed": seed,
            "success": True,
            "winner": None,
            "rounds_completed": 1,
            "trace_count": 1,
        }

    monkeypatch.setattr(run_tournament_batch, "load_config", _fake_load_config)
    monkeypatch.setattr(run_tournament_batch, "_run_tournament_job", _fake_run_job)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tournament_batch.py",
            "--config",
            "configs/does_not_matter.yaml",
            "--output-root",
            str(output_root),
            "--batch-id",
            batch_id,
            "--runs",
            "4",
            "--concurrency",
            "1",
            "--openai-base-urls",
            "http://e1,http://e2",
            "--resume",
        ],
    )
    args = SimpleNamespace(
        config="configs/does_not_matter.yaml",
        runs=4,
        start_seed=101,
        seed_step=1,
        allow_stub=False,
        no_gate_judge_variance=False,
        no_gate_judge_calibration=False,
        variance_runs=10,
        max_judge_stdev=0.05,
        min_judge_mean_a=0.55,
        min_calibration_pass_rate=0.67,
    )
    _write_checkpoint(
        checkpoint,
        batch_id=batch_id,
        fingerprint=run_tournament_batch._config_fingerprint(args, ["http://e1", "http://e2"]),
    )

    rc = run_tournament_batch.main()
    assert rc == 0
    assert sorted(scheduled) == [(2, 102, "http://e2"), (4, 104, "http://e2")]

    manifest = json.loads((batch_root / "batch_manifest.json").read_text(encoding="utf-8"))
    assert [r["run_no"] for r in manifest["records"]] == [1, 2, 3, 4]
    assert manifest["aggregate"]["runs_attempted"] == 4
    raw_payloads = [
        json.loads(line)
        for line in (batch_root / "batch_summary.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all(
        payload.get("__schema__") == run_tournament_batch.TOURNAMENT_SUMMARY_SCHEMA_NAME
        for payload in raw_payloads
    )


def test_main_without_resume_keeps_default_behavior(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "batches"
    batch_id = "default_batch"
    batch_root = output_root / batch_id
    batch_root.mkdir(parents=True, exist_ok=True)
    (batch_root / "batch_summary.jsonl").write_text(
        json.dumps({"run_no": 1, "success": True}),
        encoding="utf-8",
    )

    scheduled: list[int] = []

    def _fake_load_config(_: str):
        return SimpleNamespace(judges=[SimpleNamespace(model="judge:test")])

    def _fake_run_job(
        run_no,
        _seed,
        _batch_root,
        _batch_id,
        _args,
        _gate_variance,
        _gate_calibration,
        _judge_model,
        _summary_jsonl,
        _write_lock,
        _endpoint,
    ):
        scheduled.append(run_no)
        return {
            "run_no": run_no,
            "success": True,
            "winner": None,
            "rounds_completed": 1,
            "trace_count": 1,
        }

    monkeypatch.setattr(run_tournament_batch, "load_config", _fake_load_config)
    monkeypatch.setattr(run_tournament_batch, "_run_tournament_job", _fake_run_job)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tournament_batch.py",
            "--config",
            "configs/does_not_matter.yaml",
            "--output-root",
            str(output_root),
            "--batch-id",
            batch_id,
            "--runs",
            "3",
            "--concurrency",
            "1",
        ],
    )

    rc = run_tournament_batch.main()
    assert rc == 0
    assert sorted(scheduled) == [1, 2, 3]
    rows, _ = load_checkpoint_jsonl(
        str(batch_root / "batch_summary.jsonl"),
        schema_name=run_tournament_batch.TOURNAMENT_SUMMARY_SCHEMA_NAME,
    )
    assert [row.get("run_no") for row in rows] == [1, 2, 3]


def test_main_records_exceptions_and_returns_failure(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "batches"
    batch_id = "exception_batch"

    def _fake_load_config(_: str):
        return SimpleNamespace(judges=[SimpleNamespace(model="judge:test")])

    def _fake_run_job(
        run_no,
        _seed,
        _batch_root,
        _batch_id,
        _args,
        _gate_variance,
        _gate_calibration,
        _judge_model,
        _summary_jsonl,
        _write_lock,
        _endpoint,
    ):
        if run_no == 2:
            raise RuntimeError("boom")
        return {
            "run_no": run_no,
            "success": True,
            "winner": None,
            "rounds_completed": 1,
            "trace_count": 1,
        }

    monkeypatch.setattr(run_tournament_batch, "load_config", _fake_load_config)
    monkeypatch.setattr(run_tournament_batch, "_run_tournament_job", _fake_run_job)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tournament_batch.py",
            "--config",
            "configs/does_not_matter.yaml",
            "--output-root",
            str(output_root),
            "--batch-id",
            batch_id,
            "--runs",
            "3",
            "--concurrency",
            "2",
        ],
    )

    rc = run_tournament_batch.main()
    assert rc == 1
    manifest = json.loads((output_root / batch_id / "batch_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["records"]) == 3
    failing = [r for r in manifest["records"] if r.get("run_no") == 2][0]
    assert failing["success"] is False
    assert failing["exit_code"] == 9


def test_resume_rejects_incompatible_checkpoint_schema(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "batches"
    batch_id = "resume_schema_mismatch"
    batch_root = output_root / batch_id
    checkpoint = batch_root / run_tournament_batch.CHECKPOINT_FILENAME
    _write_checkpoint(checkpoint, batch_id=batch_id, fingerprint="abc123", schema_version=999)

    def _fake_load_config(_: str):
        return SimpleNamespace(judges=[SimpleNamespace(model="judge:test")])

    monkeypatch.setattr(run_tournament_batch, "load_config", _fake_load_config)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tournament_batch.py",
            "--config",
            "configs/does_not_matter.yaml",
            "--output-root",
            str(output_root),
            "--batch-id",
            batch_id,
            "--runs",
            "1",
            "--resume",
        ],
    )
    try:
        run_tournament_batch.main()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "schema_version" in str(exc)


def test_resume_rejects_config_fingerprint_mismatch(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "batches"
    batch_id = "resume_fingerprint_mismatch"
    batch_root = output_root / batch_id
    checkpoint = batch_root / run_tournament_batch.CHECKPOINT_FILENAME
    _write_checkpoint(checkpoint, batch_id=batch_id, fingerprint="deadbeefdeadbeef")

    def _fake_load_config(_: str):
        return SimpleNamespace(judges=[SimpleNamespace(model="judge:test")])

    monkeypatch.setattr(run_tournament_batch, "load_config", _fake_load_config)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tournament_batch.py",
            "--config",
            "configs/does_not_matter.yaml",
            "--output-root",
            str(output_root),
            "--batch-id",
            batch_id,
            "--runs",
            "1",
            "--resume",
        ],
    )
    try:
        run_tournament_batch.main()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "configuration mismatch" in str(exc)
