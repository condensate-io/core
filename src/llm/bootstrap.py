import os
import httpx
import logging
import asyncio

logger = logging.getLogger("LLMBootstrap")

async def bootstrap_llm():
    """
    Ensure the configured models are pulled in local Ollama and warmed up.
    Also performs basic GPU diagnostics.
    """
    import json
    configs = []
    
    # 0. GPU Diagnostics
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"GPU Detected: {gpu_name}")
        else:
            logger.warning("GPU not detected by PyTorch. LLM (if local) and NER will run on CPU.")
    except Exception as e:
        logger.debug(f"GPU check failed: {e}")

    # 1. Load configs from file or environment
    config_path = "llm_config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                configs = data.get("configs", [])
        except Exception as e:
            logger.warning(f"Failed to read {config_path}: {e}")
    
    # Fallback to environment if no configs found
    if not configs:
        configs = [{
            "baseUrl": os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
            "model": os.getenv("LLM_MODEL", "phi3"),
            "is_active": True,
            "is_primary": True
        }]

    async with httpx.AsyncClient(timeout=600.0) as client:
        for config in configs:
            if not config.get("is_active"):
                continue
                
            base_url = config.get("baseUrl", "")
            if not base_url: continue
            
            ollama_host = base_url.split("/v1")[0]
            model_name = config.get("model", "")
            
            # Skip pulling for remote providers
            is_local = any(x in ollama_host for x in ["ollama", "localhost", "127.0.0.1", "172.18"])
            
            if is_local:
                logger.info(f"Bootstrapping LLM: Checking for {model_name} at {ollama_host}...")
                try:
                    resp = await client.get(f"{ollama_host}/api/tags")
                    if resp.status_code == 200:
                        models = [m['name'] for m in resp.json().get('models', [])]
                        if any(model_name in m for m in models):
                            logger.info(f"Model {model_name} already exists.")
                        else:
                            logger.info(f"Pulling model {model_name} (this may take a few minutes)...")
                            pull_resp = await client.post(
                                f"{ollama_host}/api/pull",
                                json={"name": model_name, "stream": False},
                                timeout=None
                            )
                            pull_resp.raise_for_status()
                            logger.info(f"Successfully pulled {model_name}.")
                except Exception as e:
                    logger.warning(f"Failed to pull {model_name} at {ollama_host}: {e}")

            # Warmup if primary (even if remote, to ensure connection is hot)
            if config.get("is_primary"):
                logger.info(f"Warming up primary model {model_name} at {base_url}...")
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "hello"}]
                }
                if any(m in model_name.lower() for m in ["o1-", "o3-", "nano"]):
                    payload["max_completion_tokens"] = 10
                else:
                    payload["max_tokens"] = 1
                    
                try:
                    await client.post(
                        f"{base_url}/chat/completions",
                        json=payload,
                        headers={"Authorization": f"Bearer {config.get('apiKey', 'ollama')}"}
                    )
                    logger.info(f"Warmup complete for {model_name}.")
                except Exception as e:
                    logger.warning(f"Warmup failed for {model_name}: {e}")
