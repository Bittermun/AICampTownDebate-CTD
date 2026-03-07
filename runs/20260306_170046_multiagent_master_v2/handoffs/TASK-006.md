# TASK-006 HANDOFF

owner: worker + gate verifier
batch: B
changed_files:
- src/db/agent_registry.py
spec_compliance:
- yes
verify_commands:
- TASK-006 register_agent smoke command
verify_raw_output:
```text
TASK006 PASS qwen-qwen3-32b-api-groq-com
```
blocked_rules_check:
- order respected
- file scope respected
risks:
- apply_patch_notification query relies on patch applied_at ordering semantics
unlocks:
- contributes to Gate B completion
