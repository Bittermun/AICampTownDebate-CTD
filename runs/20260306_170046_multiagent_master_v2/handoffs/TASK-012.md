# TASK-012 HANDOFF

owner: worker + gate verifier
batch: D
changed_files:
- scripts/migrate_json_logs.py
spec_compliance:
- yes
verify_commands:
- migrate clean_100 batch
- tournaments count >= 90
verify_raw_output:
```text
[migrate] done: 97 imported, 2 skipped, 0 failed
TASK012 PASS: 104 tournaments in DB
```
blocked_rules_check:
- order respected
- contaminated path guard implemented
risks:
- duplicate tournament ids in source produce skips by design
unlocks:
- Gate D complete
