# Contributing to AICampTownDebate

Thank you for your interest in contributing! This project is an experimental framework for AI alignment and reasoning optimization through economic pressure.

## How to Contribute

### 1. Adding New Models
If you want to add support for a new LLM backend:
- Check `src/models/ollama_backend.py` for inspiration.
- Ensure your model wrapper returns a `GenerationResult` with `tokens_used`.

### 2. Tuning Prompts
Prompts are currently hardcoded in `src/models/debater.py` and `src/models/judge.py`. We plan to move these to a central `prompts/` directory.

### 3. Improving the Economy
The token economy is defined in `src/economy/ledger.py` and `src/arena/round.py`. Strategic changes to reward distribution or debt mechanics are welcome.

## Development Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Install Ollama: [ollama.com](https://ollama.com)
3. Pull the default test model: `ollama pull qwen2.5:1.5b`
4. Run the demo: `python demo_ollama.py`

## Coding Standards
- Use type hints for all function signatures.
- Document key design decisions in a local `DEVLOG.md` if you're making major architectural changes.

## Recognition
All contributors will be added to the `README.md`.
