from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from utils.config import Settings


def _request_json(url: str, payload: dict | None, timeout: int) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP error {error.code}: {body}") from error
    except URLError as error:
        raise RuntimeError("Could not reach Ollama. Start Ollama or set USE_MOCK_LLM=true.") from error


def list_models(settings: Settings) -> list[str]:
    result = _request_json(
        f"{settings.ollama_base_url}/api/tags",
        payload=None,
        timeout=min(settings.ollama_timeout_seconds, 30),
    )
    return [model.get("name", "") for model in result.get("models", []) if model.get("name")]


def check_model_available(settings: Settings) -> dict[str, Any]:
    models = list_models(settings)
    requested = settings.ollama_model
    resolved_model = resolve_model_name(requested, models)
    return {
        "base_url": settings.ollama_base_url,
        "requested_model": requested,
        "resolved_model": resolved_model,
        "available": resolved_model is not None,
        "installed_models": models,
    }


def resolve_model_name(requested_model: str, installed_models: list[str] | None = None) -> str | None:
    models = installed_models if installed_models is not None else []
    if requested_model in models:
        return requested_model
    for model in models:
        if model.split(":", 1)[0] == requested_model:
            return model
    return None


def ensure_model_available(settings: Settings) -> None:
    status = check_model_available(settings)
    if not status["available"]:
        installed = ", ".join(status["installed_models"]) or "none"
        raise RuntimeError(
            f"Ollama model '{status['requested_model']}' is not installed. "
            f"Installed models: {installed}. Run: ollama pull {status['requested_model']}"
        )
    return status["resolved_model"]


def _extract_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError(f"Ollama did not return JSON: {text}")

    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Ollama returned invalid JSON: {text}") from error


def generate_text(settings: Settings, prompt: str) -> str:
    model_name = ensure_model_available(settings)
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
        },
    }

    last_error: Exception | None = None
    for attempt in range(settings.ollama_retries + 1):
        try:
            result = _request_json(
                f"{settings.ollama_base_url}/api/generate",
                payload=payload,
                timeout=settings.ollama_timeout_seconds,
            )
            if "error" in result:
                raise RuntimeError(f"Ollama error: {result['error']}")
            return result.get("response", "").strip()
        except RuntimeError as error:
            last_error = error
            if attempt >= settings.ollama_retries:
                break
            time.sleep(0.75 * (attempt + 1))

    raise RuntimeError(f"Ollama generation failed after retries: {last_error}")


def generate_json(settings: Settings, prompt: str) -> dict[str, Any]:
    text = generate_text(settings, prompt)
    return _extract_json_object(text)
