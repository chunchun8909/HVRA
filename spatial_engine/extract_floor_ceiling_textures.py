from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract floor and ceiling textures from LGTNet panorama output.")
    parser.add_argument("--image", required=True, help="Input panorama used for LGTNet inference.")
    parser.add_argument("--json", required=True, help="LGTNet *_pred.json path.")
    parser.add_argument("--output-dir", required=True, help="Folder where floor.png and ceiling.png are saved.")
    parser.add_argument("--vp", default=None, help="Optional *_vp.txt path.")
    parser.add_argument("--pixels-per-meter", type=float, default=220.0)
    parser.add_argument("--min-size", type=int, default=256)
    parser.add_argument("--max-size", type=int, default=1600)
    return parser.parse_args()


def xyz2uvn(xyz: np.ndarray) -> np.ndarray:
    norm_xy = np.sqrt(xyz[:, [0]] ** 2 + xyz[:, [1]] ** 2)
    norm_xy[norm_xy < 1e-6] = 1e-6
    norm_xyz = np.sqrt(xyz[:, [0]] ** 2 + xyz[:, [1]] ** 2 + xyz[:, [2]] ** 2)
    v = np.arcsin(xyz[:, [2]] / norm_xyz)
    u = np.arcsin(xyz[:, [0]] / norm_xy)
    valid = (xyz[:, [1]] < 0) & (u >= 0)
    u[valid] = np.pi - u[valid]
    valid = (xyz[:, [1]] < 0) & (u <= 0)
    u[valid] = -np.pi - u[valid]
    uv = np.hstack([u, v])
    uv[np.isnan(uv[:, 0]), 0] = 0
    return uv


def uv2xyzn(uv: np.ndarray) -> np.ndarray:
    xyz = np.zeros((uv.shape[0], 3))
    xyz[:, 0] = np.cos(uv[:, 1]) * np.sin(uv[:, 0])
    xyz[:, 1] = np.cos(uv[:, 1]) * np.cos(uv[:, 0])
    xyz[:, 2] = np.sin(uv[:, 1])
    return xyz


def rotate_panorama(img: np.ndarray, vp: np.ndarray) -> np.ndarray:
    sphere_h, sphere_w, _channels = img.shape
    tx, ty = np.meshgrid(range(1, sphere_w + 1), range(1, sphere_h + 1))
    tx = tx.reshape(-1, 1, order="F")
    ty = ty.reshape(-1, 1, order="F")
    angle_x = (tx - sphere_w / 2 - 0.5) / sphere_w * np.pi * 2
    angle_y = -(ty - sphere_h / 2 - 0.5) / sphere_h * np.pi
    xyz_new = uv2xyzn(np.hstack([angle_x, angle_y]))

    rotation = np.linalg.inv(vp.T)
    xyz_old = np.linalg.solve(rotation, xyz_new.T).T
    uv_old = xyz2uvn(xyz_old)

    px = (uv_old[:, 0] + np.pi) / (2 * np.pi) * sphere_w - 0.5
    py = (-uv_old[:, 1] + np.pi / 2) / np.pi * sphere_h - 0.5
    map_x = px.reshape(sphere_h, sphere_w, order="F").astype(np.float32)
    map_y = py.reshape(sphere_h, sphere_w, order="F").astype(np.float32)

    return cv2.remap(img, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def load_pano(image_path: str, vp_path: str | None = None) -> np.ndarray:
    pano = np.array(Image.open(image_path).resize((1024, 512), Image.Resampling.BICUBIC))[..., :3]
    if vp_path:
        with open(vp_path, "r", encoding="utf-8") as file:
            vp = np.array([[float(value) for value in line.split()] for line in file if line.strip()])
        pano = rotate_panorama(pano, vp[2::-1])
        pano = np.clip(pano, 0, 255).astype(np.uint8)
    return pano


def load_layout(json_path: str) -> tuple[np.ndarray, float, float]:
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    points = sorted(data["layoutPoints"]["points"], key=lambda point: point["id"])
    floor_json = np.array([point["xyz"] for point in points], dtype=np.float32)
    floor_json[:, 2] *= -1.0
    camera_height = float(data.get("cameraHeight", 1.6))
    ceiling_height = float(data.get("cameraCeilingHeight", data["layoutHeight"] - camera_height))
    return floor_json, camera_height, ceiling_height


def project_xyz_to_pano_pixels(xyz: np.ndarray, pano_w: int, pano_h: int) -> tuple[np.ndarray, np.ndarray]:
    norm = np.linalg.norm(xyz, axis=-1)
    xyz_norm = xyz / np.maximum(norm[..., None], 1e-8)

    lon = np.arctan2(xyz_norm[..., 0], xyz_norm[..., 2])
    lat = np.arcsin(np.clip(xyz_norm[..., 1], -1.0, 1.0))

    map_x = (lon / (2.0 * math.pi) + 0.5) * pano_w - 0.5
    map_y = (lat / math.pi + 0.5) * pano_h - 0.5
    return map_x.astype(np.float32), map_y.astype(np.float32)


def unwrap_horizontal_surface(
    pano: np.ndarray,
    floor: np.ndarray,
    y_value: float,
    pixels_per_meter: float,
    min_size: int,
    max_size: int,
) -> tuple[np.ndarray, dict]:
    min_x, max_x = float(floor[:, 0].min()), float(floor[:, 0].max())
    min_z, max_z = float(floor[:, 2].min()), float(floor[:, 2].max())
    width_m = max(max_x - min_x, 0.1)
    depth_m = max(max_z - min_z, 0.1)
    out_w = int(np.clip(round(width_m * pixels_per_meter), min_size, max_size))
    out_h = int(np.clip(round(depth_m * pixels_per_meter), min_size, max_size))

    xs = np.linspace(min_x, max_x, out_w, dtype=np.float32)
    zs = np.linspace(min_z, max_z, out_h, dtype=np.float32)
    grid_x = np.repeat(xs[None, :], out_h, axis=0)
    grid_z = np.repeat(zs[:, None], out_w, axis=1)
    grid_y = np.full_like(grid_x, y_value)
    surface_xyz = np.stack([grid_x, grid_y, grid_z], axis=-1)

    map_x, map_y = project_xyz_to_pano_pixels(surface_xyz, pano.shape[1], pano.shape[0])
    texture = cv2.remap(pano, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    texture = np.flipud(texture)
    polygon_px = np.column_stack(
        [
            (floor[:, 0] - min_x) / width_m * (out_w - 1),
            (max_z - floor[:, 2]) / depth_m * (out_h - 1),
        ]
    ).astype(np.int32)
    mask = np.zeros((out_h, out_w), dtype=np.uint8)
    cv2.fillPoly(mask, [polygon_px], 255)
    texture_rgba = np.dstack([texture, mask])
    return texture, {
        "bounds_xz": [[min_x, min_z], [max_x, max_z]],
        "width_px": out_w,
        "height_px": out_h,
        "width_m": round(width_m, 4),
        "depth_m": round(depth_m, 4),
        "polygon_px": polygon_px.tolist(),
        "masked_pixel_count": int(np.count_nonzero(mask)),
        "total_pixel_count": int(mask.size),
        "mask_coverage_pct": round(float(np.count_nonzero(mask) / mask.size * 100), 3),
        "rgba_texture": texture_rgba,
    }


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    vp_path = args.vp
    if vp_path is None:
        candidate = str(Path(args.json).with_name(Path(args.json).name.replace("_pred.json", "_vp.txt")))
        vp_path = candidate if os.path.exists(candidate) else None

    pano = load_pano(args.image, vp_path=vp_path)
    floor, camera_height, ceiling_height = load_layout(args.json)

    floor_texture, floor_meta = unwrap_horizontal_surface(
        pano, floor, camera_height, args.pixels_per_meter, args.min_size, args.max_size
    )
    ceiling_texture, ceiling_meta = unwrap_horizontal_surface(
        pano, floor, -ceiling_height, args.pixels_per_meter, args.min_size, args.max_size
    )

    floor_path = output_dir / "floor.png"
    ceiling_path = output_dir / "ceiling.png"
    floor_rgba = floor_meta.pop("rgba_texture")
    ceiling_rgba = ceiling_meta.pop("rgba_texture")
    Image.fromarray(floor_rgba, mode="RGBA").save(floor_path)
    Image.fromarray(ceiling_rgba, mode="RGBA").save(ceiling_path)

    manifest = {
        "image": args.image,
        "json": args.json,
        "vp": vp_path,
        "floor": {**floor_meta, "path": str(floor_path), "surface_id": "floor"},
        "ceiling": {**ceiling_meta, "path": str(ceiling_path), "surface_id": "ceiling"},
    }
    with open(output_dir / "manifest.json", "w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)

    print(f"Saved floor and ceiling textures to {output_dir}")


if __name__ == "__main__":
    main()
