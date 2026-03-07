# TASK-004B HANDOFF

owner: worker + gate verifier
batch: B
changed_files:
- src/models/debater.py
- src/models/judge.py
- src/models/ollama_backend.py (deleted)
- src/models/vllm_backend.py (deleted)
- src/models/openai_compat_backend.py (deleted)
- src/models/__init__.py
- src/runtime/preflight.py
spec_compliance:
- yes (plus required dependency fix in runtime preflight)
verify_commands:
- python -c "from src.models.provider_backend import ProviderBackend, ProviderConfig; print('PASS import')"
- python -m pytest tests/test_debater_multi_agent.py tests/test_response_models.py tests/test_openai_compat_backend.py -q
- python -m pytest tests/test_benchmark_artifact_isolation.py -q
- python legacy backend deletion/assertion check
- python src.models export-surface assertion check
verify_raw_output:
```text
PASS import
8 passed in 0.22s
1 passed in 0.50s
PASS all legacy backends gone
PASS exports
```
blocked_rules_check:
- order respected
- dependency blocker resolved
risks:
- full suite still may have unrelated issues
unlocks:
- Gate C
