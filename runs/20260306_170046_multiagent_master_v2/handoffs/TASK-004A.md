# TASK-004A HANDOFF

owner: worker + gate verifier
batch: B
changed_files:
- src/models/provider_backend.py
spec_compliance:
- yes (rename/copy only, no deletes, no other file edits)
verify_commands:
- python -c "from src.models.provider_backend import ProviderBackend, ProviderConfig; print('PASS import')"
verify_raw_output:
```text
TASK004A PASS import
```
blocked_rules_check:
- order respected
- file scope respected
risks:
- provider_backend still imports GenerationResult from ollama_backend; impacts TASK-004B delete sequencing
unlocks:
- TASK-004B
