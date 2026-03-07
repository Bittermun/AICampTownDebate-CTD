# TASK-014 output - see CODEX_QUEUE.md
import argparse
import json
import os
import signal
from datetime import datetime

from src.arena.dynamic_round import DynamicDebateRound
from src.config_loader import load_config
from src.db.agent_registry import apply_patch_notification, register_agent
from src.db.config_bridge import register_from_yaml
from src.db.connection import get_db
from src.db.leaderboard import get_leaderboard
from src.db.ops import (
    add_participant,
    create_tournament,
    set_participant_final_balance,
    update_agent_state,
    update_tournament_status,
)
from src.db.resume import get_resumable_tournament, get_resume_point
from src.db.round_writer import RoundWriter
from src.economy import BettingManager, TokenDistributor, TokenLedger
from src.models import Debater, DebaterConfig
from src.models.judge import JudgeConfig, LLMJudge
from src.runtime import normalize_model_path

PATCH_VERSION = "v1.2-20260306"


def _normalize_model_id(model: str) -> str:
    value = (model or "").strip()
    for prefix in ("openai:", "ollama:", "vllm:"):
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def _build_debater(spec, initial_balance: float) -> Debater:
    return Debater(
        DebaterConfig(
            model_path=normalize_model_path(spec.model),
            name=f"Debater_{spec.name}",
            system_prompt=spec.system_prompt,
            ev_guard_enabled=spec.ev_guard_enabled,
            ev_guard_min_ev=spec.ev_guard_min_ev,
            ev_guard_edge_scale=spec.ev_guard_edge_scale,
            low_balance_threshold=spec.low_balance_threshold,
            low_balance_bet_cap=spec.low_balance_bet_cap,
            kelly_enabled=spec.kelly_enabled,
            kelly_scale=spec.kelly_scale,
            kelly_cap=spec.kelly_cap,
            verbosity_scale_enabled=spec.verbosity_scale_enabled,
            verbosity_base_tokens=spec.verbosity_base_tokens,
            initial_balance_ref=initial_balance,
            multi_agent_enabled=spec.multi_agent_enabled,
            multi_agent_mode=spec.multi_agent_mode,
            multi_agent_max_tokens=spec.multi_agent_max_tokens,
            multi_agent_min_balance=spec.multi_agent_min_balance,
        )
    )


def _build_judge(cfg) -> LLMJudge:
    judge_spec = cfg.judges[0]
    return LLMJudge(
        JudgeConfig(
            model_path=normalize_model_path(judge_spec.model),
            name=judge_spec.name or "Judge_Main",
            randomize_argument_order=cfg.randomize_argument_order,
        )
    )


def _new_tournament_id(seed: int | None) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if seed is None:
        return f"league_{ts}"
    return f"league_{ts}_seed{seed}"


def _ensure_participant(conn, tournament_id: str, agent_id: str, role: str, starting_balance: int) -> None:
    try:
        add_participant(conn, tournament_id, agent_id, role, starting_balance)
    except Exception:
        # already exists on resume/idempotent rerun
        return


def _restore_balance(ledger: TokenLedger, debater_name: str, target_balance: float, round_id: int) -> None:
    current = ledger.balance(debater_name)
    delta = float(target_balance) - current
    if delta > 0:
        ledger.award(debater_name, delta, "resume_restore", round_id)
    elif delta < 0:
        ledger.deduct(debater_name, abs(delta), "resume_restore", round_id)


def _update_career(conn, agent_id: str, won: bool, lost: bool, roi: float, current_balance: float) -> None:
    row = conn.execute(
        "SELECT career_roi FROM agents WHERE id = ?",
        (agent_id,),
    ).fetchone()
    prev_roi = float(row["career_roi"]) if row and row["career_roi"] is not None else 0.0
    blended_roi = (prev_roi + float(roi)) / 2.0
    update_agent_state(
        conn,
        agent_id,
        career_wins=(1 if won else 0) + int(conn.execute("SELECT career_wins FROM agents WHERE id = ?", (agent_id,)).fetchone()["career_wins"]),
        career_losses=(1 if lost else 0) + int(conn.execute("SELECT career_losses FROM agents WHERE id = ?", (agent_id,)).fetchone()["career_losses"]),
        career_roi=blended_roi,
        current_balance=int(round(current_balance)),
        last_active_at=datetime.utcnow().isoformat(),
    )


def _apply_patch_note(conn, agent_id: str, debater: Debater) -> None:
    note = apply_patch_notification(conn, agent_id, PATCH_VERSION)
    if not note:
        return
    base = debater.config.system_prompt or ""
    debater.config.system_prompt = f"{note}\n\n{base}" if base else note
    update_agent_state(conn, agent_id, last_patch_applied=PATCH_VERSION)


def run_league(config_path: str, tournament_id: str | None = None, seed: int | None = None) -> int:
    cfg = load_config(config_path)
    conn = get_db()
    started_at = datetime.utcnow().isoformat()

    if "OPENAI_COMPAT_BASE_URL" not in os.environ:
        raise RuntimeError("OPENAI_COMPAT_BASE_URL must be set")
    base_url = os.environ["OPENAI_COMPAT_BASE_URL"]

    debater_a = _build_debater(cfg.debaters[0], cfg.economy.initial_balance)
    debater_b = _build_debater(cfg.debaters[1], cfg.economy.initial_balance)
    judge = _build_judge(cfg)

    aid_a = register_agent(conn, _normalize_model_id(cfg.debaters[0].model), base_url)
    aid_b = register_agent(conn, _normalize_model_id(cfg.debaters[1].model), base_url)
    jid = register_agent(conn, _normalize_model_id(cfg.judges[0].model), base_url)
    register_from_yaml(conn, config_path)

    resumable = None
    if tournament_id:
        resumable = get_resumable_tournament(conn, tournament_id)

    if resumable:
        start_round = get_resume_point(conn, tournament_id)
        print(f"[league] resuming tournament {tournament_id} from round {start_round}")
        update_tournament_status(conn, tournament_id, "running", started_at=started_at)
    else:
        if not tournament_id:
            tournament_id = _new_tournament_id(seed)
        print(f"[league] starting new tournament {tournament_id}")
        create_tournament(
            conn,
            tournament_id,
            json.dumps({"config_path": config_path}, ensure_ascii=True),
            PATCH_VERSION,
            seed,
        )
        update_tournament_status(conn, tournament_id, "running", started_at=started_at)
        start_round = 1

    _ensure_participant(conn, tournament_id, aid_a, "debater_a", int(cfg.economy.initial_balance))
    _ensure_participant(conn, tournament_id, aid_b, "debater_b", int(cfg.economy.initial_balance))
    _ensure_participant(conn, tournament_id, jid, "judge", int(cfg.economy.initial_balance))
    conn.commit()

    ledger = TokenLedger(cfg.economy.initial_balance, cfg.economy.max_debt)
    betting = BettingManager(0.05, 5.0)
    distributor = TokenDistributor(cfg.economy.tokens_per_round)
    ledger.register(debater_a.name)
    ledger.register(debater_b.name)

    if resumable:
        pa = conn.execute(
            "SELECT final_balance FROM tournament_participants WHERE tournament_id=? AND agent_id=? AND role='debater_a'",
            (tournament_id, aid_a),
        ).fetchone()
        pb = conn.execute(
            "SELECT final_balance FROM tournament_participants WHERE tournament_id=? AND agent_id=? AND role='debater_b'",
            (tournament_id, aid_b),
        ).fetchone()
        if pa and pa["final_balance"] is not None:
            _restore_balance(ledger, debater_a.name, float(pa["final_balance"]), start_round)
        if pb and pb["final_balance"] is not None:
            _restore_balance(ledger, debater_b.name, float(pb["final_balance"]), start_round)

    debater_a.load_model()
    debater_b.load_model()
    judge.load_model()

    try:
        total_rounds = int(cfg.rounds.num_rounds)
        for round_id in range(start_round, total_rounds + 1):
            _apply_patch_note(conn, aid_a, debater_a)
            _apply_patch_note(conn, aid_b, debater_b)
            conn.commit()

            topic = cfg.rounds.topics[(round_id - 1) % len(cfg.rounds.topics)]
            writer = RoundWriter(conn, tournament_id, PATCH_VERSION)
            round_engine = DynamicDebateRound(
                debater_a,
                debater_b,
                judge,
                ledger,
                betting,
                distributor,
                max_iterations=cfg.rounds.max_iterations,
                split_pot_enabled=cfg.economy.split_pot_enabled,
                initial_pot_amount=cfg.economy.initial_pot_amount,
                round_writer=writer,
            )
            result = round_engine.run(topic, round_id, transcript=None)
            set_participant_final_balance(conn, tournament_id, aid_a, int(round(ledger.balance(debater_a.name))))
            set_participant_final_balance(conn, tournament_id, aid_b, int(round(ledger.balance(debater_b.name))))
            conn.commit()
            print(
                f"[league] round {round_id}/{total_rounds} done: "
                f"A={result.final_judgment.confidence_a:.3f} B={result.final_judgment.confidence_b:.3f}"
            )
    except KeyboardInterrupt:
        update_tournament_status(
            conn,
            tournament_id,
            "failed",
            ended_at=datetime.utcnow().isoformat(),
            notes="paused via KeyboardInterrupt",
        )
        conn.commit()
        print("[league] paused")
        return 130
    except Exception as exc:
        update_tournament_status(
            conn,
            tournament_id,
            "failed",
            ended_at=datetime.utcnow().isoformat(),
            notes=f"error: {exc}",
        )
        conn.commit()
        raise
    finally:
        debater_a.unload_model()
        debater_b.unload_model()
        judge.unload_model()

    bal_a = ledger.balance(debater_a.name)
    bal_b = ledger.balance(debater_b.name)
    winner = aid_a if bal_a > bal_b else aid_b if bal_b > bal_a else None
    update_tournament_status(
        conn,
        tournament_id,
        "completed",
        ended_at=datetime.utcnow().isoformat(),
        winner_agent_id=winner,
    )
    _update_career(conn, aid_a, won=(winner == aid_a), lost=(winner == aid_b), roi=(bal_a - cfg.economy.initial_balance) / max(cfg.economy.initial_balance, 1.0), current_balance=bal_a)
    _update_career(conn, aid_b, won=(winner == aid_b), lost=(winner == aid_a), roi=(bal_b - cfg.economy.initial_balance) / max(cfg.economy.initial_balance, 1.0), current_balance=bal_b)
    conn.commit()

    print("[league] leaderboard top 10")
    for i, row in enumerate(get_leaderboard(conn, limit=10), start=1):
        print(
            f"{i:02d}. {row.get('name')} roi={row.get('career_roi')} "
            f"W={row.get('career_wins')} L={row.get('career_losses')}"
        )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DB-backed resumable league tournament.")
    parser.add_argument("--config", required=True, help="Path to tournament YAML config")
    parser.add_argument("--tournament-id", default=None, help="Existing tournament id to resume")
    parser.add_argument("--seed", type=int, default=None, help="Optional seed")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_league(args.config, args.tournament_id, args.seed)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.default_int_handler)
    raise SystemExit(main())
