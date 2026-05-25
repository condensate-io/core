import hashlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_ENCODING = "cl100k_base"


def count_tokens(text: str, model: Optional[str] = None) -> int:
    if not text:
        return 0
    try:
        import tiktoken

        if model:
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                encoding = tiktoken.get_encoding(_DEFAULT_ENCODING)
        else:
            encoding = tiktoken.get_encoding(_DEFAULT_ENCODING)
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def count_context_items(items: List[str], model: Optional[str] = None) -> int:
    return count_tokens("\n\n".join(items), model)


def build_token_metrics(
    *,
    router_prompt: str,
    context: str,
    query: str,
    synthesized: bool,
    sys_prompt: str = "",
    user_msg: str = "",
    model: Optional[str] = None,
) -> Dict[str, int]:
    answer_prompt = ""
    total_answer_call = 0
    if synthesized:
        answer_prompt = f"{sys_prompt}\n{user_msg}"
        total_answer_call = count_tokens(answer_prompt, model)

    return {
        "router_classification": count_tokens(router_prompt, model),
        "retrieved_context": count_tokens(context, model),
        "answer_prompt": count_tokens(answer_prompt, model) if synthesized else 0,
        "total_answer_call": total_answer_call,
    }


def log_token_metrics(
    token_metrics: Dict[str, int],
    *,
    project_id: Any,
    query: str,
    strategy: str,
) -> None:
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
    logger.info(
        "retrieve token_metrics project_id=%s query_hash=%s strategy=%s metrics=%s",
        project_id,
        query_hash,
        strategy,
        token_metrics,
    )
