from __future__ import annotations

from utils.config import Settings
from .agent import review_consistency


def run_review_loop(payload: dict, settings: Settings) -> dict:
    return review_consistency(payload, settings)

