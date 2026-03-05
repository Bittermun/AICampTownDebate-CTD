#!/usr/bin/env python3
"""Run a batch of phase-1 benchmark jobs with retry-once bankruptcy policy."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import json
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.batch_utils import (  # noqa: E402
    BATCH_CHECKPOINT_FILENAME as CHECKPOINT_FILENAME,
    BATCH_CHECKPOINT_SCHEMA_VERSION as CHECKPOINT_SCHEMA_VERSION,
    BatchRunRecord,
    assert_resume_compatible as _assert_resume_compatible,
    atomic_write_json as _atomic_write_json,
    build_batch_checkpoint_payload,
    detect_bankruptcy_from_summary,
    load_batch_checkpoint as _load_checkpoint,
    load_checkpoint_jsonl,
    load_json,
    persist_jsonl,
    should_retry_bankruptcy,
    summarize_batch,
)
PHASE1_SUMMARY_SCHEMA_NAME = "benchmark.phase1.batch_summary"


def _parse_csv_int(raw: str) -> List[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_csv_str(raw: str) -> List[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _is_openai_model(model_id: Optional[str]) -> bool:
    return bool(model_id) and str(model_id).startswith("openai:")


def _is_vllm_model(model_id: Optional[str]) -> bool:
    return bool(model_id) and str(model_id).startswith("vllm:")


def _uses_endpoint_roster(model_id: Optional[str], judge_model: Optional[str]) -> bool:
    return (
        _is_openai_model(model_id)
        or _is_openai_model(judge_model)
        or _is_vllm_model(model_id)
        or _is_vllm_model(judge_model)
    )


def _build_jobs(
    seeds: List[int],
    labels: List[str],
    openai_base_urls: List[str],
    model_id: str,
    judge_model: Optional[str],
) -> List[Tuple[int, str, Optional[str]]]:
    jobs: List[Tuple[int, str, Optional[str]]] = []
    use_endpoints = bool(openai_base_urls) and _uses_endpoint_roster(model_id, judge_model)
    for idx, (seed, label) in enumerate((seed, label) for seed in seeds for label in labels):
        endpoint = openai_base_urls[idx % len(openai_base_urls)] if use_endpoints else None
        jobs.append((seed, label, endpoint))
    return jobs


def _job_key(seed: int, label: str) -> Tuple[int, str]:
    return (int(seed), str(label))


def _record_job_key(record: BatchRunRecord) -> Tuple[int, str]:
    return _job_key(record.seed, record.topic_set)


def _record_from_payload(payload: Dict[str, Any]) -> BatchRunRecord:
    return BatchRunRecord(
        run_id=str(payload.get("run_id", "")),
        attempt=int(payload.get("attempt", 1)),
        seed=int(payload.get("seed", 0)),
        topic_set=str(payload.get("topic_set", "")),
        summary_path=str(payload.get("summary_path", "")),
        registry_path=str(payload.get("registry_path", "")),
        return_code=int(payload.get("return_code", 0)),
        bankrupt=bool(payload.get("bankrupt", False)),
        terminal_bankrupt=bool(payload.get("terminal_bankrupt", False)),
        pass_fail=str(payload.get("pass_fail", "unknown")),
        final_pass=bool(payload.get("final_pass", False)),
        benchmark_score_pass=bool(payload.get("benchmark_score_pass", False)),
        gates_pass=bool(payload.get("gates_pass", False)),
        validity_pass=bool(payload.get("validity_pass", False)),
        degraded_mode=bool(payload.get("degraded_mode", False)),
        live_source_failures=int(payload.get("live_source_failures", 0)),
        original_model_id=str(payload.get("original_model_id", "")),
        effective_model_id=str(payload.get("effective_model_id", "")),
        openai_base_url=payload.get("openai_base_url"),
        was_replaced=bool(payload.get("was_replaced", False)),
        replacement_index=int(payload.get("replacement_index", 0)),
        replaced_from_run_id=payload.get("replaced_from_run_id"),
    )


def _load_checkpoint_records(summary_jsonl: Path) -> List[BatchRunRecord]:
    rows, stats = load_checkpoint_jsonl(
        str(summary_jsonl),
        schema_name=PHASE1_SUMMARY_SCHEMA_NAME,
    )
    if stats["rows_malformed"] or stats["rows_invalid"]:
        print(
            f"[batch][warn] checkpoint decode issues: malformed={stats['rows_malformed']} "
            f"invalid={stats['rows_invalid']}"
        )
    if stats["rows_legacy"]:
        print(f"[batch] migrated legacy summary rows={stats['rows_legacy']} -> schema=v1")

    records: List[BatchRunRecord] = []
    for index, payload in enumerate(rows, start=1):
        try:
            records.append(_record_from_payload(payload))
        except Exception as exc:
            print(f"[batch][warn] skipping malformed checkpoint row index={index}: {exc}")
    return records


def _is_completed_primary_record(record: BatchRunRecord) -> bool:
    expected_run_id = f"seed{record.seed}_{record.topic_set}"
    return (
        record.run_id == expected_run_id
        and int(record.replacement_index) == 0
        and str(record.summary_path).strip() != ""
        and int(record.return_code) != 9
    )


def _extract_completed_jobs(records: List[BatchRunRecord]) -> Set[Tuple[int, str]]:
    completed: Set[Tuple[int, str]] = set()
    for record in records:
        if _is_completed_primary_record(record):
            completed.add(_record_job_key(record))
    return completed


def _atomic_write_summary(path: Path, records: List[BatchRunRecord]) -> None:
    persist_jsonl(
        str(path),
        (r.to_dict() for r in records),
        schema_name=PHASE1_SUMMARY_SCHEMA_NAME,
    )


def _config_fingerprint(
    *,
    args: argparse.Namespace,
    seeds: List[int],
    labels: List[str],
    openai_base_urls: List[str],
) -> str:
    payload = {
        "config": args.config,
        "tournament_config": args.tournament_config,
        "model_id": args.model_id,
        "judge_model": args.judge_model,
        "seeds": list(seeds),
        "matrix_labels": list(labels),
        "offline_fixtures_dir": args.offline_fixtures_dir,
        "source_mode": args.source_mode,
        "allow_stub": bool(args.allow_stub),
        "bankruptcy_retries": int(args.bankruptcy_retries),
        "replacement_mode": args.replacement_mode,
        "replacement_roster": _parse_csv_str(args.replacement_roster),
        "replacement_judge_model": args.replacement_judge_model,
        "max_replacements_per_run": int(args.max_replacements_per_run),
        "openai_base_urls": list(openai_base_urls),
        "openai_endpoint_strategy": "round_robin" if openai_base_urls else "none",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _checkpoint_payload(*, batch_id: str, fingerprint: str) -> Dict[str, Any]:
    return build_batch_checkpoint_payload(batch_id=batch_id, config_fingerprint=fingerprint)


def _run_once(
    *,
    config: str,
    tournament_config: str,
    model_id: str,
    judge_model: str | None,
    fixtures_dir: str,
    seed: int,
    source_mode: str,
    artifact_root: str,
    output_summary: str,
    output_registry: str,
    run_label: str,
    allow_stub: bool,
    refresh_live_cache: bool,
    cache_only_live: bool,
    openai_base_url: Optional[str],
) -> int:
    cmd = [
        sys.executable,
        "tests/run_phase1_benchmark.py",
        "--config",
        config,
        "--tournament-config",
        tournament_config,
        "--model-id",
        model_id,
        "--seeds",
        str(seed),
        "--offline-fixtures-dir",
        fixtures_dir,
        "--source-mode",
        source_mode,
        "--artifact-root",
        artifact_root,
        "--output-summary",
        output_summary,
        "--output-registry",
        output_registry,
        "--run-label",
        run_label,
    ]
    if judge_model:
        cmd.extend(["--judge-model", judge_model])
    if allow_stub:
        cmd.append("--allow-stub")
    if refresh_live_cache:
        cmd.append("--refresh-live-cache")
    if cache_only_live:
        cmd.append("--cache-only-live")
    env = os.environ.copy()
    if openai_base_url:
        if _is_openai_model(model_id) or _is_openai_model(judge_model):
            env["OPENAI_COMPAT_BASE_URL"] = openai_base_url
        if _is_vllm_model(model_id) or _is_vllm_model(judge_model):
            env["VLLM_BASE_URL"] = openai_base_url
    proc = subprocess.run(cmd, text=True, env=env)
    return int(proc.returncode)


def _run_job(args, batch_id: str, seed: int, matrix_label: str, openai_base_url: Optional[str]) -> List[BatchRunRecord]:
    run_id = f"seed{seed}_{matrix_label}"
    batch_root = Path(args.output_dir) / batch_id
    replacement_roster = _parse_csv_str(args.replacement_roster)
    replacement_cap = max(0, int(args.max_replacements_per_run))

    def _run_with_retry(
        *,
        current_run_id: str,
        model_id: str,
        judge_model: str | None,
        was_replaced: bool,
        replacement_index: int,
        replaced_from_run_id: str | None,
    ) -> BatchRunRecord:
        run_root = batch_root / current_run_id
        run_root.mkdir(parents=True, exist_ok=True)

        summary_path = run_root / "benchmark_summary.json"
        registry_path = run_root / "champion_registry.json"

        attempt = 1
        final_record: BatchRunRecord | None = None
        while True:
            attempt_label = f"{current_run_id}_attempt{attempt}"
            attempt_root = run_root / f"attempt_{attempt}"
            attempt_root.mkdir(parents=True, exist_ok=True)
            attempt_summary = attempt_root / "benchmark_summary.json"
            attempt_registry = attempt_root / "champion_registry.json"

            rc = _run_once(
                config=args.config,
                tournament_config=args.tournament_config,
                model_id=model_id,
                judge_model=judge_model,
                fixtures_dir=args.offline_fixtures_dir,
                seed=seed,
                source_mode=args.source_mode,
                artifact_root=str(attempt_root),
                output_summary=str(attempt_summary),
                output_registry=str(attempt_registry),
                run_label=attempt_label,
                allow_stub=args.allow_stub,
                refresh_live_cache=args.refresh_live_cache and attempt == 1,
                cache_only_live=args.cache_only_live,
                openai_base_url=openai_base_url,
            )

            bankrupt = False
            payload: Dict = {}
            if attempt_summary.exists():
                payload = load_json(str(attempt_summary))
                bankrupt = detect_bankruptcy_from_summary(payload)

            retry = should_retry_bankruptcy(bankrupt=bankrupt, attempt=attempt, max_retries=args.bankruptcy_retries)
            terminal_bankrupt = bankrupt and not retry

            record = BatchRunRecord(
                run_id=current_run_id,
                attempt=attempt,
                seed=seed,
                topic_set=matrix_label,
                summary_path=str(attempt_summary),
                registry_path=str(attempt_registry),
                return_code=rc,
                bankrupt=bankrupt,
                terminal_bankrupt=terminal_bankrupt,
                pass_fail=str(payload.get("pass_fail", "unknown")) if payload else "unknown",
                final_pass=bool(payload.get("final_pass", False)) if payload else False,
                benchmark_score_pass=bool(payload.get("benchmark_score_pass", False)) if payload else False,
                gates_pass=bool(payload.get("gates_pass", False)) if payload else False,
                validity_pass=bool(payload.get("validity_pass", False)) if payload else False,
                degraded_mode=bool(payload.get("degraded_mode", False)) if payload else False,
                live_source_failures=len(payload.get("live_source_failures", [])) if payload else 0,
                original_model_id=args.model_id,
                effective_model_id=model_id,
                openai_base_url=openai_base_url,
                was_replaced=was_replaced,
                replacement_index=replacement_index,
                replaced_from_run_id=replaced_from_run_id,
            )

            final_record = record
            if not retry:
                if attempt_summary.exists():
                    summary_path.write_text(attempt_summary.read_text(encoding="utf-8"), encoding="utf-8")
                if attempt_registry.exists():
                    registry_path.write_text(attempt_registry.read_text(encoding="utf-8"), encoding="utf-8")
                break
            attempt += 1

        if final_record is None:
            raise RuntimeError(f"Failed to produce run record for {current_run_id}")
        return final_record

    records: List[BatchRunRecord] = []
    original_record = _run_with_retry(
        current_run_id=run_id,
        model_id=args.model_id,
        judge_model=args.judge_model,
        was_replaced=False,
        replacement_index=0,
        replaced_from_run_id=None,
    )
    records.append(original_record)

    if (
        args.replacement_mode != "on"
        or not original_record.terminal_bankrupt
        or replacement_cap <= 0
        or not replacement_roster
    ):
        return records

    replacement_judge = args.replacement_judge_model if args.replacement_judge_model else args.judge_model
    previous_record = original_record
    max_replacements = min(replacement_cap, len(replacement_roster))
    for idx in range(1, max_replacements + 1):
        if not previous_record.terminal_bankrupt:
            break
        replacement_run_id = f"{run_id}__replacement{idx}"
        replacement_model_id = replacement_roster[idx - 1]
        replacement_record = _run_with_retry(
            current_run_id=replacement_run_id,
            model_id=replacement_model_id,
            judge_model=replacement_judge,
            was_replaced=True,
            replacement_index=idx,
            replaced_from_run_id=previous_record.run_id,
        )
        records.append(replacement_record)
        previous_record = replacement_record
    return records


def main() -> int:
    p = argparse.ArgumentParser(description="Batch phase-1 runner with retry-once bankruptcy handling")
    p.add_argument("--config", default="configs/benchmark_phase1.yaml")
    p.add_argument("--tournament-config", default="configs/ollama_tournament_recommended.yaml")
    p.add_argument("--model-id", required=True)
    p.add_argument("--judge-model", default=None)
    p.add_argument("--seeds", default="101,202,303")
    p.add_argument("--matrix-labels", default="set01")
    p.add_argument("--output-dir", default="logs/benchmark_batches")
    p.add_argument("--batch-id", default=None, help="Optional custom batch ID (required with --resume)")
    p.add_argument("--resume", action="store_true", help="Resume an existing --batch-id by skipping completed seed/label jobs")
    p.add_argument("--offline-fixtures-dir", default="benchmarks/fixtures")
    p.add_argument("--source-mode", default="core_live_stretch_fixture", choices=["default", "core_live_stretch_fixture", "all_live", "all_fixture"])
    p.add_argument("--concurrency", type=int, default=2)
    p.add_argument("--bankruptcy-retries", type=int, default=1)
    p.add_argument("--replacement-mode", default="off", choices=["off", "on"])
    p.add_argument("--replacement-roster", default="")
    p.add_argument("--replacement-judge-model", default=None)
    p.add_argument("--max-replacements-per-run", type=int, default=1)
    p.add_argument("--allow-stub", action="store_true")
    p.add_argument("--refresh-live-cache", action="store_true")
    p.add_argument("--cache-only-live", action="store_true")
    p.add_argument(
        "--openai-base-urls",
        default="",
        help=(
            "Comma-separated endpoint roster for openai:* and vllm:* models. "
            "Jobs are assigned round-robin."
        ),
    )
    args = p.parse_args()

    seeds = _parse_csv_int(args.seeds)
    labels = _parse_csv_str(args.matrix_labels)
    openai_base_urls = _parse_csv_str(args.openai_base_urls)
    if not seeds or not labels:
        raise ValueError("seeds and matrix-labels must be non-empty")

    if args.resume and not args.batch_id:
        raise ValueError("--resume requires --batch-id")

    batch_id = args.batch_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_root = Path(args.output_dir) / batch_id
    if args.resume and not batch_root.exists():
        raise FileNotFoundError(f"--resume requested but batch directory does not exist: {batch_root}")
    batch_root.mkdir(parents=True, exist_ok=True)
    checkpoint_path = batch_root / CHECKPOINT_FILENAME

    jobs = _build_jobs(
        seeds=seeds,
        labels=labels,
        openai_base_urls=openai_base_urls,
        model_id=args.model_id,
        judge_model=args.judge_model,
    )
    config_fp = _config_fingerprint(args=args, seeds=seeds, labels=labels, openai_base_urls=openai_base_urls)
    if args.resume:
        checkpoint = _load_checkpoint(checkpoint_path)
        _assert_resume_compatible(checkpoint, config_fp)
    else:
        _atomic_write_json(
            checkpoint_path,
            build_batch_checkpoint_payload(batch_id=batch_id, config_fingerprint=config_fp),
        )

    all_job_keys = {_job_key(seed, label) for seed, label, _ in jobs}
    summary_jsonl = batch_root / "batch_summary.jsonl"
    existing_records = _load_checkpoint_records(summary_jsonl) if args.resume else []
    completed_job_keys = _extract_completed_jobs(existing_records) if args.resume else set()
    completed_job_keys &= all_job_keys
    records: List[BatchRunRecord] = (
        [r for r in existing_records if _record_job_key(r) in completed_job_keys] if args.resume else []
    )
    if args.resume:
        # Rewrite checkpoint to keep only completed jobs and drop stale partial/error rows.
        _atomic_write_summary(summary_jsonl, records)
    elif summary_jsonl.exists():
        _atomic_write_summary(summary_jsonl, [])

    pending_jobs = [
        (seed, label, endpoint)
        for seed, label, endpoint in jobs
        if _job_key(seed, label) not in completed_job_keys
    ]

    if openai_base_urls and not _uses_endpoint_roster(args.model_id, args.judge_model):
        print("[batch][warn] --openai-base-urls ignored because model/judge are not openai:* or vllm:*")
    if args.resume:
        print(
            f"[batch] resume batch_id={batch_id} completed_jobs={len(completed_job_keys)} "
            f"pending_jobs={len(pending_jobs)}"
        )

    with ThreadPoolExecutor(max_workers=max(1, int(args.concurrency))) as ex:
        futs = {
            ex.submit(_run_job, args, batch_id, seed, label, endpoint): (seed, label, endpoint)
            for seed, label, endpoint in pending_jobs
        }
        for fut in as_completed(futs):
            seed, label, endpoint = futs[fut]
            try:
                for rec in fut.result():
                    records.append(rec)
                    _atomic_write_summary(summary_jsonl, records)
                    endpoint_note = f" endpoint={rec.openai_base_url}" if rec.openai_base_url else ""
                    print(
                        f"[batch] seed={seed} label={label} run_id={rec.run_id} attempt={rec.attempt} "
                        f"model={rec.effective_model_id or args.model_id}{endpoint_note} "
                        f"bankrupt={rec.bankrupt} final_pass={rec.final_pass}"
                    )
            except Exception as exc:
                print(f"[batch][ERROR] seed={seed} label={label}: {exc}")
                records.append(
                    BatchRunRecord(
                        run_id=f"seed{seed}_{label}",
                        attempt=1,
                        seed=seed,
                        topic_set=label,
                        summary_path="",
                        registry_path="",
                        return_code=9,
                        bankrupt=False,
                        terminal_bankrupt=False,
                        original_model_id=args.model_id,
                        effective_model_id=args.model_id,
                        openai_base_url=endpoint,
                    )
                )
                _atomic_write_summary(summary_jsonl, records)

    records.sort(key=lambda r: (r.seed, r.topic_set, r.replacement_index, r.run_id))
    _atomic_write_summary(summary_jsonl, records)

    aggregate = summarize_batch(records)
    manifest = {
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "config_fingerprint": config_fp,
        "batch_id": batch_id,
        "config": args.config,
        "tournament_config": args.tournament_config,
        "model_id": args.model_id,
        "judge_model": args.judge_model,
        "seeds": seeds,
        "matrix_labels": labels,
        "source_mode": args.source_mode,
        "concurrency": args.concurrency,
        "resume": bool(args.resume),
        "bankruptcy_retries": args.bankruptcy_retries,
        "replacement_mode": args.replacement_mode,
        "replacement_roster": _parse_csv_str(args.replacement_roster),
        "replacement_judge_model": args.replacement_judge_model,
        "max_replacements_per_run": args.max_replacements_per_run,
        "openai_base_urls": openai_base_urls,
        "openai_endpoint_strategy": "round_robin" if openai_base_urls else "none",
        "endpoint_model_prefixes": ["openai", "vllm"],
        "records": [asdict(r) for r in records],
    }
    _atomic_write_json(batch_root / "batch_manifest.json", manifest)
    _atomic_write_json(batch_root / "aggregate_report.json", aggregate)

    print(f"[batch] wrote: {batch_root / 'batch_manifest.json'}")
    print(f"[batch] wrote: {summary_jsonl}")
    print(f"[batch] wrote: {batch_root / 'aggregate_report.json'}")
    tolerated_codes = {0, 2, 3}
    has_fatal_error = any(
        int(r.return_code) not in tolerated_codes or (not str(r.summary_path).strip())
        for r in records
    )
    return 1 if has_fatal_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
