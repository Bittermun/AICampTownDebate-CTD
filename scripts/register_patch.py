# TASK-005 output — see CODEX_QUEUE.md
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db.connection import get_db


DEFAULT_PATCHES = [
    {
        "version": "v1.0-20260304",
        "description": "Initial economy. Pot=40, self-judge.",
        "affected": [],
        "delta": {},
    },
    {
        "version": "v1.1-20260306",
        "description": "Economy fix: pot 40->200. External judge llama-3.3-70b.",
        "affected": [],
        "delta": {},
    },
    {
        "version": "v1.2-20260306",
        "description": "Deliberation prompt v2: cost ratio visible, delib cost disclosed.",
        "affected": [],
        "delta": {},
    },
]


def _is_sqlite(conn) -> bool:
    return conn.__class__.__module__.startswith("sqlite3")


def register_patch(conn, version: str, description: str, affected: list[str], delta):
    is_sqlite = _is_sqlite(conn)

    if is_sqlite:
        delta_value = json.dumps(delta)
        affected_value = json.dumps(affected)
    else:
        try:
            from psycopg2.extras import Json
        except Exception:
            Json = None
        delta_value = Json(delta) if Json else json.dumps(delta)
        affected_value = affected

    if is_sqlite:
        cur = conn.execute(
            """
            INSERT INTO patches (version, description, config_delta, affected_components)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(version) DO NOTHING
            """,
            (version, description, delta_value, affected_value),
        )
    else:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO patches (version, description, config_delta, affected_components)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(version) DO NOTHING
            """,
            (version, description, delta_value, affected_value),
        )

    rowcount = cur.rowcount
    if rowcount == 1:
        print(f"[patch] registered {version}")
    else:
        print("[patch] already exists, skipping")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version")
    parser.add_argument("--description")
    parser.add_argument("--affected")
    parser.add_argument("--delta")
    return parser.parse_args()


def parse_affected(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def main():
    args = parse_args()
    provided = [args.version, args.description, args.affected, args.delta]
    has_any = any(v is not None for v in provided)
    has_all = all(v is not None for v in provided)
    if has_any and not has_all:
        raise SystemExit("When using CLI flags, provide --version --description --affected --delta")

    conn = get_db()
    try:
        for patch in DEFAULT_PATCHES:
            register_patch(
                conn,
                patch["version"],
                patch["description"],
                patch["affected"],
                patch["delta"],
            )

        if has_all:
            try:
                delta = json.loads(args.delta)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid --delta JSON: {exc}") from exc
            register_patch(
                conn,
                args.version,
                args.description,
                parse_affected(args.affected),
                delta,
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
