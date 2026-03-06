$env:OPENAI_COMPAT_BASE_URL = "https://api.groq.com/openai/v1"
$env:OPENAI_COMPAT_API_KEY = "gsk_YOUR_API_KEY_HERE"
C:\Python314\python.exe scripts/run_tournament_batch.py `
    --config configs/groq_emergent_config.yaml `
    --runs 50 `
    --output-root logs/groq_campaign_50 `
    --concurrency 4 `
    --no-gate-judge-variance `
    --no-gate-judge-calibration
