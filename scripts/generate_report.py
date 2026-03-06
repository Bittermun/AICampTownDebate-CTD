"""
generate_report.py — 4-panel debate arena results report
Reads CSVs from tmp/rapid_extracts/ and outputs report_output/debate_report.png
"""

import csv
import os
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE = Path(__file__).parent.parent
EXTRACTS = BASE / "tmp" / "rapid_extracts"
OUT = BASE / "report_output"
OUT.mkdir(exist_ok=True)

# ── load CSVs ──────────────────────────────────────────────────────────────
def load_csv(name):
    with open(EXTRACTS / name) as f:
        return list(csv.DictReader(f))

evo_rows   = load_csv("evolution_leaderboard_flat.csv")
night_rows = load_csv("overnight_batch_summaries_metrics.csv")
lc_rows    = load_csv("tournament_learning_curve.csv")
groq_rows  = load_csv("groq_multikey_batch_aggregate.csv")

# ── palette ────────────────────────────────────────────────────────────────
COLORS = {
    "ADAPT_ON_LOSS":       "#4e9af1",
    "ANTI_RAMBLE":         "#f4a442",
    "PUNISH_WEAKNESS":     "#e05c5c",
    "ANTI_RAMBLE;PRESS_EDGE": "#a478d4",
    "PUNISH_WEAKNESS;PRESS_EDGE": "#d46078",
    "Baseline":            "#888888",
    "1_rookie":  "#5bc98e",
    "2_veteran": "#4e9af1",
    "3_direct":  "#f4a442",
}

# ══════════════════════════════════════════════════════════════════════════
# PANEL 1 — Evolution: per-campaign results (NOT pooled — campaigns contradict each other)
# ══════════════════════════════════════════════════════════════════════════
import json, re

CAMP_PATHS = {
    "164759Z\n(3 gens)": "logs/evolution_campaign_20260302T164759Z/campaign_report.json",
    "165752Z\n(ref run)": "logs/evolution_campaign_20260302T165752Z/campaign_report.json",
    "overnight\nevo": "logs/overnight_20260305T022154Z/4_evolution/evolution_campaign_20260305T134310Z/campaign_report.json",
}
DIRECTIVE_ORDER = ["ADAPT_ON_LOSS", "ANTI_RAMBLE", "PUNISH_WEAKNESS", "Baseline"]
DIR_COLORS = {
    "ADAPT_ON_LOSS":  "#4e9af1",
    "ANTI_RAMBLE":    "#f4a442",
    "PUNISH_WEAKNESS":"#e05c5c",
    "Baseline":       "#888888",
}

# For each campaign, get Gen 0 top fitness per directive (canonical comparison)
camp_results = {}  # camp_label -> {directive -> fitness}
for camp_label, path in CAMP_PATHS.items():
    with open(BASE / path) as f:
        d = json.load(f)
    gr = d.get("generation_records", [])
    gen0 = gr[0].get("leaderboard", []) if gr else []
    by_dir = {}
    for c in gen0:
        dirs = c.get("profile", {}).get("directive_ids", []) or []
        fit = c.get("fitness", None)
        if fit is None or fit < -0.1:
            continue
        label = dirs[0] if len(dirs) == 1 else (";".join(dirs) if dirs else "Baseline")
        if label not in by_dir or fit > by_dir[label]:
            by_dir[label] = fit
    camp_results[camp_label] = by_dir

# ══════════════════════════════════════════════════════════════════════════
# PANEL 2 — Overnight: pass_rate & health by condition
# ══════════════════════════════════════════════════════════════════════════
cond_data = defaultdict(lambda: {"pass_rate": [], "health_score": []})
for r in night_rows:
    c = r["condition"]
    if r["pass_rate"]:   cond_data[c]["pass_rate"].append(float(r["pass_rate"]))
    if r["health_score"]:cond_data[c]["health_score"].append(float(r["health_score"]))

cond_order   = ["1_rookie", "2_veteran", "3_direct"]
cond_labels  = ["Rookie\n(fresh)", "Veteran\n(playbook)", "Direct\n(prompted)"]
avg_pass     = [statistics.mean(cond_data[c]["pass_rate"])    for c in cond_order]
avg_health   = [statistics.mean(cond_data[c]["health_score"]) for c in cond_order]
cond_colors  = [COLORS[c] for c in cond_order]

# ══════════════════════════════════════════════════════════════════════════
# PANEL 3 — Learning curves: a_improvement distribution
# ══════════════════════════════════════════════════════════════════════════
lc_valid = [r for r in lc_rows if r["a_improvement"] and r["b_improvement"]]
a_imps = [float(r["a_improvement"]) for r in lc_valid]
b_imps = [float(r["b_improvement"]) for r in lc_valid]

# clip extreme outliers for readability (keep 95th pct)
clip = np.percentile(np.abs(a_imps + b_imps), 95) * 1.5

# ══════════════════════════════════════════════════════════════════════════
# PANEL 4 — Groq multikey: success rate & alpha/beta win ratio over time
# ══════════════════════════════════════════════════════════════════════════
groq_valid = [r for r in groq_rows if int(r["runs_success"]) > 0]
groq_labels = [r["batch_id"].replace("groq_multikey_", "").replace("Z", "") for r in groq_valid]
groq_alpha  = [int(r["winner_debater_alpha_count"]) for r in groq_valid]
groq_beta   = [int(r["winner_debater_beta_count"])  for r in groq_valid]
groq_pr     = [float(r["pass_rate_mean"]) if r["pass_rate_mean"] else 0 for r in groq_valid]

# ══════════════════════════════════════════════════════════════════════════
# DRAW
# ══════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(18, 13), facecolor="#0f0f14")
fig.suptitle(
    "AIcamptowndebate — Results Overview",
    fontsize=18, color="white", fontweight="bold", y=0.97
)

axes_bg = "#1a1a24"
grid_c  = "#2e2e3e"
text_c  = "#d4d4d4"

def style_ax(ax, title):
    ax.set_facecolor(axes_bg)
    ax.tick_params(colors=text_c, labelsize=9)
    ax.spines[["top","right"]].set_visible(False)
    ax.spines[["bottom","left"]].set_color(grid_c)
    ax.yaxis.grid(True, color=grid_c, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    ax.set_title(title, color="white", fontsize=11, fontweight="bold", pad=8)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(text_c)

# ── P1 ─────────────────────────────────────────────────────────────────────
ax1 = fig.add_subplot(2, 2, 1)
camp_labels_list = list(camp_results.keys())
n_camps = len(camp_labels_list)
n_dirs  = len(DIRECTIVE_ORDER)
w = 0.2
x1 = np.arange(n_camps)

for di, directive in enumerate(DIRECTIVE_ORDER):
    vals = [camp_results[c].get(directive, None) for c in camp_labels_list]
    offsets = x1 + (di - n_dirs/2 + 0.5) * w
    for xi, v in zip(offsets, vals):
        if v is not None:
            ax1.bar(xi, v, width=w*0.9, color=DIR_COLORS[directive], alpha=0.85, zorder=3)
            ax1.text(xi, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=7, color=text_c)
        else:
            ax1.text(xi, 0.02, "—", ha="center", va="bottom", fontsize=8, color="#555555")

ax1.set_xticks(x1)
ax1.set_xticklabels(camp_labels_list, fontsize=8.5)
ax1.set_ylim(0, 0.85)
ax1.set_ylabel("Fitness (Gen 0)", color=text_c)
legend_patches = [mpatches.Patch(color=DIR_COLORS[d], label=d) for d in DIRECTIVE_ORDER]
ax1.legend(handles=legend_patches, fontsize=7.5, facecolor=axes_bg, labelcolor=text_c, edgecolor=grid_c, loc="lower right")
style_ax(ax1, "Q1 · Directives — Per-Campaign (NOT pooled, results vary)")
ax1.text(0.01, 0.97, "⚠ Ordering flips between campaigns — no single directive consistently wins",
         transform=ax1.transAxes, va="top", fontsize=7.5, color="#f4a442", style="italic")

# ── P2 ─────────────────────────────────────────────────────────────────────
ax2 = fig.add_subplot(2, 2, 2)
x2 = np.arange(len(cond_labels))
w = 0.33
b1 = ax2.bar(x2 - w/2, avg_pass,   width=w, color=[COLORS[c] for c in cond_order], alpha=0.85, zorder=3, label="Pass/HOLD rate")
b2 = ax2.bar(x2 + w/2, avg_health, width=w, color=[COLORS[c] for c in cond_order], alpha=0.45, zorder=3, label="Health score", hatch="//")
for i, (p, h) in enumerate(zip(avg_pass, avg_health)):
    ax2.text(i - w/2, p + 0.01, f"{p:.2f}", ha="center", fontsize=8.5, color=text_c)
    ax2.text(i + w/2, h + 0.01, f"{h:.2f}", ha="center", fontsize=8.5, color=text_c)
ax2.set_xticks(x2)
ax2.set_xticklabels(cond_labels, fontsize=9)
ax2.set_ylim(0, 1.05)
ax2.set_ylabel("Rate / Score", color=text_c)
ax2.legend(fontsize=8, facecolor=axes_bg, labelcolor=text_c, edgecolor=grid_c)
style_ax(ax2, "Q2 · Does Experience Help? (Overnight 3-Condition)")
note = "Veteran holds more (high HOLD rate)\nbut lower health — overly conservative?"
ax2.text(0.97, 0.05, note, transform=ax2.transAxes, ha="right", va="bottom",
         fontsize=7.5, color="#aaaaaa", style="italic")

# ── P3 ─────────────────────────────────────────────────────────────────────
ax3 = fig.add_subplot(2, 2, 3)
a_clip = np.clip(a_imps, -clip, clip)
b_clip = np.clip(b_imps, -clip, clip)
ax3.hist(a_clip, bins=30, alpha=0.7, color="#4e9af1", label=f"Debater A (n={len(a_clip)})", zorder=3)
ax3.hist(b_clip, bins=30, alpha=0.7, color="#f4a442", label=f"Debater B (n={len(b_clip)})", zorder=3)
ax3.axvline(0, color="white", linewidth=1, linestyle="--", alpha=0.5)
a_pos = sum(1 for x in a_imps if x > 0)
b_pos = sum(1 for x in b_imps if x > 0)
ax3.set_xlabel("Efficiency improvement (late − early avg)", color=text_c)
ax3.set_ylabel("Count", color=text_c)
ax3.legend(fontsize=8, facecolor=axes_bg, labelcolor=text_c, edgecolor=grid_c)
style_ax(ax3, "Q3 · Do Agents Improve Within a Tournament?")
note2 = f"A improves: {a_pos}/{len(a_imps)} ({100*a_pos//len(a_imps)}%)   B improves: {b_pos}/{len(b_imps)} ({100*b_pos//len(b_imps)}%)\nMean near 0 — no consistent learning signal yet"
ax3.text(0.97, 0.95, note2, transform=ax3.transAxes, ha="right", va="top",
         fontsize=7.5, color="#aaaaaa", style="italic")

# ── P4 ─────────────────────────────────────────────────────────────────────
ax4 = fig.add_subplot(2, 2, 4)
if groq_valid:
    x4 = np.arange(len(groq_labels))
    ax4.bar(x4, groq_alpha, color="#4e9af1", alpha=0.85, label="Alpha wins", zorder=3)
    ax4.bar(x4, groq_beta,  bottom=groq_alpha, color="#f4a442", alpha=0.85, label="Beta wins", zorder=3)
    ax4_r = ax4.twinx()
    ax4_r.plot(x4, groq_pr, color="#5bc98e", linewidth=2, marker="o", markersize=5, label="Pass rate", zorder=5)
    ax4_r.set_ylim(0, 1.0)
    ax4_r.set_ylabel("Pass rate", color="#5bc98e", fontsize=9)
    ax4_r.tick_params(colors="#5bc98e")
    ax4_r.spines[["top"]].set_visible(False)
    ax4_r.spines[["right"]].set_color(grid_c)
    ax4.set_xticks(x4)
    ax4.set_xticklabels([l[8:] for l in groq_labels], rotation=35, ha="right", fontsize=7)
    ax4.set_ylabel("Win count", color=text_c)
    ax4.legend(loc="upper left", fontsize=8, facecolor=axes_bg, labelcolor=text_c, edgecolor=grid_c)
    ax4_r.legend(loc="upper right", fontsize=8, facecolor=axes_bg, labelcolor=text_c, edgecolor=grid_c)
    tot_a = sum(groq_alpha); tot_b = sum(groq_beta)
    ax4.text(0.5, 0.92, f"Total: Alpha {tot_a}  Beta {tot_b}  ({100*tot_a//(tot_a+tot_b)}% / {100*tot_b//(tot_a+tot_b)}%)",
             transform=ax4.transAxes, ha="center", color=text_c, fontsize=8.5)
else:
    ax4.text(0.5, 0.5, "No successful Groq multikey runs\n(all failed on rate limits)",
             transform=ax4.transAxes, ha="center", va="center", color=text_c, fontsize=10)
style_ax(ax4, "Q4 · Groq Multikey — Alpha vs Beta Win Rate")

plt.tight_layout(rect=[0, 0, 1, 0.95])
out_path = OUT / "debate_report.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved: {out_path}")
