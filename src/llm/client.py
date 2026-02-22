import os
import httpx
import logging
import asyncio
from typing import List, Dict, Any, Optional
from tenacity import retry, wait_exponential, stop_after_attempt

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
        # Default to localhost ollama if not set
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.api_key = os.getenv("LLM_API_KEY", "ollama")
        self.model = os.getenv("LLM_MODEL", "llama3")
        
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def generate(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        sem = _get_semaphore()
        async with sem:
            async with httpx.AsyncClient(timeout=120.0) as client:
                try:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt}
                            ],
                            "format": "json",
                            "temperature": 0.0
                        },
                        headers={"Authorization": f"Bearer {self.api_key}"}
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data['choices'][0]['message']['content']
                except Exception as e:
                    logger.error(f"LLM Call failed to {self.base_url} [model={self.model}]: {type(e).__name__}: {e}")
                    raise e
