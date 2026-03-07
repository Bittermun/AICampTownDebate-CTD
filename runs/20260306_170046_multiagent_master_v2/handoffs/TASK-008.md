# TASK-008 HANDOFF

owner: worker + gate verifier
batch: C
changed_files:
- src/db/round_writer.py
spec_compliance:
- yes
verify_commands:
- round writer insert/complete status check
verify_raw_output:
```text
TASK008 PASS
```
blocked_rules_check:
- order respected
risks:
- fail_round stores reason in judge_scores error payload
unlocks:
- contributes to Gate C completion
