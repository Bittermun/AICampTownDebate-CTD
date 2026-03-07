# Blocking Questions

- TASK-004 scope conflict: queue says do not touch non-listed files, but deleting old backends may require import updates in additional files.
- TASK-004 verify command is shell-specific (`tail -3`) and may fail in PowerShell.
- tournament_rounds uniqueness: per-agent and per-round uniqueness both appear; confirm intended invariant before TASK-008/009.
- fail_round(reason) contract is underspecified; define persistence location before TASK-008.
