from __future__ import annotations


def require_keys(data: dict, keys: list[str], label: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise ValueError(f"{label} is missing required keys: {', '.join(missing)}")

