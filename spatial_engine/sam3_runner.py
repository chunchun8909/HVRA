from __future__ import annotations

import json
import subprocess
from pathlib import Path

from utils.config import Settings


PROMPTS = ["window"]


def _png_size(path: Path) -> tuple[int | None, int | None]:
    if not path.exists() or path.suffix.lower() != ".png":
        return None, None
    with path.open("rb") as file:
        file.seek(16)
        return int.from_bytes(file.read(4), "big"), int.from_bytes(file.read(4), "big")


def _component_dimensions(
    box: list[float],
    wall: dict | None,
    wall_image: Path,
) -> dict:
    image_width, image_height = _png_size(wall_image)
    if not wall or not image_width or not image_height:
        return {
            "width_m": None,
            "height_m": None,
            "bbox_width_px": round(float(box[2] - box[0]), 3),
            "bbox_height_px": round(float(box[3] - box[1]), 3),
            "dimension_source": "sam3_bbox_missing_wall_scale",
        }

    bbox_width_px = max(0.0, float(box[2] - box[0]))
    bbox_height_px = max(0.0, float(box[3] - box[1]))
    width_m = bbox_width_px / image_width * float(wall.get("length_m") or 0)
    height_m = bbox_height_px / image_height * float(wall.get("height_m") or 0)

    return {
        "width_m": round(width_m, 3),
        "height_m": round(height_m, 3),
        "bbox_width_px": round(bbox_width_px, 3),
        "bbox_height_px": round(bbox_height_px, 3),
        "estimated_area_m2": round(width_m * height_m, 3),
        "dimension_source": "sam3_bbox_scaled_to_lgtnet_wall_fragment",
    }


def _fallback_components(room_model: dict, building_info: dict) -> dict:
    walls = room_model.get("walls", [])
    external_wall = next((wall for wall in walls if wall.get("is_external")), walls[0] if walls else None)
    components = []

    if external_wall:
        window_area = building_info.get("window_area_m2")
        if window_area is None:
            window_area = min(external_wall["estimated_area_m2"] * 0.22, 3.2)
        components.append(
            {
                "id": f"{room_model['room']['id']}_WINDOW_01",
                "component_type": "window",
                "wall_id": external_wall["id"],
                "estimated_area_m2": round(float(window_area), 3),
                "width_m": None,
                "height_m": None,
                "bbox_px": None,
                "confidence": 0.55,
                "source": "sam3_fallback_from_building_info",
                "orientation": external_wall["orientation"],
                "glazing_type": building_info.get("glazing_type", "unknown"),
                "has_external_shading": building_info.get("has_external_shading", False),
            }
        )

    return {
        "mode": "fallback_components",
        "components": components,
    }


def _components_from_meta(
    meta_path: Path,
    room_model: dict,
    prompt: str,
    wall: dict | None,
    wall_index: int,
    wall_image: Path,
) -> list[dict]:
    if not meta_path.exists():
        return []
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    components = []
    boxes = meta.get("boxes", [])
    scores = meta.get("scores", [None] * len(boxes))
    for index, box in enumerate(boxes, start=1):
        score = scores[index - 1] if index - 1 < len(scores) else None
        dimensions = _component_dimensions(box, wall, wall_image)
        components.append(
            {
                "id": f"{room_model['room']['id']}_WALL_{wall_index:02d}_{prompt.upper()}_{index:02d}",
                "component_type": prompt,
                "wall_id": wall["id"] if wall else None,
                "estimated_area_m2": dimensions.get("estimated_area_m2"),
                "width_m": dimensions.get("width_m"),
                "height_m": dimensions.get("height_m"),
                "bbox_px": box,
                "bbox_width_px": dimensions.get("bbox_width_px"),
                "bbox_height_px": dimensions.get("bbox_height_px"),
                "confidence": score,
                "source": str(meta_path),
                "wall_fragment_image": str(wall_image),
                "dimension_source": dimensions.get("dimension_source"),
            }
        )
    return components


def _extract_wall_sides(
    image_path: Path,
    lgtnet_layout: dict | None,
    output_dir: Path,
    settings: Settings,
) -> list[Path]:
    lgtnet_layout = lgtnet_layout or {}
    lgtnet_json = lgtnet_layout.get("lgtnet_output_json")
    if not lgtnet_json:
        raise RuntimeError("LGTNet output JSON is missing; cannot create straight wall images for SAM3.")

    json_path = Path(lgtnet_json)
    if not json_path.exists():
        raise RuntimeError(f"LGTNet output JSON not found: {json_path}")

    lgtnet_root = Path(settings.lgtnet_root)
    python_exe = Path(settings.lgtnet_python)
    script = lgtnet_root / "extract_wall_sides.py"
    if not python_exe.exists():
        raise RuntimeError(f"LGTNet Python not found: {python_exe}")
    if not script.exists():
        raise RuntimeError(f"LGTNet wall extraction script not found: {script}")

    wall_output = output_dir / "wall_sides"
    wall_output.mkdir(parents=True, exist_ok=True)
    command = [
        str(python_exe),
        str(script),
        "--image",
        str(image_path),
        "--json",
        str(json_path),
        "--output-dir",
        str(wall_output),
    ]
    vp_path = json_path.with_name(json_path.name.replace("_pred.json", "_vp.txt"))
    if vp_path.exists():
        command.extend(["--vp", str(vp_path)])

    result = subprocess.run(
        command,
        cwd=str(lgtnet_root),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LGTNet wall extraction failed: {result.stderr[-2000:]}")

    manifest_path = wall_output / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"LGTNet wall extraction did not write manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [Path(path) for path in manifest.get("walls", []) if Path(path).exists()]


def _run_sam3_on_wall(
    wall_image: Path,
    wall: dict | None,
    wall_index: int,
    room_model: dict,
    output_dir: Path,
    settings: Settings,
) -> list[dict]:
    sam3_root = Path(settings.sam3_root)
    python_exe = Path(settings.sam3_python)
    script = sam3_root / "sam3_wall_window_door_test.py"
    if not python_exe.exists():
        raise RuntimeError(f"SAM3 Python not found: {python_exe}")
    if not script.exists():
        raise RuntimeError(f"SAM3 test script not found: {script}")

    sam_output = output_dir / "sam3" / f"wall_{wall_index:02d}"
    sam_output.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            str(python_exe),
            str(script),
            "--image",
            str(wall_image),
            "--output-dir",
            str(sam_output),
            "--sam3-src",
            str(sam3_root / "sam3-main"),
            "--prompts",
            *PROMPTS,
        ],
        cwd=str(sam3_root.parent),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"SAM3 failed: {result.stderr[-2000:]}")

    components = []
    for prompt in PROMPTS:
        components.extend(
            _components_from_meta(sam_output / f"{prompt}_meta.json", room_model, prompt, wall, wall_index, wall_image)
        )
    return components


def _components_from_cached_wall_outputs(
    wall_images: list[Path],
    room_model: dict,
    output_dir: Path,
) -> list[dict]:
    walls = room_model.get("walls", [])
    components = []
    for wall_index, wall_image in enumerate(wall_images):
        wall = walls[wall_index] if wall_index < len(walls) else None
        sam_output = output_dir / "sam3" / f"wall_{wall_index:02d}"
        if not sam_output.exists():
            continue
        for prompt in PROMPTS:
            components.extend(
                _components_from_meta(
                    sam_output / f"{prompt}_meta.json",
                    room_model,
                    prompt,
                    wall,
                    wall_index,
                    wall_image,
                )
            )
    return components


def _run_real_sam3(
    image_path: Path,
    room_model: dict,
    output_dir: Path,
    settings: Settings,
    lgtnet_layout: dict | None,
) -> dict:
    wall_images = _extract_wall_sides(image_path, lgtnet_layout, output_dir, settings)
    if not wall_images:
        raise RuntimeError("No straight wall images were extracted from LGTNet output.")

    cached_components = _components_from_cached_wall_outputs(wall_images, room_model, output_dir)
    if cached_components:
        return {
            "mode": "real_sam3_wall_images_cached",
            "components": cached_components,
            "sam3_output_dir": str(output_dir / "sam3"),
            "wall_side_dir": str(output_dir / "wall_sides"),
            "wall_images": [str(path) for path in wall_images],
        }

    walls = room_model.get("walls", [])
    components = []
    for wall_index, wall_image in enumerate(wall_images):
        wall = walls[wall_index] if wall_index < len(walls) else None
        components.extend(_run_sam3_on_wall(wall_image, wall, wall_index, room_model, output_dir, settings))

    return {
        "mode": "real_sam3_wall_images",
        "components": components,
        "sam3_output_dir": str(output_dir / "sam3"),
        "wall_side_dir": str(output_dir / "wall_sides"),
        "wall_images": [str(path) for path in wall_images],
    }


def run_sam3(
    image_path: Path | None,
    room_model: dict,
    building_info: dict,
    output_dir: Path,
    settings: Settings,
    lgtnet_layout: dict | None = None,
) -> dict:
    if image_path is None or settings.use_mock_sam3:
        return _fallback_components(room_model, building_info)

    try:
        result = _run_real_sam3(image_path, room_model, output_dir, settings, lgtnet_layout)
        if not result["components"]:
            fallback = _fallback_components(room_model, building_info)
            fallback["mode"] = "fallback_after_empty_sam3"
            return fallback
        return result
    except Exception as error:
        fallback = _fallback_components(room_model, building_info)
        fallback["mode"] = "fallback_after_sam3_error"
        fallback["sam3_error"] = str(error)
        return fallback
