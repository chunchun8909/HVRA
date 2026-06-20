"""Non-interactive LGTNet asset-registry integration smoke test.

This script reads an LGTNet prediction JSON, derives simple room/wall geometry,
optionally calls an external 3D asset registry with an API key from .env, and
writes a JSON manifest describing which web-optimized 3D components could be
injected into the room model.

It intentionally does not create a web interface and does not expose API keys to
browser code.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LGTNET_JSON = ROOT_DIR / "data" / "output" / "spatial" / "lgtnet" / "demo1_pred.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "lgtnet_asset_manifest.json"


@dataclass
class AssetCandidate:
    category: str
    query: str
    placement_hint: dict[str, Any]
    registry_status: str
    asset_id: str | None = None
    asset_name: str | None = None
    asset_url: str | None = None
    raw_registry_item: dict[str, Any] | None = None
    error: str | None = None


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def layout_points(layout: dict[str, Any]) -> list[dict[str, float]]:
    points = layout.get("layoutPoints", {}).get("points", [])
    result = []
    for point in points:
        xyz = point.get("xyz", [0, 0, 0])
        result.append({"x": float(xyz[0]), "y": float(xyz[1]), "z": float(xyz[2]), "id": point.get("id")})
    return result


def wall_segments(points: list[dict[str, float]]) -> list[dict[str, Any]]:
    walls = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        dx = end["x"] - start["x"]
        dz = end["z"] - start["z"]
        length = (dx**2 + dz**2) ** 0.5
        walls.append(
            {
                "wall_index": index,
                "id": f"LGTNET_WALL_{index:02d}",
                "start": {"x": start["x"], "z": start["z"]},
                "end": {"x": end["x"], "z": end["z"]},
                "length_m_raw": round(length, 3),
                "midpoint": {"x": round((start["x"] + end["x"]) / 2, 3), "z": round((start["z"] + end["z"]) / 2, 3)},
            }
        )
    return walls


def bbox(points: list[dict[str, float]]) -> dict[str, float]:
    xs = [point["x"] for point in points]
    zs = [point["z"] for point in points]
    return {
        "min_x": round(min(xs), 3),
        "max_x": round(max(xs), 3),
        "min_z": round(min(zs), 3),
        "max_z": round(max(zs), 3),
        "center_x": round((min(xs) + max(xs)) / 2, 3),
        "center_z": round((min(zs) + max(zs)) / 2, 3),
    }


def default_queries() -> list[tuple[str, str]]:
    return [
        ("window_dressing", "web optimized low poly interior window curtain blinds glb"),
        ("interior_shading", "web optimized roller blind venetian blind glb"),
        ("furniture", "web optimized low poly room chair table glb"),
        ("plant", "web optimized low poly indoor plant glb"),
    ]


def placement_hint(category: str, room_bbox: dict[str, float], walls: list[dict[str, Any]]) -> dict[str, Any]:
    longest_wall = max(walls, key=lambda wall: wall["length_m_raw"]) if walls else None
    center = {"x": room_bbox["center_x"], "y": 0.0, "z": room_bbox["center_z"]}
    if category in {"window_dressing", "interior_shading"} and longest_wall:
        return {
            "target": "longest_wall",
            "wall_id": longest_wall["id"],
            "position": {"x": longest_wall["midpoint"]["x"], "y": 1.35, "z": longest_wall["midpoint"]["z"]},
            "reason": "placeholder target until SAM/window metadata is linked",
        }
    if category == "plant":
        return {
            "target": "near_window_or_corner",
            "position": {"x": room_bbox["max_x"] - 0.45, "y": 0.0, "z": room_bbox["min_z"] + 0.45},
            "reason": "simple non-interactive placement for smoke test",
        }
    return {
        "target": "open_floor_area",
        "position": center,
        "reason": "simple non-interactive placement for smoke test",
    }


def extract_asset_url(item: dict[str, Any]) -> str | None:
    for key in ("glb_url", "gltf_url", "download_url", "asset_url", "url"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    files = item.get("files")
    if isinstance(files, list):
        for file_item in files:
            if not isinstance(file_item, dict):
                continue
            url = file_item.get("url") or file_item.get("download_url")
            name = str(file_item.get("name") or file_item.get("format") or "").lower()
            if url and ("glb" in name or "gltf" in name):
                return str(url)
    return None


def call_registry(
    registry_url: str,
    api_key: str,
    query: str,
    category: str,
    timeout_s: int,
) -> tuple[str, dict[str, Any] | None, str | None]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "X-API-Key": api_key,
    }
    payload = {"query": query, "category": category, "format": "glb", "max_results": 1}
    try:
        response = requests.post(registry_url, headers=headers, json=payload, timeout=timeout_s)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001 - smoke test should capture all registry failures in output JSON.
        return "error", None, str(exc)

    if isinstance(data, dict):
        items = data.get("items") or data.get("results") or data.get("assets") or []
        if isinstance(items, list) and items:
            return "matched", items[0], None
        return "empty", data, None
    return "unexpected_response", {"raw": data}, None


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv(ROOT_DIR / ".env")
    layout = load_json(Path(args.lgtnet_json))
    points = layout_points(layout)
    if len(points) < 3:
        raise ValueError("LGTNet layout has fewer than 3 points; cannot build room geometry summary.")

    walls = wall_segments(points)
    room_bbox = bbox(points)
    registry_url = args.registry_url or os.getenv("ASSET_REGISTRY_API_URL", "").strip()
    api_key = os.getenv(args.api_key_env, "").strip()
    timeout_s = int(args.timeout_s)

    candidates: list[AssetCandidate] = []
    for category, query in default_queries():
        hint = placement_hint(category, room_bbox, walls)
        if args.dry_run or not registry_url or not api_key:
            status = "dry_run" if args.dry_run else "skipped_missing_registry_config"
            candidates.append(AssetCandidate(category=category, query=query, placement_hint=hint, registry_status=status))
            continue

        status, item, error = call_registry(registry_url, api_key, query, category, timeout_s)
        asset_url = extract_asset_url(item or {}) if item else None
        candidates.append(
            AssetCandidate(
                category=category,
                query=query,
                placement_hint=hint,
                registry_status=status,
                asset_id=str((item or {}).get("id")) if isinstance(item, dict) and (item or {}).get("id") is not None else None,
                asset_name=str((item or {}).get("name") or (item or {}).get("title")) if isinstance(item, dict) and ((item or {}).get("name") or (item or {}).get("title")) else None,
                asset_url=asset_url,
                raw_registry_item=item if isinstance(item, dict) else None,
                error=error,
            )
        )

    return {
        "test_name": "lgtnet_asset_registry_integration",
        "interactive": False,
        "source_lgtnet_json": str(Path(args.lgtnet_json).resolve()),
        "registry_url": registry_url or None,
        "api_key_env": args.api_key_env,
        "api_key_loaded": bool(api_key),
        "dry_run": bool(args.dry_run),
        "room_geometry": {
            "wall_count": len(walls),
            "layout_height_m_raw": layout.get("layoutHeight"),
            "bbox": room_bbox,
            "walls": walls,
        },
        "asset_candidates": [asdict(candidate) for candidate in candidates],
        "next_integration_target": "spatial_index_with_assets.json",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a non-interactive LGTNet + 3D asset-registry integration smoke test.")
    parser.add_argument("--lgtnet-json", default=str(DEFAULT_LGTNET_JSON), help="Path to LGTNet prediction JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output manifest JSON path.")
    parser.add_argument("--registry-url", default=None, help="Asset registry API URL. Defaults to ASSET_REGISTRY_API_URL from .env.")
    parser.add_argument("--api-key-env", default="ASSET_REGISTRY_API_KEY", help="Name of .env variable containing the registry API key.")
    parser.add_argument("--timeout-s", default=20, help="Registry API timeout in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Do not call the registry API; only produce placement/query plan.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_manifest(args)
    output = Path(args.output)
    write_json(output, manifest)
    print(f"Wrote asset registry integration manifest: {output}")
    print(f"Wall count: {manifest['room_geometry']['wall_count']}")
    print(f"Asset candidates: {len(manifest['asset_candidates'])}")
    print(f"Registry call enabled: {bool(manifest['registry_url'] and manifest['api_key_loaded'] and not manifest['dry_run'])}")


if __name__ == "__main__":
    main()

