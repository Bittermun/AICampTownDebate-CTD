"""Generic OpenAI-compatible backend for local or remote inference servers.

Supports providers that expose OpenAI-compatible chat/models APIs on `/v1`
or `/v3` prefixes.
Examples include local Intel-friendly stacks that provide an OpenAI-compatible
gateway, and paid remote GPU endpoints.
"""
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class GenerationResult:
    """Result of a generation call, including token usage."""
    text: str
    tokens_used: int  # Number of LLM tokens generated (for cost tracking)


@dataclass
class ProviderConfig:
    base_url: str = os.getenv("OPENAI_COMPAT_BASE_URL", "http://localhost:8000")
    model: str = os.getenv("OPENAI_COMPAT_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
    timeout: int = 120
    api_key: Optional[str] = os.getenv("OPENAI_COMPAT_API_KEY")
    api_version: str = os.getenv("OPENAI_COMPAT_API_VERSION", "auto").lower()
    healthcheck_ttl_sec: int = int(os.getenv("OPENAI_COMPAT_HEALTHCHECK_TTL_SEC", "30"))


class ProviderBackend:
    """REST client for OpenAI-compatible chat endpoints."""

    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or ProviderConfig()
        self._session = requests.Session()
        self._resolved_models_url: Optional[str] = None
        self._resolved_api_version: Optional[str] = None
        self._availability_cached = False
        self._availability_checked_at = 0.0

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _base_and_embedded_version(self) -> tuple[str, Optional[str]]:
        base = self.config.base_url.rstrip("/")
        for version in ("v1", "v3"):
            suffix = f"/{version}"
            if base.lower().endswith(suffix):
                return base[: -len(suffix)], version
        return base, None

    def _candidate_versions(self, prioritize_resolved: bool = False) -> list[str]:
        base, embedded = self._base_and_embedded_version()
        del base  # base only used for embedded detection above
        requested = (self.config.api_version or "auto").strip().lower()
        if requested not in {"auto", "v1", "v3"}:
            requested = "auto"

        versions: list[str] = []
        if prioritize_resolved and self._resolved_api_version is not None:
            versions.append(self._resolved_api_version)

        if requested == "auto":
            if embedded:
                versions.append(embedded)
            versions.extend(["v1", "v3", ""])
        else:
            versions.extend([requested, ""])

        deduped: list[str] = []
        for version in versions:
            if version not in deduped:
                deduped.append(version)
        return deduped

    def _models_url_candidates(self) -> list[tuple[str, str]]:
        base, _ = self._base_and_embedded_version()
        out: list[tuple[str, str]] = []
        for version in self._candidate_versions(prioritize_resolved=False):
            if version:
                out.append((version, f"{base}/{version}/models"))
            else:
                out.append((version, f"{base}/models"))
        return out

    def _chat_url_candidates(self) -> list[str]:
        base, _ = self._base_and_embedded_version()
        out: list[str] = []
        for version in self._candidate_versions(prioritize_resolved=True):
            if version:
                out.append(f"{base}/{version}/chat/completions")
            else:
                out.append(f"{base}/chat/completions")
        return out

    def _probe_models_endpoint(self) -> Optional[str]:
        for version, url in self._models_url_candidates():
            try:
                resp = self._session.get(url, headers=self._headers(), timeout=5)
                if resp.status_code == 200:
                    self._resolved_models_url = url
                    self._resolved_api_version = version
                    return url
            except Exception:
                continue
        self._resolved_models_url = None
        self._resolved_api_version = None
        return None

    def _refresh_availability(self, force: bool = False) -> bool:
        now = time.monotonic()
        ttl = max(0, int(self.config.healthcheck_ttl_sec))
        if not force and self._availability_checked_at > 0 and (now - self._availability_checked_at) <= ttl:
            return self._availability_cached

        self._availability_cached = self._probe_models_endpoint() is not None
        self._availability_checked_at = now
        return self._availability_cached

    def _build_payload(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        json_mode: bool,
        temperature: float,
    ) -> dict:
        is_groq = "groq.com" in self.config.base_url.lower()
        
        if is_groq and max_tokens < 1024:
            max_tokens = 2048
            
        payload = {
            "model": self.config.model,
            "messages": ([{"role": "system", "content": system}] if system else [])
            + [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if is_groq and ("qwen" in self.config.model.lower() or "qwq" in self.config.model.lower() or "deepseek" in self.config.model.lower()):
            # Disable hybrid chain-of-thought mode so output is always
            # clean JSON (no <think> tags) and latency is predictable.
            payload["reasoning_effort"] = "none"
        # Allow any endpoint to opt out of response_format via env var
        no_json_mode = os.environ.get("OPENAI_COMPAT_NO_JSON_MODE", "").lower() in ("1", "true", "yes")
        if json_mode and not is_groq and not no_json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def is_available(self) -> bool:
        return self._refresh_availability(force=False)

    def list_models(self) -> list[str]:
        url = self._resolved_models_url or self._probe_models_endpoint()
        if not url:
            return []
        try:
            resp = self._session.get(url, headers=self._headers(), timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        except Exception:
            return []

    def _parse_generation_payload(self, data: dict) -> GenerationResult:
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

    def _post_sync(self, payload: dict) -> GenerationResult:
        max_retries = 6
        base_delay = 2.0

        for url in self._chat_url_candidates():
            for attempt in range(max_retries):
                try:
                    resp = self._session.post(
                        url,
                        json=payload,
                        headers=self._headers(),
                        timeout=self.config.timeout,
                    )
                    if resp.status_code == 429:
                        retry_after = resp.headers.get("retry-after")
                        if retry_after and retry_after.replace(".", "").isdigit():
                            wait_time = float(retry_after)
                        else:
                            wait_time = base_delay * (1.5 ** attempt)
                        print(f"[{self.config.model}] 429 Rate limit, sleeping {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue
                    
                    if resp.status_code in (404, 405):
                        break  # Try next URL candidate
                    
                    data = resp.json()
                    if "error" in data and resp.status_code != 200:
                        # Groq sometimes returns 400 for rate limit details unfortunately in the body
                        err_msg = str(data.get("error", {}).get("message", "")).lower()
                        if "rate limit" in err_msg or "please try again in" in err_msg:
                            import re
                            m = re.search(r"please try again in ([0-9.]+)s", err_msg)
                            wait_time = float(m.group(1)) if m else base_delay * (1.5 ** attempt)
                            print(f"[{self.config.model}] 400 Rate limit body, sleeping {wait_time:.1f}s...")
                            time.sleep(wait_time)
                            continue
                            
                    parsed = self._parse_generation_payload(data)
                    if parsed.text.startswith("[OPENAI_COMPAT_ERROR]") and resp.status_code in (404, 405):
                        break
                    return parsed
                except Exception as exc:
                    err = str(exc)
                    if "404" in err:
                        break
                    return GenerationResult(text=f"[OPENAI_COMPAT_ERROR] {exc}", tokens_used=0)
            # If we exhausted retries on this URL, move to the next URL or fail
            return GenerationResult(text=f"[OPENAI_COMPAT_ERROR] Exhausted retries (429)", tokens_used=0)

        self._availability_cached = False
        self._availability_checked_at = time.monotonic()
        return GenerationResult(text="[OPENAI_COMPAT_UNAVAILABLE] Endpoint not responding", tokens_used=0)

    async def _post_async(self, payload: dict) -> GenerationResult:
        try:
            import aiohttp
            import asyncio
        except ImportError:
            return self._post_sync(payload)

        max_retries = 6
        base_delay = 2.0
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)

        for url in self._chat_url_candidates():
            for attempt in range(max_retries):
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post(
                            url,
                            json=payload,
                            headers=self._headers(),
                        ) as resp:
                            if resp.status == 429:
                                retry_after = resp.headers.get("retry-after")
                                if retry_after and retry_after.replace(".", "").isdigit():
                                    wait_time = float(retry_after)
                                else:
                                    wait_time = base_delay * (1.5 ** attempt)
                                print(f"[{self.config.model}] 429 Rate limit, sleeping {wait_time:.1f}s...")
                                await asyncio.sleep(wait_time)
                                continue

                            if resp.status in (404, 405):
                                break

                            data = await resp.json()
                            if "error" in data and resp.status != 200:
                                err_msg = str(data.get("error", {}).get("message", "")).lower()
                                if "rate limit" in err_msg or "please try again in" in err_msg:
                                    import re
                                    m = re.search(r"please try again in ([0-9.]+)s", err_msg)
                                    wait_time = float(m.group(1)) if m else base_delay * (1.5 ** attempt)
                                    print(f"[{self.config.model}] 400 Rate limit body, sleeping {wait_time:.1f}s...")
                                    await asyncio.sleep(wait_time)
                                    continue
                            
                            parsed = self._parse_generation_payload(data)
                            if parsed.text.startswith("[OPENAI_COMPAT_ERROR]") and resp.status in (404, 405):
                                break
                            return parsed
                except Exception as exc:
                    err = str(exc)
                    if "404" in err:
                        break
                    return GenerationResult(text=f"[ASYNC_OPENAI_COMPAT_ERROR] {exc}", tokens_used=0)
            return GenerationResult(text=f"[OPENAI_COMPAT_ERROR] Exhausted retries (429)", tokens_used=0)

        self._availability_cached = False
        self._availability_checked_at = time.monotonic()
        return GenerationResult(text="[OPENAI_COMPAT_UNAVAILABLE] Endpoint not responding", tokens_used=0)

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

        payload = self._build_payload(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            json_mode=json_mode,
            temperature=temperature,
        )
        return self._post_sync(payload)

    async def generate_async(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
        temperature: float = 0.8,
    ) -> GenerationResult:
        if not self.is_available():
            return GenerationResult(text="[OPENAI_COMPAT_UNAVAILABLE] Endpoint not responding", tokens_used=0)

        payload = self._build_payload(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            json_mode=json_mode,
            temperature=temperature,
        )
        return await self._post_async(payload)

    def __del__(self):
        try:
            self._session.close()
        except Exception:
            pass

