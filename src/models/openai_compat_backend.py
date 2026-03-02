"""Generic OpenAI-compatible backend for local or remote inference servers.

Supports providers that expose `/v1/chat/completions` and `/v1/models`.
Examples include local Intel-friendly stacks that provide an OpenAI-compatible
gateway, and paid remote GPU endpoints.
"""
import json
import os
from dataclasses import dataclass
from typing import Optional

import requests

from .ollama_backend import GenerationResult


@dataclass
class OpenAICompatConfig:
    base_url: str = os.getenv("OPENAI_COMPAT_BASE_URL", "http://localhost:8000")
    model: str = os.getenv("OPENAI_COMPAT_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
    timeout: int = 120
    api_key: Optional[str] = os.getenv("OPENAI_COMPAT_API_KEY")


class OpenAICompatBackend:
    """REST client for OpenAI-compatible chat endpoints."""

    def __init__(self, config: Optional[OpenAICompatConfig] = None):
        self.config = config or OpenAICompatConfig()

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _models_url_candidates(self) -> list[str]:
        base = self.config.base_url.rstrip("/")
        return [f"{base}/v1/models", f"{base}/models"]

    def is_available(self) -> bool:
        for url in self._models_url_candidates():
            try:
                resp = requests.get(url, headers=self._headers(), timeout=5)
                if resp.status_code == 200:
                    return True
            except Exception:
                continue
        return False

    def list_models(self) -> list[str]:
        for url in self._models_url_candidates():
            try:
                resp = requests.get(url, headers=self._headers(), timeout=10)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
            except Exception:
                continue
        return []

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
        temperature: float = 0.8,
    ) -> GenerationResult:
        if not self.is_available():
            return GenerationResult(text="[OPENAI_COMPAT_UNAVAILABLE] Endpoint not responding", tokens_used=0)

        base = self.config.base_url.rstrip("/")
        payload = {
            "model": self.config.model,
            "messages": ([{"role": "system", "content": system}] if system else [])
            + [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(
                f"{base}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.config.timeout,
            )
            data = resp.json()
            if "choices" not in data:
                return GenerationResult(
                    text=f"[OPENAI_COMPAT_ERROR] Unexpected response: {json.dumps(data)[:400]}",
                    tokens_used=0,
                )
            message = data["choices"][0].get("message", {})
            text = (message.get("content") or "").strip()
            usage = data.get("usage", {}) if isinstance(data.get("usage", {}), dict) else {}
            tokens_used = int(usage.get("completion_tokens", 0) or 0)
            return GenerationResult(text=text, tokens_used=tokens_used)
        except Exception as exc:
            return GenerationResult(text=f"[OPENAI_COMPAT_ERROR] {exc}", tokens_used=0)

    async def generate_async(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
        temperature: float = 0.8,
    ) -> GenerationResult:
        try:
            import aiohttp
        except ImportError:
            return self.generate(prompt, system, max_tokens, json_mode, temperature)

        if not self.is_available():
            return GenerationResult(text="[OPENAI_COMPAT_UNAVAILABLE] Endpoint not responding", tokens_used=0)

        base = self.config.base_url.rstrip("/")
        payload = {
            "model": self.config.model,
            "messages": ([{"role": "system", "content": system}] if system else [])
            + [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base}/v1/chat/completions",
                    json=payload,
                    headers=self._headers(),
                ) as resp:
                    data = await resp.json()
                    if "choices" not in data:
                        return GenerationResult(
                            text=f"[OPENAI_COMPAT_ERROR] Unexpected response: {json.dumps(data)[:400]}",
                            tokens_used=0,
                        )
                    message = data["choices"][0].get("message", {})
                    text = (message.get("content") or "").strip()
                    usage = data.get("usage", {}) if isinstance(data.get("usage", {}), dict) else {}
                    tokens_used = int(usage.get("completion_tokens", 0) or 0)
                    return GenerationResult(text=text, tokens_used=tokens_used)
        except Exception as exc:
            return GenerationResult(text=f"[ASYNC_OPENAI_COMPAT_ERROR] {exc}", tokens_used=0)
