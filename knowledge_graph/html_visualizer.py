from __future__ import annotations

import json
from pathlib import Path

from utils.config import INTERMEDIATE_DIR, OUTPUT_DIR
from utils.file_io import read_json, write_json


KG_OUTPUT_DIR = OUTPUT_DIR / "kg"


def _load_optional(path: Path) -> dict:
    return read_json(path) if path.exists() else {}


def _add_node(nodes: dict[str, dict], node_id: str | None, label: str, group: str, **props) -> None:
    if not node_id:
        return
    existing = nodes.get(node_id, {})
    nodes[node_id] = {
        "id": node_id,
        "label": label,
        "group": group,
        **existing,
        **{key: value for key, value in props.items() if value is not None},
    }


def _add_edge(edges: list[dict], source: str | None, target: str | None, label: str) -> None:
    if source and target:
        edges.append({"source": source, "target": target, "label": label})


def build_kg_view_data() -> dict:
    spatial = _load_optional(INTERMEDIATE_DIR / "spatial_index_with_overrides.json") or _load_optional(
        INTERMEDIATE_DIR / "spatial_index.json"
    )
    diagnosis = _load_optional(INTERMEDIATE_DIR / "diagnosis_result.json")
    problem_map = _load_optional(INTERMEDIATE_DIR / "problem_map.json")
    validation_options = _load_optional(INTERMEDIATE_DIR / "retrofit_validation_options.json")
    validation = _load_optional(INTERMEDIATE_DIR / "retrofit_validation.json")
    user_selection = _load_optional(INTERMEDIATE_DIR / "user_selection.json")
    user_decision = _load_optional(INTERMEDIATE_DIR / "user_decision.json")

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    building = spatial.get("building", {})
    room = spatial.get("room", {})
    _add_node(nodes, building.get("id"), "building", "building")
    _add_node(
        nodes,
        room.get("id"),
        f"room | {room.get('room_type', 'room')}",
        "room",
        area_m2=room.get("area_m2"),
        height_m=room.get("height_m"),
        risk_level=diagnosis.get("risk_level"),
    )
    _add_edge(edges, building.get("id"), room.get("id"), "has room")

    for index, wall in enumerate(spatial.get("walls", []), start=1):
        label = f"wall {index:02d} | {wall.get('orientation', '')}"
        _add_node(
            nodes,
            wall.get("id"),
            label,
            "wall",
            area_m2=wall.get("estimated_area_m2"),
            external=wall.get("is_external"),
        )
        _add_edge(edges, room.get("id"), wall.get("id"), "has wall")

    component_groups = [
        ("windows", "window", "has window"),
        ("doors", "door", "has door"),
        ("furniture", "furniture", "has furniture"),
    ]
    for group_name, group, relation in component_groups:
        for component in spatial.get(group_name, []):
            label = f"{group} | {component.get('estimated_area_m2', '?')} m2"
            _add_node(
                nodes,
                component.get("id"),
                label,
                group,
                confidence=component.get("confidence"),
                area_m2=component.get("estimated_area_m2"),
            )
            _add_edge(edges, component.get("wall_id") or room.get("id"), component.get("id"), relation)

    for problem in problem_map.get("problems", []):
        _add_node(
            nodes,
            problem.get("id"),
            str(problem.get("problem_type", "problem")).replace("_", " "),
            "problem",
            severity=problem.get("severity"),
            score=problem.get("score"),
        )
        _add_edge(edges, room.get("id"), problem.get("id"), "has problem")
        for target in problem.get("spatial_targets", []):
            _add_edge(edges, target.get("wall_id") or target.get("surface_id"), problem.get("id"), "contributes")

    baseline_id = f"{room.get('id', 'ROOM')}_BASELINE"
    if diagnosis:
        _add_node(
            nodes,
            baseline_id,
            "room risk",
            "risk",
            risk_level=diagnosis.get("risk_level"),
            room_score=diagnosis.get("composite_room_risk_score"),
            final_score=diagnosis.get("composite_risk_score_with_urban_context"),
        )
        _add_edge(edges, room.get("id"), baseline_id, "has risk")

    checkpoint_id = "08_strategy_validation"
    if validation_options:
        _add_node(
            nodes,
            checkpoint_id,
            "upgrade review",
            "review",
            status=user_decision.get("action") or "waiting",
            recommended=validation_options.get("recommended_option_id"),
        )
        _add_edge(edges, room.get("id"), checkpoint_id, "has review")

    for option in validation_options.get("validated_options", []):
        strategy = option.get("strategy", {})
        strategy_id = strategy.get("strategy_id")
        validation_id = f"{strategy_id}_VALIDATION" if strategy_id else None
        _add_node(
            nodes,
            strategy_id,
            strategy.get("strategy_name", strategy_id),
            "fix",
            rank=option.get("validation_rank"),
        )
        _add_node(
            nodes,
            validation_id,
            f"{str(option.get('benchmark_result', {}).get('overall', 'review')).replace('_', ' ')}",
            "review",
            benchmark_status=option.get("benchmark_result", {}).get("overall"),
            confidence=option.get("confidence", {}).get("level"),
            proposed_score=option.get("proposed", {}).get("composite_room_risk_score"),
            strategy_id=strategy_id,
        )
        _add_edge(edges, checkpoint_id, strategy_id, "reviews")
        _add_edge(edges, strategy_id, validation_id, "has result")
        for problem_id in option.get("problem_targets", {}).keys():
            _add_edge(edges, strategy_id, problem_id, "fixes")

    selected_strategy = user_selection.get("selected_strategy", {})
    if selected_strategy:
        selection_id = user_selection.get("id", "USER_SELECTION")
        _add_node(nodes, selection_id, "selected fix", "selection", mode=str(user_selection.get("selection_mode", "")).replace("_", " "))
        _add_edge(edges, selection_id, selected_strategy.get("strategy_id"), "selects")
        _add_edge(edges, checkpoint_id, selection_id, "creates")
        if validation:
            _add_edge(edges, selected_strategy.get("strategy_id"), f"{selected_strategy.get('strategy_id')}_VALIDATION", "selected result")

    data = {
        "nodes": list(nodes.values()),
        "edges": edges,
        "meta": {
            "source": "canonical_json",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "outputs": {
                "html": "data/output/kg/kg_view.html",
                "json": "data/output/kg/kg_view_data.json",
            },
        },
    }
    return data


def export_kg_view(output_path: Path = KG_OUTPUT_DIR / "kg_view.html") -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_kg_view_data()
    write_json(output_path.parent / "kg_view_data.json", data)
    html_data = json.dumps(data, ensure_ascii=False)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>links view</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400&family=DM+Sans:wght@400&display=swap" rel="stylesheet">
  <style>
    body {{ margin: 0; font-family: "DM Sans", Arial, sans-serif; background: #f5f4f2; color: #0a0a0a; overflow: hidden; }}
    header {{ height: 46px; display: flex; align-items: center; justify-content: space-between; padding: 0 14px; background: #fff; border-bottom: 1px solid rgba(0,0,0,0.08); font: 400 10.5px "DM Mono", monospace; letter-spacing: 0.10em; color: #b0b0b0; }}
    canvas {{ display: block; width: 100vw; height: calc(100vh - 46px); cursor: grab; }}
    canvas:active {{ cursor: grabbing; }}
    #panel {{ position: fixed; top: 60px; right: 14px; width: 300px; max-height: calc(100vh - 82px); overflow: auto; }}
    #filters {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
    label {{ font: 400 13px "DM Sans", Arial, sans-serif; display: inline-flex; gap: 4px; align-items: center; color: #0a0a0a; }}
    #details {{ font: 400 13px "DM Sans", Arial, sans-serif; white-space: pre-wrap; overflow-wrap: anywhere; color: #0a0a0a; }}
    button {{ border: 1px solid rgba(0,0,0,0.14); background: #fff; padding: 4px 8px; cursor: pointer; font: 400 10px "DM Mono", monospace; color: #b0b0b0; }}
    .section {{ width: 100%; margin-bottom: 8px; padding: 10px 12px; background: rgba(255,255,255,0.95); border: 1px solid rgba(0,0,0,0.08); }}
    .section.isCollapsed {{ width: 112px; padding: 7px 10px; background: rgba(255,255,255,0.95); border-color: rgba(0,0,0,0.08); }}
    .sectionHeader {{ display: flex; align-items: center; justify-content: space-between; width: 100%; border: 0; background: transparent; padding: 0 0 8px; font: 400 10.5px "DM Mono", monospace; letter-spacing: 0.10em; color: #b0b0b0; }}
    .section.isCollapsed .sectionHeader {{ width: 100%; min-height: 24px; gap: 8px; padding: 0; border: 0; background: transparent; }}
    .section.isCollapsed .sectionHeader span:first-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .sectionBody[hidden] {{ display: none; }}
  </style>
</head>
<body>
  <header>
    <span>links view</span>
    <span id="meta"></span>
  </header>
  <canvas id="kg"></canvas>
  <aside id="panel">
    <section class="section">
      <button class="sectionHeader" data-toggle="filterPanel"><span>legend</span><span>&#9662;</span></button>
      <div id="filterPanel" class="sectionBody">
        <div id="filters"></div>
        <button id="reset">reset layout</button>
      </div>
    </section>
    <section class="section">
      <button class="sectionHeader" data-toggle="detailPanel"><span>selected item</span><span>&#9662;</span></button>
      <div id="detailPanel" class="sectionBody"><div id="details">click a node.</div></div>
    </section>
  </aside>
  <script>
    const graph = {html_data};
    const canvas = document.getElementById("kg");
    const ctx = canvas.getContext("2d");
    const meta = document.getElementById("meta");
    const details = document.getElementById("details");
    const filters = document.getElementById("filters");
    const selectedStrategyId = new URLSearchParams(window.location.search).get("strategy_id") || "";
    meta.textContent = selectedStrategyId ? `${{graph.nodes.length}} items | ${{graph.edges.length}} links | option focus` : `${{graph.nodes.length}} items | ${{graph.edges.length}} links`;

    const palette = {{
      building: "#59656f",
      room: "#3d6f8e",
      wall: "#a56b43",
      window: "#5a9bcf",
      door: "#8766a8",
      furniture: "#7f8a5c",
      problem: "#b84747",
      risk: "#c37b2d",
      review: "#5d6fb7",
      fix: "#2f8062",
      selection: "#4b8063"
    }};
    const visibleGroups = Object.fromEntries([...new Set(graph.nodes.map(n => n.group))].map(g => [g, true]));
    const nodeById = Object.fromEntries(graph.nodes.map((node, index) => {{
      const angle = (index / Math.max(1, graph.nodes.length)) * Math.PI * 2;
      node.x = Math.cos(angle) * 260;
      node.y = Math.sin(angle) * 190;
      node.vx = 0;
      node.vy = 0;
      return [node.id, node];
    }}));
    const focusedIds = new Set();
    if (selectedStrategyId) {{
      focusedIds.add(selectedStrategyId);
      focusedIds.add(`${{selectedStrategyId}}_VALIDATION`);
      graph.edges.forEach(edge => {{
        if (edge.source === selectedStrategyId || edge.target === selectedStrategyId || edge.source === `${{selectedStrategyId}}_VALIDATION` || edge.target === `${{selectedStrategyId}}_VALIDATION`) {{
          focusedIds.add(edge.source);
          focusedIds.add(edge.target);
        }}
      }});
    }}
    function focusAlpha(node) {{
      if (!selectedStrategyId || focusedIds.has(node.id) || ["building", "room", "wall", "window", "risk"].includes(node.group)) return 1;
      return 0.22;
    }}
    const view = {{ x: 0, y: 0, zoom: 1 }};
    let selected = null;
    let drag = null;
    let panning = false;
    let lastPointer = {{ x: 0, y: 0 }};

    function plainKey(key) {{
      return String(key).replaceAll("_", " ");
    }}

    function plainValue(value) {{
      if (value === null || value === undefined) return "";
      if (typeof value === "boolean") return value ? "yes" : "no";
      return String(value).replaceAll("_", " ");
    }}

    function selectedDetails(node) {{
      if (!node) return "click a node.";
      const hidden = new Set(["id", "x", "y", "vx", "vy"]);
      const lines = [`${{node.label}}`, `type: ${{plainValue(node.group)}}`];
      Object.entries(node).forEach(([key, value]) => {{
        if (hidden.has(key) || key === "label" || key === "group") return;
        lines.push(`${{plainKey(key)}}: ${{plainValue(value)}}`);
      }});
      return lines.join("\\n");
    }}

    function resize() {{
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      draw();
    }}

    function screen(node) {{
      return [
        canvas.width / 2 + view.x * devicePixelRatio + node.x * view.zoom * devicePixelRatio,
        canvas.height / 2 + view.y * devicePixelRatio + node.y * view.zoom * devicePixelRatio
      ];
    }}

    function graphPoint(event) {{
      const rect = canvas.getBoundingClientRect();
      const x = (event.clientX - rect.left - canvas.clientWidth / 2 - view.x) / view.zoom;
      const y = (event.clientY - rect.top - canvas.clientHeight / 2 - view.y) / view.zoom;
      return {{ x, y }};
    }}

    function clampNode(node) {{
      const margin = 70;
      const maxX = Math.max(120, canvas.width / devicePixelRatio / view.zoom / 2 - margin);
      const maxY = Math.max(90, canvas.height / devicePixelRatio / view.zoom / 2 - margin);
      node.x = Math.max(-maxX, Math.min(maxX, node.x));
      node.y = Math.max(-maxY, Math.min(maxY, node.y));
      if (Math.abs(node.x) >= maxX) node.vx *= -0.25;
      if (Math.abs(node.y) >= maxY) node.vy *= -0.25;
    }}

    function tick() {{
      const nodes = graph.nodes.filter(n => visibleGroups[n.group]);
      graph.edges.forEach(edge => {{
        const a = nodeById[edge.source];
        const b = nodeById[edge.target];
        if (!a || !b || !visibleGroups[a.group] || !visibleGroups[b.group]) return;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const force = Math.max(-0.04, Math.min(0.04, (distance - 145) * 0.00025));
        a.vx += dx * force;
        a.vy += dy * force;
        b.vx -= dx * force;
        b.vy -= dy * force;
      }});
      for (let i = 0; i < nodes.length; i++) {{
        for (let j = i + 1; j < nodes.length; j++) {{
          const a = nodes[i];
          const b = nodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const distance = Math.max(1, Math.hypot(dx, dy));
          const force = Math.min(0.035, 18 / (distance * distance));
          a.vx -= dx * force;
          a.vy -= dy * force;
          b.vx += dx * force;
          b.vy += dy * force;
        }}
      }}
      nodes.forEach(node => {{
        if (node === drag) return;
        node.vx = Math.max(-6, Math.min(6, node.vx * 0.82));
        node.vy = Math.max(-6, Math.min(6, node.vy * 0.82));
        node.x += node.vx;
        node.y += node.vy;
        clampNode(node);
      }});
    }}

    function draw() {{
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.font = `${{10 * devicePixelRatio}}px "DM Mono", monospace`;
      graph.edges.forEach(edge => {{
        const a = nodeById[edge.source];
        const b = nodeById[edge.target];
        if (!a || !b || !visibleGroups[a.group] || !visibleGroups[b.group]) return;
        const [x1, y1] = screen(a);
        const [x2, y2] = screen(b);
        const edgeFocused = !selectedStrategyId || focusedIds.has(edge.source) || focusedIds.has(edge.target);
        ctx.globalAlpha = edgeFocused ? 1 : 0.18;
        ctx.strokeStyle = "#b7afa5";
        ctx.lineWidth = devicePixelRatio;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
        ctx.fillStyle = "#6f675f";
        ctx.fillText(edge.label, (x1 + x2) / 2 + 4, (y1 + y2) / 2 - 4);
        ctx.globalAlpha = 1;
      }});
      graph.nodes.forEach(node => {{
        if (!visibleGroups[node.group]) return;
        const [x, y] = screen(node);
        ctx.beginPath();
        ctx.arc(x, y, node === selected ? 12 * devicePixelRatio : 9 * devicePixelRatio, 0, Math.PI * 2);
        ctx.fillStyle = palette[node.group] || "#777";
        ctx.fill();
        ctx.strokeStyle = node === selected ? "#111" : "#fff";
        ctx.lineWidth = 2 * devicePixelRatio;
        ctx.stroke();
        ctx.fillStyle = "#222";
        ctx.fillText(node.label, x + 12 * devicePixelRatio, y + 4 * devicePixelRatio);
        ctx.globalAlpha = 1;
      }});
    }}

    function renderFilters() {{
      filters.innerHTML = "";
      Object.keys(visibleGroups).sort().forEach(group => {{
        const item = document.createElement("label");
        item.innerHTML = `<input type="checkbox" checked> ${{group}}`;
        item.querySelector("input").addEventListener("change", event => {{
          visibleGroups[group] = event.target.checked;
          draw();
        }});
        filters.appendChild(item);
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

    function hitTest(event) {{
      const rect = canvas.getBoundingClientRect();
      const x = (event.clientX - rect.left) * devicePixelRatio;
      const y = (event.clientY - rect.top) * devicePixelRatio;
      return graph.nodes.find(node => {{
        if (!visibleGroups[node.group]) return false;
        const [nx, ny] = screen(node);
        return Math.hypot(nx - x, ny - y) < 14 * devicePixelRatio;
      }});
    }}

    canvas.addEventListener("pointerdown", event => {{
      drag = hitTest(event);
      panning = !drag || event.shiftKey;
      lastPointer = {{ x: event.clientX, y: event.clientY }};
      selected = drag || selected;
      details.textContent = selectedDetails(selected);
      draw();
    }});
    canvas.addEventListener("pointermove", event => {{
      if (panning) {{
        view.x += event.clientX - lastPointer.x;
        view.y += event.clientY - lastPointer.y;
        lastPointer = {{ x: event.clientX, y: event.clientY }};
        draw();
        return;
      }}
      if (!drag) return;
      const point = graphPoint(event);
      drag.x = point.x;
      drag.y = point.y;
      draw();
    }});
    canvas.addEventListener("pointerup", () => {{
      drag = null;
      panning = false;
    }});
    canvas.addEventListener("pointerleave", () => {{
      drag = null;
      panning = false;
    }});
    canvas.addEventListener("wheel", event => {{
      event.preventDefault();
      const previousZoom = view.zoom;
      const nextZoom = Math.max(0.25, Math.min(3.5, previousZoom * Math.exp(-event.deltaY * 0.001)));
      const rect = canvas.getBoundingClientRect();
      const mx = event.clientX - rect.left - canvas.clientWidth / 2;
      const my = event.clientY - rect.top - canvas.clientHeight / 2;
      view.x = mx - (mx - view.x) * (nextZoom / previousZoom);
      view.y = my - (my - view.y) * (nextZoom / previousZoom);
      view.zoom = nextZoom;
      draw();
    }}, {{ passive: false }});
    document.getElementById("reset").addEventListener("click", () => {{
      view.x = 0;
      view.y = 0;
      view.zoom = 1;
      graph.nodes.forEach((node, index) => {{
        const angle = (index / Math.max(1, graph.nodes.length)) * Math.PI * 2;
        node.x = Math.cos(angle) * 260;
        node.y = Math.sin(angle) * 190;
        node.vx = 0;
        node.vy = 0;
      }});
      draw();
    }});

    renderFilters();
    resize();
    addEventListener("resize", resize);
    setInterval(() => {{
      tick();
      draw();
    }}, 30);
  </script>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


