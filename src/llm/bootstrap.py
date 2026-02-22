import os
import httpx
import logging
import asyncio

logger = logging.getLogger("LLMBootstrap")

async def bootstrap_llm():
    """
    Ensure the default model is pulled in local Ollama.
    """
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    # Base URL is expected to be /v1 for client. 
    # For pull, we use the naked host.
    ollama_host = base_url.split("/v1")[0]
    model_name = os.getenv("LLM_MODEL", "phi3")
    
    logger.info(f"Bootstrapping LLM: Checking for {model_name} at {ollama_host}...")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            # Check if tags API is healthy
            resp = await client.get(f"{ollama_host}/api/tags")
            if resp.status_code == 200:
                models = [m['name'] for m in resp.json().get('models', [])]
                if any(model_name in m for m in models):
                    logger.info(f"Model {model_name} already exists.")
                    return
            
            logger.info(f"Pulling model {model_name} (this may take a few minutes)...")
            # Trigger pull
            pull_resp = await client.post(
                f"{ollama_host}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=None
            )
            pull_resp.raise_for_status()
            logger.info(f"Successfully pulled {model_name}.")
            
        except Exception as e:
            logger.warning(f"LLM Bootstrap failed: {e}. If running outside Docker/WSL without Ollama, this is expected.")
