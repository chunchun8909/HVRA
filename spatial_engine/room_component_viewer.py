from __future__ import annotations

import json
from pathlib import Path

from utils.config import ROOT_DIR
from .room_viewer import export_room_view
from .host_geometry import build_host_geometry


def _spatial_logic_rules() -> dict:
    rules_path = ROOT_DIR / "3D_test" / "one_wall_spatial_logic" / "spatial_logic_rules.json"
    if not rules_path.exists():
        return {}
    try:
        return json.loads(rules_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _phase3_strategy_packages() -> dict:
    package_path = ROOT_DIR / "data" / "intermediate" / "phase3_strategy_packages.json"
    if not package_path.exists():
        return {"packages": []}
    try:
        return json.loads(package_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"packages": []}


def _component_overlay_script(room_model: dict) -> str:
    rules_data = json.dumps(_spatial_logic_rules(), ensure_ascii=False)
    host_data = json.dumps(build_host_geometry(room_model), ensure_ascii=False)
    package_data = json.dumps(_phase3_strategy_packages(), ensure_ascii=False)
    script = """
    const componentLogicRules = __RULES_DATA__;
    const hostGeometry = __HOST_DATA__;
    const phase3Packages = __PACKAGE_DATA__;
    const qaComponentOrder = [
      "solarControlGlazing",
      "venetianBlind",
      "verticalBlind",
      "romanShade",
      "shortSillCurtain",
      "fullHeightDrape",
      "externalAwning",
      "ceilingFan",
      "airPath",
      "wallInsulation",
      "trellis",
      "planterShelf",
      "hangingRail",
      "plantLadder",
      "rectangularPlanter",
      "floorPlants"
    ];
    const qaComponentLabels = {
      solarControlGlazing: "solar-control glazing tint",
      venetianBlind: "venetian blind",
      verticalBlind: "vertical blind",
      romanShade: "roman shade",
      shortSillCurtain: "short sill curtain",
      fullHeightDrape: "full-height drape",
      externalAwning: "external awning",
      ceilingFan: "ceiling fan",
      airPath: "air-path indicators",
      wallInsulation: "wall insulation layer",
      trellis: "trellis greenery",
      planterShelf: "planter shelf",
      hangingRail: "hanging rail",
      plantLadder: "plant ladder",
      rectangularPlanter: "rectangular planter",
      floorPlants: "floor plants"
    };
    const componentAlias = {
      insulationReinforcementLayer: "wallInsulation",
      wall_insulation_reinforcement_layer: "wallInsulation",
      floorPlantsB: "floorPlants",
      planterShelfB: "planterShelf",
      rectangularPlanterB: "rectangularPlanter",
      solarControlGlazingTint: "solarControlGlazing"
    };
    const fallbackOptionComponents = {
      option1: ["externalAwning", "shortSillCurtain", "wallInsulation", "plantLadder", "trellis", "ceilingFan"],
      option2: ["verticalBlind", "hangingRail", "floorPlants", "rectangularPlanter", "ceilingFan"],
      option3: ["fullHeightDrape", "rectangularPlanter", "planterShelf", "ceilingFan"]
    };
    const qaComponentState = Object.fromEntries(qaComponentOrder.map(name => [name, false]));

    function normalizeOption(value) {
      return String(value || "").replace(/_/g, "").toLowerCase();
    }

    function packageForSelection(value) {
      const packages = phase3Packages.packages || [];
      const normalized = normalizeOption(value);
      const optionMatch = normalized.match(/^option([0-9]+)$/);
      if (optionMatch) return packages[Number(optionMatch[1]) - 1] || null;
      return packages.find(pkg => value === pkg.package_id || String(value || "").includes(pkg.package_id)) || null;
    }

    function componentNamesForSelection(value) {
      const packages = phase3Packages.packages || [];
      const normalized = normalizeOption(value);
      const optionMatch = normalized.match(/^option([0-9]+)$/);
      const optionKey = optionMatch ? `option${optionMatch[1]}` : null;
      const pkg = packageForSelection(value);
      const source = pkg?.visual_generation?.component_ids || (optionKey ? fallbackOptionComponents[optionKey] : null) || fallbackOptionComponents.option1;
      return new Set(source.map(name => componentAlias[name] || name).filter(name => qaComponentOrder.includes(name)));
    }

    function applyComponentSelection(value) {
      const selected = componentNamesForSelection(value);
      qaComponentOrder.forEach(name => { qaComponentState[name] = selected.has(name); });
    }

    const query = new URLSearchParams(window.location.search);
    const requestedPackage = (query.get("strategy_id") || query.get("package_id") || query.get("strategy_ids") || "option1").split(",")[0].trim();
    applyComponentSelection(requestedPackage);
    const qaOpeningHost = (hostGeometry.openings || []).find(host => host.is_main_opening)
      || (hostGeometry.openings || [])[0]
      || null;
    const qaOpeningComponent = (model.components || []).find(component => component.id === qaOpeningHost?.component_id)
      || (model.components || [])
        .filter(component => component.component_type === "window")
        .sort((a, b) => (b.estimated_area_m2 || 0) - (a.estimated_area_m2 || 0))[0]
      || null;
    const qaWallId = hostGeometry.main_wall_id || qaOpeningHost?.wall_id || qaOpeningComponent?.wall_id || "ROOM_001_WALL_07";

    function strategyComponentSet() {
      return new Set(qaComponentOrder.filter(name => qaComponentState[name]));
    }

    function qaWallName() {
      const index = model.walls.findIndex(wall => wall.id === qaWallId);
      return index >= 0 ? `wall ${String(index + 1).padStart(2, "0")}` : qaWallId;
    }

    function renderComponentQaPanel() {
      const panel = document.getElementById("strategyComponentPanel");
      const target = document.getElementById("strategyComponentTarget");
      if (!panel) return;
      if (target) {
        const pkg = packageForSelection(requestedPackage);
        const selectedName = pkg?.package_name || requestedPackage || "option 1";
        target.textContent = `${selectedName} | ${qaWallName()} | main large window | ${(qaOpeningComponent?.estimated_area_m2 || 0).toFixed(3)} m2`;
      }
      panel.innerHTML = qaComponentOrder.map(name => `
        <label class="vvRow">
          <input type="checkbox" data-component-name="${name}" ${qaComponentState[name] ? "checked" : ""}>
          <span>${qaComponentLabels[name]}<small>${name}</small></span>
        </label>
      `).join("");
      panel.querySelectorAll("input[data-component-name]").forEach(input => {
        input.addEventListener("change", event => {
          qaComponentState[event.target.dataset.componentName] = event.target.checked;
          draw();
        });
      });
    }

    function hostForComponent(component) {
      return (hostGeometry.openings || []).find(host => host.component_id === component?.id) || qaOpeningHost;
    }

    function openingUvForComponent(component) {
      const host = hostForComponent(component);
      if (host?.uv) return host.uv;
      const bbox = component?.bbox_px;
      const wallTexture = component ? wallTextures(component.wall_id)[0] : null;
      const image = wallTexture ? textureImages[wallTexture.id] : null;
      const imageWidth = image?.naturalWidth || 1;
      const imageHeight = image?.naturalHeight || 1;
      let u0 = 0.32, u1 = 0.68, v0 = 0.34, v1 = 0.68;
      if (Array.isArray(bbox) && bbox.length >= 4 && imageWidth > 1 && imageHeight > 1) {
        u0 = Math.max(0.08, Math.min(0.92, bbox[0] / imageWidth));
        u1 = Math.max(0.08, Math.min(0.92, bbox[2] / imageWidth));
        v0 = Math.max(0.08, Math.min(0.92, bbox[1] / imageHeight));
        v1 = Math.max(0.08, Math.min(0.96, bbox[3] / imageHeight));
      }
      if (u1 < u0) [u0, u1] = [u1, u0];
      if (v1 < v0) [v0, v1] = [v1, v0];
      return { u0, u1, v0, v1 };
    }

    function quadFromUv(wallFace, uv) {
      return [
        pointOnQuad(wallFace, uv.u0, uv.v1),
        pointOnQuad(wallFace, uv.u1, uv.v1),
        pointOnQuad(wallFace, uv.u1, uv.v0),
        pointOnQuad(wallFace, uv.u0, uv.v0)
      ];
    }

    function zoneQuadForComponent(wallFace, component, zoneName) {
      const host = hostForComponent(component);
      const zone = host?.zones?.[zoneName] || host?.uv || openingUvForComponent(component);
      return quadFromUv(wallFace, zone);
    }

    function drawSoftPolygon(points, fill, stroke, opacity = 1, width = 1) {
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.beginPath();
      points.forEach((point, index) => index ? ctx.lineTo(point[0], point[1]) : ctx.moveTo(point[0], point[1]));
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.strokeStyle = stroke;
      ctx.lineWidth = width * devicePixelRatio;
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }

    function drawLine(points, color, width = 1, opacity = 1) {
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.strokeStyle = color;
      ctx.lineWidth = width * devicePixelRatio;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      points.forEach((point, index) => index ? ctx.lineTo(point[0], point[1]) : ctx.moveTo(point[0], point[1]));
      ctx.stroke();
      ctx.restore();
    }

    function drawEllipse(center, rx, ry, fill, stroke = "rgba(30,70,42,0.45)", opacity = 1) {
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.beginPath();
      ctx.ellipse(center[0], center[1], rx * devicePixelRatio, ry * devicePixelRatio, 0, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 0.7 * devicePixelRatio;
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }

    function interp(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]; }
    function moveToward(a, b, amount) {
      const dx = b[0] - a[0], dy = b[1] - a[1];
      const len = Math.hypot(dx, dy) || 1;
      return [a[0] + dx / len * amount * devicePixelRatio, a[1] + dy / len * amount * devicePixelRatio];
    }

    function drawSolarTintOnOpening(opening) {
      drawSoftPolygon(opening, "rgba(61,139,142,0.28)", "rgba(61,139,142,0.52)", 1, 1.1);
    }

    function drawVenetianOnOpening(opening) {
      const leftBottom = opening[0], rightBottom = opening[1], rightTop = opening[2], leftTop = opening[3];
      for (let i = 0; i < 15; i++) {
        const t = 0.12 + i * 0.052;
        const a = interp(leftTop, leftBottom, t);
        const b = interp(rightTop, rightBottom, t);
        drawLine([a, b], "rgba(246,243,232,0.92)", 1.2, 0.92);
      }
    }

    function drawVerticalBlindOnOpening(opening) {
      const leftBottom = opening[0], rightBottom = opening[1], rightTop = opening[2], leftTop = opening[3];
      for (let i = 0; i < 13; i++) {
        const t = i / 12;
        const top = interp(leftTop, rightTop, t);
        const bottom = interp(leftBottom, rightBottom, t);
        drawLine([top, bottom], "rgba(238,229,217,0.72)", 2.1, 0.7);
      }
      drawLine([leftTop, rightTop], "rgba(90,76,58,0.78)", 2, 0.9);
    }

    function drawRomanShadeOnOpening(opening) {
      const leftTop = opening[3], rightTop = opening[2], leftBottom = opening[0], rightBottom = opening[1];
      const panel = [
        interp(leftTop, leftBottom, 0.04),
        interp(rightTop, rightBottom, 0.04),
        interp(rightTop, rightBottom, 0.34),
        interp(leftTop, leftBottom, 0.34)
      ];
      drawSoftPolygon(panel, "rgba(216,194,173,0.72)", "rgba(154,121,90,0.62)", 1, 1);
      for (let i = 1; i < 5; i++) {
        const a = interp(panel[3], panel[0], i / 5);
        const b = interp(panel[2], panel[1], i / 5);
        drawLine([a, b], "rgba(132,98,70,0.55)", 1, 0.75);
      }
    }

    function drawShortSillCurtainOnOpening(opening) {
      const leftTop = opening[3], rightTop = opening[2], leftBottom = opening[0], rightBottom = opening[1];
      drawLine([leftTop, rightTop], "rgba(91,66,48,0.92)", 2.4, 1);
      for (let i = 0; i < 12; i++) {
        const t = i / 11;
        const top = interp(leftTop, rightTop, t);
        const endTop = interp(leftTop, leftBottom, 0.36);
        const endRight = interp(rightTop, rightBottom, 0.36);
        const bottom = interp(endTop, endRight, t + Math.sin(i) * 0.012);
        drawLine([top, bottom], i % 2 ? "rgba(210,180,164,0.70)" : "rgba(232,210,198,0.70)", 3, 0.72);
      }
    }

    function drawFullHeightDrapeOnOpening(opening) {
      const leftTop = opening[3], rightTop = opening[2], leftBottom = opening[0], rightBottom = opening[1];
      drawLine([moveToward(leftTop, rightTop, -8), moveToward(rightTop, leftTop, -8)], "rgba(91,66,48,0.92)", 2.6, 1);
      for (let i = 0; i < 20; i++) {
        const t = i / 19;
        const top = interp(leftTop, rightTop, t);
        const bottom = interp(leftBottom, rightBottom, t + Math.sin(i * 0.75) * 0.01);
        drawLine([top, bottom], i % 2 ? "rgba(202,158,142,0.66)" : "rgba(222,188,174,0.66)", 3.2, 0.7);
      }
    }

    function drawExternalAwningOnOpening(opening) {
      const leftTop = opening[3], rightTop = opening[2];
      const outLeft = [leftTop[0] - 10 * devicePixelRatio, leftTop[1] - 22 * devicePixelRatio];
      const outRight = [rightTop[0] + 10 * devicePixelRatio, rightTop[1] - 22 * devicePixelRatio];
      const frontRight = [rightTop[0] + 16 * devicePixelRatio, rightTop[1] + 8 * devicePixelRatio];
      const frontLeft = [leftTop[0] - 16 * devicePixelRatio, leftTop[1] + 8 * devicePixelRatio];
      drawSoftPolygon([frontLeft, frontRight, outRight, outLeft], "rgba(130,174,118,0.52)", "rgba(78,112,76,0.78)", 1, 1.1);
      drawLine([leftTop, frontLeft], "rgba(86,80,67,0.8)", 1.3, 0.9);
      drawLine([rightTop, frontRight], "rgba(86,80,67,0.8)", 1.3, 0.9);
    }

    function sideZone(wallFace, opening, side = "right") {
      const sign = side === "right" ? 1 : -1;
      const openCenterTop = interp(opening[3], opening[2], 0.5);
      const faceLeftTop = wallFace[3], faceRightTop = wallFace[2], faceLeftBottom = wallFace[0], faceRightBottom = wallFace[1];
      const u = side === "right" ? 0.76 : 0.24;
      const xTop = interp(faceLeftTop, faceRightTop, u);
      const xBottom = interp(faceLeftBottom, faceRightBottom, u);
      const away = moveToward(xTop, openCenterTop, -18 * sign);
      return { top: away, bottom: moveToward(xBottom, interp(opening[0], opening[1], 0.5), -18 * sign), u };
    }

    function drawPlanterShelfOnWall(wallFace, opening) {
      const zone = sideZone(wallFace, opening, "right");
      const shelfTop = interp(zone.top, zone.bottom, 0.54);
      const shelfEnd = [shelfTop[0] + 84 * devicePixelRatio, shelfTop[1] + 4 * devicePixelRatio];
      drawLine([shelfTop, shelfEnd], "rgba(169,132,92,0.94)", 5, 1);
      drawLine([[shelfTop[0], shelfTop[1] - 22 * devicePixelRatio], shelfTop], "rgba(120,104,88,0.7)", 2, 0.9);
      for (let i = 0; i < 4; i++) {
        const p = interp(shelfTop, shelfEnd, 0.12 + i * 0.24);
        drawEllipse([p[0], p[1] - 7 * devicePixelRatio], 6, 6, "rgba(128,82,50,0.92)", "rgba(85,54,34,0.6)");
        drawEllipse([p[0], p[1] - 21 * devicePixelRatio], 8 + (i % 2) * 3, 6 + (i % 3), i % 2 ? "rgba(83,139,78,0.95)" : "rgba(47,116,65,0.95)");
      }
    }

    function drawHangingRailOnWall(wallFace, opening) {
      const zone = sideZone(wallFace, opening, "left");
      const railCenter = interp(zone.top, zone.bottom, 0.28);
      const railLeft = [railCenter[0] - 58 * devicePixelRatio, railCenter[1]];
      const railRight = [railCenter[0] + 58 * devicePixelRatio, railCenter[1]];
      drawLine([railLeft, railRight], "rgba(91,66,48,0.9)", 3, 1);
      [0.15, 0.5, 0.85].forEach((t, i) => {
        const hook = interp(railLeft, railRight, t);
        const potBase = [hook[0], hook[1] + (42 + i * 4) * devicePixelRatio];
        drawLine([hook, potBase], "rgba(92,85,72,0.72)", 1, 0.9);
        drawEllipse(potBase, 7, 6, "rgba(128,82,50,0.9)", "rgba(85,54,34,0.65)");
        for (let j = 0; j < 5; j++) {
          const leaf = [potBase[0] + (j - 2) * 5 * devicePixelRatio, potBase[1] - (12 + (j % 2) * 5) * devicePixelRatio];
          drawLine([potBase, leaf], "rgba(44,98,57,0.75)", 1, 0.8);
          drawEllipse(leaf, 5, 4, j % 2 ? "rgba(79,139,87,0.94)" : "rgba(47,116,65,0.94)");
        }
      });
    }

    function drawPlantLadderOnWall(wallFace, opening) {
      const zone = sideZone(wallFace, opening, "left");
      const top = interp(zone.top, zone.bottom, 0.34);
      const bottom = interp(zone.top, zone.bottom, 0.88);
      const leftTop = [top[0] - 32 * devicePixelRatio, top[1]];
      const rightTop = [top[0] + 32 * devicePixelRatio, top[1] + 2 * devicePixelRatio];
      const leftBottom = [bottom[0] - 42 * devicePixelRatio, bottom[1]];
      const rightBottom = [bottom[0] + 42 * devicePixelRatio, bottom[1] + 2 * devicePixelRatio];
      drawLine([leftTop, leftBottom], "rgba(139,107,72,0.9)", 3, 1);
      drawLine([rightTop, rightBottom], "rgba(139,107,72,0.9)", 3, 1);
      for (let i = 0; i < 4; i++) {
        const a = interp(leftTop, leftBottom, i / 3);
        const b = interp(rightTop, rightBottom, i / 3);
        drawLine([a, b], "rgba(199,170,130,0.94)", 4, 1);
        const p = interp(a, b, i % 2 ? 0.68 : 0.35);
        drawEllipse([p[0], p[1] - 5 * devicePixelRatio], 7, 6, "rgba(142,92,58,0.9)", "rgba(91,57,37,0.7)");
        drawEllipse([p[0], p[1] - 20 * devicePixelRatio], 10 + i, 6 + (i % 2) * 2, i % 2 ? "rgba(92,158,92,0.94)" : "rgba(54,133,68,0.94)");
      }
    }
    function drawRectangularPlanterOnWall(wallFace, opening) {
      const bottom = interp(opening[1], wallFace[1], 0.38);
      const left = [bottom[0] - 54 * devicePixelRatio, bottom[1] - 10 * devicePixelRatio];
      const right = [bottom[0] + 54 * devicePixelRatio, bottom[1] - 10 * devicePixelRatio];
      drawSoftPolygon([[left[0], left[1] + 16 * devicePixelRatio], [right[0], right[1] + 16 * devicePixelRatio], right, left], "rgba(134,96,67,0.86)", "rgba(93,67,48,0.72)", 1, 1);
      for (let i = 0; i < 12; i++) {
        const base = interp(left, right, i / 11);
        const top = [base[0] + Math.sin(i) * 4 * devicePixelRatio, base[1] - (16 + (i % 4) * 5) * devicePixelRatio];
        drawLine([base, top], "rgba(45,96,58,0.8)", 1, 0.9);
        drawEllipse(top, 5 + (i % 3), 4 + (i % 2), i % 2 ? "rgba(89,151,84,0.94)" : "rgba(47,116,65,0.94)");
      }
    }

    function drawTrellisOnWall(wallFace, opening) {
      const zone = sideZone(wallFace, opening, "right");
      const top = interp(zone.top, zone.bottom, 0.25);
      const bottom = interp(zone.top, zone.bottom, 0.78);
      const width = 68 * devicePixelRatio;
      const leftTop = [top[0] - width / 2, top[1]];
      const rightTop = [top[0] + width / 2, top[1]];
      const leftBottom = [bottom[0] - width / 2, bottom[1]];
      const rightBottom = [bottom[0] + width / 2, bottom[1]];
      for (let i = 0; i < 4; i++) {
        const a = interp(leftTop, rightTop, i / 3);
        const b = interp(leftBottom, rightBottom, i / 3);
        drawLine([a, b], "rgba(158,121,78,0.92)", 2.2, 1);
      }
      for (let i = 0; i < 6; i++) {
        const a = interp(leftTop, leftBottom, i / 5);
        const b = interp(rightTop, rightBottom, i / 5);
        drawLine([a, b], "rgba(158,121,78,0.92)", 1.8, 1);
      }
      for (let i = 0; i < 36; i++) {
        const x = leftTop[0] + ((i * 37) % 100) / 100 * width;
        const y = top[1] + ((i * 53) % 100) / 100 * (bottom[1] - top[1]);
        const r = 4 + (i % 4);
        drawEllipse([x, y], r, r * 0.82, i % 3 ? "rgba(54,133,68,0.95)" : "rgba(96,165,92,0.95)");
        const rail = i % 2 ? [x, top[1] + Math.round((y - top[1]) / ((bottom[1] - top[1]) / 5)) * ((bottom[1] - top[1]) / 5)] : [leftTop[0] + Math.round((x - leftTop[0]) / (width / 3)) * (width / 3), y];
        drawLine([rail, [x, y]], "rgba(54,94,51,0.55)", 0.8, 0.75);
      }
    }

    function drawFloorPlantsOnWall(wallFace, opening) {
      const floorBase = interp(opening[0], wallFace[0], 0.48);
      for (let i = 0; i < 5; i++) {
        const p = [floorBase[0] - 26 * devicePixelRatio + i * 13 * devicePixelRatio, floorBase[1] - (i % 2) * 4 * devicePixelRatio];
        drawEllipse([p[0], p[1]], 6, 5, "rgba(126,83,54,0.9)", "rgba(90,58,35,0.7)");
        drawLine([p, [p[0], p[1] - (22 + i * 3) * devicePixelRatio]], "rgba(42,93,53,0.8)", 1.5, 0.9);
        drawEllipse([p[0], p[1] - (26 + i * 3) * devicePixelRatio], 9 + i, 6 + (i % 2) * 2, i % 2 ? "rgba(78,143,78,0.94)" : "rgba(43,118,67,0.94)");
      }
    }

    function drawWallInsulationOnFace(wallFace) {
      const inset = wallFace.map((point, index) => {
        const center = wallFace.reduce((sum, p) => [sum[0] + p[0] / wallFace.length, sum[1] + p[1] / wallFace.length], [0, 0]);
        return [point[0] * 0.96 + center[0] * 0.04, point[1] * 0.96 + center[1] * 0.04];
      });
      drawSoftPolygon(inset, "rgba(205,185,143,0.24)", "rgba(130,107,72,0.45)", 1, 1);
    }

    function drawAirPathOnOpening(opening) {
      const left = interp(opening[0], opening[3], 0.45);
      const right = interp(opening[1], opening[2], 0.55);
      for (let i = 0; i < 3; i++) {
        const a = interp(left, right, i / 2);
        const b = [a[0] + 36 * devicePixelRatio, a[1] - (8 - i * 6) * devicePixelRatio];
        drawLine([a, b], "rgba(47,127,152,0.55)", 2.4, 0.8);
        drawEllipse(b, 4, 4, "rgba(47,127,152,0.45)", "rgba(47,127,152,0.6)");
      }
    }

    function drawStrategyComponentsOnFace(face) {
      if (face.wallId !== qaWallId) return;
      const set = strategyComponentSet();
      const openings = qaOpeningComponent ? [qaOpeningComponent] : [null];
      openings.forEach(component => {
        const opening = zoneQuadForComponent(face.points, component, "opening_no_go_zone");
        const glassZone = zoneQuadForComponent(face.points, component, "opening_glass_zone");
        const blindZone = zoneQuadForComponent(face.points, component, "interior_blind_zone");
        const shortCurtainZone = zoneQuadForComponent(face.points, component, "short_curtain_zone");
        const fullDrapeZone = zoneQuadForComponent(face.points, component, "full_drape_zone");
        const awningZone = zoneQuadForComponent(face.points, component, "exterior_awning_zone");
        if (set.has("wallInsulation")) drawWallInsulationOnFace(face.points);
        if (set.has("solarControlGlazing")) drawSolarTintOnOpening(glassZone);
        if (set.has("venetianBlind")) drawVenetianOnOpening(blindZone);
        if (set.has("verticalBlind")) drawVerticalBlindOnOpening(blindZone);
        if (set.has("romanShade")) drawRomanShadeOnOpening(opening);
        if (set.has("shortSillCurtain")) drawShortSillCurtainOnOpening(shortCurtainZone);
        if (set.has("fullHeightDrape")) drawFullHeightDrapeOnOpening(fullDrapeZone);
        if (set.has("externalAwning")) drawExternalAwningOnOpening(awningZone);
        if (set.has("trellis")) drawTrellisOnWall(face.points, opening);
        if (set.has("planterShelf")) drawPlanterShelfOnWall(face.points, opening);
        if (set.has("hangingRail")) drawHangingRailOnWall(face.points, opening);
        if (set.has("plantLadder")) drawPlantLadderOnWall(face.points, opening);
        if (set.has("rectangularPlanter")) drawRectangularPlanterOnWall(face.points, opening);
        if (set.has("floorPlants")) drawFloorPlantsOnWall(face.points, opening);
        if (set.has("airPath")) drawAirPathOnOpening(opening);
      });
    }

    function drawStrategyCeilingFan() {
      if (!qaComponentState.ceilingFan) return;
      const center = project(sceneCenter.x, model.room.height_m - 0.22, sceneCenter.z);
      drawEllipse(center, 7, 7, "rgba(238,233,223,0.88)", "rgba(110,106,95,0.75)");
      for (let i = 0; i < 4; i++) {
        const angle = Math.PI / 2 * i + 0.34;
        const end = [center[0] + Math.cos(angle) * 42 * devicePixelRatio, center[1] + Math.sin(angle) * 18 * devicePixelRatio];
        drawLine([center, end], "rgba(178,149,106,0.78)", 5, 0.88);
      }
    }
"""
    return script.replace("__RULES_DATA__", rules_data).replace("__HOST_DATA__", host_data).replace("__PACKAGE_DATA__", package_data)


def _inject_component_overlay(html: str, room_model: dict) -> str:
    html = html.replace("<title>room view</title>", "<title>component room view</title>")
    html = html.replace('<span class="appTitle">room view</span>', '<span class="appTitle">component room view</span>')
    html = html.replace(
        '<section class="section">\n        <button class="sectionHeader" data-toggle="surfacePanel"><span>surfaces</span><span>&#9662;</span></button>',
        '<section class="section">\n        <button class="sectionHeader" data-toggle="strategyComponentPanelBody"><span>strategy components</span><span>&#9662;</span></button>\n        <div id="strategyComponentPanelBody" class="sectionBody">\n          <div class="type3" id="strategyComponentTarget">main large window wall</div>\n          <div id="strategyComponentPanel"></div>\n        </div>\n      </section>\n      <section class="section">\n        <button class="sectionHeader" data-toggle="surfacePanel"><span>surfaces</span><span>&#9662;</span></button>',
    )
    html = html.replace(
        '<div id="surfacePanel" class="sectionBody"><div id="surfaceList"></div></div>',
        '<div id="surfacePanel" class="sectionBody"><div id="surfaceList"></div><div class="type3" style="margin-top:8px">component QA is anchored to the main large window wall; base architecture is not duplicated.</div></div>',
    )
    script = _component_overlay_script(room_model)
    html = html.replace("    function setView(name) {", script + "\n\n    function setView(name) {")
    html = html.replace(
        "          componentsForWall(face.wallId).forEach((component, index) => drawWindowTag(component, face.points, index));",
        "          drawStrategyComponentsOnFace(face);",
    )
    html = html.replace(
        "      faces.forEach(face => {",
        "      faces.forEach(face => {",
    )
    html = html.replace(
        "      });\n\n    }\n\n    function renderSurfacePanel()",
        "      });\n      if (viewerMode === \"review\") drawStrategyCeilingFan();\n\n    }\n\n    function renderSurfacePanel()",
    )
    return html


def export_room_component_view(room_model: dict, output_path: Path) -> str:
    export_room_view(room_model, output_path)
    html = output_path.read_text(encoding="utf-8")
    output_path.write_text(_inject_component_overlay(html, room_model), encoding="utf-8")
    return str(output_path)











