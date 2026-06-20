from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

from utils.config import Settings


def _image_size(path: Path) -> dict:
    if not path.exists():
        return {"width": None, "height": None}
    if path.suffix.lower() == ".png":
        with path.open("rb") as file:
            file.seek(16)
            return {
                "width": int.from_bytes(file.read(4), "big"),
                "height": int.from_bytes(file.read(4), "big"),
            }
    return {"width": None, "height": None}


def _fallback_layout(building_info: dict, image_path: Path | None) -> dict:
    area = float(building_info.get("room_area_m2") or 18.0)
    aspect = 1.35
    width = math.sqrt(area / aspect)
    depth = area / width
    height = float(building_info.get("room_height_m") or 2.7)
    half_w = width / 2
    half_d = depth / 2
    points = [
        {"id": 0, "xyz": [-half_w, 0.0, -half_d]},
        {"id": 1, "xyz": [half_w, 0.0, -half_d]},
        {"id": 2, "xyz": [half_w, 0.0, half_d]},
        {"id": 3, "xyz": [-half_w, 0.0, half_d]},
    ]
    walls = []
    for index, pair in enumerate([(0, 1), (1, 2), (2, 3), (3, 0)]):
        walls.append({"pointsIdx": list(pair), "normal": [0.0, 0.0, 0.0], "id": index})

    return {
        "mode": "fallback_layout",
        "source_image": str(image_path) if image_path else None,
        "image_size": _image_size(image_path) if image_path else {"width": None, "height": None},
        "cameraHeight": 1.6,
        "layoutHeight": height,
        "layoutPoints": {"num": len(points), "points": points},
        "layoutWalls": {"num": len(walls), "walls": walls},
        "notes": ["Fallback rectangular layout generated from room_area_m2 and room_height_m."],
    }


def _latest_lgtnet_json(output_dir: Path, image_stem: str) -> Path | None:
    preferred = output_dir / f"{image_stem}_pred.json"
    if preferred.exists():
        return preferred
    candidates = sorted(output_dir.glob("*_pred.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _run_real_lgtnet(image_path: Path, output_dir: Path, settings: Settings) -> dict:
    lgtnet_root = Path(settings.lgtnet_root)
    python_exe = Path(settings.lgtnet_python)
    if not lgtnet_root.exists():
        raise RuntimeError(f"LGTNet root not found: {lgtnet_root}")
    if not python_exe.exists():
        raise RuntimeError(f"LGTNet Python not found: {python_exe}")
    if not image_path.exists():
        raise FileNotFoundError(f"Panorama image not found: {image_path}")

    staging_dir = output_dir / "lgtnet_input"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_image = staging_dir / image_path.name
    shutil.copy2(image_path, staged_image)

    result = subprocess.run(
        [
            str(python_exe),
            "inference.py",
            "--img_glob",
            str(staged_image),
            "--output_dir",
            str(output_dir / "lgtnet"),
            "--device",
            "cpu",
            "--output_3d",
        ],
        cwd=str(lgtnet_root),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LGTNet failed: {result.stderr[-2000:]}")

    output_json = _latest_lgtnet_json(output_dir / "lgtnet", image_path.stem)
    if not output_json:
        raise RuntimeError("LGTNet completed but no *_pred.json was found.")
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    payload["mode"] = "real_lgtnet"
    payload["source_image"] = str(image_path)
    payload["lgtnet_output_json"] = str(output_json)
    payload["image_size"] = _image_size(image_path)
    return payload




def _cached_lgtnet_layout(image_path: Path, output_dir: Path) -> dict | None:
    output_json = _latest_lgtnet_json(output_dir / "lgtnet", image_path.stem)
    if not output_json:
        return None
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    payload["mode"] = "cached_lgtnet_after_error"
    payload["source_image"] = str(image_path)
    payload["lgtnet_output_json"] = str(output_json)
    payload["image_size"] = _image_size(image_path)
    payload["notes"] = [
        "Real LGTNet inference failed during this run, so the latest valid cached LGTNet prediction JSON was reused.",
        "Wall count and layout geometry come from the cached LGTNet output, not the rectangular fallback.",
    ]
    return payload

def run_lgtnet(
    image_path: Path | None,
    building_info: dict,
    output_dir: Path,
    settings: Settings,
) -> dict:
    if image_path is None or settings.use_mock_lgtnet:
        return _fallback_layout(building_info, image_path)

    try:
        return _run_real_lgtnet(image_path, output_dir, settings)
    except Exception as error:
        cached = _cached_lgtnet_layout(image_path, output_dir)
        if cached is not None:
            cached["lgtnet_error"] = str(error)
            return cached
        fallback = _fallback_layout(building_info, image_path)
        fallback["mode"] = "fallback_after_lgtnet_error"
        fallback["lgtnet_error"] = str(error)
        return fallback

