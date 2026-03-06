import json
import os
import requests
from dataclasses import dataclass
from typing import Optional
from .ollama_backend import GenerationResult


@dataclass
class VLLMConfig:
    """Configuration for vLLM backend."""
    base_url: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
    model: str = "Qwen/Qwen2.5-1.5B-Instruct"
    timeout: int = 120
    api_key: Optional[str] = os.getenv("VLLM_API_KEY")


class VLLMBackend:
    """
    vLLM backend - uses OpenAI-compatible completions API.
    Provides significantly higher throughput than Ollama.
    """
    
    def __init__(self, config: Optional[VLLMConfig] = None):
        self.config = config or VLLMConfig()
        self._available = None
    
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers
    
    def is_available(self) -> bool:
        """Check if vLLM server is running."""
        try:
            # vLLM provides an OpenAI-compatible /v1/models endpoint
            resp = requests.get(
                f"{self.config.base_url}/v1/models",
                headers=self._headers(),
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False
    
    def list_models(self) -> list[str]:
        """List models exposed by the vLLM OpenAI-compatible endpoint."""
        if not self.is_available():
            return []
        try:
            resp = requests.get(
                f"{self.config.base_url}/v1/models",
                headers=self._headers(),
                timeout=10,
            )
            data = resp.json()
            return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        except Exception:
            return []
    
    def _build_chat_payload(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
        temperature: float = 0.8,
    ) -> dict:
        """Build OpenAI-compatible chat payload."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        if "groq.com" in self.config.base_url.lower() and max_tokens < 1024:
            max_tokens = 2048
            
        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if json_mode:
            # Groq's qwen models frequently fail their own backend validation when json_object is forced.
            if "groq.com" not in self.config.base_url.lower():
                payload["response_format"] = {"type": "json_object"}
        return payload
    
    def _build_completions_payload(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.8,
    ) -> dict:
        """Build fallback completions payload for compatibility."""
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        return {
            "model": self.config.model,
            "prompt": full_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
        temperature: float = 0.8,
    ) -> GenerationResult:
        """Sync generation via vLLM REST API."""
        if not self.is_available():
            return GenerationResult(text="[VLLM_UNAVAILABLE] vLLM server not responding", tokens_used=0)
        
        try:
            # Preferred: chat completions endpoint
            payload = self._build_chat_payload(prompt, system, max_tokens, json_mode, temperature)
            resp = requests.post(
                f"{self.config.base_url}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.config.timeout,
            )
            data = resp.json()
            
            if "choices" not in data:
                # Compatibility fallback for older deployments
                fallback = self._build_completions_payload(prompt, system, max_tokens, temperature)
                resp = requests.post(
                    f"{self.config.base_url}/v1/completions",
                    json=fallback,
                    headers=self._headers(),
                    timeout=self.config.timeout,
                )
                data = resp.json()
                if "choices" not in data:
                    return GenerationResult(text=f"[VLLM_ERROR] Unexpected response: {json.dumps(data)}", tokens_used=0)
                text = data["choices"][0].get("text", "").strip()
                tokens_used = data.get("usage", {}).get("completion_tokens", 0)
                return GenerationResult(text=text, tokens_used=tokens_used)

            message = data["choices"][0].get("message", {})
            text = message.get("content", "").strip()
            tokens_used = data.get("usage", {}).get("completion_tokens", 0)
            return GenerationResult(text=text, tokens_used=tokens_used)
            
        except Exception as e:
            return GenerationResult(text=f"[VLLM_ERROR] {str(e)}", tokens_used=0)
    
    async def generate_async(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
        temperature: float = 0.8,
    ) -> GenerationResult:
        """Async generation for parallel calls."""
        try:
            import aiohttp
        except ImportError:
            return self.generate(prompt, system, max_tokens, json_mode, temperature)
            
        if not self.is_available():
            return GenerationResult(text="[VLLM_UNAVAILABLE] vLLM server not responding", tokens_used=0)
        
        import asyncio
        import aiohttp
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    payload = self._build_chat_payload(prompt, system, max_tokens, json_mode, temperature)
                    async with session.post(
                        f"{self.config.base_url}/v1/chat/completions",
                        json=payload,
                        headers=self._headers(),
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        if "choices" in data:
                            message = data["choices"][0].get("message", {})
                            text = message.get("content", "").strip()
                            tokens_used = data.get("usage", {}).get("completion_tokens", 0)
                            return GenerationResult(text=text, tokens_used=tokens_used)
                        return self.generate(prompt, system, max_tokens, json_mode, temperature)
            except Exception as e:
                if isinstance(e, asyncio.CancelledError):
                    raise
                if attempt == max_retries - 1:
                    print(f"[VLLMBackend] Max retries reached: {e}")
                    return GenerationResult(text=f"[ASYNC_VLLM_ERROR] {str(e)}", tokens_used=0)
                print(f"[VLLMBackend] Transient error {type(e).__name__}. Retrying {attempt+1}/{max_retries} in 5s...")
                await asyncio.sleep(5)
