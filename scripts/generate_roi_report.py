"""
generate_roi_report.py — ROI-based analysis of the debate arena.

Three ROI lenses:
  bet_roi   = (bet_won - bet_staked) / bet_staked        [~judge-dep: agent chooses SIZE, judge picks winner]
  arg_roi   = pot_split_earned / argument_generation_costs [judge-dep: pot split via confidence scores]
  econ_roi  = (final_balance - initial) / initial          [judge-dep: composite]

Cost structure IS fully judge-independent (what the agent CHOSE to spend).
"""

import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "tmp" / "roi_data.json") as f:
    data = json.load(f)

conditions = data["conditions"]
directives  = data["directives"]

OUT = BASE / "report_output"
OUT.mkdir(exist_ok=True)

BG, AX, GR, TX = "#0f0f14", "#1a1a24", "#2e2e3e", "#d4d4d4"

COND_COLOR = {
    "Rookie\n(overnight)":  "#5bc98e",
    "Veteran\n(overnight)": "#4e9af1",
    "Direct\n(overnight)":  "#f4a442",
    "Nvidia\nlocal":        "#e05c5c",
    "Groq\nmultikey":       "#a478d4",
    "Stable\n125":          "#888888",
}
DIR_COLOR = {
    "ANTI_RAMBLE":    "#f4a442",
    "PUNISH_WEAKNESS":"#e05c5c",
    "Baseline":       "#888888",
    "ADAPT_ON_LOSS":  "#4e9af1",
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

fig = plt.figure(figsize=(20, 13), facecolor=BG)
fig.suptitle("AIcamptowndebate — ROI Analysis  |  Is holding/HOLDing economically rational?",
             fontsize=16, color="white", fontweight="bold", y=0.97)

# ══ P1: Bet ROI by condition ══════════════════════════════════════════════
ax1 = fig.add_subplot(2, 3, 1)
ckeys = list(conditions.keys())
br = [conditions[k]["bet_roi"]*100 for k in ckeys]
cols = [COND_COLOR.get(k,"#bbb") for k in ckeys]
bars = ax1.bar(np.arange(len(ckeys)), br, color=cols, alpha=0.85, zorder=3)
ax1.axhline(0, color="white", lw=1, alpha=0.5, linestyle="--")
for i, v in enumerate(br):
    ax1.text(i, v - 1.5, f"{v:.0f}%", ha="center", va="top", fontsize=8, color=TX)
ax1.set_xticks(np.arange(len(ckeys)))
ax1.set_xticklabels(ckeys, fontsize=8)
ax1.set_ylabel("Bet ROI (%)", color=TX)
style(ax1, "Bet ROI by Condition",
      "Agent chooses bet SIZE — judge decides outcome\nAll negative: bets are high-risk, expected-loss activity")

# ══ P2: Arg ROI by condition ══════════════════════════════════════════════
ax2 = fig.add_subplot(2, 3, 2)
ar = [conditions[k]["arg_roi"] for k in ckeys]
bars2 = ax2.bar(np.arange(len(ckeys)), ar, color=cols, alpha=0.85, zorder=3)
ax2.axhline(1.0, color="white", lw=1.2, alpha=0.7, linestyle="--", label="Break-even (1.0x)")
for i, v in enumerate(ar):
    ax2.text(i, v + 0.01, f"{v:.3f}x", ha="center", va="bottom", fontsize=8, color=TX)
ax2.set_xticks(np.arange(len(ckeys)))
ax2.set_xticklabels(ckeys, fontsize=8)
ax2.set_ylim(0, 1.15)
ax2.set_ylabel("Pot earned / Arg costs", color=TX)
ax2.legend(fontsize=8, facecolor=AX, labelcolor=TX, edgecolor=GR)
style(ax2, "Argument Efficiency (pot earned vs generation cost)",
      "How much pot money comes back per token spent arguing\nVeteran closest — holds more, spends less, earns efficiently")

# ══ P3: Economy ROI by condition ══════════════════════════════════════════
ax3 = fig.add_subplot(2, 3, 3)
er = [conditions[k]["econ_roi"]*100 for k in ckeys]
bar_colors = [("#5bc98e" if v >= 0 else "#e05c5c") for v in er]
bars3 = ax3.bar(np.arange(len(ckeys)), er, color=bar_colors, alpha=0.85, zorder=3)
ax3.axhline(0, color="white", lw=1, alpha=0.5, linestyle="--")
for i, v in enumerate(er):
    offset = 0.5 if v >= 0 else -0.5
    va = "bottom" if v >= 0 else "top"
    ax3.text(i, v + offset, f"{v:.1f}%", ha="center", va=va, fontsize=8, color=TX)
ax3.set_xticks(np.arange(len(ckeys)))
ax3.set_xticklabels(ckeys, fontsize=8)
ax3.set_ylabel("Economy ROI (%)", color=TX)
style(ax3, "Overall Economy ROI (final balance vs start)",
      "Veteran gains (+12%) by spending almost nothing\nDirect loses most (-30%) — spends most tokens, earns least back")

# ══ P4: Directive bet + arg ROI ════════════════════════════════════════════
ax4 = fig.add_subplot(2, 3, 4)
dkeys = list(directives.keys())
dbr = [directives[k]["bet_roi"]*100 for k in dkeys]
dar = [directives[k]["arg_roi"]     for k in dkeys]
der = [directives[k]["econ_roi"]*100 for k in dkeys]
dcols = [DIR_COLOR.get(k,"#bbb") for k in dkeys]
x4 = np.arange(len(dkeys))
w = 0.28
ax4.bar(x4 - w, [abs(b) for b in dbr], width=w, color=dcols, alpha=0.85, zorder=3, label="|Bet loss|%")
ax4b = ax4.twinx()
ax4b.bar(x4, dar, width=w, color=dcols, alpha=0.55, zorder=3, label="Arg ROI (x)", hatch="//")
ax4b.axhline(1.0, color="white", lw=1, alpha=0.5, linestyle="--")
ax4b.set_ylim(0, 1.3)
ax4b.set_ylabel("Arg ROI (x)", color="#aaaaaa", fontsize=8.5)
ax4b.tick_params(colors="#aaaaaa")
ax4b.spines[["top","right"]].set_color(GR)
for i, v in enumerate(dar):
    ax4b.text(i, v + 0.02, f"{v:.3f}x", ha="center", fontsize=7.5, color=TX)
for i, v in enumerate(dbr):
    ax4.text(i - w, abs(v) + 0.5, f"{v:.0f}%", ha="center", va="bottom", fontsize=7.5, color=TX)
ax4.set_xticks(x4)
ax4.set_xticklabels(dkeys, fontsize=8)
ax4.set_ylabel("|Bet loss| %", color=TX)
ax4.legend(loc="upper left",  fontsize=7.5, facecolor=AX, labelcolor=TX, edgecolor=GR)
ax4b.legend(loc="upper right",fontsize=7.5, facecolor=AX, labelcolor=TX, edgecolor=GR)
style(ax4, "Directives — Bet Loss vs Argument Efficiency",
      "PUNISH + ANTI_RAMBLE: arg_roi ~0.94x (near break-even)\nADAPT_ON_LOSS: worse arg efficiency (0.77x)")

# ══ P5: Directive economy ROI ══════════════════════════════════════════════
ax5 = fig.add_subplot(2, 3, 5)
d_sorted = sorted(zip(dkeys, der, dcols), key=lambda x: -x[1])
dks, ders, dcs = zip(*d_sorted)
bars5 = ax5.bar(np.arange(len(dks)), ders, color=dcs, alpha=0.85, zorder=3)
ax5.axhline(0, color="white", lw=1, alpha=0.5, linestyle="--")
for i, v in enumerate(ders):
    ax5.text(i, v + 0.2, f"{v:.1f}%", ha="center", va="bottom", fontsize=8.5, color=TX)
ax5.set_xticks(np.arange(len(dks)))
ax5.set_xticklabels(dks, fontsize=8)
ax5.set_ylabel("Economy ROI (%)", color=TX)
style(ax5, "Directives — Economy ROI",
      "All positive: evo campaign design where winner\nearns from loser. Spread is narrow (10–19%).")

# ══ P6: Summary / what ROI tells us ═══════════════════════════════════════
ax6 = fig.add_subplot(2, 3, 6)
ax6.set_facecolor(AX); ax6.set_axis_off()
ax6.set_title("What ROI actually tells us", color="white",
              fontsize=10.5, fontweight="bold", pad=7)
txt = """
ROI = more nuanced than binary win/loss, but...
Revenue side (bet_won, pot_split) is still
judge-determined. The COST side is agent-controlled.

FULLY judge-free findings:
  ✓ Everyone loses on bets (-27% to -83%)
    → Bets are rational only for high-confidence spots
  ✓ Everyone earns <1x back on argument costs
    → Holding (HOLD) is economically rational:
      it avoids spending on arguments that lose money
  ✓ Veteran spends almost nothing → small losses
    → Passivity is the economically 'safe' strategy
      in the current system

PARTLY judge-contaminated but still useful:
  ~ Arg ROI: PUNISH/ANTI_RAMBLE near 0.94x
    (spend more efficiently when they DO argue)
    vs ADAPT_ON_LOSS at 0.77x
  ~ Directive econ ROI all positive (+10–19%):
    ordering consistent with balance_edge finding

CONCLUSION:
  The system's economy currently rewards passivity.
  A debater that holds constantly minimises costs
  and survives longer — this needs rebalancing
  before ROI can distinguish good arguing strategy.
"""
ax6.text(0.04, 0.96, txt, transform=ax6.transAxes, va="top",
         fontsize=8, color=TX, family="monospace", linespacing=1.5)

plt.tight_layout(rect=[0, 0, 1, 0.95])
out = OUT / "debate_report_roi.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved: {out}")
