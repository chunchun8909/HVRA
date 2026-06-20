from __future__ import annotations


def generate_mock_visual(gemini_prompt: dict) -> dict:
    return {
        "mode": "mock",
        "model": "mock-gemini",
        "case_id": gemini_prompt["case_id"],
        "selected_strategy_id": gemini_prompt["selected_strategy_id"],
        "image_status": "not_generated",
        "image_path": None,
        "description": "Mock Gemini result. Real image generation is disabled by USE_MOCK_GEMINI=true.",
        "prompt_used": gemini_prompt["prompt"],
    }

