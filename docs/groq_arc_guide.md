# Groq APIs and Intel Arc GPU Troubleshooting Guide

This document captures operational best practices for scaling the tournament infrastructure on Groq cloud endpoints and troubleshooting edge-cases with local acceleration (Intel Arc via LM Studio).

---

## 🚀 Operating Groq APIs for Tournaments

Groq provides extremely low-latency inference, making it excellent for large-scale tournament sweeps. However, free-tier accounts have strict Rate Limits (typically 6,000 Tokens Per Minute and a Requests Per Minute cap).

### Multi-Key Concurrency Management

To bypass limits legally and effectively without hitting HTTP 429 Errors, we use multiple accounts mapped to multiple keys, executing single-concurrency threads.

**How to use `scripts/launch_groq_multikey.ps1`:**

1. **Edit the Keys Array**: Open the script and paste your API keys into the `$GroqKeys` array.
   ```powershell
   $GroqKeys = @(
       "gsk_YOUR_KEY_1",  # Account 1
       "gsk_YOUR_KEY_2"   # Account 2
   )
   ```
2. **Launch the Campaign**: Pass the target YAML config, and keep concurrency at `1` to avoid TPM lockouts.
   ```powershell
   .\scripts\launch_groq_multikey.ps1 -RunsPerKey 50 -Concurrency 1 -Config "configs/groq_scarcity.yaml"
   ```
3. **Observation**: The script launches independent isolated PowerShell processes. Each process uses a different `OPENAI_COMPAT_BASE_URL` and `OPENAI_COMPAT_API_KEY`. They will log concurrently into `logs/groq_multikey_<timestamp>/account_X`.

---

## 🚫 Intel Arc GPU & LM Studio: Known Networking Issues

While we successfully loaded models (e.g., `qwen2.5-coder-7b-instruct-gguf`) onto the Intel Arc GPU using LM Studio's Vulkan backend, we encountered network instability at the HTTP layer between our Python backend and LM Studio.

### The Problem: `[WinError 10054] An existing connection was forcibly closed` (ECONNRESET)

During intensive tournament runs, LM Studio occasionally drops the connection before returning the response. This is likely an upstream issue with LM Studio's current local inference server implementation when under high sustained load.

### The Workaround: JSON-Mode Feature Toggles

At one point, these resets were compounded by `response_format: {"type": "json_object"}`. Some local inference gateways struggle when JSON mode is strictly enforced, leading to crashes or ignored system instructions.

As of March 2026, we updated `openai_compat_backend.py` to allow skipping JSON mode enforcement dynamically:

```python
# In src/models/openai_compat_backend.py
no_json_mode = os.environ.get("OPENAI_COMPAT_NO_JSON_MODE", "").lower() in ("1", "true", "yes")
if json_mode and not is_groq and not no_json_mode:
    payload["response_format"] = {"type": "json_object"}
```

**To use the Arc GPU safely:**
If you start seeing ECONNRESETs from `localhost:1234`, you can bypass JSON-mode on the endpoint by setting:

```powershell
$env:OPENAI_COMPAT_NO_JSON_MODE="1"
```

_(Note: If errors persist despite this env var, it means the API implementation in the current LM Studio release is simply structurally unstable under concurrent load. For highly reliable data gathering, routing traffic to the Nvidia GPU via Ollama remains the most robust choice)._
