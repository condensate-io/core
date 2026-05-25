import os
import httpx
import logging
import asyncio
from typing import List, Dict, Any, Optional
from tenacity import retry, wait_exponential, stop_after_attempt

from src.config import settings
from src.config_cache import load_json_config

logger = logging.getLogger("LLMClient")

# Per-loop semaphore cache to avoid RuntimeError across different event loops
_loop_semaphores = {}

def _get_semaphore():
    loop = asyncio.get_running_loop()
    if loop not in _loop_semaphores:
        _loop_semaphores[loop] = asyncio.Semaphore(int(os.getenv("LLM_MAX_CONCURRENCY", "4")))
    return _loop_semaphores[loop]

class LLMClient:
    def __init__(self):
        self._load_config()

    def _load_config(self):
        data = load_json_config("llm_config.json", settings.CONFIG_CACHE_TTL_SECONDS)
        if data:
            try:
                configs = data.get("configs", [])
                # Find primary active config
                primary = next((c for c in configs if c.get("is_primary") and c.get("is_active")), None)
                if not primary:
                    # Fallback to any active config
                    primary = next((c for c in configs if c.get("is_active")), None)

                if primary:
                    self.base_url = primary.get("baseUrl")
                    self.api_key = primary.get("apiKey")
                    self.model = primary.get("model")
                    return

                # Legacy support for old flat structure if it exists
                if "baseUrl" in data:
                    self.base_url = data.get("baseUrl")
                    self.api_key = data.get("apiKey")
                    self.model = data.get("model")
                    return
            except Exception as e:
                logger.error(f"Failed to load llm_config.json: {e}")

        # Default to env vars or defaults
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.api_key = os.getenv("LLM_API_KEY", "ollama")
        self.model = os.getenv("LLM_MODEL", "phi3")

    @staticmethod
    def get_active_config() -> Dict[str, Any]:
        data = load_json_config("llm_config.json", settings.CONFIG_CACHE_TTL_SECONDS)
        if data:
            try:
                configs = data.get("configs", [])
                primary = next((c for c in configs if c.get("is_primary") and c.get("is_active")), None)
                if not primary:
                    primary = next((c for c in configs if c.get("is_active")), None)
                if primary:
                    return primary

                if "baseUrl" in data:
                    return data  # old format fallback
            except Exception:
                pass
        
        return {
            "baseUrl": os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
            "apiKey": os.getenv("LLM_API_KEY", "ollama"),
            "model": os.getenv("LLM_MODEL", "phi3")
        }

    @retry(wait=wait_exponential(multiplier=2, min=4, max=30), stop=stop_after_attempt(5))
    async def generate(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        # Reload config before each call to ensure we use latest settings saved via admin
        self._load_config()
        sem = _get_semaphore()
        async with sem:
            async with httpx.AsyncClient(timeout=120.0) as client:
                try:
                    payload = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ]
                    }
                    
                    is_openai = "openai.com" in self.base_url.lower()
                    is_o_model = any(m in self.model.lower() for m in ["o1-", "o3-", "nano"])
                    
                    if is_openai:
                        # OpenAI uses response_format for JSON mode
                        payload["response_format"] = {"type": "json_object"}
                        # O-models (o1, o3, nano) use 'developer' role and don't support temperature
                        if is_o_model:
                            payload["messages"][0]["role"] = "developer"
                        else:
                            payload["temperature"] = 0.0
                    else:
                        # Ollama-style defaults
                        payload["format"] = "json"
                        payload["temperature"] = 0.0
                        
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers={"Authorization": f"Bearer {self.api_key}"}
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data['choices'][0]['message']['content']
                except Exception as e:
                    logger.error(f"LLM Call failed to {self.base_url} [model={self.model}]: {type(e).__name__}: {e}")
                    raise e
