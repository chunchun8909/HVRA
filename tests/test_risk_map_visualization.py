#!/usr/bin/env python
"""Risk Map 3D visualization contract check."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app


def main() -> int:
    payload = app._build_risk_map_context_payload()
    visual = payload.get("visual_context", {})
    infrared = visual.get("infrared_analysis", {})
    grids = visual.get("contextual_grids", {})
    geometry = visual.get("geometry", {})
    buildings = geometry.get("osm_aligned_buildings", {}).get("buildings", [])
    roads = geometry.get("context_contours", {}).get("roads", [])
    sky_view = infrared.get("raw_grid_status", {}).get("sky_view_factor", {}).get("mean")
    has_raw_cells = any(metric.get("has_raw_cells") for metric in infrared.get("raw_grid_status", {}).values())
    total_raster_cells = sum(len(grid.get("cells", [])) for grid in grids.values())

    checks = {
        "backend_connected": payload.get("backend", {}).get("connected") is True,
        "infrared_available": infrared.get("available") is True,
        "sky_view_normalized": sky_view is not None and 0.0 <= float(sky_view) <= 1.0,
        "heat_exposure_present": infrared.get("heat_exposure_score") is not None,
        "analysis_layers_present": len(grids) >= 7,
        "no_fake_raster_cells": (total_raster_cells > 0) if has_raw_cells else total_raster_cells == 0,
        "buildings_present": len(buildings) > 0,
        "roads_present": len(roads) > 0,
    }

    html = (app.RISK_MAP_TEST_DIR / "index.html").read_text(encoding="utf-8")
    checks["html_uses_backend_first"] = "/api/risk-map/context" in html
    checks["html_has_static_fallback"] = "risk_map_context.json" in html

    snapshot_path = app.RISK_MAP_TEST_DIR / "risk_map_context.json"
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot_sky = (
            snapshot.get("visual_context", {})
            .get("infrared_analysis", {})
            .get("raw_grid_status", {})
            .get("sky_view_factor", {})
            .get("mean")
        )
        snapshot_grids = snapshot.get("visual_context", {}).get("contextual_grids", {})
        snapshot_cells = sum(len(grid.get("cells", [])) for grid in snapshot_grids.values())
        checks["static_snapshot_normalized"] = snapshot_sky is not None and 0.0 <= float(snapshot_sky) <= 1.0
        checks["static_snapshot_no_fake_raster"] = snapshot_cells == 0
    else:
        checks["static_snapshot_normalized"] = False

    print("\nRISK MAP VISUALIZATION CHECK")
    print("=" * 72)
    print(f"Infrared heat exposure: {infrared.get('heat_exposure_score')}")
    print(f"Sky-view factor: {sky_view}")
    print(f"Analysis layers: {len(grids)}")
    print(f"Raw raster available: {has_raw_cells}")
    print(f"Rendered raster cells: {total_raster_cells}")
    print(f"3D buildings: {len(buildings)}")
    print(f"Road contours: {len(roads)}")
    print("-" * 72)
    for name, passed in checks.items():
        print(f"{'OK' if passed else 'FAIL'} {name}")
    print("=" * 72)

    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

