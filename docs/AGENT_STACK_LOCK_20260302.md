# Agent Stack Lock (2026-03-02)

This lock records the exact skill sources used by `scripts/bootstrap_agent_stack.ps1`.

## Defaults

- Ref: `main`
- Codex home: `$CODEX_HOME` or `~/.codex`
- Destination: `$CODEX_HOME/skills/<skill-name>`

## Skills

1. `openai/skills` -> `skills/.curated/openai-docs`
2. `openai/skills` -> `skills/.curated/jupyter-notebook`
3. `openai/skills` -> `skills/.curated/spreadsheet`
4. `openai/skills` -> `skills/.curated/pdf`
5. `openai/skills` -> `skills/.curated/doc`
6. `openai/skills` -> `skills/.curated/security-threat-model`
7. `Orchestra-Research/AI-Research-SKILLs` -> `11-evaluation/lm-evaluation-harness`
8. `Orchestra-Research/AI-Research-SKILLs` -> `12-inference-serving/vllm`
9. `Orchestra-Research/AI-Research-SKILLs` -> `13-mlops/mlflow`
10. `Orchestra-Research/AI-Research-SKILLs` -> `13-mlops/weights-and-biases`
11. `Orchestra-Research/AI-Research-SKILLs` -> `17-observability/phoenix`
12. `am-will/codex-skills` -> `skills/context7`
13. `am-will/codex-skills` -> `skills/read-github`

## Post-Install Patch

- Applies a Windows compatibility patch to:
  - `$CODEX_HOME/skills/read-github/scripts/gitmcp.py`
- Purpose:
  - use `npx.cmd` on Windows via helper function `_npx_command()`
  - keep `npx` behavior on non-Windows

## Usage

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_agent_stack.ps1
```

Dry run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_agent_stack.ps1 -DryRun
```

