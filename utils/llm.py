from __future__ import annotations

import threading
from typing import Any

from openai import OpenAI

DEFAULT_OPENAI_TIMEOUT = 90.0
_FIXED_TEMPERATURE_PREFIXES = ("o1", "o3", "o4", "gpt-5", "gpt-6")
_FIXED_TEMPERATURE_MODELS: set[str] = set()
_LOCK = threading.Lock()


def create_openai_client(api_key: str | None, timeout: float = DEFAULT_OPENAI_TIMEOUT) -> OpenAI:
    """Cria cliente OpenAI com timeout explícito para evitar travamentos indefinidos de leitura."""
    return OpenAI(
        api_key=api_key or "not-configured",
        timeout=timeout,
        max_retries=2,
    )


def _normalize_model_name(model: str) -> str:
    return (model or "").strip().lower()


def _is_fixed_temperature_model(model: str) -> bool:
    normalized = _normalize_model_name(model)
    if normalized.startswith(_FIXED_TEMPERATURE_PREFIXES):
        return True
    with _LOCK:
        return normalized in _FIXED_TEMPERATURE_MODELS


def _is_unsupported_temperature_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "temperature" not in message:
        return False
    return (
        "unsupported" in message
        or "does not support" in message
        or "not support" in message
        or "only the default" in message
    )


def create_chat_completion(client: Any, *, model: str, **kwargs: Any) -> Any:
    """
    Executa chat.completions.create omitindo `temperature` para modelos que aceitam
    apenas o valor padrão (ex.: séries o*, gpt-5*, gpt-6*) ou fazendo fallback
    automático caso a API retorne erro 400 por `temperature` não suportado.
    """
    request_kwargs = dict(kwargs)
    if "temperature" in request_kwargs and _is_fixed_temperature_model(model):
        request_kwargs.pop("temperature", None)

    try:
        return client.chat.completions.create(model=model, **request_kwargs)
    except Exception as exc:
        if "temperature" in request_kwargs and _is_unsupported_temperature_error(exc):
            with _LOCK:
                _FIXED_TEMPERATURE_MODELS.add(_normalize_model_name(model))
            request_kwargs.pop("temperature", None)
            return client.chat.completions.create(model=model, **request_kwargs)
        raise
