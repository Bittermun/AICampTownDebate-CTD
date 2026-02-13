# AICampTownDebate

**Adversarial Token-Economy Debate for Inference-Time Compute & Mesa-Cognition**

## Quick Summary

AICampTownDebate is a novel AI training paradigm that combines:
- **Dual-Model Debate**: Adversarial reasoning between two LLMs.
- **Persistent Token Economy**: Models manage their own "compute currency" for generation and strategic bets.
- **Amnesiac Judges**: Small, high-quality models that evaluate arguments without bias accumulation.
- **Futarchy-Inspired Betting**: Models wager on their own confidence and the quality of their research/refutations.

The ultimate goal is to optimize **inference-time compute** and **mesa-cognition** in LLMs through economic selection pressure.

## Key Concepts

- **Token (economic)**: Currency earned from successful arguments, spent on generation.
- **Token (LLM)**: Actual compute cost of generation, deducted from the economic balance.
- **Strategic Options**: REFUTE (counter opponent), RESEARCH (strengthen own), or PASS (save resources).
- **Information Asymmetry**: Hiding judge reasoning to prevent models from learning to pander.
- **`<thinking>` Tags**: Chain-of-thought reasoning hidden from judge but logged for mesa-cognition analysis.
- **Web Search (ResearchTool)**: Real DuckDuckGo search during RESEARCH phase with dynamic token cost.
- **Self-Summarization**: Memory management where debaters compress their history (costs tokens).

## Getting Started

1. **Prerequisites**: [Ollama](https://ollama.com) installed and running.
2. **Setup**:
   ```bash
   pip install -r requirements.txt
   ollama pull qwen2.5:1.5b
   ```
3. **Run Demo**:
   ```bash
   python demo_dynamic.py --config configs/tournament_config.yaml
   ```

## Documentation

- [CONCEPT.md](./CONCEPT.md): The core theory, mechanics, and key innovations.
- [DEVLOG.md](./DEVLOG.md): Recent development sessions (archived history in DEVLOG_ARCHIVE.md).
- [architecture.md](./docs/architecture.md): System design and data flow.

## Project Status

🟢 **Phase: Core Complete** — Dynamic debates with inference-time compute features (thinking tags, web search, self-summarization), modular judges, and full token economy.

**Roadmap:** Ground truth calibration, tiered arenas, reputation system.

## Troubleshooting

- **Validation Failures**: If judges fail to parse JSON, check `ollama logs`. The system now includes a JSON repair mechanism (`_repair_truncated_json`), but extreme truncation may still cause issues. Try increasing `max_tokens` in `JudgeConfig`.
- **Positional Bias**: If the judge always favors the first debater, ensure `randomize_argument_order: true` is set in your config.

## License

MIT (or check local license file).

