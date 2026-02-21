import json
import requests
from dataclasses import dataclass
from typing import Optional
from .ollama_backend import GenerationResult


@dataclass
class VLLMConfig:
    """Configuration for vLLM backend."""
    base_url: str = "http://localhost:8000"  # vLLM server
    model: str = "Qwen/Qwen2.5-1.5B-Instruct"
    timeout: int = 120


class VLLMBackend:
    """
    vLLM backend - uses OpenAI-compatible completions API.
    Provides significantly higher throughput than Ollama.
    """
    
    def __init__(self, config: Optional[VLLMConfig] = None):
        self.config = config or VLLMConfig()
        self._available = None
    
    def is_available(self) -> bool:
        """Check if vLLM server is running."""
        try:
            # vLLM provides an OpenAI-compatible /v1/models endpoint
            resp = requests.get(
                f"{self.config.base_url}/v1/models",
                timeout=5
            )
            return resp.status_code == 200
        except Exception:
            return False
    
    def _build_payload(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
        temperature: float = 0.8,
    ) -> dict:
        """Build OpenAI-compatible payload."""
        # vLLM completions endpoint uses a single prompt string
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        
        payload = {
            "model": self.config.model,
            "prompt": full_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        
        return payload

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
            
        payload = self._build_payload(prompt, system, max_tokens, json_mode, temperature)
        
        try:
            resp = requests.post(
                f"{self.config.base_url}/v1/completions",
                json=payload,
                timeout=self.config.timeout,
            )
            data = resp.json()
            
            if "choices" not in data:
                return GenerationResult(text=f"[VLLM_ERROR] Unexpected response: {json.dumps(data)}", tokens_used=0)
                
            text = data["choices"][0]["text"].strip()
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

        payload = self._build_payload(prompt, system, max_tokens, json_mode, temperature)
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.config.base_url}/v1/completions",
                    json=payload,
                ) as resp:
                    data = await resp.json()
                    text = data["choices"][0]["text"].strip()
                    tokens_used = data.get("usage", {}).get("completion_tokens", 0)
                    return GenerationResult(text=text, tokens_used=tokens_used)
        except Exception as e:
            return GenerationResult(text=f"[ASYNC_VLLM_ERROR] {str(e)}", tokens_used=0)
