#!/usr/bin/env python3
"""
Tournament HTML Dashboard Generator

Reads a transcript JSON and produces a self-contained HTML file with:
  - Balance trajectory chart (line chart, per-round)
  - Confidence trajectory chart (per-iteration within a round)
  - Bet event markers
  - Selection health score badge
  - Kelly regret display

Usage:
    python src/analysis/tournament_html.py
    python src/analysis/tournament_html.py logs/tournament_results_transcript.json
    python src/analysis/tournament_html.py logs/last_run_transcript.json --out logs/dashboard.html
"""
import sys
import json
import argparse
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.analysis.selection_health import compute_selection_health


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tournament Dashboard — {title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3e;
    --text: #e2e8f0; --muted: #94a3b8;
    --a: #60a5fa; --b: #f472b6; --accent: #a78bfa;
    --green: #34d399; --red: #f87171; --yellow: #fbbf24;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif;
          padding: 24px; min-height: 100vh; }}
  h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 4px; color: var(--text); }}
  .subtitle {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
  .grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
  @media (max-width: 768px) {{ .grid, .grid-3 {{ grid-template-columns: 1fr; }} }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }}
  .card h2 {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em;
              color: var(--muted); margin-bottom: 16px; }}
  .chart-wrap {{ position: relative; height: 200px; }}
  .stat {{ display: flex; justify-content: space-between; align-items: center;
           padding: 8px 0; border-bottom: 1px solid var(--border); }}
  .stat:last-child {{ border-bottom: none; }}
  .stat-label {{ color: var(--muted); font-size: 0.85rem; }}
  .stat-value {{ font-weight: 600; font-size: 0.9rem; }}
  .badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px;
            border-radius: 9999px; font-size: 0.8rem; font-weight: 600; }}
  .badge-green {{ background: rgba(52,211,153,0.15); color: var(--green); border: 1px solid rgba(52,211,153,0.3); }}
  .badge-yellow {{ background: rgba(251,191,36,0.15); color: var(--yellow); border: 1px solid rgba(251,191,36,0.3); }}
  .badge-red {{ background: rgba(248,113,113,0.15); color: var(--red); border: 1px solid rgba(248,113,113,0.3); }}
  .winner-a {{ color: var(--a); }}
  .winner-b {{ color: var(--b); }}
  .winner-tie {{ color: var(--muted); }}
  .bet-event {{ display: flex; gap: 8px; align-items: center; padding: 6px 0;
                border-bottom: 1px solid var(--border); font-size: 0.82rem; }}
  .bet-event:last-child {{ border-bottom: none; }}
  .dot-a {{ width: 8px; height: 8px; border-radius: 50%; background: var(--a); flex-shrink: 0; }}
  .dot-b {{ width: 8px; height: 8px; border-radius: 50%; background: var(--b); flex-shrink: 0; }}
  .health-bar {{ height: 6px; border-radius: 3px; background: var(--border); margin-top: 6px; }}
  .health-fill {{ height: 100%; border-radius: 3px; transition: width 0.6s ease; }}
  .footer {{ color: var(--muted); font-size: 0.75rem; margin-top: 24px; text-align: center; }}
</style>
</head>
<body>
<h1>🏆 Tournament Dashboard</h1>
<p class="subtitle">{subtitle}</p>

<div class="grid">
  <!-- Confidence Trajectory Chart -->
  <div class="card">
    <h2>Confidence Trajectory</h2>
    <div class="chart-wrap"><canvas id="confChart"></canvas></div>
  </div>

  <!-- Balance Summary -->
  <div class="card">
    <h2>Final Standings</h2>
    {standings_html}
    <div style="margin-top:16px">
      <div class="stat"><span class="stat-label">Winner</span>
        <span class="stat-value {winner_class}">{winner}</span></div>
      <div class="stat"><span class="stat-label">Duration</span>
        <span class="stat-value">{duration}</span></div>
      <div class="stat"><span class="stat-label">Total Iterations</span>
        <span class="stat-value">{total_iters}</span></div>
    </div>
  </div>
</div>

<div class="grid-3">
  <!-- Health Dashboard -->
  <div class="card">
    <h2>Selection Health</h2>
    <div style="margin-bottom:12px;">
      {health_badge}
      <div class="health-bar" style="margin-top:10px;">
        <div class="health-fill" style="width:{health_pct}%; background:{health_color};"></div>
      </div>
    </div>
    <div class="stat"><span class="stat-label">Judge Margin</span>
      <span class="stat-value">{judge_margin:.3f}</span></div>
    <div class="stat"><span class="stat-label">Adaptation ↑loss</span>
      <span class="stat-value">{adaptation:+.3f}</span></div>
    <div class="stat"><span class="stat-label">Economy Reasoning</span>
      <span class="stat-value">{economy_pct:.0f}%</span></div>
    <div class="stat"><span class="stat-label">Pass Rate</span>
      <span class="stat-value">{pass_rate:.0f}% <span style="color:var(--muted);font-size:0.75rem">(target 35%)</span></span></div>
  </div>

  <!-- Bet Events -->
  <div class="card">
    <h2>Bet Events</h2>
    {bet_events_html}
  </div>

  <!-- Score Distribution -->
  <div class="card">
    <h2>Score Distribution</h2>
    <div class="chart-wrap"><canvas id="scoreChart"></canvas></div>
  </div>
</div>

<p class="footer">Generated {generated_at} · AICampTownDebate</p>

<script>
const confData = {conf_data_json};
const scoreData = {score_data_json};

// Confidence trajectory chart
new Chart(document.getElementById('confChart'), {{
  type: 'line',
  data: {{
    labels: confData.labels,
    datasets: [
      {{ label: 'Debater A', data: confData.a, borderColor: '#60a5fa', backgroundColor: 'rgba(96,165,250,0.1)',
         tension: 0.4, fill: true, pointRadius: 5, pointHoverRadius: 8 }},
      {{ label: 'Debater B', data: confData.b, borderColor: '#f472b6', backgroundColor: 'rgba(244,114,182,0.1)',
         tension: 0.4, fill: true, pointRadius: 5, pointHoverRadius: 8 }},
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8', boxWidth: 12 }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8', font: {{ size: 11 }} }}, grid: {{ color: '#2a2d3e' }} }},
      y: {{ min: 0, max: 1, ticks: {{ color: '#94a3b8', font: {{ size: 11 }},
           callback: v => (v*100).toFixed(0)+'%' }}, grid: {{ color: '#2a2d3e' }} }}
    }}
  }}
}});

// Score distribution bar chart
new Chart(document.getElementById('scoreChart'), {{
  type: 'bar',
  data: {{
    labels: scoreData.labels,
    datasets: [
      {{ label: 'A', data: scoreData.a, backgroundColor: 'rgba(96,165,250,0.7)', borderRadius: 4 }},
      {{ label: 'B', data: scoreData.b, backgroundColor: 'rgba(244,114,182,0.7)', borderRadius: 4 }},
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8', boxWidth: 12 }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8', font: {{ size: 10 }} }}, grid: {{ color: '#2a2d3e' }} }},
      y: {{ min: 0, max: 1, ticks: {{ color: '#94a3b8', font: {{ size: 11 }},
           callback: v => (v*100).toFixed(0)+'%' }}, grid: {{ color: '#2a2d3e' }} }}
    }}
  }}
}});
</script>
</body>
</html>"""


def _health_badge(score: float) -> tuple[str, str, str]:
    """Returns (badge_html, color_hex, pct_str)."""
    pct = f"{score * 100:.0f}"
    if score >= 0.6:
        return f'<span class="badge badge-green">✓ Healthy {score:.3f}</span>', "#34d399", pct
    elif score >= 0.35:
        return f'<span class="badge badge-yellow">⚠ Marginal {score:.3f}</span>', "#fbbf24", pct
    else:
        return f'<span class="badge badge-red">✗ Degenerate {score:.3f}</span>', "#f87171", pct


def generate_dashboard(transcript_path: str, ledger_path: str | None, out_path: str):
    with open(transcript_path, encoding="utf-8") as f:
        transcript = json.load(f)
    ledger = None
    if ledger_path and Path(ledger_path).exists():
        with open(ledger_path, encoding="utf-8") as f:
            ledger = json.load(f)

    cfg = transcript.get("config", {})
    rounds = transcript.get("rounds", [])
    started = transcript.get("started_at", "")[:19]
    ended = transcript.get("ended_at", "")[:19]
    winner = transcript.get("winner") or "TIE"
    final_bals = transcript.get("final_balances", {})

    debater_names = list(final_bals.keys()) if final_bals else ["A", "B"]
    name_a = debater_names[0] if debater_names else "A"
    name_b = debater_names[1] if len(debater_names) > 1 else "B"

    # ── Confidence trajectory ─────────────────────────────────────────────────
    conf_labels, conf_a, conf_b = [], [], []
    score_labels, score_a_vals, score_b_vals = [], [], []

    for r in rounds:
        round_id = r.get("round_id", "?")
        turns = r.get("turns", [])
        judgments = [t for t in turns if t.get("type") == "judgment"]
        for j_idx, j in enumerate(judgments):
            ca = float(j.get("confidence_a", 0.5))
            cb = float(j.get("confidence_b", 0.5))
            label = f"R{round_id}·J{j_idx+1}"
            conf_labels.append(label)
            conf_a.append(round(ca, 4))
            conf_b.append(round(cb, 4))
        # Final judgment for score distribution
        if judgments:
            lj = judgments[-1]
            score_labels.append(f"Rd {round_id}")
            score_a_vals.append(round(float(lj.get("confidence_a", 0.5)), 4))
            score_b_vals.append(round(float(lj.get("confidence_b", 0.5)), 4))

    conf_data_json = json.dumps({"labels": conf_labels, "a": conf_a, "b": conf_b})
    score_data_json = json.dumps({"labels": score_labels, "a": score_a_vals, "b": score_b_vals})

    # ── Bet events ────────────────────────────────────────────────────────────
    bet_htmls = []
    for r in rounds:
        turns = r.get("turns", [])
        for t in turns:
            if t.get("type") != "deliberation":
                continue
            content = t.get("content", "")
            speaker = t.get("speaker", "?")
            dec_m = re.search(r"\*\*Decision\*\*:\s*(\w+)", content)
            amt_m = re.search(r"\*\*Bet Amount\*\*:\s*([\d.]+)", content)
            if dec_m and dec_m.group(1).upper() == "RESPOND":
                amt = float(amt_m.group(1)) if amt_m else 0.0
                dot_class = "dot-a" if name_a in speaker else "dot-b"
                bet_htmls.append(
                    f'<div class="bet-event"><div class="{dot_class}"></div>'
                    f'<span>{speaker}</span><span style="margin-left:auto;font-weight:600">{amt:.1f} tok</span></div>'
                )
    if not bet_htmls:
        bet_htmls = ['<p style="color:var(--muted);font-size:0.85rem">No RESPOND bets in this transcript</p>']
    bet_events_html = "\n".join(bet_htmls)

    # ── Standings HTML ────────────────────────────────────────────────────────
    bal_a = final_bals.get(name_a, 0)
    bal_b = final_bals.get(name_b, 0)
    standings_html = f"""
    <div style="display:flex;gap:12px;margin-bottom:4px;">
      <div style="flex:1;background:rgba(96,165,250,0.1);border:1px solid rgba(96,165,250,0.3);
                  border-radius:8px;padding:12px;text-align:center;">
        <div style="color:#60a5fa;font-weight:700;font-size:1.1rem">{name_a}</div>
        <div style="font-size:1.5rem;font-weight:800;margin:4px 0">{bal_a:.1f}</div>
        <div style="color:var(--muted);font-size:0.8rem">tokens</div>
      </div>
      <div style="flex:1;background:rgba(244,114,182,0.1);border:1px solid rgba(244,114,182,0.3);
                  border-radius:8px;padding:12px;text-align:center;">
        <div style="color:#f472b6;font-weight:700;font-size:1.1rem">{name_b}</div>
        <div style="font-size:1.5rem;font-weight:800;margin:4px 0">{bal_b:.1f}</div>
        <div style="color:var(--muted);font-size:0.8rem">tokens</div>
      </div>
    </div>"""

    winner_class = "winner-a" if winner == name_a else ("winner-b" if winner == name_b else "winner-tie")

    # ── Health Dashboard ──────────────────────────────────────────────────────
    health = compute_selection_health(transcript, ledger=ledger)
    health_badge_html, health_color, health_pct = _health_badge(health.health_score)

    # ── Duration ──────────────────────────────────────────────────────────────
    total_iters = sum(
        max((j.get("iteration", 1) for j in r.get("turns", []) if j.get("type") == "judgment"), default=1)
        for r in rounds
    )
    duration = f"{len(rounds)} round{'s' if len(rounds) != 1 else ''}"

    # ── Title / subtitle ──────────────────────────────────────────────────────
    from datetime import datetime, timezone
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subtitle = f"{name_a} vs {name_b}  ·  {started}  ·  {len(rounds)} round{'s' if len(rounds) != 1 else ''}"

    html = _HTML_TEMPLATE.format(
        title=f"{name_a} vs {name_b}",
        subtitle=subtitle,
        standings_html=standings_html,
        winner=winner,
        winner_class=winner_class,
        duration=duration,
        total_iters=total_iters,
        health_badge=health_badge_html,
        health_pct=health_pct,
        health_color=health_color,
        judge_margin=health.judge_margin_mean,
        adaptation=health.adaptation_gain_after_loss,
        economy_pct=health.economy_reasoning_rate * 100,
        pass_rate=health.pass_rate * 100,
        bet_events_html=bet_events_html,
        conf_data_json=conf_data_json,
        score_data_json=score_data_json,
        generated_at=generated_at,
    )

    Path(out_path).write_text(html, encoding="utf-8")
    print(f"Dashboard written to: {Path(out_path).resolve()}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generate HTML tournament dashboard")
    parser.add_argument(
        "transcript",
        nargs="?",
        default="logs/tournament_results_transcript.json",
        help="Path to transcript JSON",
    )
    parser.add_argument("--ledger", default=None, help="Path to ledger JSON")
    parser.add_argument("--out", default=None, help="Output HTML path")
    args = parser.parse_args()

    transcript_path = args.transcript
    if not Path(transcript_path).exists():
        fallback = "logs/last_run_transcript.json"
        if Path(fallback).exists():
            transcript_path = fallback
            print(f"[INFO] Using fallback: {fallback}")
        else:
            print(f"[ERROR] Transcript not found: {args.transcript}")
            sys.exit(1)

    ledger_path = args.ledger or str(
        Path(transcript_path).parent / (Path(transcript_path).stem.replace("_transcript", "_ledger") + ".json")
    )

    out_path = args.out or str(
        Path(transcript_path).parent / (Path(transcript_path).stem.replace("_transcript", "") + "_dashboard.html")
    )

    generate_dashboard(transcript_path, ledger_path, out_path)


if __name__ == "__main__":
    main()
