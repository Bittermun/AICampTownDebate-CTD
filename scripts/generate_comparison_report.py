"""
generate_comparison_report.py
Rookie (clean_100, n=99) vs Veteran (veteran_quick, n=20) side-by-side comparison.
First fair head-to-head under correct economy + external judge.
"""

import json, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

BASE = Path(__file__).parent.parent
OUT  = BASE / "report_output"
OUT.mkdir(exist_ok=True)

def load(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(l)["record"] for l in lines if l.strip() and json.loads(l)["record"]["success"]]

rookie  = load(BASE / "logs/clean_overnight_01/clean_100/batch_summary.jsonl")
veteran = load(BASE / "logs/clean_overnight_01/veteran_quick/batch_summary.jsonl")

def stats(data, key):
    vals = [r[key] for r in data]
    return statistics.mean(vals), statistics.stdev(vals) if len(vals) > 1 else 0, vals

BG, AX, GR, TX = "#0f0f14", "#1a1a24", "#2e2e3e", "#d4d4d4"
CR, CV, C_RED = "#4e9af1", "#f4a442", "#e05c5c"

def style(ax, title, note=None):
    ax.set_facecolor(AX)
    ax.tick_params(colors=TX, labelsize=9)
    for s in ["top","right"]:  ax.spines[s].set_visible(False)
    for s in ["bottom","left"]: ax.spines[s].set_color(GR)
    ax.yaxis.grid(True, color=GR, lw=0.5, alpha=0.6); ax.set_axisbelow(True)
    ax.set_title(title, color="white", fontsize=10.5, fontweight="bold", pad=8)
    for l in ax.get_xticklabels()+ax.get_yticklabels(): l.set_color(TX)
    if note:
        ax.text(0.99, 0.97, note, transform=ax.transAxes, ha="right", va="top",
                fontsize=7.5, color="#aaaaaa", style="italic")

fig = plt.figure(figsize=(22, 14), facecolor=BG)
fig.suptitle(
    "Rookie vs Veteran  |  First fair comparison: fixed economy + external judge",
    fontsize=15, color="white", fontweight="bold", y=0.98
)

x = np.array([0, 1])
labels = [f"Rookie\n(n={len(rookie)})", f"Veteran\n(n={len(veteran)})"]

# ── P1: Pass Rate ─────────────────────────────────────────────────────────────
ax1 = fig.add_subplot(2, 3, 1)
rm, rs, rv = stats(rookie,  "pass_rate")
vm, vs, vv = stats(veteran, "pass_rate")
bars = ax1.bar(x, [rm, vm], color=[CR, CV], alpha=0.85, width=0.5, zorder=3,
               yerr=[rs, vs], capsize=6, error_kw=dict(color=TX, lw=1.5))
ax1.axhline(0.5, color="white", lw=1, linestyle="--", alpha=0.5, label="50% reference")
for i, (v, m) in enumerate([(rm, "0.49"), (vm, "0.78")]):
    ax1.text(i, v + vs + 0.03, m, ha="center", fontsize=11, fontweight="bold", color=TX)
ax1.set_xticks(x); ax1.set_xticklabels(labels, fontsize=9)
ax1.set_ylabel("Fraction of turns argued", color=TX)
ax1.set_ylim(0, 1.1)
ax1.legend(fontsize=8, facecolor=AX, labelcolor=TX, edgecolor=GR)
style(ax1, "Pass Rate  (how often they argue)",
      "Veteran argues MORE, not less\nEV-guard fires but not on argue/hold decision")

# ── P2: Health Score ──────────────────────────────────────────────────────────
ax2 = fig.add_subplot(2, 3, 2)
rm, rs, rv = stats(rookie,  "health_score")
vm, vs, vv = stats(veteran, "health_score")
bars2 = ax2.bar(x, [rm, vm], color=[CR, CV], alpha=0.85, width=0.5, zorder=3,
                yerr=[rs, vs], capsize=6, error_kw=dict(color=TX, lw=1.5))
ax2.axhline(0.5, color=C_RED, lw=1.2, linestyle=":", alpha=0.7, label="Min threshold")
for i, (v, m) in enumerate([(rm, "0.70"), (vm, "0.52")]):
    ax2.text(i, v + vs + 0.01, m, ha="center", fontsize=11, fontweight="bold", color=TX)
ax2.set_xticks(x); ax2.set_xticklabels(labels, fontsize=9)
ax2.set_ylabel("Health score (0-1)", color=TX)
ax2.set_ylim(0, 1.0)
ax2.legend(fontsize=8, facecolor=AX, labelcolor=TX, edgecolor=GR)
style(ax2, "Debate Health Score",
      "Rookie debates more balanced\nVeteran's aggression asymmetry hurts health")

# ── P3: Adaptation Gain ───────────────────────────────────────────────────────
ax3 = fig.add_subplot(2, 3, 3)
rm, rs, rv = stats(rookie,  "adaptation_gain_after_loss")
vm, vs, vv = stats(veteran, "adaptation_gain_after_loss")
bars3 = ax3.bar(x, [rm, vm], color=[CR, CV], alpha=0.85, width=0.5, zorder=3,
                yerr=[rs, vs], capsize=6, error_kw=dict(color=TX, lw=1.5))
ax3.axhline(0, color="white", lw=1, linestyle="--", alpha=0.5)
for i, (v, m) in enumerate([(rm, "0.033"), (vm, "0.047")]):
    ax3.text(i, v + vs + 0.002, m, ha="center", fontsize=11, fontweight="bold", color=TX)
ax3.set_xticks(x); ax3.set_xticklabels(labels, fontsize=9)
ax3.set_ylabel("Avg gain after falling behind", color=TX)
style(ax3, "Adaptation After Loss  (learning signal)",
      "Veteran adapts slightly better (+42%)\nADAPT_ON_LOSS directive may be working")

# ── P4: Pass Rate Distributions (violin/strip) ────────────────────────────────
ax4 = fig.add_subplot(2, 3, 4)
_, _, rv = stats(rookie,  "pass_rate")
_, _, vv = stats(veteran, "pass_rate")
vp = ax4.violinplot([rv, vv], positions=x, widths=0.5, showmedians=True)
for pc, col in zip(vp["bodies"], [CR, CV]):
    pc.set_facecolor(col); pc.set_alpha(0.6)
for part in ["cmedians","cbars","cmins","cmaxes"]:
    vp[part].set_color(TX); vp[part].set_linewidth(1.5)
ax4.set_xticks(x); ax4.set_xticklabels(labels, fontsize=9)
ax4.set_ylabel("Pass rate distribution", color=TX)
ax4.set_ylim(0, 1.1)
style(ax4, "Pass Rate Distribution (all runs)",
      "Veteran tightly clustered at 0.78\nRookie spreads 0.3-0.7 (more variable)")

# ── P5: Aggression Rate ───────────────────────────────────────────────────────
ax5 = fig.add_subplot(2, 3, 5)
rm, rs, rv = stats(rookie,  "aggression_rate")
vm, vs, vv = stats(veteran, "aggression_rate")
bars5 = ax5.bar(x, [rm, vm], color=[CR, CV], alpha=0.85, width=0.5, zorder=3,
                yerr=[rs, vs], capsize=6, error_kw=dict(color=TX, lw=1.5))
for i, (v, m) in enumerate([(rm, "0.51"), (vm, "0.22")]):
    ax5.text(i, v + vs + 0.01, m, ha="center", fontsize=11, fontweight="bold", color=TX)
ax5.set_xticks(x); ax5.set_xticklabels(labels, fontsize=9)
ax5.set_ylabel("Aggression rate", color=TX)
ax5.set_ylim(0, 0.8)
style(ax5, "Aggression Rate  (bet sizing)",
      "Veteran bets far more conservatively\nKelly + EV-guard doing their job")

# ── P6: Summary ───────────────────────────────────────────────────────────────
ax6 = fig.add_subplot(2, 3, 6)
ax6.set_facecolor(AX); ax6.set_axis_off()
ax6.set_title("What This Means", color="white", fontsize=10.5, fontweight="bold", pad=8)
txt = """
Rookie (no directives, no guardrails):
  pass_rate  0.491   health  0.700
  adaptation 0.033   aggress 0.509

Veteran (directives + kelly + ev-guard):
  pass_rate  0.782   health  0.521
  adaptation 0.047   aggress 0.218

KEY FINDINGS:

1. VETERAN ARGUES MORE (0.78 vs 0.49)
   Unexpected. Directives make them commit
   to responding rather than holding back.
   EV-guard is NOT suppressing argue/hold —
   it only limits BET SIZE once committed.

2. VETERAN HEALTH IS LOWER (0.52 vs 0.70)
   High pass rate + low aggression = one
   side talks a lot but bets little. Debates
   become lopsided in token spend.

3. VETERAN ADAPTS BETTER (+42% gain)
   ADAPT_ON_LOSS directive appears to work.
   Weak signal (n=20) but consistent direction.

4. VETERAN IS MORE CONSERVATIVE ON BETS
   Aggression 0.22 vs 0.51. Kelly criterion
   is working — veterans stake less per bet.

CONCLUSION:
   Directives change behavior, but not always
   as intended. High pass rate + low aggression
   is a new failure mode: they argue cheaply
   but don't stake their conviction.
   Next: tune directives to reward conviction.
"""
ax6.text(0.04, 0.97, txt, transform=ax6.transAxes, va="top",
         fontsize=8.2, color=TX, family="monospace", linespacing=1.45)

# Legend
legend_patches = [
    mpatches.Patch(color=CR, label=f"Rookie (n={len(rookie)}, seeds 5010-5109)"),
    mpatches.Patch(color=CV, label=f"Veteran (n={len(veteran)}, seeds 6001-6020)"),
]
fig.legend(handles=legend_patches, loc="lower center", ncol=2,
           fontsize=9, facecolor=AX, labelcolor=TX, edgecolor=GR,
           bbox_to_anchor=(0.5, 0.01))

plt.tight_layout(rect=[0, 0.04, 1, 0.96])
out = OUT / "rookie_vs_veteran.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved: {out}")
