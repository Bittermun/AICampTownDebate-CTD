import os
import json
import glob
import shutil
from datetime import datetime

TARGET_DIRS = [
    "logs/stable_campaign_125",
    "logs/test_tmp_training_contracts",
    "logs/benchmark_artifacts",
    "logs/20260303T200411Z",
    "logs/batch",
    "logs/evolution_campaign*",
    "logs/groq_multikey*"
]

MIN_HEALTH_SCORE = 0.3

# Create export directory
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
export_dir = os.path.join("data", f"export_{timestamp}")
os.makedirs(export_dir, exist_ok=True)

print(f"Exporting valid data (Health >= {MIN_HEALTH_SCORE}) to: {export_dir}")
print("-" * 60)

exported_count = 0
aggregated_data = []

for d in TARGET_DIRS:
    base_dirs = glob.glob(d)
    for bd in base_dirs:
        if not os.path.exists(bd):
            continue
        
        pattern = os.path.join(bd, "**", "*selection_health*.json")
        health_files = glob.glob(pattern, recursive=True)
        
        for hf_path in health_files:
            try:
                with open(hf_path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                    
                health = data.get("health_score", 0.0)
                if health >= MIN_HEALTH_SCORE:
                    run_dir = os.path.dirname(hf_path)
                    
                    # Find the transcript JSON and MD
                    transcript_json = os.path.join(run_dir, "tournament_results_transcript.json")
                    if not os.path.exists(transcript_json):
                        # Some older formats might not have the "tournament_results_" prefix
                        transcript_json = os.path.join(run_dir, "transcript.json")
                        
                    transcript_md = os.path.join(run_dir, "tournament_results_transcript.md")
                    if not os.path.exists(transcript_md):
                        transcript_md = os.path.join(run_dir, "transcript.md")
                    
                    # Try to parse the seed from the folder name
                    folder_name = os.path.basename(run_dir)
                    campaign_name = os.path.basename(bd)
                    
                    if os.path.exists(transcript_json):
                        base_name = f"{campaign_name}_{folder_name}"
                        
                        out_json = os.path.join(export_dir, f"{base_name}.json")
                        out_md = os.path.join(export_dir, f"{base_name}.md")
                        
                        shutil.copy2(transcript_json, out_json)
                        if os.path.exists(transcript_md):
                            shutil.copy2(transcript_md, out_md)
                            
                        # Load and add to aggregate
                        try:
                            with open(transcript_json, 'r', encoding='utf-8') as tf:
                                tj = json.load(tf)
                                # Inject identifier
                                tj["_export_id"] = base_name
                                tj["_export_health"] = health
                                aggregated_data.append(tj)
                        except Exception as parse_e:
                            print(f"[!] Failed to parse aggregate: {base_name}: {parse_e}")
                            
                        exported_count += 1
                        print(f"Exported: {base_name} (Health: {health:.3f})")
                        
            except Exception as e:
                pass

print("-" * 60)
print(f"Done! Exported {exported_count} valid transcripts to {export_dir}")

aggregate_path = os.path.join(export_dir, "aggregated_transcripts.json")
with open(aggregate_path, 'w', encoding='utf-8') as af:
    json.dump(aggregated_data, af, indent=2)
print(f"Created consolidated JSON at: {aggregate_path}")

# Create a 'latest' symlink/copy for easiest access
latest_link = os.path.join("data", "export_latest")
if os.path.exists(latest_link):
    if os.path.islink(latest_link):
        os.unlink(latest_link)
    else:
        shutil.rmtree(latest_link)

try:
    os.symlink(os.path.basename(export_dir), latest_link, target_is_directory=True)
except OSError:
    # Fallback for Windows if symlinks unprivileged
    print("Symlink failed, copying to data/export_latest instead...")
    shutil.copytree(export_dir, latest_link)

print(f"Accessible at: data/export_latest/")
