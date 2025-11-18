from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Generator, List, Optional

from ollama import Client, RequestError, ResponseError

from .models import ModelSummary


class OllamaError(RuntimeError):
    """Raised when Ollama cannot fulfill a request."""


def _normalize_base_url(base_url: str) -> str:
    if not base_url:
        return "http://localhost:11434"
    return base_url.rstrip("/")


@lru_cache(maxsize=4)
def _get_client(base_url: str) -> Client:
    """Return a cached Ollama client for the provided base URL."""
    return Client(host=_normalize_base_url(base_url))


def list_models(base_url: str) -> List[ModelSummary]:
    """Return locally available models."""
    client = _get_client(base_url)
    try:
        response = client.list()
    except (RequestError, ResponseError, ConnectionError) as exc:
        raise OllamaError(f"Unable to list models: {exc}") from exc
    models: List[ModelSummary] = []
    for entry in response.models:
        raw = entry.model_dump()
        if "name" not in raw and "model" in raw:
            raw["name"] = raw["model"]
        models.append(ModelSummary.from_raw(raw))
    return models


def fetch_model_details(
    base_url: str, model: str, verbose: bool = False
) -> Dict[str, Any]:
    del verbose  # The Python SDK does not support verbose payloads.
    client = _get_client(base_url)
    try:
        response = client.show(model=model)
    except (RequestError, ResponseError, ConnectionError) as exc:
        raise OllamaError(f"Unable to fetch model details: {exc}") from exc
    return response.model_dump()


def chat_completion(
    base_url: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Blocking chat completion (non-streaming)."""
    client = _get_client(base_url)
    try:
        response = client.chat(stream=False, **payload)
    except (RequestError, ResponseError, ConnectionError) as exc:
        raise OllamaError(f"Chat request failed: {exc}") from exc
    return response.model_dump()


def stream_chat(
    base_url: str,
    payload: Dict[str, Any],
) -> Generator[Dict[str, Any], None, None]:
    """Stream chat completion events."""
    client = _get_client(base_url)
    try:
        stream = client.chat(stream=True, **payload)
        for chunk in stream:
            yield chunk.model_dump()
    except (RequestError, ResponseError, ConnectionError) as exc:
        raise OllamaError(f"Streaming chat failed: {exc}") from exc


def get_version(base_url: str) -> Optional[str]:
    client = _get_client(base_url)
    try:
        response = client._request_raw("GET", "/api/version")
    except (ResponseError, ConnectionError):
        return None
    return response.json().get("version")
