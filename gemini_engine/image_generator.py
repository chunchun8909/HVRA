from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from utils.config import Settings
from .mock_gemini import generate_mock_visual


def _extract_text(result: dict) -> str:
    parts = (
        result.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    return "\n".join(text for text in texts if text).strip()


def generate_visual(gemini_prompt: dict, settings: Settings) -> dict:
    if settings.use_mock_gemini:
        return generate_mock_visual(gemini_prompt)

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Set it or use USE_MOCK_GEMINI=true.")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{settings.gemini_model}:generateContent"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": gemini_prompt["prompt"]}],
            }
        ]
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.gemini_api_key,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP error {error.code}: {body}") from error
    except URLError as error:
        raise RuntimeError("Could not reach Gemini API. Use USE_MOCK_GEMINI=true for offline runs.") from error

    return {
        "mode": "real",
        "model": settings.gemini_model,
        "case_id": gemini_prompt["case_id"],
        "selected_strategy_id": gemini_prompt["selected_strategy_id"],
        "image_status": "prompt_generated",
        "image_path": None,
        "description": _extract_text(result),
        "raw_response": result,
        "prompt_used": gemini_prompt["prompt"],
    }

