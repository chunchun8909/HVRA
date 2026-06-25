from __future__ import annotations

import json
import re
from pathlib import Path
from time import time
from typing import Any

from utils.config import INTERMEDIATE_DIR, SPATIAL_OUTPUT_DIR
from utils.file_io import read_json


def _read_optional(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def _baseline_from_diagnosis(diagnosis: dict[str, Any]) -> dict[str, Any]:
    details = diagnosis.get("calculation_details", {})
    room = diagnosis.get("room_diagnosis", {})
    scores = diagnosis.get("component_scores", {})
    return {
        "peak_indoor_operative_temperature_c": details.get("peak_indoor_operative_temperature_c") or room.get("peak_indoor_operative_temperature_c") or 33.0,
        "wbgt_peak_c": details.get("wbgt_peak_c") or room.get("wbgt_peak_c") or 27.0,
        "overheating_hours": details.get("overheating_hours") or room.get("overheating_hours") or 0,
        "nocturnal_recovery_score": scores.get("nocturnal_recovery") or details.get("nocturnal_recovery_score") or 0,
        "estimated_indoor_3am_temp_c": details.get("estimated_indoor_3am_temp_c") or room.get("estimated_indoor_3am_temp_c") or 26.0,
        "composite_room_risk_score": room.get("composite_room_risk_score") or diagnosis.get("final_score") or 0,
        "final_score": diagnosis.get("final_score") or room.get("final_score") or 0,
        "risk_level": diagnosis.get("risk_level") or "unknown",
    }


def _clean_window(window: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in window.items() if key not in {"source", "wall_fragment_image"}}


def _viewer_data(spatial_index: dict[str, Any]) -> dict[str, Any]:
    ts = int(time())
    walls = []
    for index, wall in enumerate(spatial_index.get("walls", [])):
        walls.append({
            "id": wall.get("id"),
            "start_xyz": wall.get("start_xyz"),
            "end_xyz": wall.get("end_xyz"),
            "orientation": wall.get("orientation"),
            "is_external": wall.get("is_external"),
            "texture": f"wall_sides/wall_{index:02d}.png?v={ts}",
        })
    return {
        "room": {
            "area_m2": spatial_index.get("room", {}).get("area_m2"),
            "height_m": spatial_index.get("room", {}).get("height_m"),
        },
        "points": [point.get("xyz") if isinstance(point, dict) else point for point in spatial_index.get("layout_points", [])],
        "walls": walls,
        "windows": [_clean_window(window) for window in spatial_index.get("windows", spatial_index.get("components", []))],
        "textures": {
            "floor": f"surface_textures/floor.png?v={ts}",
            "ceiling": f"surface_textures/ceiling.png?v={ts}",
        },
    }


def _replace_const(html: str, name: str, value: Any, next_token: str) -> str:
    pattern = rf"const {name}=.*?;{re.escape(next_token)}"
    replacement = f"const {name}={json.dumps(value, ensure_ascii=False)};{next_token}"
    return re.sub(pattern, replacement, html, count=1, flags=re.S)


def _main_wall_id(spatial_index: dict[str, Any], problem_map: dict[str, Any]) -> str | None:
    for problem in problem_map.get("problems", []):
        for target in problem.get("spatial_targets", []):
            if target.get("wall_id"):
                return target.get("wall_id")
    windows = spatial_index.get("windows", [])
    largest = max(windows, key=lambda item: item.get("estimated_area_m2") or 0, default={})
    return largest.get("wall_id") or (spatial_index.get("walls", [{}])[-1].get("id"))


def refresh_full_texture_component_check(spatial_index: dict[str, Any]) -> str:
    path = SPATIAL_OUTPUT_DIR / "room_3d_full_texture_component_check.html"
    if not path.exists():
        return "missing"
    html = path.read_text(encoding="utf-8")
    packages = _read_optional(INTERMEDIATE_DIR / "phase3_strategy_packages.json")
    scenarios = _read_optional(INTERMEDIATE_DIR / "retrofit_generation_scenarios.json")
    diagnosis = _read_optional(INTERMEDIATE_DIR / "diagnosis_result.json")
    problem_map = _read_optional(INTERMEDIATE_DIR / "problem_map.json")
    viewer_data = _viewer_data(spatial_index)

    room_label = f"{viewer_data['room'].get('area_m2') or 'n/a'} m2 | {viewer_data['room'].get('height_m') or 'n/a'} m"
    html = re.sub(r'<div class="row"><span>room</span><b>.*?</b></div>', f'<div class="row"><span>room</span><b>{room_label}</b></div>', html, count=1)
    html = _replace_const(html, "DATA", viewer_data, "const errorBox")
    html = _replace_const(html, "SCENARIO_REPORT", scenarios, "const BASELINE_REPORT")
    html = _replace_const(html, "BASELINE_REPORT", _baseline_from_diagnosis(diagnosis), "\nconst PROBLEM_MAP")
    html = _replace_const(html, "PROBLEM_MAP", problem_map, "\nconst objects")
    if "const PHASE3_PACKAGES=" in html:
        html = _replace_const(html, "PHASE3_PACKAGES", packages, "const BASELINE_REPORT")
    else:
        html = html.replace(
            "const BASELINE_REPORT=",
            f"const PHASE3_PACKAGES={json.dumps(packages, ensure_ascii=False)};const BASELINE_REPORT=",
            1,
        )

    main_wall_id = _main_wall_id(spatial_index, problem_map)
    if main_wall_id:
        html = re.sub(
            r"const host=wallItems\[[0-9]+\];",
            f"const hostIndex=Math.max(0,DATA.walls.findIndex(w=>w.id===\"{main_wall_id}\"));const host=wallItems[hostIndex]||wallItems[0];",
            html,
            count=1,
        )
        html = re.sub(
            r"DATA\.windows\|\|\[\]\)\.find\(w=>w\.wall_id===['\"][^'\"]+['\"]\)",
            f"DATA.windows||[]).find(w=>w.wall_id===\"{main_wall_id}\")",
            html,
            count=1,
        )
    path.write_text(html, encoding="utf-8")
    return str(path)

