from __future__ import annotations

from pathlib import Path

from utils.config import INPUT_DIR, SPATIAL_OUTPUT_DIR, Settings, load_settings
from .lgtnet_runner import run_lgtnet
from .mock_spatial_output import build_mock_spatial_index
from .room_decomposer import decompose_room
from .room_viewer import export_room_view
from .sam3_runner import run_sam3
from .scaling_engine import build_scaling_report, scale_layout_to_room
from .surface_texture_runner import extract_surface_textures
from utils.file_io import write_json


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def _image_priority(path: Path) -> tuple[int, float, str]:
    path_text = str(path).lower()
    name = path.name.lower()
    if "pano_image" in path_text:
        folder_score = 0
    elif "pano" in name or "panorama" in name:
        folder_score = 1
    elif "images" in path_text:
        folder_score = 2
    elif "perspective_image" in path_text:
        folder_score = 3
    else:
        folder_score = 4
    return (folder_score, -path.stat().st_mtime, name)


def _find_pano_image() -> Path | None:
    explicit_candidates = [
        INPUT_DIR / "images" / "pano_image" / "pano.png",
        INPUT_DIR / "images" / "pano_image" / "pano.jpg",
        INPUT_DIR / "images" / "pano_image" / "pano.jpeg",
        INPUT_DIR / "images" / "pano.png",
        INPUT_DIR / "images" / "pano.jpg",
        INPUT_DIR / "images" / "pano.jpeg",
        INPUT_DIR / "images" / "perspective_image" / "perspective.png",
        INPUT_DIR / "images" / "perspective_image" / "perspective.jpg",
        INPUT_DIR / "images" / "perspective.png",
        INPUT_DIR / "images" / "perspective.jpg",
    ]
    for path in explicit_candidates:
        if path.exists():
            return path

    image_root = INPUT_DIR / "images"
    if not image_root.exists():
        return None

    candidates = [
        path
        for path in image_root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    if candidates:
        return sorted(candidates, key=_image_priority)[0]
    return None


def create_spatial_index(building_info: dict, settings: Settings | None = None) -> dict:
    settings = settings or load_settings()
    SPATIAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if settings.use_mock_lgtnet or settings.use_mock_sam3:
        return build_mock_spatial_index(building_info)

    image_path = _find_pano_image()
    raw_layout = run_lgtnet(image_path, building_info, SPATIAL_OUTPUT_DIR, settings)
    scaled_layout = scale_layout_to_room(raw_layout, building_info)
    scaling_report = build_scaling_report(raw_layout, scaled_layout, building_info)
    write_json(SPATIAL_OUTPUT_DIR / "scaling_report.json", scaling_report)
    room_model = decompose_room(scaled_layout, building_info)
    surface_textures = extract_surface_textures(image_path, raw_layout, SPATIAL_OUTPUT_DIR, settings)
    sam3_result = run_sam3(image_path, room_model, building_info, SPATIAL_OUTPUT_DIR, settings, raw_layout)
    components = [component for component in sam3_result["components"] if component["component_type"] == "window"]
    windows = components
    doors = []
    furniture = []

    room_model["components"] = components
    room_model["windows"] = windows
    room_model["doors"] = doors
    room_model["furniture"] = furniture
    room_model["source_image"] = str(image_path) if image_path else None
    room_model["lgtnet"] = {
        "mode": raw_layout.get("mode"),
        "image_size": raw_layout.get("image_size"),
        "scale": scaled_layout.get("scale"),
        "error": raw_layout.get("lgtnet_error"),
    }
    room_model["scaling"] = {
        "mode": scaling_report.get("mode"),
        "scale_factor": scaling_report.get("scale_factor"),
        "source_area_m2": scaling_report.get("source_area_m2"),
        "target_area_m2": scaling_report.get("target_area_m2"),
        "scaled_area_m2": scaling_report.get("scaled_area_m2"),
        "area_error_pct": scaling_report.get("area_error_pct"),
        "target_height_m": scaling_report.get("target_height_m"),
        "scaled_height_m": scaling_report.get("scaled_height_m"),
        "validation": scaling_report.get("validation"),
        "report_path": str(SPATIAL_OUTPUT_DIR / "scaling_report.json"),
    }
    room_model["sam3"] = {
        "mode": sam3_result.get("mode"),
        "error": sam3_result.get("sam3_error"),
        "output_dir": sam3_result.get("sam3_output_dir"),
        "wall_side_dir": sam3_result.get("wall_side_dir"),
        "wall_images": sam3_result.get("wall_images"),
    }
    room_model["surface_textures"] = surface_textures
    room_model["scale_source"] = scaled_layout.get("scale", {}).get("scale_source")

    view_path = export_room_view(room_model, SPATIAL_OUTPUT_DIR / "room_3d_view.html")
    room_model["view_3d_html"] = view_path
    return room_model
