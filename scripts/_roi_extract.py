import json, glob, os
from collections import defaultdict

def compute_roi(path):
    with open(path) as f:
        ledger = json.load(f)
    initial = ledger['initial_balance']
    per = defaultdict(lambda: defaultdict(float))
    for tx in ledger['transactions']:
        reason = tx.get('reason','')
        amt = tx.get('amount', 0)
        frm, to = tx.get('from'), tx.get('to')
        if reason == 'bet_stake' and frm:             per[frm]['bet_stake'] += amt
        elif reason == 'bet_fee' and frm:             per[frm]['bet_fee'] += amt
        elif reason.startswith('bet_won') and to:     per[to]['bet_won'] += amt
        elif reason == 'pot_split' and to:            per[to]['pot_split'] += amt
        elif reason == 'generation_cost' and frm:     per[frm]['gen_cost'] += amt
        elif reason == 'deliberation_cost' and frm:   per[frm]['delib_cost'] += amt
        elif reason == 'search_tool_cost' and frm:    per[frm]['search_cost'] += amt
        elif reason == 'summarization_cost' and frm:  per[frm]['summ_cost'] += amt
    for debater, bal in ledger['balances'].items():
        per[debater]['final_balance'] = bal
        per[debater]['initial'] = initial
    out = {}
    for debater, d in per.items():
        arg_costs = d['gen_cost'] + d['delib_cost'] + d['search_cost'] + d['summ_cost']
        out[debater] = {
            'bet_roi':   (d['bet_won'] - d['bet_stake']) / d['bet_stake'] if d['bet_stake'] > 0 else None,
            'arg_roi':   d['pot_split'] / arg_costs if arg_costs > 0 else None,
            'econ_roi':  (d['final_balance'] - d['initial']) / d['initial'] if d['initial'] > 0 else None,
            'gen_cost':  d['gen_cost'],  'delib_cost': d['delib_cost'],
            'search_cost': d['search_cost'], 'bet_stake': d['bet_stake'],
            'bet_won': d['bet_won'], 'pot_split': d['pot_split'],
        }
    return out

# --- conditions ---
SOURCES = {
    "Rookie\n(overnight)":   "logs/overnight_20260305T022154Z/1_rookie/**/tournament_results_ledger.json",
    "Veteran\n(overnight)":  "logs/overnight_20260305T022154Z/2_veteran/**/tournament_results_ledger.json",
    "Direct\n(overnight)":   "logs/overnight_20260305T022154Z/3_direct/**/tournament_results_ledger.json",
    "Nvidia\nlocal":         "logs/nvidia_afternoon/**/tournament_results_ledger.json",
    "Groq\nmultikey":        "logs/groq_multikey_*/**/tournament_results_ledger.json",
    "Stable\n125":           "logs/stable_campaign_125/**/tournament_results_ledger.json",
}

cond_roi = {}
for label, pattern in SOURCES.items():
    files = glob.glob(pattern, recursive=True)
    br_all, ar_all, er_all = [], [], []
    gn_all, dl_all, sc_all, bs_all = [], [], [], []
    for fpath in files:
        try:
            roi = compute_roi(fpath)
            for d in roi.values():
                if d['bet_roi'] is not None:  br_all.append(d['bet_roi'])
                if d['arg_roi'] is not None:  ar_all.append(d['arg_roi'])
                if d['econ_roi'] is not None: er_all.append(d['econ_roi'])
                gn_all.append(d['gen_cost']); dl_all.append(d['delib_cost'])
                sc_all.append(d['search_cost']); bs_all.append(d['bet_stake'])
        except: pass
    avg = lambda x: sum(x)/len(x) if x else None
    cond_roi[label] = {
        'n': len(files),
        'bet_roi': avg(br_all), 'arg_roi': avg(ar_all), 'econ_roi': avg(er_all),
        'gen_cost': avg(gn_all), 'delib_cost': avg(dl_all),
        'search_cost': avg(sc_all), 'bet_stake': avg(bs_all),
    }

# --- directives from evo campaigns ---
real_camps = [
    "logs/evolution_campaign_20260302T163806Z",
    "logs/evolution_campaign_20260302T164759Z",
    "logs/evolution_campaign_20260302T165752Z",
    "logs/overnight_20260305T022154Z/4_evolution/evolution_campaign_20260305T134310Z",
]
dir_roi = defaultdict(lambda: {'bet_roi':[], 'arg_roi':[], 'econ_roi':[]})

for camp_path in real_camps:
    ledgers = glob.glob(os.path.join(camp_path, "**", "tournament_results_ledger.json"), recursive=True)
    summaries = {}
    for s in glob.glob(os.path.join(camp_path, "**", "benchmark_summary.json"), recursive=True):
        key = os.path.dirname(s)
        summaries[os.path.normpath(key)] = s

    for lpath in ledgers:
        # ledger is at gen_XX/g00_cXX/artifacts/benchmark_artifacts/seed_101/ledger.json
        # summary is at gen_XX/g00_cXX/benchmark_summary.json  (3 levels up from ledger dir)
        cand_dir = os.path.normpath(os.path.dirname(lpath))
        for _ in range(3):
            cand_dir = os.path.dirname(cand_dir)
        cand_dir = os.path.normpath(cand_dir)
        summary_path = summaries.get(cand_dir)
        if not summary_path:
            continue
        try:
            with open(summary_path) as f:
                s = json.load(f)
            dirs = s.get('evolution',{}).get('candidate_profile',{}).get('directive_ids',[]) or ['Baseline']
            if len(dirs) != 1: continue
            directive = dirs[0]
            roi = compute_roi(lpath)
            for d in roi.values():
                if d['bet_roi'] is not None:  dir_roi[directive]['bet_roi'].append(d['bet_roi'])
                if d['arg_roi'] is not None:  dir_roi[directive]['arg_roi'].append(d['arg_roi'])
                if d['econ_roi'] is not None: dir_roi[directive]['econ_roi'].append(d['econ_roi'])
        except: pass

avg = lambda x: sum(x)/len(x) if x else None
dir_roi_summary = {
    d: {k: avg(v) for k,v in vals.items()}
    for d, vals in dir_roi.items()
}

print("CONDITION ROI:")
for label, d in cond_roi.items():
    print(f"  {label.replace(chr(10),' '):22s} n={d['n']} bet_roi={d['bet_roi']:+.1%} arg_roi={d['arg_roi']:.3f}x econ_roi={d['econ_roi']:+.4%}")
print("\nDIRECTIVE ROI:")
for directive, d in sorted(dir_roi_summary.items(), key=lambda x: -(x[1].get('econ_roi') or -999)):
    n = len(dir_roi[directive]['econ_roi'])
    print(f"  {directive:22s} n={n} bet_roi={d['bet_roi']:+.1%} arg_roi={d['arg_roi']:.3f}x econ_roi={d['econ_roi']:+.4%}")

# Save for viz
import json as _json
with open("tmp/roi_data.json","w") as f:
    _json.dump({"conditions": {k: {kk: vv for kk,vv in v.items()} for k,v in cond_roi.items()},
                "directives": dir_roi_summary}, f, indent=2)
print("\nSaved tmp/roi_data.json")
