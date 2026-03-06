import json
import glob
import os

export_dir = "data/export_latest"
json_files = glob.glob(os.path.join(export_dir, "*.json"))

results = []
adaption_keys_found = False

for file_path in json_files:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    initial_balance = data.get("config", {}).get("initial_balance", 0)
    final_balances = data.get("final_balances", {})
    winner = data.get("winner", "Unknown")
    
    # Check for adaption score
    if "adaption_score" in data or "adaptation_score" in data:
        adaption_keys_found = True
        
    for ai, end_bal in final_balances.items():
        net_gain = end_bal - initial_balance
        is_winner = (ai == winner)
        results.append({
            "file": os.path.basename(file_path),
            "ai": ai,
            "net_gain": net_gain,
            "final_balance": end_bal,
            "is_winner": is_winner,
            "data": data # store to extract excerpts later
        })

results.sort(key=lambda x: x["net_gain"], reverse=True)

print(f"Found {len(json_files)} JSON files.\n")
print(f"Top 5 Largest Winners (by Net Gain):")
for i, res in enumerate(results[:5]):
    print(f"{i+1}. {res['ai']} in {res['file']} - Net Gain: {res['net_gain']:.2f} (Final: {res['final_balance']:.2f})")

print("\nBottom 5 (Largest Losers):")
for i, res in enumerate(results[-5:]):
    print(f"{len(results)-4+i}. {res['ai']} in {res['file']} - Net Gain: {res['net_gain']:.2f} (Final: {res['final_balance']:.2f})")

print(f"\nWere adaption scores found in the root? {adaption_keys_found}")

# Search for adaption in any string or key
adaption_found_anywhere = False
import re
for file_path in json_files:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        if re.search(r'adapt[ia]on', content, re.IGNORECASE):
            adaption_found_anywhere = True
            print(f"Found 'adaption'/'adaptation' in {os.path.basename(file_path)}")

if not adaption_keys_found and not adaption_found_anywhere:
    print("No adaption scores were found in the JSON structures.")

# Print an excerpt from the largest winner
if results:
    best_res = results[0]
    best_ai = best_res["ai"]
    print(f"\n--- Excerpts from Best Career: {best_ai} in {best_res['file']} ---")
    data = best_res["data"]
    count = 0
    for round_data in data.get("rounds", []):
        for turn in round_data.get("turns", []):
            if turn.get("speaker") == best_ai and turn.get("type") == "argument":
                content = turn.get("content", "")
                # Extract first 300 chars
                excerpt = content[:300].replace('\n', ' ')
                print(f"Round {round_data['round_id']} Excerpt: {excerpt}...")
                count += 1
                if count >= 3: break
        if count >= 3: break
