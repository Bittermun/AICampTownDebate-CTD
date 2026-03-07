# TASK-012 output - see CODEX_QUEUE.md
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db.connection import get_db
from src.db.ops import (
    add_participant,
    create_tournament,
    insert_round,
    set_participant_final_balance,
    update_round,
    update_tournament_status,
    upsert_agent,
)

PATCH_VERSION = "v1.1-20260306"
DEFAULT_PATCH_DESCRIPTION = "Economy fix: pot 40->200. External judge llama-3.3-70b."
CONTAMINATED_PREFIXES = ("groq_multikey", "overnight_", "evolution_")
CONTAMINATED_EXACT = {"nvidia_afternoon"}


def _normalize_path(value: str | Path) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return (ROOT / p).resolve()


def _parts_lower(path: Path) -> list[str]:
    return [part.lower() for part in path.parts]


def _is_contaminated_path(path: Path) -> bool:
    for part in _parts_lower(path):
        if part in CONTAMINATED_EXACT:
            return True
        if any(part.startswith(prefix) for prefix in CONTAMINATED_PREFIXES):
            return True
    return False


def _ensure_patch_exists(conn) -> None:
    conn.execute(
        """
        INSERT INTO patches (version, description, config_delta, affected_components)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(version) DO NOTHING
        """,
        (PATCH_VERSION, DEFAULT_PATCH_DESCRIPTION, "{}", "[]"),
    )


def _read_summary_records(summary_path: Path) -> list[dict]:
    records: list[dict] = []
    with summary_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            data = json.loads(raw)
            record = data.get("record") or {}
            if record.get("success") is True:
                records.append(record)
    return records


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _format_total(n: int) -> int:
    return max(3, len(str(max(n, 0))))


def _import_run(conn, record: dict) -> tuple[str, str]:
    artifact_paths = record.get("artifact_paths") or {}
    transcript_rel = artifact_paths.get("transcript_json")
    if not transcript_rel:
        raise ValueError("missing artifact_paths.transcript_json")

    transcript_path = _normalize_path(transcript_rel)
    transcript = _load_json(transcript_path)
    tournament_id = str(transcript.get("tournament_id") or "").strip()
    if not tournament_id:
        raise ValueError(f"missing tournament_id in {transcript_path}")

    existing = conn.execute(
        "SELECT 1 FROM tournaments WHERE id = ? LIMIT 1",
        (tournament_id,),
    ).fetchone()
    if existing:
        return tournament_id, "skipped"

    seed = record.get("seed")
    create_tournament(
        conn,
        tournament_id,
        json.dumps(transcript.get("config") or {}, ensure_ascii=True),
        PATCH_VERSION,
        seed,
    )

    config = transcript.get("config") or {}
    initial_balance = int(config.get("initial_balance", 1000))
    debater_a = config.get("debater_a")
    debater_b = config.get("debater_b")
    judge = config.get("judge")

    participants: list[tuple[str, str]] = []
    if debater_a:
        participants.append(("debater_a", str(debater_a)))
    if debater_b:
        participants.append(("debater_b", str(debater_b)))
    if judge:
        participants.append(("judge", str(judge)))

    for role, agent_id in participants:
        upsert_agent(conn, id=agent_id, name=agent_id, provider_config_id=None)
        add_participant(conn, tournament_id, agent_id, role, initial_balance)

    final_balances = transcript.get("final_balances") or {}
    if debater_a and debater_a in final_balances:
        set_participant_final_balance(
            conn,
            tournament_id,
            str(debater_a),
            int(round(float(final_balances[debater_a]))),
        )
    if debater_b and debater_b in final_balances:
        set_participant_final_balance(
            conn,
            tournament_id,
            str(debater_b),
            int(round(float(final_balances[debater_b]))),
        )

    ended_at = transcript.get("ended_at")
    for round_item in transcript.get("rounds") or []:
        round_number = int(round_item.get("round_id"))
        idem_key = f"{tournament_id}:round:{round_number}"
        judge_scores = {
            "confidence_a": round_item.get("confidence_a"),
            "confidence_b": round_item.get("confidence_b"),
        }
        roi = None
        try:
            a_award = float(round_item.get("tokens_awarded_a"))
            b_award = float(round_item.get("tokens_awarded_b"))
            total = a_award + b_award
            roi = ((a_award - b_award) / total) if total else 0.0
        except Exception:
            roi = None

        insert_round(
            conn,
            idem_key,
            tournament_id,
            round_number,
            None,
            PATCH_VERSION,
        )
        update_round(
            conn,
            idem_key,
            "completed",
            transcript_json=json.dumps(round_item, ensure_ascii=True),
            judge_scores=json.dumps(judge_scores, ensure_ascii=True),
            roi=roi,
            completed_at=ended_at,
        )

    update_tournament_status(
        conn,
        tournament_id,
        "completed",
        started_at=transcript.get("started_at"),
        ended_at=ended_at,
        winner_agent_id=transcript.get("winner"),
        notes=f"migrated_from={record.get('run_dir')}",
    )

    return tournament_id, "imported"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate clean JSON logs into DB.")
    parser.add_argument(
        "--batch-dir",
        required=True,
        help="Path to batch directory containing batch_summary.jsonl",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch_dir = _normalize_path(args.batch_dir)

    if _is_contaminated_path(batch_dir):
        print(f"[migrate] refused contaminated directory: {batch_dir}")
        return 2

    summary_path = batch_dir / "batch_summary.jsonl"
    if not summary_path.exists():
        print(f"[migrate] error: missing file {summary_path}")
        return 2

    records = _read_summary_records(summary_path)
    total = len(records)
    width = _format_total(total)
    imported = 0
    skipped = 0
    failed = 0

    conn = get_db()
    try:
        _ensure_patch_exists(conn)
        conn.commit()

        for index, record in enumerate(records, start=1):
            try:
                tournament_id, status = _import_run(conn, record)
                conn.commit()
                if status == "imported":
                    imported += 1
                else:
                    skipped += 1
                print(
                    f"[migrate] run {index:0{width}d}/{total:0{width}d} "
                    f"tournament_id={tournament_id}"
                )
            except Exception as exc:
                conn.rollback()
                failed += 1
                run_no = record.get("run_no")
                print(
                    f"[migrate] run {index:0{width}d}/{total:0{width}d} "
                    f"failed run_no={run_no} error={exc}"
                )
    finally:
        conn.close()

    print(f"[migrate] done: {imported} imported, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
