"""Build a standalone 3D retrofit visual smoke test from current HVRA outputs.

Reads the room spatial index, retrofit validation options, and visual retrofit
catalogue, then writes a simple Three.js HTML view in 3D_test/test. This is a local
visual test only; it does not call external asset registries or mutate the main
interface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
SPATIAL_PATH = ROOT_DIR / "data" / "intermediate" / "spatial_index_with_overrides.json"
FALLBACK_SPATIAL_PATH = ROOT_DIR / "data" / "intermediate" / "spatial_index.json"
VALIDATION_PATH = ROOT_DIR / "data" / "intermediate" / "retrofit_validation_options.json"
VISUAL_CATALOGUE_PATH = ROOT_DIR / "data" / "input" / "visual_retrofit_catalogue.json"
HYBRID_ASSET_CATALOGUE_PATH = ROOT_DIR / "3D_test" / "test" / "hybrid_visual_asset_catalogue.json"
VISUAL_DECISION_RULES_PATH = ROOT_DIR / "3D_test" / "test" / "visual_decision_rules.json"
BUILDING_INFO_PATH = ROOT_DIR / "data" / "input" / "building_info.json"
CONSTRAINTS_PATH = ROOT_DIR / "data" / "input" / "retrofit_constraints.json"
OUTPUT_DIR = Path(__file__).resolve().parent
PLAN_PATH = OUTPUT_DIR / "retrofit_visual_plan.json"
HTML_PATH = OUTPUT_DIR / "retrofit_room_test.html"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def collect_targets(option: dict[str, Any]) -> dict[str, list[str]]:
    wall_ids: list[str] = []
    surface_ids: list[str] = []
    for targets in option.get("problem_targets", {}).values():
        for target in targets:
            wall_id = target.get("wall_id")
            surface_id = target.get("surface_id")
            if wall_id and wall_id not in wall_ids:
                wall_ids.append(wall_id)
            if surface_id and surface_id not in surface_ids:
                surface_ids.append(surface_id)
    return {"wall_ids": wall_ids, "surface_ids": surface_ids}


def make_biophilic_test_option(visual_catalogue: dict[str, Any], spatial: dict[str, Any]) -> dict[str, Any]:
    strategy_id = "interior_biophilic_cooling_zone"
    visual_rule = visual_catalogue.get(strategy_id, {})
    external_wall_ids = [wall.get("id") for wall in spatial.get("walls", []) if wall.get("is_external")]
    fallback_wall_ids = [wall.get("id") for wall in spatial.get("walls", [])[:1]]
    wall_ids = [wall_id for wall_id in (external_wall_ids or fallback_wall_ids) if wall_id]
    return {
        "rank": 1,
        "strategy_id": strategy_id,
        "strategy_name": "Plant cooling corner",
        "status": "visual_test_only",
        "confidence": "low",
        "final_score": None,
        "visual_asset_type": visual_rule.get("visual_asset_type", "interior_plant_cluster"),
        "render_layer": visual_rule.get("render_layer", "interior_object"),
        "placement_rule": visual_rule.get("placement_rule", "Place in a daylight-accessible interior corner or occupied zone."),
        "geometry_rule": visual_rule.get("geometry_rule", "Cluster of potted plants and optional low shelf within occupied zone."),
        "material_rule": visual_rule.get("material_rule", "varied green foliage, ceramic or timber pots."),
        "wall_ids": wall_ids,
        "surface_ids": ["ROOM_001_FLOOR"],
        "numerical_comparison": [],
        "recommendation": "Test-only biophilic visualization. Treat as supportive comfort/resilience, not a standalone benchmark-passing thermal fix.",
        "test_only": True,
    }


def infer_opening_context(spatial: dict[str, Any], building_info: dict[str, Any], override: str | None = None) -> dict[str, Any]:
    components = spatial.get("components", [])
    openings = [component for component in components if component.get("component_type") in {"window", "door"}]
    selected = None
    if openings:
        selected = max(openings, key=lambda item: float(item.get("estimated_area_m2") or 0.0))
    width = float((selected or {}).get("width_m") or 0.0)
    height = float((selected or {}).get("height_m") or 0.0)
    component_type = (selected or {}).get("component_type", "window")
    inferred = "window"
    if component_type == "door" or (width >= 1.15 and height >= 1.9):
        inferred = "sliding_glass_door"
    opening_type = override or inferred
    wall_id = (selected or {}).get("wall_id")
    return {
        "opening_type": opening_type,
        "inferred_opening_type": inferred,
        "override_used": bool(override),
        "wall_id": wall_id,
        "component_id": (selected or {}).get("id"),
        "width_m": width or None,
        "height_m": height or None,
        "area_m2": (selected or {}).get("estimated_area_m2"),
        "notes": [
            "Largest detected window/door is used as the visual placement anchor.",
            "Override with --opening-type when the visual test needs a specific morphology such as sliding_glass_door."
        ]
    }


def evaluate_variant(variant: dict[str, Any], rule: dict[str, Any], opening_context: dict[str, Any], constraints: dict[str, Any], walls: list[dict[str, Any]], building_info: dict[str, Any]) -> dict[str, Any]:
    opening_type = opening_context.get("opening_type") or "window"
    wall_id = opening_context.get("wall_id")
    wall = next((item for item in walls if item.get("id") == wall_id), None)
    wall_is_external = bool((wall or {}).get("is_external")) or int(building_info.get("external_facades") or 0) > 0
    facade_allowed = bool(constraints.get("facade_modification_allowed", False))
    ownership = str(constraints.get("ownership_status", "unknown")).lower()
    has_balcony = bool(building_info.get("has_balcony", False))
    reasons = []
    status = "allowed"

    if opening_type in rule.get("blocked_opening_types", []):
        status = "blocked"
        reasons.append(f"{variant.get('label')} is not suitable for {opening_type}.")
    allowed_types = rule.get("allowed_opening_types") or []
    if allowed_types and opening_type not in allowed_types:
        status = "blocked"
        reasons.append(f"Opening type {opening_type} is outside the allowed list.")
    if rule.get("requires_external_wall") and not wall_is_external:
        status = "blocked"
        reasons.append("No confirmed external target wall for this exterior system.")
    if rule.get("requires_facade_permission") and (not facade_allowed or ownership == "renter"):
        status = "blocked"
        reasons.append("Facade-mounted retrofit requires owner/building approval and is blocked for the current constraints.")
    if rule.get("requires_balcony_or_outdoor_access") and not has_balcony:
        status = "blocked"
        reasons.append("No balcony/outdoor maintenance access is confirmed.")
    if "conditional" in str(rule.get("suitability", "")) and status == "allowed":
        status = "conditional"
        reasons.append(rule.get("notes", "Conditional product/detail check required."))
    if not reasons:
        reasons.append(rule.get("notes", "Suitable for this visual test context."))
    return {
        "status": status,
        "opening_type": opening_type,
        "target_wall_id": wall_id,
        "placement_side": rule.get("placement_side", "unknown"),
        "suitability": rule.get("suitability", "not_classified"),
        "reasons": reasons,
    }


def apply_visual_decisions(hybrid_asset_catalogue: dict[str, Any], ruleset: dict[str, Any], opening_context: dict[str, Any], constraints: dict[str, Any], walls: list[dict[str, Any]], building_info: dict[str, Any]) -> dict[str, Any]:
    rules = ruleset.get("variant_rules", {})
    variants = []
    for variant in hybrid_asset_catalogue.get("variants", []):
        copied = dict(variant)
        copied["decision"] = evaluate_variant(copied, rules.get(copied.get("id"), {}), opening_context, constraints, walls, building_info)
        variants.append(copied)
    updated = dict(hybrid_asset_catalogue)
    updated["variants"] = variants
    updated["decision_ruleset_id"] = ruleset.get("ruleset_id")
    return updated


def build_visual_plan(include_biophilic_test: bool = False, opening_type_override: str | None = None) -> dict[str, Any]:
    spatial = read_json(SPATIAL_PATH if SPATIAL_PATH.exists() else FALLBACK_SPATIAL_PATH)
    validation = read_json(VALIDATION_PATH)
    visual_catalogue = read_json(VISUAL_CATALOGUE_PATH).get("strategies", {})
    hybrid_asset_catalogue = read_json(HYBRID_ASSET_CATALOGUE_PATH) if HYBRID_ASSET_CATALOGUE_PATH.exists() else {"variants": []}
    decision_rules = read_json(VISUAL_DECISION_RULES_PATH) if VISUAL_DECISION_RULES_PATH.exists() else {"variant_rules": {}}
    building_info = read_json(BUILDING_INFO_PATH) if BUILDING_INFO_PATH.exists() else {}
    constraints = read_json(CONSTRAINTS_PATH) if CONSTRAINTS_PATH.exists() else {}
    opening_context = infer_opening_context(spatial, building_info, opening_type_override)
    hybrid_asset_catalogue = apply_visual_decisions(hybrid_asset_catalogue, decision_rules, opening_context, constraints, spatial.get("walls", []), building_info)

    options = []
    for rank, option in enumerate(validation.get("validated_options", [])[:8], start=1):
        strategy = option.get("strategy", {})
        strategy_id = strategy.get("strategy_id", f"option_{rank}")
        targets = collect_targets(option)
        visual_rule = visual_catalogue.get(strategy_id, {})
        options.append(
            {
                "rank": rank,
                "strategy_id": strategy_id,
                "strategy_name": strategy.get("strategy_name", strategy_id),
                "status": option.get("benchmark_result", {}).get("overall"),
                "confidence": option.get("confidence", {}).get("level"),
                "final_score": option.get("proposed", {}).get("final_score"),
                "visual_asset_type": visual_rule.get("visual_asset_type", "generic_overlay"),
                "render_layer": visual_rule.get("render_layer", "overlay"),
                "placement_rule": visual_rule.get("placement_rule", "Use mapped target surfaces."),
                "geometry_rule": visual_rule.get("geometry_rule", "Simple proxy geometry."),
                "material_rule": visual_rule.get("material_rule", "Neutral material."),
                "wall_ids": targets["wall_ids"],
                "surface_ids": targets["surface_ids"],
                "numerical_comparison": option.get("numerical_comparison", []),
                "recommendation": option.get("recommendation", ""),
            }
        )

    if include_biophilic_test:
        options.insert(0, make_biophilic_test_option(visual_catalogue, spatial))
        for index, option in enumerate(options, start=1):
            option["rank"] = index

    return {
        "test_mode": {
            "include_biophilic_test": include_biophilic_test,
            "note": "Biophilic test option is injected for 3D visualization only and is not treated as a primary validated thermal fix."
        },
        "source": {
            "spatial_index": str((SPATIAL_PATH if SPATIAL_PATH.exists() else FALLBACK_SPATIAL_PATH).relative_to(ROOT_DIR)),
            "retrofit_validation_options": str(VALIDATION_PATH.relative_to(ROOT_DIR)),
            "visual_retrofit_catalogue": str(VISUAL_CATALOGUE_PATH.relative_to(ROOT_DIR)),
            "hybrid_visual_asset_catalogue": str(HYBRID_ASSET_CATALOGUE_PATH.relative_to(ROOT_DIR)),
            "visual_decision_rules": str(VISUAL_DECISION_RULES_PATH.relative_to(ROOT_DIR)),
            "building_info": str(BUILDING_INFO_PATH.relative_to(ROOT_DIR)),
            "retrofit_constraints": str(CONSTRAINTS_PATH.relative_to(ROOT_DIR)),
        },
        "room": spatial.get("room", {}),
        "layout_points": spatial.get("layout_points", []),
        "walls": spatial.get("walls", []),
        "components": spatial.get("components", []),
        "opening_context": opening_context,
        "visual_decision_rules": {
            "ruleset_id": decision_rules.get("ruleset_id"),
            "global_rules": decision_rules.get("global_rules", [])
        },
        "hybrid_assets": hybrid_asset_catalogue,
        "building_info": building_info,
        "constraints": constraints,
        "boundary_rules": [
            "Roof and ceiling-roof visuals are valid only for top-floor, roof-exposed units with owner/building approval.",
            "Wall insulation reinforcement is rendered as an interior lining over the existing wall; it must not extend outward beyond the facade.",
            "Older-building external, roof, structural, and full-window retrofits remain conditional until permissions and moisture/building-physics checks pass."
        ],
        "options": options,
    }


def build_html(plan: dict[str, Any]) -> str:
    data = json.dumps(plan, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HVRA Retrofit 3D Test</title>
  <style>
    :root {{
      --bg: #f4f2ec;
      --panel: rgba(250, 248, 242, 0.96);
      --ink: #181713;
      --muted: #817b70;
      --line: rgba(24, 23, 19, 0.16);
      --blue: #2f8197;
      --green: #2d7a5f;
      --amber: #d19b43;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; margin: 0; overflow: hidden; background: var(--bg); color: var(--ink); }}
    body {{ font: 400 13px Arial, sans-serif; }}
    #view {{ width: 100vw; height: 100vh; display: block; cursor: grab; }}
    .panel {{ position: absolute; background: var(--panel); border: 1px solid var(--line); box-shadow: 0 16px 36px rgba(28, 24, 18, 0.10); }}
    #left {{ left: 18px; top: 18px; width: 360px; max-height: calc(100vh - 36px); overflow: auto; padding: 14px; }}
    #right {{ right: 18px; top: 18px; width: 210px; padding: 12px; display: grid; gap: 8px; }}
    h1, h2, .mono {{ font-family: Consolas, "DM Mono", monospace; font-size: 10.5px; font-weight: 400; letter-spacing: 0.10em; text-transform: lowercase; color: var(--muted); margin: 0 0 8px; }}
    p {{ margin: 0 0 10px; line-height: 1.45; }}
    button {{ min-height: 32px; border: 1px solid var(--line); background: #fffdfa; color: var(--ink); cursor: pointer; padding: 6px 8px; text-align: left; }}
    button.active {{ border-color: var(--blue); background: rgba(47,129,151,0.08); }}
    .option {{ display: grid; gap: 2px; width: 100%; margin: 6px 0; }}
    .row {{ display: grid; grid-template-columns: 1fr auto; gap: 8px; border-top: 1px solid var(--line); padding: 6px 0; }}
    .badge {{ font: 400 10px Consolas, monospace; color: var(--muted); }}
    .swatch {{ width: 10px; height: 10px; display: inline-block; margin-right: 6px; border: 1px solid rgba(0,0,0,0.18); }}
    .controls {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
    .asset-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 8px; }}
    .asset-grid button {{ min-height: 28px; font: 400 10px Consolas, monospace; text-align: center; }}
    .asset-grid button.blocked {{ opacity: 0.45; text-decoration: line-through; }}
    .asset-grid button.conditional {{ border-color: var(--amber); background: rgba(209,155,67,0.10); }}
    #status {{ margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--line); }}
  </style>
</head>
<body>
  <canvas id="view"></canvas>
  <section id="left" class="panel">
    <h1>retrofit 3d test</h1>
    <p>Generated from current spatial index, validation options, and visual retrofit catalogue.</p>
    <p class="badge" id="openingContext"></p>
    <div id="options"></div>
    <div id="status"></div>
  </section>
  <section id="right" class="panel">
    <h2>view control</h2>
    <div class="controls"><button id="iso">iso</button><button id="top">top</button><button id="front">front</button><button id="reset">reset</button></div>
    <p class="mono">drag rotate<br>right drag pan<br>wheel zoom</p>
    <div class="row"><span><span class="swatch" style="background:#a99f8b"></span>walls</span><span id="wallCount"></span></div>
    <div class="row"><span><span class="swatch" style="background:#2f8197"></span>airflow</span><span>overlay</span></div>
    <div class="row"><span><span class="swatch" style="background:#d8efe6"></span>roof layer</span><span>proxy</span></div>
    <div class="row"><span><span class="swatch" style="background:#2d7a5f"></span>target wall</span><span>mask</span></div>
    <div id="hybridAssets"></div>
  </section>

  <script type="importmap">
    {{
      "imports": {{
        "three": "/vendor/three/build/three.module.js",
        "three/addons/": "/vendor/three/examples/jsm/"
      }}
    }}
  </script>
  <script type="module">
    import * as THREE from 'three';
    import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

    const plan = {data};
    const query = new URLSearchParams(window.location.search);
    const requestedStrategyIds = (query.get('strategy_ids') || query.get('strategy_id') || '')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    const selectedOptionIds = new Set(requestedStrategyIds);
    window.addEventListener("DOMContentLoaded", () => {{
      const ctx = plan.opening_context || {{}};
      const node = document.getElementById("openingContext");
      if (node) node.textContent = `opening: ${{ctx.opening_type || "unknown"}} | anchor: ${{ctx.component_id || ctx.wall_id || "none"}}`;
    }});
    const canvas = document.getElementById('view');
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf4f2ec);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.05, 1000);
    const renderer = new THREE.WebGLRenderer({{ canvas, antialias: true }});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.shadowMap.enabled = true;
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.HemisphereLight(0xffffff, 0xb8b0a2, 2.4));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(4, 8, 6);
    sun.castShadow = true;
    scene.add(sun);

    const roomPoints = plan.layout_points.map(p => ({{ x: p.xyz[0], z: p.xyz[2] }}));
    const height = Number(plan.room.height_m || 2.8);
    const wallsById = new Map(plan.walls.map(w => [w.id, w]));
    const baseMaterials = [];
    const retrofitObjects = new THREE.Group();
    scene.add(retrofitObjects);
    document.getElementById('wallCount').textContent = plan.walls.length;

    function shapeFromPoints(points) {{
      const shape = new THREE.Shape();
      shape.moveTo(points[0].x, points[0].z);
      for (let i = 1; i < points.length; i += 1) shape.lineTo(points[i].x, points[i].z);
      shape.closePath();
      return shape;
    }}

    function center() {{
      const xs = roomPoints.map(p => p.x);
      const zs = roomPoints.map(p => p.z);
      return new THREE.Vector3((Math.min(...xs) + Math.max(...xs)) / 2, height / 2, (Math.min(...zs) + Math.max(...zs)) / 2);
    }}

    function wallInfo(wall) {{
      const a = wall.start_xyz;
      const b = wall.end_xyz;
      const dx = b[0] - a[0];
      const dz = b[2] - a[2];
      return {{
        x: (a[0] + b[0]) / 2,
        z: (a[2] + b[2]) / 2,
        angle: -Math.atan2(dz, dx),
        length: Math.hypot(dx, dz),
        normal: new THREE.Vector3(wall.normal?.[0] || 0, 0, wall.normal?.[2] || 1).normalize()
      }};
    }}

    function addBox(group, name, color, size, position, rotationY = 0, opacity = 1) {{
      const material = new THREE.MeshStandardMaterial({{ color, roughness: 0.72, transparent: opacity < 1, opacity }});
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(size.x, size.y, size.z), material);
      mesh.name = name;
      mesh.position.set(position.x, position.y, position.z);
      mesh.rotation.y = rotationY;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      group.add(mesh);
      return mesh;
    }}

    function addCylinder(group, name, color, radius, heightValue, position, rotationX = 0) {{
      const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, heightValue, 28), new THREE.MeshStandardMaterial({{ color, roughness: 0.68 }}));
      mesh.name = name;
      mesh.position.set(position.x, position.y, position.z);
      mesh.rotation.x = rotationX;
      mesh.castShadow = true;
      group.add(mesh);
      return mesh;
    }}

    function addArrow(group, start, end, color = 0x2f8197) {{
      const startVector = new THREE.Vector3(start.x, start.y, start.z);
      const endVector = new THREE.Vector3(end.x, end.y, end.z);
      const direction = endVector.clone().sub(startVector);
      const arrow = new THREE.ArrowHelper(direction.clone().normalize(), startVector, direction.length(), color, 0.35, 0.18);
      group.add(arrow);
    }}

    function addRoom() {{
      const floorGeometry = new THREE.ShapeGeometry(shapeFromPoints(roomPoints));
      floorGeometry.rotateX(Math.PI / 2);
      const floor = new THREE.Mesh(floorGeometry, new THREE.MeshStandardMaterial({{ color: 0xd8d0bd, roughness: 0.78, side: THREE.DoubleSide }}));
      floor.receiveShadow = true;
      scene.add(floor);

      const ceiling = floor.clone();
      ceiling.position.y = height;
      ceiling.material = new THREE.MeshStandardMaterial({{ color: 0xf8f6ee, transparent: true, opacity: 0.22, side: THREE.DoubleSide }});
      scene.add(ceiling);

      plan.walls.forEach((wall, index) => {{
        const info = wallInfo(wall);
        const material = new THREE.MeshStandardMaterial({{ color: wall.is_external ? 0xaa9a7d : 0x8894aa, transparent: true, opacity: 0.52, roughness: 0.7 }});
        baseMaterials.push(material);
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(info.length, height, 0.08), material);
        mesh.position.set(info.x, height / 2, info.z);
        mesh.rotation.y = info.angle;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        scene.add(mesh);
      }});

      const outline = roomPoints.map(p => new THREE.Vector3(p.x, 0.025, p.z));
      outline.push(new THREE.Vector3(roomPoints[0].x, 0.025, roomPoints[0].z));
      scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(outline), new THREE.LineBasicMaterial({{ color: 0x2f8197 }})));
    }}

    function addTargetWallMask(group, wallId, color = 0x2d7a5f) {{
      const wall = wallsById.get(wallId);
      if (!wall) return;
      const info = wallInfo(wall);
      const offset = info.normal.multiplyScalar(0.08);
      addBox(group, 'target wall mask', color, {{ x: info.length, y: height, z: 0.035 }}, {{ x: info.x + offset.x, y: height / 2, z: info.z + offset.z }}, info.angle, 0.24);
    }}

    function addWallLayer(group, wallId, color = 0xd8efe6) {{
      const wall = wallsById.get(wallId);
      if (!wall) return;
      const info = wallInfo(wall);
      const offset = info.normal.clone().multiplyScalar(-0.10);
      addBox(group, 'interior wall lining', color, {{ x: info.length * 0.96, y: height * 0.94, z: 0.07 }}, {{ x: info.x + offset.x, y: height / 2, z: info.z + offset.z }}, info.angle, 0.55);
    }}

    function addCeilingLayer(group, color = 0xd8efe6, opacity = 0.42) {{
      const geometry = new THREE.ShapeGeometry(shapeFromPoints(roomPoints));
      geometry.rotateX(Math.PI / 2);
      const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({{ color, transparent: true, opacity, roughness: 0.76, side: THREE.DoubleSide }}));
      mesh.position.y = height - 0.025;
      group.add(mesh);
    }}

    function addCeilingVent(group) {{
      const c = center();
      addCylinder(group, 'roof vent diffuser', 0xf6f2e8, 0.28, 0.08, {{ x: c.x, y: height - 0.08, z: c.z }}, Math.PI / 2);
      addCylinder(group, 'roof vent throat', 0xb9b1a3, 0.16, 0.45, {{ x: c.x, y: height + 0.2, z: c.z }}, 0);
    }}

    function addFan(group) {{
      const c = center();
      addCylinder(group, 'fan hub', 0xf5f1e7, 0.12, 0.16, {{ x: c.x, y: height - 0.36, z: c.z }}, 0);
      for (let i = 0; i < 4; i += 1) {{
        const blade = addBox(group, 'fan blade', 0xd5cab6, {{ x: 0.85, y: 0.035, z: 0.13 }}, {{ x: c.x, y: height - 0.36, z: c.z }}, i * Math.PI / 2, 1);
        blade.position.x += Math.cos(i * Math.PI / 2) * 0.38;
        blade.position.z += -Math.sin(i * Math.PI / 2) * 0.38;
      }}
    }}

    function addPlantCluster(group) {{
      const xs = roomPoints.map(p => p.x);
      const zs = roomPoints.map(p => p.z);
      const x = Math.min(...xs) + 0.55;
      const z = Math.max(...zs) - 0.65;
      for (let i = 0; i < 3; i += 1) {{
        addCylinder(group, 'plant pot', 0x8a5a3f, 0.14 + i * 0.02, 0.25, {{ x: x + i * 0.28, y: 0.13, z: z - i * 0.16 }});
        const crown = new THREE.Mesh(new THREE.SphereGeometry(0.25 + i * 0.04, 18, 12), new THREE.MeshStandardMaterial({{ color: 0x4f7f55, roughness: 0.65 }}));
        crown.position.set(x + i * 0.28, 0.5 + i * 0.08, z - i * 0.16);
        group.add(crown);
      }}
    }}

    function firstWindowWall(wallIds = []) {{
      const selectedWall = wallIds.find(wallId => wallsById.has(wallId));
      if (selectedWall) return selectedWall;
      const windowComponent = plan.components.find(component => component.component_type === 'window' && wallsById.has(component.wall_id));
      if (windowComponent) return windowComponent.wall_id;
      const externalWall = plan.walls.find(wall => wall.is_external);
      return externalWall?.id || plan.walls[0]?.id;
    }}

    function wallAnchor(wallId, exterior = false, y = height * 0.52) {{
      const wall = wallsById.get(wallId) || plan.walls[0];
      const info = wallInfo(wall);
      const offset = info.normal.clone().multiplyScalar(exterior ? 0.24 : -0.18);
      return {{ info, position: {{ x: info.x + offset.x, y, z: info.z + offset.z }} }};
    }}

    function addWindowOutline(group, wallId, exterior = false) {{
      const anchor = wallAnchor(wallId, exterior, height * 0.54);
      const width = Math.min(anchor.info.length * 0.55, 2.25);
      const frameColor = exterior ? 0x66806b : 0x303735;
      addBox(group, 'window frame head', frameColor, {{ x: width, y: 0.045, z: 0.045 }}, {{ x: anchor.position.x, y: height * 0.68, z: anchor.position.z }}, anchor.info.angle, 1);
      addBox(group, 'window frame sill', frameColor, {{ x: width, y: 0.045, z: 0.045 }}, {{ x: anchor.position.x, y: height * 0.36, z: anchor.position.z }}, anchor.info.angle, 1);
      addBox(group, 'window glass proxy', 0x92c6c8, {{ x: width * 0.92, y: height * 0.31, z: 0.025 }}, {{ x: anchor.position.x, y: height * 0.52, z: anchor.position.z }}, anchor.info.angle, 0.28);
      return {{ anchor, width }};
    }}

    function addCurtainVariant(group, wallId, mode) {{
      const {{ anchor, width }} = addWindowOutline(group, wallId, false);
      const color = mode === 'sheer_curtain' ? 0xbfe6e2 : 0xe88f86;
      const opacity = mode === 'sheer_curtain' ? 0.38 : 0.86;
      addBox(group, 'curtain rod', 0x6f6255, {{ x: width * 1.16, y: 0.045, z: 0.05 }}, {{ x: anchor.position.x, y: height * 0.76, z: anchor.position.z }}, anchor.info.angle, 1);
      const folds = mode === 'sheer_curtain' ? 8 : 6;
      for (let i = 0; i < folds; i += 1) {{
        const t = (i / Math.max(folds - 1, 1)) - 0.5;
        const side = new THREE.Vector3(Math.cos(anchor.info.angle), 0, -Math.sin(anchor.info.angle));
        const p = new THREE.Vector3(anchor.position.x, height * 0.52, anchor.position.z).add(side.multiplyScalar(t * width * 0.95));
        addBox(group, 'soft curtain fold', color, {{ x: width / folds * 0.72, y: height * 0.34, z: 0.038 }}, {{ x: p.x, y: p.y, z: p.z }}, anchor.info.angle, opacity);
      }}
    }}

    function addRollerShade(group, wallId) {{
      const {{ anchor, width }} = addWindowOutline(group, wallId, false);
      addBox(group, 'roller cassette', 0xf7f2e7, {{ x: width * 1.08, y: 0.08, z: 0.06 }}, {{ x: anchor.position.x, y: height * 0.75, z: anchor.position.z }}, anchor.info.angle, 1);
      addBox(group, 'roller shade fabric', 0xc7d79c, {{ x: width * 0.92, y: height * 0.32, z: 0.025 }}, {{ x: anchor.position.x, y: height * 0.54, z: anchor.position.z }}, anchor.info.angle, 0.68);
    }}

function addVerticalBlind(group, wallId) {{
      const {{ anchor, width }} = addWindowOutline(group, wallId, false);
      const side = new THREE.Vector3(Math.cos(anchor.info.angle), 0, -Math.sin(anchor.info.angle));
      for (let i = 0; i < 8; i += 1) {{
        const t = (i / 7) - 0.5;
        const p = new THREE.Vector3(anchor.position.x, height * 0.53, anchor.position.z).add(side.clone().multiplyScalar(t * width * 0.95));
        addBox(group, 'vertical blind panel', 0xd8e6d1, {{ x: width / 10, y: height * 0.42, z: 0.045 }}, {{ x: p.x, y: p.y, z: p.z }}, anchor.info.angle, 0.82);
      }}
    }}

    function addVenetianBlind(group, wallId) {{
      const {{ anchor, width }} = addWindowOutline(group, wallId, false);
      for (let i = 0; i < 11; i += 1) {{
        const y = height * 0.69 - i * height * 0.028;
        addBox(group, 'venetian blind slat', 0xf7f6ef, {{ x: width * 0.96, y: 0.024, z: 0.055 }}, {{ x: anchor.position.x, y, z: anchor.position.z }}, anchor.info.angle, 0.92);
      }}
    }}

    function addExteriorShadeVariant(group, wallId, mode) {{
      const {{ anchor, width }} = addWindowOutline(group, wallId, true);
      if (mode === 'horizontal_fixed_shade') {{
        for (let i = 0; i < 5; i += 1) addBox(group, 'horizontal fixed shade', 0xb7d98b, {{ x: width * 1.12, y: 0.045, z: 0.42 }}, {{ x: anchor.position.x, y: height * 0.72 - i * 0.32, z: anchor.position.z }}, anchor.info.angle, 0.86);
      }} else if (mode === 'vertical_movable_shade') {{
        const side = new THREE.Vector3(Math.cos(anchor.info.angle), 0, -Math.sin(anchor.info.angle));
        for (let i = 0; i < 6; i += 1) {{
          const t = (i / 5) - 0.5;
          const p = new THREE.Vector3(anchor.position.x, height * 0.54, anchor.position.z).add(side.clone().multiplyScalar(t * width));
          addBox(group, 'vertical movable fin', 0x9eca74, {{ x: 0.055, y: height * 0.42, z: 0.42 }}, {{ x: p.x, y: p.y, z: p.z }}, anchor.info.angle, 0.82);
        }}
      }} else if (mode === 'awning_shade') {{
        addBox(group, 'awning shade canopy', 0x9fd37a, {{ x: width * 1.18, y: 0.08, z: 0.72 }}, {{ x: anchor.position.x, y: height * 0.78, z: anchor.position.z }}, anchor.info.angle, 0.72);
        addBox(group, 'awning front lip', 0x6aa45d, {{ x: width * 1.12, y: 0.07, z: 0.06 }}, {{ x: anchor.position.x, y: height * 0.70, z: anchor.position.z }}, anchor.info.angle, 0.9);
      }} else if (mode === 'trellis_shade') {{
        for (let i = 0; i < 5; i += 1) {{
          const y = height * 0.34 + i * height * 0.085;
          addBox(group, 'trellis horizontal', 0x74a45e, {{ x: width * 1.02, y: 0.035, z: 0.045 }}, {{ x: anchor.position.x, y, z: anchor.position.z }}, anchor.info.angle, 1);
        }}
        const side = new THREE.Vector3(Math.cos(anchor.info.angle), 0, -Math.sin(anchor.info.angle));
        for (let i = 0; i < 5; i += 1) {{
          const t = (i / 4) - 0.5;
          const p = new THREE.Vector3(anchor.position.x, height * 0.52, anchor.position.z).add(side.clone().multiplyScalar(t * width));
          addBox(group, 'trellis vertical', 0x74a45e, {{ x: 0.04, y: height * 0.42, z: 0.045 }}, {{ x: p.x, y: p.y, z: p.z }}, anchor.info.angle, 1);
        }}
      }} else if (mode === 'vegetation_window') {{
        addExteriorShadeVariant(group, wallId, 'trellis_shade');
        const side = new THREE.Vector3(Math.cos(anchor.info.angle), 0, -Math.sin(anchor.info.angle));
        for (let i = 0; i < 9; i += 1) {{
          const t = ((i % 3) / 2) - 0.5;
          const y = height * (0.37 + Math.floor(i / 3) * 0.12);
          const p = new THREE.Vector3(anchor.position.x, y, anchor.position.z).add(side.clone().multiplyScalar(t * width * 0.78));
          const crown = new THREE.Mesh(new THREE.SphereGeometry(0.13 + (i % 2) * 0.035, 14, 9), new THREE.MeshStandardMaterial({{ color: 0x5f9b58, roughness: 0.75 }}));
          crown.position.set(p.x, p.y, p.z);
          group.add(crown);
        }}
      }}
    }}

    function addDensePlantCorner(group) {{
      addPlantCluster(group);
      const xs = roomPoints.map(p => p.x);
      const zs = roomPoints.map(p => p.z);
      const x = Math.min(...xs) + 0.92;
      const z = Math.max(...zs) - 1.05;
      for (let i = 0; i < 4; i += 1) {{
        addCylinder(group, 'extra plant pot', 0x9a6a48, 0.11 + i * 0.02, 0.2, {{ x: x + i * 0.22, y: 0.1, z: z + (i % 2) * 0.24 }});
        const crown = new THREE.Mesh(new THREE.SphereGeometry(0.22 + i * 0.025, 16, 10), new THREE.MeshStandardMaterial({{ color: i % 2 ? 0x79a95f : 0x47784c, roughness: 0.7 }}));
        crown.position.set(x + i * 0.22, 0.42 + i * 0.05, z + (i % 2) * 0.24);
        group.add(crown);
      }}
    }}

    function renderHybridAsset(variant) {{
      retrofitObjects.clear();
      const decision = variant.decision || {{ status: 'allowed', reasons: [] }};
      if (decision.status === 'blocked') {{
        document.getElementById('status').innerHTML = `
          <h2>blocked visual</h2>
          <p><strong>${{variant.label}}</strong></p>
          <div class="row"><span>opening</span><span>${{decision.opening_type}}</span></div>
          <div class="row"><span>reason</span><span>${{decision.reasons?.[0] || 'not suitable'}}</span></div>
          <p class="badge">The geometry was not rendered because this option conflicts with the current decision boundary.</p>`;
        return;
      }}
      const wallId = decision.target_wall_id || firstWindowWall([]);
      addTargetWallMask(retrofitObjects, wallId, decision.status === 'conditional' ? 0xd19b43 : 0x779f73);
      const generator = variant.generator;
      if (generator === 'curtain_drapes' || generator === 'sheer_curtain') addCurtainVariant(retrofitObjects, wallId, generator);
      else if (generator === 'roller_shade') addRollerShade(retrofitObjects, wallId);
      else if (generator === 'vertical_blind') addVerticalBlind(retrofitObjects, wallId);
      else if (generator === 'venetian_blind') addVenetianBlind(retrofitObjects, wallId);
      else if (['horizontal_fixed_shade', 'vertical_movable_shade', 'awning_shade', 'trellis_shade', 'vegetation_window'].includes(generator)) addExteriorShadeVariant(retrofitObjects, wallId, generator);
      else if (generator === 'plant_corner_dense') addDensePlantCorner(retrofitObjects);
      document.getElementById('status').innerHTML = `
        <h2>hybrid visual test</h2>
        <p><strong>${{variant.label}}</strong></p>
        <div class="row"><span>decision</span><span>${{decision.status}}</span></div>
        <div class="row"><span>opening</span><span>${{decision.opening_type}}</span></div>
        <div class="row"><span>family</span><span>${{variant.family}}</span></div>
        <div class="row"><span>generator</span><span>${{variant.generator}}</span></div>
        <p class="badge">${{decision.reasons?.[0] || variant.placement}} | future slot: ${{variant.future_glb_slot}}</p>`;
    }}

    function renderHybridAssets() {{
      const container = document.getElementById('hybridAssets');
      const variants = plan.hybrid_assets?.variants || [];
      if (!variants.length) return;
      container.innerHTML = '<h2>hybrid visual tests</h2><p class="badge">decision-gated curtain, shade, and plant generators</p><div class="asset-grid"></div>';
      const grid = container.querySelector('.asset-grid');
      variants.forEach(variant => {{
        const button = document.createElement('button');
        const decision = variant.decision || {{ status: 'allowed' }};
        button.classList.add(decision.status);
        button.textContent = `${{variant.label}} ${{decision.status === 'allowed' ? '' : '(' + decision.status + ')'}}`;
        button.title = decision.reasons?.[0] || variant.placement;
        button.addEventListener('click', () => renderHybridAsset(variant));
        grid.appendChild(button);
      }});
    }}
    function addVentilationOverlay(group, wallIds) {{
      const c = center();
      const targetWalls = wallIds.length ? wallIds : [plan.walls[0]?.id].filter(Boolean);
      targetWalls.forEach(wallId => {{
        const wall = wallsById.get(wallId);
        if (!wall) return;
        const info = wallInfo(wall);
        const start = {{ x: info.x, y: 1.35, z: info.z }};
        const end = {{ x: c.x, y: 1.75, z: c.z }};
        addArrow(group, start, end, 0x2f8197);
        addTargetWallMask(group, wallId, 0x2f8197);
      }});
    }}

    function addOptionGeometry(option) {{
      const asset = option.visual_asset_type || '';
      option.wall_ids.forEach(wallId => addTargetWallMask(retrofitObjects, wallId));
      if (asset.includes('operation_overlay')) addVentilationOverlay(retrofitObjects, option.wall_ids);
      if (asset.includes('ceiling_roof_layer') || asset.includes('cool_roof_material')) addCeilingLayer(retrofitObjects, asset.includes('cool') ? 0xf9f4dc : 0xd8efe6, asset.includes('cool') ? 0.58 : 0.42);
      if (asset.includes('ceiling_roof_vent')) addCeilingVent(retrofitObjects);
      if (asset.includes('ceiling_fan')) addFan(retrofitObjects);
      if (asset.includes('wall_layer') || asset.includes('pcm_panel')) option.wall_ids.forEach(wallId => addWallLayer(retrofitObjects, wallId, asset.includes('pcm') ? 0xe1d5be : 0xd8efe6));
      if (asset.includes('plant') || asset.includes('vegetation')) addPlantCluster(retrofitObjects);
    }}

    function selectedOptions() {{
      const matched = plan.options.filter(option => selectedOptionIds.has(option.strategy_id));
      if (matched.length) return matched;
      const first = plan.options[0];
      if (first) selectedOptionIds.add(first.strategy_id);
      return first ? [first] : [];
    }}

    function renderSelectedOptions() {{
      retrofitObjects.clear();
      const selected = selectedOptions();
      selected.forEach(addOptionGeometry);
      document.querySelectorAll('.option').forEach(item => {{
        item.classList.toggle('active', selectedOptionIds.has(item.dataset.strategyId));
      }});
      const summaryRows = selected.map(option => `
        <div class="row"><span>${{option.strategy_name}}</span><span>${{option.visual_asset_type}}</span></div>`).join('');
      const benchmark = selected.map(option => `${{option.status || 'unknown'}} / ${{option.confidence || 'unknown'}}`).join(', ');
      document.getElementById('status').innerHTML = `
        <h2>selected options</h2>
        <p><strong>${{selected.length}} strategy${{selected.length === 1 ? '' : 'ies'}} active</strong></p>
        ${{summaryRows}}
        <div class="row"><span>benchmark</span><span>${{benchmark}}</span></div>
        <p class="badge">Multiple selected strategies render together as a visual combo. Thermal combo scoring remains in the validation engine.</p>`;
    }}

    function renderOptions() {{
      const container = document.getElementById('options');
      container.innerHTML = '<h2>validated options</h2><p class="badge">click one or more options to combine visual layers</p>';
      plan.options.slice(0, 8).forEach((option) => {{
        const button = document.createElement('button');
        button.className = 'option';
        button.dataset.strategyId = option.strategy_id;
        button.innerHTML = `<span>${{option.rank}}. ${{option.strategy_name}}</span><span class="badge">${{option.visual_asset_type}} | ${{option.status}} | ${{option.confidence}}</span>`;
        button.addEventListener('click', () => {{
          if (selectedOptionIds.has(option.strategy_id) && selectedOptionIds.size > 1) selectedOptionIds.delete(option.strategy_id);
          else selectedOptionIds.add(option.strategy_id);
          renderSelectedOptions();
        }});
        container.appendChild(button);
      }});
      if (!selectedOptionIds.size && plan.options[0]) selectedOptionIds.add(plan.options[0].strategy_id);
      setTimeout(renderSelectedOptions, 0);
    }}

    function setView(mode) {{
      const target = center();
      controls.target.copy(target);
      const radius = 10;
      if (mode === 'top') camera.position.set(target.x, target.y + 14, target.z + 0.001);
      else if (mode === 'front') camera.position.set(target.x, target.y + 1.5, target.z + radius);
      else camera.position.set(target.x + 7.5, target.y + 5.5, target.z + 8.5);
      camera.lookAt(target);
      controls.update();
    }}

    function resize() {{
      const width = window.innerWidth;
      const heightPx = window.innerHeight;
      renderer.setSize(width, heightPx, false);
      camera.aspect = width / Math.max(heightPx, 1);
      camera.updateProjectionMatrix();
    }}

    function animate() {{
      controls.update();
      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    }}

    scene.add(new THREE.GridHelper(16, 32, 0xbab3a7, 0xded8cc));
    addRoom();
    renderOptions();
    renderHybridAssets();
    resize();
    setView('iso');
    animate();

    window.addEventListener('resize', resize);
    document.getElementById('iso').addEventListener('click', () => setView('iso'));
    document.getElementById('top').addEventListener('click', () => setView('top'));
    document.getElementById('front').addEventListener('click', () => setView('front'));
    document.getElementById('reset').addEventListener('click', () => setView('iso'));
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build standalone HVRA retrofit 3D test output.")
    parser.add_argument("--biophilic-test", action="store_true", help="Inject a test-only interior biophilic option into the 3D output.")
    parser.add_argument("--opening-type", choices=["window", "sliding_glass_door", "balcony_door"], default=None, help="Override inferred opening morphology for suitability testing.")
    args = parser.parse_args()

    plan = build_visual_plan(include_biophilic_test=args.biophilic_test, opening_type_override=args.opening_type)
    write_json(PLAN_PATH, plan)
    HTML_PATH.write_text(build_html(plan), encoding="utf-8")
    print(f"Wrote {PLAN_PATH}")
    print(f"Wrote {HTML_PATH}")
    print(f"Options: {len(plan['options'])}")
    print(f"Walls: {len(plan['walls'])}")
    for option in plan["options"][:5]:
        print(f"- {option['rank']}. {option['strategy_id']} -> {option['visual_asset_type']}")


if __name__ == "__main__":
    main()
















