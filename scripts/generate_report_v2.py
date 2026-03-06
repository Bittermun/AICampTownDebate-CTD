"""
generate_report_v2.py — Judge-independent metrics only.
Fitness and win/loss counts are excluded (contaminated by positional bias + binary signal).
Uses: mean_balance_edge, aggregate_score, pass_rate, health_score,
      aggression_rate, adaptation_gain, bets_per_round, tokens_per_round.
"""

import json, glob, csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE = Path(__file__).parent.parent
OUT  = BASE / "report_output"
OUT.mkdir(exist_ok=True)

# ── colours ────────────────────────────────────────────────────────────────
BG, AX, GR, TX = "#0f0f14", "#1a1a24", "#2e2e3e", "#d4d4d4"
C = {
    "ADAPT_ON_LOSS":  "#4e9af1",
    "ANTI_RAMBLE":    "#f4a442",
    "PUNISH_WEAKNESS":"#e05c5c",
    "Baseline":       "#888888",
    "overnight_rookie":  "#5bc98e",
    "overnight_veteran": "#4e9af1",
    "overnight_direct":  "#f4a442",
    "groq_multikey":     "#a478d4",
    "nvidia_afternoon":  "#e05c5c",
    "stable_125":        "#888888",
}

def style(ax, title, note=None):
    ax.set_facecolor(AX)
    ax.tick_params(colors=TX, labelsize=8.5)
    for s in ["top","right"]: ax.spines[s].set_visible(False)
    for s in ["bottom","left"]: ax.spines[s].set_color(GR)
    ax.yaxis.grid(True, color=GR, lw=0.5, alpha=0.6); ax.set_axisbelow(True)
    ax.set_title(title, color="white", fontsize=10.5, fontweight="bold", pad=7)
    for l in ax.get_xticklabels()+ax.get_yticklabels(): l.set_color(TX)
    if note:
        ax.text(0.99, 0.97, note, transform=ax.transAxes, ha="right", va="top",
                fontsize=7, color="#aaaaaa", style="italic")

# ══════════════════════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════════════════════

# -- Directives: mean_balance_edge (token economy delta, continuous) ------
real_camps = [
    "logs/evolution_campaign_20260302T163806Z",
    "logs/evolution_campaign_20260302T164759Z",
    "logs/evolution_campaign_20260302T165752Z",
    "logs/overnight_20260305T022154Z/4_evolution/evolution_campaign_20260305T134310Z",
]
dir_edge   = defaultdict(list)
dir_agg    = defaultdict(list)
dir_econ   = defaultdict(list)
dir_truth  = defaultdict(list)

for camp in real_camps:
    for path in glob.glob(f"{camp}/**/benchmark_summary.json", recursive=True):
        with open(path) as f: d = json.load(f)
        if not d.get("valid_run"): continue
        evo  = d.get("evolution", {})
        dirs = evo.get("candidate_profile", {}).get("directive_ids", []) or ["Baseline"]
        if len(dirs) != 1: continue
        label = dirs[0]
        edge = evo.get("mean_balance_edge")
        agg  = d.get("aggregate_score")
        gs   = d.get("group_scores", {})
        if edge is not None: dir_edge[label].append(edge)
        if agg  is not None: dir_agg[label].append(agg)
        if gs.get("economy_adaptation"): dir_econ[label].append(gs["economy_adaptation"])
        if gs.get("truth_core_core"):    dir_truth[label].append(gs["truth_core_core"])

DIR_ORDER = sorted(dir_edge.keys(), key=lambda d: -np.mean(dir_edge[d]))
edge_means  = [np.mean(dir_edge[d])  for d in DIR_ORDER]
edge_stds   = [np.std(dir_edge[d])   for d in DIR_ORDER]
agg_means   = [np.mean(dir_agg[d])   for d in DIR_ORDER]
econ_means  = [np.mean(dir_econ[d])  for d in DIR_ORDER]
truth_means = [np.mean(dir_truth[d]) for d in DIR_ORDER]

# -- Overnight conditions: behavioural metrics ----------------------------
COND_PAT = {
    "overnight_rookie":  "logs/overnight_20260305T022154Z/1_rookie/**/batch_summary.jsonl",
    "overnight_veteran": "logs/overnight_20260305T022154Z/2_veteran/**/batch_summary.jsonl",
    "overnight_direct":  "logs/overnight_20260305T022154Z/3_direct/**/batch_summary.jsonl",
    "groq_multikey":     "logs/groq_multikey_*/**/batch_summary.jsonl",
    "nvidia_afternoon":  "logs/nvidia_afternoon/**/batch_summary.jsonl",
}
COND_LABEL = {
    "overnight_rookie":  "Rookie\n(fresh)",
    "overnight_veteran": "Veteran\n(playbook)",
    "overnight_direct":  "Direct\n(prompted)",
    "groq_multikey":     "Groq\nmultikey",
    "nvidia_afternoon":  "Nvidia\nlocal",
}
cond_data = {}
for key, pat in COND_PAT.items():
    recs = []
    for f in glob.glob(pat, recursive=True):
        with open(f) as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line).get("record", {})
                    if r.get("success"): recs.append(r)
    if not recs: continue
    def safe_mean(field):
        vals = [r[field] for r in recs if r.get(field) is not None]
        return np.mean(vals) if vals else None
    cond_data[key] = {
        "pass_rate":   safe_mean("pass_rate"),
        "health":      safe_mean("health_score"),
        "aggression":  safe_mean("aggression_rate"),
        "adapt":       safe_mean("adaptation_gain_after_loss"),
        "rounds":      safe_mean("rounds_completed"),
        "n":           len(recs),
    }

# -- Token spend + bets per round -----------------------------------------
TOKEN_PAT = {
    "overnight_rookie":  "logs/overnight_20260305T022154Z/1_rookie/**/tournament_results.json",
    "overnight_veteran": "logs/overnight_20260305T022154Z/2_veteran/**/tournament_results.json",
    "overnight_direct":  "logs/overnight_20260305T022154Z/3_direct/**/tournament_results.json",
    "nvidia_afternoon":  "logs/nvidia_afternoon/**/tournament_results.json",
}
tok_data = {}
for key, pat in TOKEN_PAT.items():
    tokens, bets = [], []
    for f in glob.glob(pat, recursive=True):
        with open(f) as fh: d = json.load(fh)
        for r in d.get("rounds", []):
            ta, tb = r.get("tokens_a"), r.get("tokens_b")
            if ta and tb: tokens.append((ta+tb)/2)
            if r.get("bets"): bets.append(r["bets"])
    if tokens:
        tok_data[key] = {"tokens": np.mean(tokens), "bets": np.mean(bets) if bets else 0}

# ══════════════════════════════════════════════════════════════════════════
# FIGURE — 2 rows × 3 cols
# ══════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(20, 12), facecolor=BG)
fig.suptitle(
    "AIcamptowndebate — Honest Metrics (judge win/loss excluded)",
    fontsize=17, color="white", fontweight="bold", y=0.97
)

# ── P1: balance_edge per directive ────────────────────────────────────────
ax1 = fig.add_subplot(2, 3, 1)
colors1 = [C.get(d, "#bbbbbb") for d in DIR_ORDER]
x1 = np.arange(len(DIR_ORDER))
bars1 = ax1.bar(x1, edge_means, yerr=edge_stds, capsize=4,
                color=colors1, alpha=0.85, zorder=3, width=0.55,
                error_kw=dict(ecolor="#ffffff60", lw=1.2))
ax1.axhline(0, color="white", lw=0.8, alpha=0.4)
for i, (m, s, n) in enumerate(zip(edge_means, edge_stds, [len(dir_edge[d]) for d in DIR_ORDER])):
    ax1.text(i, m + s + 2, f"{m:+.1f}\n(n={n})", ha="center", fontsize=7.5, color=TX)
ax1.set_xticks(x1); ax1.set_xticklabels(DIR_ORDER, fontsize=8)
ax1.set_ylabel("Token balance edge", color=TX)
style(ax1, "Directives — Token Economy Edge",
      "Continuous metric; pos = directive debater\nfinished ahead in tokens on average")

# ── P2: benchmark aggregate scores ───────────────────────────────────────
ax2 = fig.add_subplot(2, 3, 2)
x2 = np.arange(len(DIR_ORDER))
w  = 0.25
ax2.bar(x2-w,   agg_means,   width=w, color=[C.get(d,"#bbb") for d in DIR_ORDER], alpha=0.85, zorder=3, label="Overall")
ax2.bar(x2,     truth_means, width=w, color=[C.get(d,"#bbb") for d in DIR_ORDER], alpha=0.55, zorder=3, label="Truth", hatch="//")
ax2.bar(x2+w,   econ_means,  width=w, color=[C.get(d,"#bbb") for d in DIR_ORDER], alpha=0.35, zorder=3, label="Economy", hatch="xx")
ax2.set_xticks(x2); ax2.set_xticklabels(DIR_ORDER, fontsize=8)
ax2.set_ylim(0.4, 0.7)
spread = max(agg_means)-min(agg_means)
ax2.set_ylabel("Score (0–1)", color=TX)
ax2.legend(fontsize=7.5, facecolor=AX, labelcolor=TX, edgecolor=GR)
style(ax2, "Directives — Benchmark Scores (no head-to-head)",
      f"Max spread = {spread:.3f} — within noise\nNo directive reliably beats Baseline here")

# ── P3: pass_rate vs health vs aggression ─────────────────────────────────
ax3 = fig.add_subplot(2, 3, 3)
cond_keys = list(cond_data.keys())
cond_lbls = [COND_LABEL[k] for k in cond_keys]
x3 = np.arange(len(cond_keys))
w3 = 0.25
pr = [cond_data[k]["pass_rate"] for k in cond_keys]
hs = [cond_data[k]["health"]    for k in cond_keys]
ag = [cond_data[k]["aggression"]for k in cond_keys]
cols3 = [C.get(k,"#bbb") for k in cond_keys]
ax3.bar(x3-w3, pr, width=w3, color=cols3, alpha=0.9,  zorder=3, label="HOLD rate")
ax3.bar(x3,    hs, width=w3, color=cols3, alpha=0.55, zorder=3, label="Health",    hatch="//")
ax3.bar(x3+w3, ag, width=w3, color=cols3, alpha=0.35, zorder=3, label="Aggression",hatch="xx")
ax3.set_xticks(x3); ax3.set_xticklabels(cond_lbls, fontsize=8)
ax3.set_ylim(0, 1.05)
ax3.set_ylabel("Rate / Score", color=TX)
ax3.legend(fontsize=7.5, facecolor=AX, labelcolor=TX, edgecolor=GR)
style(ax3, "Conditions — Behaviour Profile",
      "Veteran: high HOLD, low health\n→ playbook made it passive, not stronger")

# ── P4: adaptation gain on loss ───────────────────────────────────────────
ax4 = fig.add_subplot(2, 3, 4)
adapt_keys = [k for k in cond_keys if cond_data[k]["adapt"] is not None]
adapt_vals = [cond_data[k]["adapt"] for k in adapt_keys]
adapt_lbls = [COND_LABEL[k] for k in adapt_keys]
cols4 = [C.get(k,"#bbb") for k in adapt_keys]
bars4 = ax4.bar(np.arange(len(adapt_keys)), adapt_vals, color=cols4, alpha=0.85, zorder=3)
for i,v in enumerate(adapt_vals):
    ax4.text(i, v+0.0005, f"{v:.4f}", ha="center", fontsize=8, color=TX)
ax4.set_xticks(np.arange(len(adapt_keys)))
ax4.set_xticklabels(adapt_lbls, fontsize=8)
ax4.set_ylabel("Adaptation gain after loss", color=TX)
style(ax4, "Adaptation After Losing a Round",
      "Direct prompt shows most adaptation\nVeteran adapts least (relies on playbook)")

# ── P5: bets per round + tokens per round ────────────────────────────────
ax5 = fig.add_subplot(2, 3, 5)
tok_keys = list(tok_data.keys())
tok_lbls = [COND_LABEL[k] for k in tok_keys]
x5 = np.arange(len(tok_keys))
toks = [tok_data[k]["tokens"] for k in tok_keys]
bets = [tok_data[k]["bets"]   for k in tok_keys]
cols5 = [C.get(k,"#bbb") for k in tok_keys]
ax5b = ax5.twinx()
ax5.bar(x5-0.2, toks, width=0.35, color=cols5, alpha=0.8, zorder=3, label="Tokens/round (avg)")
ax5b.bar(x5+0.2,bets, width=0.35, color=cols5, alpha=0.45, zorder=3, label="Bets/round (avg)", hatch="//")
ax5.set_xticks(x5); ax5.set_xticklabels(tok_lbls, fontsize=8)
ax5.set_ylabel("Avg tokens per round", color=TX)
ax5b.set_ylabel("Avg bets per round", color="#aaaaaa", fontsize=8)
ax5b.tick_params(colors="#aaaaaa"); ax5b.spines[["top","right"]].set_color(GR)
ax5.legend(loc="upper left",  fontsize=7.5, facecolor=AX, labelcolor=TX, edgecolor=GR)
ax5b.legend(loc="upper right",fontsize=7.5, facecolor=AX, labelcolor=TX, edgecolor=GR)
style(ax5, "Token Spend & Betting Activity per Round",
      "'Direct' spends 50% more tokens than rookie\nVeteran barely bets (1.2/round vs 6.3)")

# ── P6: caveats & what the data can/can't say ────────────────────────────
ax6 = fig.add_subplot(2, 3, 6)
ax6.set_facecolor(AX)
ax6.set_axis_off()
ax6.set_title("What the data CAN and CANNOT say", color="white",
              fontsize=10.5, fontweight="bold", pad=7)
text = """
CANNOT conclude (contaminated):
  ✗  Any directive consistently wins debates
     (fitness is binary; ordering flips across campaigns)
  ✗  Veteran experience improves win rate
     (72-80% A/position bias across ALL Groq runs)
  ✗  Benchmark scores distinguish directives
     (max spread 0.023, 1 seed, degraded mode,
      all gates fail)

CAN conclude (judge-independent):
  ✓  ANTI_RAMBLE + PUNISH keep token balance higher
     on average (+27 edge) vs ADAPT_ON_LOSS (−4)
  ✓  Veteran playbook changed behaviour dramatically:
     HOLD rate 83%, bets 1.2/round → passivity, not skill
  ✓  Direct prompt spends 50% more tokens but adapts
     most on loss (0.028 vs veteran 0.014)
  ✓  Rookie debaters are most active (6.3 bets/round,
     0.81 aggression) with healthy scores (0.66)
  ✓  System produces real debate post-prompt-fix
     (pass_rate 0.55-0.57, not degenerate 0.0 or 1.0)

To make any stronger claim, need:
  → External judge (different model/provider)
  → 5+ seeds per candidate
  → Larger populations (10+)
"""
ax6.text(0.04, 0.95, text, transform=ax6.transAxes, va="top",
         fontsize=8.2, color=TX, family="monospace",
         linespacing=1.55)

plt.tight_layout(rect=[0, 0, 1, 0.95])
out_path = OUT / "debate_report_v2.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved: {out_path}")
