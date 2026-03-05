"""
Ollama Backend: Unified interface for Ollama-based inference.
Handles both debater and judge operations.
"""
import json
import requests
from dataclasses import dataclass, field
from typing import Optional


import os

@dataclass
class OllamaConfig:
    base_url: str = field(default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    model: str = "qwen2.5:1.5b"
    timeout: int = 120


@dataclass
class GenerationResult:
    """Result of a generation call, including token usage."""
    text: str
    tokens_used: int  # Number of LLM tokens generated (for cost tracking)



class OllamaBackend:
    """
    Simple wrapper for Ollama API.
    Used by both Debater and Judge classes.
    """
    
    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig()
        self._available = None
    
    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        if self._available is not None:
            return self._available
        
        try:
            resp = requests.get(
                f"{self.config.base_url}/api/tags",
                timeout=5
            )
            self._available = resp.status_code == 200
        except requests.exceptions.ConnectionError:
            self._available = False
        
        return self._available
    
    def list_models(self) -> list[str]:
        """List available models."""
        if not self.is_available():
            return []
        
        try:
            resp = requests.get(
                f"{self.config.base_url}/api/tags",
                timeout=10
            )
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
    
    def _build_payload(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
        temperature: float = 0.8,
    ) -> dict:
        """Build the API payload for generation requests."""
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            }
        }
        
        if json_mode:
            payload["format"] = "json"
        
        if system:
            payload["system"] = system
        
        return payload
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
        temperature: float = 0.8,
    ) -> GenerationResult:
        """Generate a response from the model. Returns text and token count.
        
        Args:
            prompt: The user prompt
            system: Optional system prompt
            max_tokens: Maximum tokens to generate
            json_mode: If True, force JSON output format (uses Ollama's format parameter)
            temperature: Model temperature (default 0.8)
        """
        if not self.is_available():
            return GenerationResult(
                text=f"[OLLAMA_UNAVAILABLE] Prompt was: {prompt[:100]}...",
                tokens_used=0
            )
        
        payload = self._build_payload(prompt, system, max_tokens, json_mode)
        
        try:
            resp = requests.post(
                f"{self.config.base_url}/api/generate",
                json=payload,
                timeout=self.config.timeout,
            )
            data = resp.json()
            text = data.get("response", "").strip()
            # Ollama returns eval_count = number of tokens generated
            tokens_used = data.get("eval_count", 0)
            return GenerationResult(text=text, tokens_used=tokens_used)
        except requests.exceptions.Timeout:
            return GenerationResult(text="[TIMEOUT] Model took too long to respond", tokens_used=0)
        except Exception as e:
            return GenerationResult(text=f"[ERROR] {str(e)}", tokens_used=0)
    
    async def generate_async(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
        temperature: float = 0.8,
    ) -> GenerationResult:
        """Async version of generate() for parallel LLM calls.
        
        Uses aiohttp for non-blocking HTTP requests. Enables parallel
        debater argument generation and multi-model inference.
        """
        try:
            import aiohttp
        except ImportError:
            # Fallback to sync if aiohttp not installed
            return self.generate(prompt, system, max_tokens, json_mode, temperature)
        
        if not self.is_available():
            return GenerationResult(
                text=f"[OLLAMA_UNAVAILABLE] Prompt was: {prompt[:100]}...",
                tokens_used=0
            )
        
        payload = self._build_payload(prompt, system, max_tokens, json_mode, temperature)
        
        import asyncio
        import aiohttp
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Need to use a fresh session to avoid hanging if the socket is tainted
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"{self.config.base_url}/api/generate",
                        json=payload,
                    ) as resp:
                        # Add raise_for_status to ensure we catch HTTP bad statuses as throws
                        resp.raise_for_status()
                        data = await resp.json()
                        text = data.get("response", "").strip()
                        tokens_used = data.get("eval_count", 0)
                        return GenerationResult(text=text, tokens_used=tokens_used)
            except Exception as e:
                # Catch asyncio.exceptions.CancelledError effectively to avoid freezing
                if isinstance(e, asyncio.CancelledError):
                    raise
                if attempt == max_retries - 1:
                    print(f"[OllamaBackend] Max retries reached: {e}")
                    return GenerationResult(text=f"[ASYNC_ERROR] {str(e)}", tokens_used=0)
                print(f"[OllamaBackend] Transient error {type(e).__name__}. Retrying {attempt+1}/{max_retries} in 5s...")
                await asyncio.sleep(5)

    
    def pull_model(self, model_name: str) -> bool:
        """Pull a model from Ollama registry."""
        if not self.is_available():
            print("Ollama not available")
            return False
        
        print(f"Pulling model: {model_name}...")
        try:
            resp = requests.post(
                f"{self.config.base_url}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=600,  # Models can be large
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"Pull failed: {e}")
            return False


# Singleton for shared use
_default_backend: Optional[OllamaBackend] = None


def get_backend(config: Optional[OllamaConfig] = None) -> OllamaBackend:
    """Get or create the default Ollama backend."""
    global _default_backend
    if _default_backend is None or config is not None:
        _default_backend = OllamaBackend(config)
    return _default_backend
