# Token-Debate Experiment

**Adversarial Token-Economy Debate Training for Internal Reasoning Optimization**

## Quick Summary

A novel AI training paradigm combining:
- **Dual-model debate** for adversarial reasoning
- **Token economy** with persistent balances and debt
- **Amnesiac judges** to prevent bias accumulation
- **Betting mechanics** to create stakes on argument quality

Goal: Optimize internal thinking/mesa-cognition (ITMC) through economic pressure.

## Hardware Requirements

- Intel Core Ultra 9 185H (or equivalent)
- 8GB dedicated GPU VRAM
- 32GB+ system RAM
- Models: 7B quantized (4-bit) or multiple 1-3B models

## Project Structure

```
├── README.md           # This file
├── CONCEPT.md          # Core idea and terminology
├── DEVLOG.md           # Development journal (append-only)
├── .agent/workflows/   # AI assistant workflows
├── docs/               # Architecture, experiments
└── src/                # Implementation code
```

## Getting Started

1. Read `CONCEPT.md` to understand the core idea
2. Check `DEVLOG.md` for current state
3. See `docs/architecture.md` for system design

## For AI Assistants

If you're an AI resuming work on this project:
1. **First**: Read `.agent/workflows/resume.md`
2. **Then**: Check `DEVLOG.md` for latest entry
3. **Ask user** what they want to work on next

## Status

🟡 **Phase: Foundation** - Setting up project structure and documentation
