#!/usr/bin/env python3
import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


TASK_RE = re.compile(r"^## TASK-([0-9]{3}[A-Z]?) \[status: ([^\]]+)\] \[batch: ([^\]]+)\]")
TITLE_RE = re.compile(r"^\*\*Title:\*\* (.+)$")


@dataclass
class Task:
    task_id: str
    status: str
    batch: str
    title: str


def parse_tasks(queue_text: str) -> list[Task]:
    lines = queue_text.splitlines()
    tasks: list[Task] = []
    i = 0
    while i < len(lines):
        m = TASK_RE.match(lines[i].strip())
        if not m:
            i += 1
            continue
        task_id, status, batch = m.group(1), m.group(2), m.group(3)
        title = ""
        for j in range(i + 1, min(i + 12, len(lines))):
            t = TITLE_RE.match(lines[j].strip())
            if t:
                title = t.group(1)
                break
        tasks.append(Task(task_id=task_id, status=status, batch=batch, title=title))
        i += 1
    return tasks


def write_handoff_template(path: Path, task: Task) -> None:
    text = (
        f"# TASK-{task.task_id} HANDOFF\n\n"
        f"owner:\n"
        f"batch: {task.batch}\n"
        f"changed_files:\n"
        f"spec_compliance:\n"
        f"verify_commands:\n"
        f"verify_raw_output:\n"
        f"blocked_rules_check:\n"
        f"risks:\n"
        f"unlocks:\n"
    )
    path.write_text(text, encoding="utf-8")


def write_gate_status(path: Path, tasks: list[Task]) -> None:
    grouped: dict[str, list[Task]] = {}
    for t in tasks:
        grouped.setdefault(t.batch, []).append(t)
    lines = ["# Gate Status", "", "Run-time gate board for Queue Lead and Verifier.", ""]
    for batch in sorted(grouped.keys()):
        lines.append(f"## Batch {batch}")
        for t in sorted(grouped[batch], key=lambda x: x.task_id):
            lines.append(f"- [ ] TASK-{t.task_id} | {t.title} | status={t.status}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_blockers(path: Path) -> None:
    text = """# Blocking Questions

- TASK-004 scope conflict: queue says do not touch non-listed files, but deleting old backends may require import updates in additional files.
- TASK-004 verify command is shell-specific (`tail -3`) and may fail in PowerShell.
- tournament_rounds uniqueness: per-agent and per-round uniqueness both appear; confirm intended invariant before TASK-008/009.
- fail_round(reason) contract is underspecified; define persistence location before TASK-008.
"""
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a gated run workspace from CODEX_QUEUE.md")
    parser.add_argument("--queue", default="CODEX_QUEUE.md", help="Path to queue markdown")
    parser.add_argument("--out-root", default="runs", help="Root output directory")
    parser.add_argument("--label", default="", help="Optional label suffix")
    args = parser.parse_args()

    queue_path = Path(args.queue)
    if not queue_path.exists():
        raise SystemExit(f"Queue file not found: {queue_path}")

    queue_text = queue_path.read_text(encoding="utf-8", errors="replace")
    tasks = parse_tasks(queue_text)
    if not tasks:
        raise SystemExit("No TASK entries found in queue file.")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{ts}_{args.label}" if args.label else ts
    run_dir = Path(args.out_root) / run_id
    handoffs_dir = run_dir / "handoffs"
    verify_logs_dir = run_dir / "verify_logs"
    notes_dir = run_dir / "notes"

    handoffs_dir.mkdir(parents=True, exist_ok=True)
    verify_logs_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "queue_file": str(queue_path),
        "tasks": [asdict(t) for t in tasks],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_gate_status(run_dir / "GATE_STATUS.md", tasks)
    write_blockers(run_dir / "BLOCKERS.md")

    for task in tasks:
        write_handoff_template(handoffs_dir / f"TASK-{task.task_id}.md", task)

    print(f"RUN_DIR={run_dir}")
    print(f"TASK_COUNT={len(tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
