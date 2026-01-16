# AICampTownDebate

**Adversarial Token-Economy Debate Training for Internal Reasoning Optimization (ITMC)**

## Quick Summary

AICampTownDebate is a novel AI training paradigm that combines:
- **Dual-Model Debate**: Adversarial reasoning between two LLMs.
- **Persistent Token Economy**: Models manage their own "compute currency" for generation and strategic bets.
- **Amnesiac Judges**: Small, high-quality models that evaluate arguments without bias accumulation.
- **Futarchy-Inspired Betting**: Models wager on their own confidence and the quality of their research/refutations.

The ultimate goal is to optimize the **Internal Thinking / Mesa-Cognition (ITMC)** of LLMs through economic selection pressure.

## Key Concepts

- **Token (economic)**: Currency earned from successful arguments, spent on generation.
- **Token (LLM)**: Actual compute cost of generation, deducted from the economic balance.
- **Strategic Options**: REFUTE (counter opponent), RESEARCH (strengthen own), or PASS (save resources).
- **Information Asymmetry**: Hiding judge reasoning to prevent models from learning to pander.

## Getting Started

1. **Prerequisites**: [Ollama](https://ollama.com) installed and running.
2. **Setup**:
   ```bash
   pip install -r requirements.txt
   ollama pull qwen2.5:1.5b
   ```
3. **Run Demo**:
   ```bash
   python demo_ollama.py
   ```

## Documentation

- [CONCEPT.md](file:///c:/Users/msunw/Downloads/AIcamptowndebate/CONCEPT.md): The core theory and mechanics.
- [DEVLOG.md](file:///c:/Users/msunw/Downloads/AIcamptowndebate/DEVLOG.md): Append-only history of development sessions.
- [architecture.md](file:///c:/Users/msunw/Downloads/AIcamptowndebate/docs/architecture.md): System design and data flow.
- [CONTRIBUTING.md](file:///c:/Users/msunw/Downloads/AIcamptowndebate/docs/CONTRIBUTING.md): How to add new agents or judges.

## Project Status

🟡 **Phase: Foundation** - Setting up project structure, local LLM integration, and token economy dynamics.

## License

MIT (or check local license file).
