from __future__ import annotations

import json
import subprocess
from pathlib import Path

from utils.config import ROOT_DIR, Settings


def extract_surface_textures(
    image_path: Path | None,
    lgtnet_layout: dict,
    output_dir: Path,
    settings: Settings,
) -> dict:
    if image_path is None:
        return {"mode": "missing_source_image", "error": "No panorama image was found."}

    lgtnet_json = lgtnet_layout.get("lgtnet_output_json")
    if not lgtnet_json:
        return {"mode": "missing_lgtnet_json", "error": "LGTNet output JSON is missing."}

    json_path = Path(lgtnet_json)
    if not json_path.exists():
        return {"mode": "missing_lgtnet_json", "error": f"LGTNet output JSON not found: {json_path}"}

    python_exe = Path(settings.lgtnet_python)
    script = ROOT_DIR / "spatial_engine" / "extract_floor_ceiling_textures.py"
    surface_output = output_dir / "surface_textures"
    surface_output.mkdir(parents=True, exist_ok=True)
    if not python_exe.exists():
        return {"mode": "missing_lgtnet_python", "error": f"LGTNet Python not found: {python_exe}"}

    command = [
        str(python_exe),
        str(script),
        "--image",
        str(image_path),
        "--json",
        str(json_path),
        "--output-dir",
        str(surface_output),
    ]
    vp_path = json_path.with_name(json_path.name.replace("_pred.json", "_vp.txt"))
    if vp_path.exists():
        command.extend(["--vp", str(vp_path)])

    result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
    if result.returncode != 0:
        return {"mode": "surface_texture_error", "error": result.stderr[-2000:]}

    manifest_path = surface_output / "manifest.json"
    if not manifest_path.exists():
        return {"mode": "surface_texture_error", "error": f"Manifest not written: {manifest_path}"}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "mode": "real_surface_textures",
        "output_dir": str(surface_output),
        "manifest": str(manifest_path),
        "floor": manifest.get("floor"),
        "ceiling": manifest.get("ceiling"),
        "error": None,
    }
