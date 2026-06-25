from __future__ import annotations

import json
from pathlib import Path

from utils.config import INTERMEDIATE_DIR


def _relative_image(path: Path, output_path: Path) -> str:
    return path.resolve().relative_to(output_path.parent.resolve()).as_posix()


def _viewer_overlays(output_path: Path) -> list[dict]:
    spatial_dir = output_path.parent
    overlays = []

    for surface_id in ["floor", "ceiling"]:
        path = spatial_dir / "surface_textures" / f"{surface_id}.png"
        if path.exists():
            overlays.append(
                {
                    "id": f"{surface_id}_texture",
                    "surface_id": surface_id,
                    "type": "surface",
                    "label": f"{surface_id} texture",
                    "src": _relative_image(path, output_path),
                }
            )

    for path in sorted((spatial_dir / "wall_sides").glob("wall_*.png")):
        wall_id = path.stem
        wall_index = int(wall_id.rsplit("_", 1)[1])
        model_wall_id = f"ROOM_001_WALL_{wall_index:02d}"
        overlays.append(
            {
                "id": f"{wall_id}_fragment",
                "wall_id": model_wall_id,
                "type": "fragment",
                "label": f"{wall_id} fragment",
                "src": _relative_image(path, output_path),
            }
        )
    return overlays


def _viewer_strategy_state() -> dict:
    options_path = INTERMEDIATE_DIR / "retrofit_validation_options.json"
    if not options_path.exists():
        return {"options": [], "by_wall": {}, "recommended_strategy_id": None}
    try:
        payload = json.loads(options_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"options": [], "by_wall": {}, "recommended_strategy_id": None}

    options = []
    by_wall: dict[str, list[dict]] = {}
    for index, option in enumerate(payload.get("validated_options", [])[:3], start=1):
        strategy = option.get("strategy", {})
        strategy_id = strategy.get("strategy_id") or f"option_{index}"
        wall_ids = []
        for targets in option.get("problem_targets", {}).values():
            for target in targets:
                wall_id = target.get("wall_id")
                if wall_id and wall_id not in wall_ids:
                    wall_ids.append(wall_id)
        summary = {
            "strategy_id": strategy_id,
            "label": f"option {index}",
            "strategy_name": strategy.get("strategy_name") or f"option {index}",
            "status": option.get("benchmark_result", {}).get("overall"),
            "confidence": option.get("confidence", {}).get("level"),
            "recommendation": option.get("recommendation"),
            "wall_ids": wall_ids,
            "numerical_comparison": option.get("numerical_comparison", []),
        }
        options.append(summary)
        for wall_id in wall_ids:
            by_wall.setdefault(wall_id, []).append(summary)
    return {
        "options": options,
        "by_wall": by_wall,
        "recommended_strategy_id": options[0]["strategy_id"] if options else None,
    }
def export_room_view(room_model: dict, output_path: Path) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(room_model, ensure_ascii=False)
    overlay_data = json.dumps(_viewer_overlays(output_path), ensure_ascii=False)
    strategy_data = json.dumps(_viewer_strategy_state(), ensure_ascii=False)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>room view</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400&family=DM+Sans:wght@400&display=swap" rel="stylesheet">
  <style>
    body {{ margin: 0; font-family: "DM Sans", Arial, sans-serif; background: #f5f4f2; color: #0a0a0a; overflow: hidden; }}
    header {{ height: 46px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 0 14px; border-bottom: 1px solid rgba(0,0,0,0.08); background: #ffffff; }}
    #meta {{ color: #b0b0b0; font: 400 10px "DM Mono", monospace; white-space: nowrap; }}
    #hint {{ display: flex; align-items: center; gap: 8px; color: #b0b0b0; font: 400 10px "DM Mono", monospace; }}
    button {{ border: 1px solid rgba(0,0,0,0.14); background: #ffffff; padding: 4px 8px; cursor: pointer; font: 400 10px "DM Mono", monospace; color: #b0b0b0; }}
    #roomShell {{ display: grid; grid-template-columns: 330px 1fr; height: calc(100vh - 46px); min-height: 0; }}
    #viewerArea {{ position: relative; min-width: 0; min-height: 0; overflow: hidden; background: #f5f4f2; }}
    canvas {{ display: block; width: 100%; height: 100%; cursor: grab; }}
    canvas:active {{ cursor: grabbing; }}
    .appTitle {{ font: 400 10.5px "DM Mono", monospace; letter-spacing: 0.10em; color: #b0b0b0; }}
    .panel {{ z-index: 2; background: rgba(250,248,242,0.96); border: 1px solid rgba(20,18,16,0.14); }}
    #controls {{ width: 330px; height: 100%; overflow: auto; padding: 10px 12px; border-left: 0; border-top: 0; border-bottom: 0; box-shadow: none; }}
    #wallDiagnosisPanel {{ position: absolute; right: 14px; top: 14px; width: 280px; padding: 10px 12px; box-shadow: 0 14px 34px rgba(20,18,16,0.10); }}
    .section {{ width: 100%; margin: 0; padding: 9px 0; background: transparent; border: 0; border-top: 1px solid rgba(20,18,16,0.14); }}
    #controls .section:first-child, #wallDiagnosisPanel .section:first-child {{ border-top: 0; padding-top: 0; }}
    .section.isCollapsed {{ width: 82px; padding: 6px 0; background: transparent; border-top: 1px solid rgba(20,18,16,0.14); }}
    .sectionHeader {{ display: flex; align-items: center; justify-content: space-between; width: 100%; border: 0; background: transparent; padding: 0; font: 400 10.5px "DM Mono", monospace; letter-spacing: 0.10em; color: #8d857b; text-transform: lowercase; }}
    .section.isCollapsed .sectionHeader {{ width: 82px; min-height: 24px; gap: 8px; padding: 5px 10px; border: 1px solid rgba(20,18,16,0.14); border-radius: 100px; background: #f5f4f2; }}
    .section.isCollapsed .sectionHeader span:first-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .sectionBody {{ margin-top: 6px; }}
    .sectionBody[hidden] {{ display: none; }}
    .type1 {{ font: 400 10.5px "DM Mono", monospace; letter-spacing: 0.10em; color: #b0b0b0; }}
    .type2 {{ font: 400 13px "DM Sans", Arial, sans-serif; color: #0a0a0a; }}
    .type3 {{ font: 400 10px "DM Mono", monospace; color: #b0b0b0; }}
    .row {{ display: grid; grid-template-columns: 18px minmax(96px, 1fr) 92px 34px; align-items: center; gap: 6px; margin: 5px 0; font: 400 13px "DM Sans", Arial, sans-serif; }}
    .row input[type="range"] {{ width: 92px; }}
    .orientationRow {{ display: grid; grid-template-columns: 18px minmax(82px, 1fr) 70px; align-items: center; gap: 6px; margin: 5px 0; font: 400 13px "DM Sans", Arial, sans-serif; }}
    .openingRow {{ display: grid; grid-template-columns: minmax(0, 1fr) 70px; align-items: center; gap: 6px; margin: 5px 0; font: 400 13px "DM Sans", Arial, sans-serif; }}
    select {{ width: 70px; border: 1px solid rgba(0,0,0,0.12); background: #fff; padding: 3px 5px; font: 400 10px "DM Mono", monospace; color: #0a0a0a; }}
    .vvRow {{ display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 6px; align-items: start; margin: 5px 0; font: 400 13px "DM Sans", Arial, sans-serif; }}
    .vvRow small {{ display: block; color: #716a61; margin-top: 2px; overflow-wrap: anywhere; }}
    .actions {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin: 0; }}
    #phaseActions {{ padding-bottom: 0; }}
    #phaseActions button {{ height: 30px; }}
    .saveStatus {{ margin-top: 6px; font: 400 10px "DM Mono", monospace; color: #716a61; }}
    textarea {{ width: 100%; height: 92px; resize: vertical; font: 400 10px "DM Mono", monospace; border: 1px solid rgba(0,0,0,0.08); }}
    .diagnosisValue {{ margin: 4px 0 10px; }}
    .strategyNote {{ padding: 7px 8px; border: 1px solid rgba(45,122,95,0.18); background: rgba(45,122,95,0.08); }}
  </style>
</head>
<body>
  <header>
    <div><span class="appTitle">room view</span> <span id="meta"></span></div>
    <div id="hint">
      <button data-view="iso">iso</button>
      <button data-view="plan">plan</button>
      <button data-view="front">front</button>
      <button data-view="right">right</button>
      <span>drag | pan | zoom | reset</span>
    </div>
  </header>
  <main id="roomShell">
    <aside id="controls" class="panel">
      <section class="section">
        <button class="sectionHeader" data-toggle="orientationPanel"><span>orientation</span><span>&#9662;</span></button>
        <div id="orientationPanel" class="sectionBody">
          <div class="type3">click the main window wall in the model; directions update from that wall</div>
          <div class="openingRow">
            <span>main window direction</span>
            <select id="mainOpeningDirection" aria-label="main window direction"></select>
          </div>
          <div id="orientationList"></div>
          <div id="saveStatus" class="saveStatus">waiting for confirmation</div>
        </div>
      </section>
      <section class="section">
        <button class="sectionHeader" data-toggle="checkPanel"><span>room check</span><span>&#9662;</span></button>
        <div id="checkPanel" class="sectionBody">
          <div class="type3">click a window tag in the model or use the list below to include/exclude it</div>
          <div id="componentList"></div>
          <textarea id="overrideJson" spellcheck="false" aria-label="room check JSON"></textarea>
        </div>
      </section>
      <section class="section">
        <button class="sectionHeader" data-toggle="surfacePanel"><span>surfaces</span><span>&#9662;</span></button>
        <div id="surfacePanel" class="sectionBody"><div id="surfaceList"></div></div>
      </section>
      <section class="section" id="phaseActions">
        <div class="actions">
          <button id="saveOrientation">save</button>
          <button id="saveReturnOrientation">continue</button>
        </div>
      </section>
    </aside>
    <section id="viewerArea">
      <aside id="wallDiagnosisPanel" class="panel">
        <section class="section">
          <button class="sectionHeader" data-toggle="wallDiagnosisBody"><span>wall diagnosis</span><span>&#9662;</span></button>
          <div id="wallDiagnosisBody" class="sectionBody">
            <div class="type3">wall</div>
            <div class="diagnosisValue type2" id="wallDiagnosisId">select a wall</div>
            <div class="type3">risk label</div>
            <div class="diagnosisValue type2" id="wallDiagnosisRisk">not selected</div>
            <div class="type3">top factor</div>
            <div class="diagnosisValue type2" id="wallDiagnosisFactor">not selected</div>
            <div class="type3">suggested action</div>
            <div class="diagnosisValue type2 strategyNote" id="wallDiagnosisAction">not selected</div>
            <div class="type3">selected fix</div>
            <div class="diagnosisValue type2 strategyNote" id="wallDiagnosisStrategy">select an option</div>
          </div>
        </section>
      </aside>
      <canvas id="view"></canvas>
    </section>
  </main>
  <script>
    const model = {data};
    const overlayImages = {overlay_data};
    const strategyState = {strategy_data};
    const canvas = document.getElementById("view");
    const ctx = canvas.getContext("2d");
    const viewerMode = new URLSearchParams(window.location.search).get("viewer_mode") || "review";
    const meta = document.getElementById("meta");
    const surfaceList = document.getElementById("surfaceList");
    const orientationList = document.getElementById("orientationList");
    const componentList = document.getElementById("componentList");
    const mainOpeningDirection = document.getElementById("mainOpeningDirection");
    const overrideJson = document.getElementById("overrideJson");
    const saveStatus = document.getElementById("saveStatus");
    const wallDiagnosisId = document.getElementById("wallDiagnosisId");
    const wallDiagnosisRisk = document.getElementById("wallDiagnosisRisk");
    const wallDiagnosisFactor = document.getElementById("wallDiagnosisFactor");
    const wallDiagnosisAction = document.getElementById("wallDiagnosisAction");
    const wallDiagnosisStrategy = document.getElementById("wallDiagnosisStrategy");
    const apiBase = new URLSearchParams(window.location.search).get("api_base") || "http://127.0.0.1:8010";
    const selectedStrategyId = new URLSearchParams(window.location.search).get("strategy_id") || strategyState.recommended_strategy_id || "";
    meta.textContent = ` | ${{model.room.area_m2}} m2 | ${{model.room.height_m}} m | ${{model.walls.length}} walls`;
    if (viewerMode === "spatial_vv") {{
      document.getElementById("wallDiagnosisPanel").hidden = true;
    }} else {{
      document.getElementById("orientationPanel").closest(".section").hidden = true;
      document.getElementById("checkPanel").closest(".section").hidden = true;
      document.getElementById("phaseActions").hidden = true;
    }}

    const xs = model.layout_points.map(p => p.xyz[0]);
    const zs = model.layout_points.map(p => p.xyz[2]);
    const sceneCenter = {{
      x: (Math.min(...xs) + Math.max(...xs)) / 2,
      y: model.room.height_m / 2,
      z: (Math.min(...zs) + Math.max(...zs)) / 2
    }};

    const surfaceState = {{
      floor: {{ visible: true, opacity: 0.45 }},
      ceiling: {{ visible: true, opacity: 0.25 }},
      strategyMask: {{ visible: true, opacity: 0.22 }}
    }};
    model.walls.forEach(wall => surfaceState[wall.id] = {{ visible: true, opacity: 0.55 }});
    const orientationOptions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    const compassDegrees = {{ N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 }};
    const orientationState = {{}};
    model.walls.forEach((wall, index) => orientationState[wall.id] = {{
      orientation: wall.orientation || orientationOptions[index % orientationOptions.length],
      is_external: Boolean(wall.is_external)
    }});
    const vvState = {{}};
    model.walls.forEach(wall => vvState[wall.id] = {{
      id: wall.id,
      kind: "surface",
      include_in_calculation: true,
      reason: ""
    }});
    (model.components || []).filter(component => component.component_type === "window").forEach(component => vvState[component.id] = {{
      id: component.id,
      kind: "component",
      include_in_calculation: true,
      reason: ""
    }});
    const textureImages = {{}};

    const camera = {{
      yaw: -0.78,
      pitch: -0.82,
      zoom: 1,
      panX: 0,
      panY: 0
    }};
    let dragging = false;
    let panning = false;
    let lastX = 0;
    let lastY = 0;
    let pointerStartX = 0;
    let pointerStartY = 0;
    let selectedWallId = null;
    let wallDiagnosisState = {{}};
    let drawnWallFaces = [];
    let drawnComponentFaces = [];

    function activeStrategy() {{
      return (strategyState.options || []).find(option => option.strategy_id === selectedStrategyId) || (strategyState.options || [])[0] || null;
    }}

    function strategyForWall(wallId) {{
      const active = activeStrategy();
      if (!active || !(active.wall_ids || []).includes(wallId)) return null;
      return active;
    }}

    function wallName(wallId) {{
      const index = model.walls.findIndex(wall => wall.id === wallId);
      const wall = model.walls[index] || {{}};
      return index >= 0 ? `wall ${{String(index + 1).padStart(2, "0")}} | ${{wall.orientation || "room"}}` : "select a wall";
    }}

    function resize() {{
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      draw();
    }}

    function rotate(point) {{
      const cy = Math.cos(camera.yaw);
      const sy = Math.sin(camera.yaw);
      const cp = Math.cos(camera.pitch);
      const sp = Math.sin(camera.pitch);
      const x1 = point[0] * cy - point[2] * sy;
      const z1 = point[0] * sy + point[2] * cy;
      const y1 = point[1] * cp - z1 * sp;
      const z2 = point[1] * sp + z1 * cp;
      return [x1, y1, z2];
    }}

    function project(x, y, z) {{
      const rotated = rotate([x - sceneCenter.x, y - sceneCenter.y, z - sceneCenter.z]);
      const scale = Math.min(canvas.width, canvas.height) / 8.5 * camera.zoom;
      return [
        canvas.width * 0.5 + camera.panX * devicePixelRatio + rotated[0] * scale,
        canvas.height * 0.58 + camera.panY * devicePixelRatio - rotated[1] * scale,
        rotated[2]
      ];
    }}

    function poly(points, fill, stroke, opacity = 1) {{
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.beginPath();
      points.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1.5 * devicePixelRatio;
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }}

    function drawLabel(text, point) {{
      ctx.fillStyle = "#242424";
      ctx.font = `${{10 * devicePixelRatio}}px "DM Mono", monospace`;
      ctx.fillText(text, point[0] + 5 * devicePixelRatio, point[1] - 4 * devicePixelRatio);
    }}

    function pointInPolygon(point, polygon) {{
      let inside = false;
      for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {{
        const xi = polygon[i][0], yi = polygon[i][1];
        const xj = polygon[j][0], yj = polygon[j][1];
        const intersect = ((yi > point[1]) !== (yj > point[1])) &&
          (point[0] < (xj - xi) * (point[1] - yi) / ((yj - yi) || 0.0001) + xi);
        if (intersect) inside = !inside;
      }}
      return inside;
    }}

    function hitWall(clientX, clientY) {{
      const rect = canvas.getBoundingClientRect();
      const point = [
        (clientX - rect.left) * devicePixelRatio,
        (clientY - rect.top) * devicePixelRatio
      ];
      for (let index = drawnWallFaces.length - 1; index >= 0; index--) {{
        const face = drawnWallFaces[index];
        if (pointInPolygon(point, face.points)) return face.wallId;
      }}
      return null;
    }}

    function hitComponent(clientX, clientY) {{
      const rect = canvas.getBoundingClientRect();
      const point = [
        (clientX - rect.left) * devicePixelRatio,
        (clientY - rect.top) * devicePixelRatio
      ];
      for (let index = drawnComponentFaces.length - 1; index >= 0; index--) {{
        const face = drawnComponentFaces[index];
        if (pointInPolygon(point, face.points)) return face.componentId;
      }}
      return null;
    }}

    function toggleComponent(componentId) {{
      const state = vvState[componentId];
      if (!state) return;
      state.include_in_calculation = !state.include_in_calculation;
      state.reason = state.include_in_calculation ? "" : "user deselected in room_3d_view.html";
      renderComponentPanel();
      refreshOverrideJson();
      draw();
    }}

    function setSelectedWall(wallId) {{
      selectedWallId = wallId;
      if (viewerMode === "spatial_vv" && wallId) {{
        assignMainOpeningWall(wallId);
      }}
      const diagnosis = wallDiagnosisState[wallId] || {{}};
      wallDiagnosisId.textContent = wallName(wallId);
      wallDiagnosisRisk.textContent = diagnosis.risk_label || "not assigned";
      wallDiagnosisFactor.textContent = diagnosis.top_factor || "no mapped problem";
      wallDiagnosisAction.textContent = diagnosis.suggested_action || "no mapped action";
      const strategy = strategyForWall(wallId);
      wallDiagnosisStrategy.textContent = strategy ? `${{strategy.label}}: ${{strategy.strategy_name}} | ${{strategy.status || "screening"}}` : "no selected fix mapped to this wall";
      draw();
    }}

    function componentLabel(component, index) {{
      return `W${{String(index + 1).padStart(2, "0")}}`;
    }}

    function wallNormalAngle(wall) {{
      if (wall.normal && wall.normal.length >= 3) {{
        return (Math.atan2(wall.normal[0], wall.normal[2]) * 180 / Math.PI + 360) % 360;
      }}
      const dx = wall.end_xyz[0] - wall.start_xyz[0];
      const dz = wall.end_xyz[2] - wall.start_xyz[2];
      return (Math.atan2(dz, -dx) * 180 / Math.PI + 360) % 360;
    }}

    function closestCompass(degrees) {{
      const normalized = (degrees + 360) % 360;
      return orientationOptions.reduce((best, option) => {{
        const diff = Math.abs(((normalized - compassDegrees[option] + 540) % 360) - 180);
        return diff < best.diff ? {{ option, diff }} : best;
      }}, {{ option: "N", diff: 999 }}).option;
    }}

    function assignMainOpeningWall(wallId) {{
      const mainWall = model.walls.find(wall => wall.id === wallId);
      if (!mainWall) return;
      const selectedDirection = mainOpeningDirection?.value || model.room.facing_direction || orientationState[wallId]?.orientation || "SW";
      model.room.facing_direction = selectedDirection;
      const baseAngle = wallNormalAngle(mainWall);
      const targetAngle = compassDegrees[selectedDirection] ?? 225;
      Object.keys(orientationState).forEach(id => orientationState[id].is_external = false);
      orientationState[wallId].is_external = true;
      model.walls.forEach(wall => {{
        const relativeAngle = wallNormalAngle(wall) - baseAngle;
        const orientation = closestCompass(targetAngle + relativeAngle);
        orientationState[wall.id].orientation = orientation;
        wall.orientation = orientation;
        wall.is_external = wall.id === wallId;
      }});
      renderOrientationPanel();
      renderSurfacePanel();
      renderComponentPanel();
      refreshOverrideJson();
    }}

    function triangleTransform(source, target) {{
      const [s0, s1, s2] = source;
      const [d0, d1, d2] = target;
      const denom = s0[0] * (s1[1] - s2[1]) + s1[0] * (s2[1] - s0[1]) + s2[0] * (s0[1] - s1[1]);
      return {{
        a: (d0[0] * (s1[1] - s2[1]) + d1[0] * (s2[1] - s0[1]) + d2[0] * (s0[1] - s1[1])) / denom,
        b: (d0[1] * (s1[1] - s2[1]) + d1[1] * (s2[1] - s0[1]) + d2[1] * (s0[1] - s1[1])) / denom,
        c: (d0[0] * (s2[0] - s1[0]) + d1[0] * (s0[0] - s2[0]) + d2[0] * (s1[0] - s0[0])) / denom,
        d: (d0[1] * (s2[0] - s1[0]) + d1[1] * (s0[0] - s2[0]) + d2[1] * (s1[0] - s0[0])) / denom,
        e: (d0[0] * (s1[0] * s2[1] - s2[0] * s1[1]) + d1[0] * (s2[0] * s0[1] - s0[0] * s2[1]) + d2[0] * (s0[0] * s1[1] - s1[0] * s0[1])) / denom,
        f: (d0[1] * (s1[0] * s2[1] - s2[0] * s1[1]) + d1[1] * (s2[0] * s0[1] - s0[0] * s2[1]) + d2[1] * (s0[0] * s1[1] - s1[0] * s0[1])) / denom,
      }};
    }}

    function drawImageTriangle(image, source, target) {{
      const t = triangleTransform(source, target);
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(target[0][0], target[0][1]);
      ctx.lineTo(target[1][0], target[1][1]);
      ctx.lineTo(target[2][0], target[2][1]);
      ctx.closePath();
      ctx.clip();
      ctx.setTransform(t.a, t.b, t.c, t.d, t.e, t.f);
      ctx.drawImage(image, 0, 0);
      ctx.restore();
    }}

    function drawImageOnWall(image, face, opacity) {{
      if (!image?.complete || !image.naturalWidth || !image.naturalHeight) return;
      const w = image.naturalWidth;
      const h = image.naturalHeight;
      const quad = [face[3], face[2], face[1], face[0]];
      ctx.save();
      ctx.globalAlpha = opacity;
      drawImageTriangle(image, [[0, 0], [w, 0], [w, h]], [quad[0], quad[1], quad[2]]);
      drawImageTriangle(image, [[0, 0], [w, h], [0, h]], [quad[0], quad[2], quad[3]]);
      ctx.restore();
    }}

    function clipToPolygon(projectedPoints) {{
      ctx.beginPath();
      projectedPoints.forEach((point, index) => {{
        if (index) {{
          ctx.lineTo(point[0], point[1]);
        }} else {{
          ctx.moveTo(point[0], point[1]);
        }}
      }});
      ctx.closePath();
      ctx.clip();
    }}

    function drawImageOnPolygon(image, modelPoints, projectedPoints, opacity) {{
      if (!image?.complete || !image.naturalWidth || !image.naturalHeight || modelPoints.length < 3) return;
      const xs = modelPoints.map(point => point[0]);
      const zs = modelPoints.map(point => point[2]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minZ = Math.min(...zs);
      const maxZ = Math.max(...zs);
      const y = modelPoints[0][1];
      const rectangle = [
        project(minX, y, maxZ),
        project(maxX, y, maxZ),
        project(maxX, y, minZ),
        project(minX, y, minZ)
      ];
      const w = image.naturalWidth;
      const h = image.naturalHeight;
      ctx.save();
      ctx.globalAlpha = opacity;
      clipToPolygon(projectedPoints);
      drawImageTriangle(image, [[0, 0], [w, 0], [w, h]], [rectangle[0], rectangle[1], rectangle[2]]);
      drawImageTriangle(image, [[0, 0], [w, h], [0, h]], [rectangle[0], rectangle[2], rectangle[3]]);
      ctx.restore();
    }}

    function wallTextures(wallId) {{
      return overlayImages.filter(item => {{
        if (item.wall_id !== wallId) return false;
        return item.type === "fragment";
      }});
    }}

    function surfaceTexture(surfaceId) {{
      return overlayImages.find(item => item.surface_id === surfaceId);
    }}

    function textureOpacity(item, wallId) {{
      return surfaceState[wallId]?.opacity ?? 1;
    }}

    function componentsForWall(wallId) {{
      return (model.components || []).filter(component => component.component_type === "window" && component.wall_id === wallId);
    }}

    function pointOnQuad(quad, u, v) {{
      const top = [
        quad[3][0] + (quad[2][0] - quad[3][0]) * u,
        quad[3][1] + (quad[2][1] - quad[3][1]) * u
      ];
      const bottom = [
        quad[0][0] + (quad[1][0] - quad[0][0]) * u,
        quad[0][1] + (quad[1][1] - quad[0][1]) * u
      ];
      return [
        top[0] + (bottom[0] - top[0]) * v,
        top[1] + (bottom[1] - top[1]) * v
      ];
    }}

    function drawWindowTag(component, wallFace, index) {{
      const bbox = component.bbox_px;
      const wallTexture = wallTextures(component.wall_id)[0];
      const image = wallTexture ? textureImages[wallTexture.id] : null;
      const imageWidth = image?.naturalWidth || 1;
      const imageHeight = image?.naturalHeight || 1;
      let u0 = 0.32;
      let u1 = 0.68;
      let v0 = 0.34;
      let v1 = 0.68;
      if (Array.isArray(bbox) && bbox.length >= 4 && imageWidth > 1 && imageHeight > 1) {{
        u0 = Math.max(0, Math.min(1, bbox[0] / imageWidth));
        u1 = Math.max(0, Math.min(1, bbox[2] / imageWidth));
        v0 = Math.max(0, Math.min(1, bbox[1] / imageHeight));
        v1 = Math.max(0, Math.min(1, bbox[3] / imageHeight));
      }}
      const points = [
        pointOnQuad(wallFace, u0, v1),
        pointOnQuad(wallFace, u1, v1),
        pointOnQuad(wallFace, u1, v0),
        pointOnQuad(wallFace, u0, v0)
      ];
      const included = vvState[component.id]?.include_in_calculation !== false;
      ctx.save();
      ctx.fillStyle = included ? "rgba(255, 255, 255, 0.24)" : "rgba(255, 255, 255, 0.08)";
      ctx.strokeStyle = included ? "#0a0a0a" : "#b0b0b0";
      ctx.lineWidth = 1.25 * devicePixelRatio;
      ctx.beginPath();
      points.forEach((point, pointIndex) => pointIndex ? ctx.lineTo(point[0], point[1]) : ctx.moveTo(point[0], point[1]));
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      const label = componentLabel(component, index);
      const center = points.reduce((sum, point) => [sum[0] + point[0] / points.length, sum[1] + point[1] / points.length], [0, 0]);
      ctx.fillStyle = included ? "#0a0a0a" : "#8a8a8a";
      ctx.font = `${{10 * devicePixelRatio}}px "DM Mono", monospace`;
      ctx.fillText(label, center[0] - 10 * devicePixelRatio, center[1] + 3 * devicePixelRatio);
      ctx.restore();
      drawnComponentFaces.push({{ componentId: component.id, points }});
    }}

    function setView(name) {{
      if (name === "plan") {{
        camera.yaw = 0;
        camera.pitch = -1.5707;
      }} else if (name === "front") {{
        camera.yaw = 0;
        camera.pitch = 0;
      }} else if (name === "right") {{
        camera.yaw = 1.5707;
        camera.pitch = 0;
      }} else {{
        camera.yaw = -0.78;
        camera.pitch = -0.82;
      }}
      camera.zoom = 1;
      camera.panX = 0;
      camera.panY = 0;
      draw();
    }}

    function centerOf(points) {{
      return points.reduce((sum, point) => sum + point[2], 0) / points.length;
    }}

    function draw() {{
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      drawnWallFaces = [];
      drawnComponentFaces = [];
      const h = model.room.height_m;
      const faces = [];
      const floorModel = model.layout_points.map(p => [p.xyz[0], 0, p.xyz[2]]);
      const ceilingModel = model.layout_points.map(p => [p.xyz[0], h, p.xyz[2]]);
      const floor = floorModel.map(p => project(p[0], p[1], p[2]));
      const ceiling = ceilingModel.map(p => project(p[0], p[1], p[2]));
      if (surfaceState.floor.visible) {{
        faces.push({{ depth: centerOf(floor), points: floor, modelPoints: floorModel, surfaceId: "floor", fill: "#81a094", stroke: "#516f67", label: "floor", opacity: surfaceState.floor.opacity }});
      }}
      if (surfaceState.ceiling.visible) {{
        faces.push({{ depth: centerOf(ceiling), points: ceiling, modelPoints: ceilingModel, surfaceId: "ceiling", fill: "#dcd7cc", stroke: "#9b948a", label: "ceiling", opacity: surfaceState.ceiling.opacity }});
      }}

      model.walls.forEach(wall => {{
        if (!surfaceState[wall.id]?.visible) return;
        const a = wall.start_xyz;
        const b = wall.end_xyz;
        const face = [
          project(a[0], 0, a[2]),
          project(b[0], 0, b[2]),
          project(b[0], h, b[2]),
          project(a[0], h, a[2])
        ];
        const label = `${{wall.id.replace(model.room.id + "_", "")}} ${{wall.orientation || ""}}`;
        faces.push({{
          depth: centerOf(face),
          points: face,
          wallId: wall.id,
          fill: wall.is_external ? "#b7815b" : "#6e85b0",
          stroke: "#6d6760",
          label,
          labelPoint: face[2],
          opacity: Math.max(0.12, surfaceState[wall.id].opacity * 0.55)
        }});
      }});

      faces.sort((a, b) => a.depth - b.depth);
      faces.forEach(face => {{
        if (face.wallId) drawnWallFaces.push(face);
        poly(face.points, face.fill, face.stroke, face.opacity ?? 1);
        if (face.surfaceId) {{
          const texture = surfaceTexture(face.surfaceId);
          if (texture) {{
            drawImageOnPolygon(textureImages[texture.id], face.modelPoints, face.points, surfaceState[face.surfaceId].opacity);
          }}
        }}
        if (face.wallId) {{
          wallTextures(face.wallId).forEach(item => {{
            drawImageOnWall(textureImages[item.id], face.points, textureOpacity(item, face.wallId));
          }});
          const strategy = strategyForWall(face.wallId);
          if (viewerMode === "review" && strategy && surfaceState.strategyMask.visible) {{
            poly(face.points, "rgba(45, 122, 95, 0.55)", "rgba(45, 122, 95, 0.9)", surfaceState.strategyMask.opacity);
          }}
          componentsForWall(face.wallId).forEach((component, index) => drawWindowTag(component, face.points, index));
          ctx.strokeStyle = face.stroke;
          if (face.wallId === selectedWallId) {{
            ctx.strokeStyle = "#0a0a0a";
          }}
          ctx.lineWidth = 1.5 * devicePixelRatio;
          ctx.beginPath();
          face.points.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
          ctx.closePath();
          ctx.stroke();
        }}
        if (face.labelPoint) drawLabel(face.label, face.labelPoint);
      }});

    }}

    function renderSurfacePanel() {{
      const entries = [
        {{ id: "floor", label: "floor" }},
        {{ id: "ceiling", label: "ceiling" }},
                ...(viewerMode === "review" ? [{{ id: "strategyMask", label: "upgrade mask" }}] : []),
        ...model.walls.map((wall, index) => ({{
          id: wall.id,
          label: `wall ${{String(index + 1).padStart(2, "0")}} | ${{wall.orientation || ""}}`
        }}))
      ];
      surfaceList.innerHTML = "";
      entries.forEach(item => {{
        const row = document.createElement("div");
        row.className = "row";
        const state = surfaceState[item.id];
        row.innerHTML = `
          <input type="checkbox" ${{state.visible ? "checked" : ""}}>
          <span>${{item.label}}</span>
          <input type="range" min="0" max="1" step="0.05" value="${{state.opacity}}">
          <span>${{Math.round(state.opacity * 100)}}%</span>
        `;
        const checkbox = row.querySelector('input[type="checkbox"]');
        const range = row.querySelector('input[type="range"]');
        const value = row.querySelector("span:last-child");
        checkbox.addEventListener("change", event => {{
          state.visible = event.target.checked;
          draw();
        }});
        range.addEventListener("input", event => {{
          state.opacity = Number(event.target.value);
          value.textContent = `${{Math.round(state.opacity * 100)}}%`;
          draw();
        }});
        surfaceList.appendChild(row);
      }});

    }}

    function renderOrientationPanel() {{
      mainOpeningDirection.innerHTML = orientationOptions.map(value => `
        <option value="${{value}}" ${{value === (model.room.facing_direction || "SW") ? "selected" : ""}}>${{value}}</option>
      `).join("");
      mainOpeningDirection.onchange = () => {{
        model.room.facing_direction = mainOpeningDirection.value;
        const mainWallId = Object.entries(orientationState).find(([, state]) => state.is_external)?.[0] || selectedWallId;
        if (mainWallId) assignMainOpeningWall(mainWallId);
      }};
      orientationList.innerHTML = "";
      model.walls.forEach((wall, index) => {{
        const state = orientationState[wall.id];
        const row = document.createElement("div");
        row.className = "orientationRow";
        const options = orientationOptions.map(value => `
          <option value="${{value}}" ${{state.orientation === value ? "selected" : ""}}>${{value}}</option>
        `).join("");
        row.innerHTML = `
          <input type="radio" name="mainExternalWall" ${{state.is_external ? "checked" : ""}} title="main outside/window wall">
          <span>wall ${{String(index + 1).padStart(2, "0")}}</span>
          <select aria-label="wall orientation">${{options}}</select>
        `;
        const radio = row.querySelector('input[type="radio"]');
        const select = row.querySelector("select");
        radio.addEventListener("change", () => {{
          selectedWallId = wall.id;
          assignMainOpeningWall(wall.id);
        }});
        select.addEventListener("change", event => {{
          orientationState[wall.id].orientation = event.target.value;
          wall.orientation = event.target.value;
          refreshOverrideJson();
          renderSurfacePanel();
          renderComponentPanel();
          draw();
        }});
        orientationList.appendChild(row);
      }});
    }}

    function buildOverridePayload() {{
      const surface_overrides = [];
      const component_overrides = [];
      const orientation_overrides = [];
      model.walls.forEach((wall, index) => {{
        const state = orientationState[wall.id];
        orientation_overrides.push({{
          id: wall.id,
          wall_index: index,
          orientation: state.orientation,
          is_external: Boolean(state.is_external),
          source: "user_confirmed_in_room_3d_view"
        }});
      }});
      Object.values(vvState).forEach(item => {{
        if (item.include_in_calculation) return;
        const payload = {{
          id: item.id,
          include_in_calculation: false,
          reason: item.reason || "user deselected in room_3d_view.html",
          checkpoint_stage: "spatial_vv"
        }};
        if (item.kind === "surface") {{
          surface_overrides.push(payload);
        }} else {{
          component_overrides.push(payload);
        }}
      }});
      return {{
        stage: "spatial_vv",
        status: "user_reviewed",
        orientation_confirmed: true,
        room_id: model.room.id,
        source_viewer: "data/output/spatial/room_3d_view.html",
        notes: [
          "Save this JSON as data/intermediate/spatial_user_overrides.json before rerunning diagnosis.",
          "Orientation confirmation happens after LGTNet geometry and before diagnosis/KG writes."
        ],
        orientation_overrides,
        surface_overrides,
        component_overrides
      }};
    }}

    function refreshOverrideJson() {{
      overrideJson.value = JSON.stringify(buildOverridePayload(), null, 2);
    }}

    function renderComponentPanel() {{
      componentList.innerHTML = "";
      const items = (model.components || [])
        .filter(component => component.component_type === "window")
        .map((component, index) => ({{
          id: component.id,
          title: `${{componentLabel(component, index)}} | window`,
          detail: `${{wallName(component.wall_id)}} | ${{component.estimated_area_m2 || "?"}} m2 | confidence ${{component.confidence ?? "?"}}`
        }}));
      if (!items.length) {{
        componentList.innerHTML = `<div class="type3">no window segments found; fallback window estimate will be used</div>`;
        refreshOverrideJson();
        return;
      }}
      items.forEach(item => {{
        const row = document.createElement("label");
        row.className = "vvRow";
        const state = vvState[item.id];
        row.innerHTML = `
          <input type="checkbox" ${{state.include_in_calculation ? "checked" : ""}}>
          <span>${{item.title}}<small>${{item.id}} | ${{item.detail}}</small></span>
        `;
        row.querySelector("input").addEventListener("change", event => {{
          state.include_in_calculation = event.target.checked;
          state.reason = event.target.checked ? "" : "user deselected in room_3d_view.html";
          refreshOverrideJson();
        }});
        componentList.appendChild(row);
      }});
      refreshOverrideJson();
    }}

    function saveOverrides() {{
      refreshOverrideJson();
      if (saveStatus) saveStatus.textContent = "saving...";
      return fetch(`${{apiBase}}/api/spatial/overrides`, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: overrideJson.value
      }})
        .then(response => response.ok ? response.json() : Promise.reject(new Error("save failed")))
        .then(payload => {{
          if (saveStatus) saveStatus.textContent = payload.message;
          window.parent?.postMessage({{
            type: "hvra_spatial_vv_saved",
            stage: "spatial_vv",
            path: payload.path,
            message: payload.message
          }}, "*");
        }})
        .catch(() => {{
          if (saveStatus) saveStatus.textContent = "backend save unavailable. try again after starting the API.";
          throw new Error("save failed");
        }});
    }}

    function saveAndReturn() {{
      refreshOverrideJson();
      if (saveStatus) saveStatus.textContent = "saving and continuing...";
      fetch(`${{apiBase}}/api/spatial/continue`, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: overrideJson.value
      }})
        .then(response => response.ok ? response.json() : response.text().then(text => Promise.reject(new Error(text || "continue failed"))))
        .then(payload => {{
          if (saveStatus) saveStatus.textContent = payload.message || "continued";
          window.parent?.postMessage({{
            type: "hvra_spatial_vv_continue",
            stage: payload.current_stage || "processing",
            path: payload.path,
            message: payload.message,
            refresh_views: Boolean(payload.refresh_views)
          }}, "*");
        }})
        .catch(error => {{
          if (saveStatus) saveStatus.textContent = `continue failed: ${{error.message}}`;
          window.parent?.postMessage({{
            type: "hvra_spatial_vv_error",
            stage: "spatial_vv",
            message: error.message
          }}, "*");
        }});
    }}

    function loadWallDiagnosisState() {{
      if (viewerMode === "spatial_vv") return;
      fetch("wall_diagnosis_state.json")
        .then(response => response.ok ? response.json() : null)
        .then(state => {{
          wallDiagnosisState = state?.walls || {{}};
        }})
        .catch(() => {{
          wallDiagnosisState = {{}};
        }});
    }}

    document.querySelectorAll("[data-toggle]").forEach(button => {{
      button.addEventListener("click", () => {{
        const body = document.getElementById(button.dataset.toggle);
        const arrow = button.querySelector("span:last-child");
        const section = button.closest(".section");
        body.hidden = !body.hidden;
        if (section) section.classList.toggle("isCollapsed", body.hidden);
        arrow.textContent = body.hidden ? "\\u25b8" : "\\u25be";
      }});
    }});

    function loadTextures() {{
      overlayImages.forEach((item, index) => {{
        if (!textureImages[item.id]) {{
          const image = new Image();
          image.onload = draw;
          image.src = item.src;
          textureImages[item.id] = image;
        }}
      }});
    }}

    canvas.addEventListener("pointerdown", event => {{
      dragging = true;
      panning = event.shiftKey || event.button === 1 || event.button === 2;
      pointerStartX = event.clientX;
      pointerStartY = event.clientY;
      lastX = event.clientX;
      lastY = event.clientY;
      canvas.setPointerCapture(event.pointerId);
    }});

    canvas.addEventListener("pointermove", event => {{
      if (!dragging) return;
      const dx = event.clientX - lastX;
      const dy = event.clientY - lastY;
      lastX = event.clientX;
      lastY = event.clientY;
      if (panning) {{
        camera.panX += dx;
        camera.panY += dy;
      }} else {{
        camera.yaw += dx * 0.008;
        camera.pitch = Math.max(-1.35, Math.min(0.15, camera.pitch + dy * 0.006));
      }}
      draw();
    }});

    canvas.addEventListener("pointerup", event => {{
      const moved = Math.hypot(event.clientX - pointerStartX, event.clientY - pointerStartY);
      if (moved < 4 && !panning) {{
        const componentId = viewerMode === "spatial_vv" ? hitComponent(event.clientX, event.clientY) : null;
        if (componentId) {{
          toggleComponent(componentId);
        }} else {{
          const wallId = hitWall(event.clientX, event.clientY);
          if (wallId) setSelectedWall(wallId);
        }}
      }}
      dragging = false;
      canvas.releasePointerCapture(event.pointerId);
    }});
    canvas.addEventListener("contextmenu", event => event.preventDefault());
    canvas.addEventListener("wheel", event => {{
      event.preventDefault();
      camera.zoom = Math.max(0.35, Math.min(3.2, camera.zoom * Math.exp(-event.deltaY * 0.001)));
      draw();
    }}, {{ passive: false }});
    document.querySelectorAll("[data-view]").forEach(button => {{
      button.addEventListener("click", () => setView(button.dataset.view));
    }});
    document.getElementById("saveOrientation").addEventListener("click", saveOverrides);
    document.getElementById("saveReturnOrientation").addEventListener("click", saveAndReturn);
    addEventListener("keydown", event => {{
      if (event.key.toLowerCase() === "r") {{
        setView("iso");
      }}
    }});
    addEventListener("resize", resize);
    renderOrientationPanel();
    renderSurfacePanel();
    renderComponentPanel();
    loadWallDiagnosisState();
    loadTextures();
    resize();
  </script>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)













