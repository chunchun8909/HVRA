from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from html import escape
from pathlib import Path
import shutil

from utils.config import INPUT_DIR, OUTPUT_DIR


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}



def _display_value(value) -> str:
    if isinstance(value, bool) or value is None:
        return "" if value is None else ("yes" if value else "no")
    text = str(value)
    suffix = "%" if text.endswith("%") else ""
    number_text = text[:-1] if suffix else text
    try:
        number = Decimal(number_text)
    except Exception:
        return text
    if number == 0:
        return f"0{suffix}"
    exponent = Decimal("1e{}".format(number.adjusted() - 2))
    rounded = number.quantize(exponent, rounding=ROUND_HALF_UP)
    formatted = format(rounded.normalize(), "f")
    return f"{formatted}{suffix}"

def _first_image(paths: list[Path]) -> Path | None:
    for folder in paths:
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and path.name != ".gitkeep":
                return path
    return None


def _copy_report_image(source: Path, target_name: str) -> str | None:
    if not source.exists():
        return None
    target_dir = OUTPUT_DIR / "report_assets"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{target_name}{source.suffix.lower()}"
    if not target.exists() or source.stat().st_mtime > target.stat().st_mtime:
        shutil.copy2(source, target)
    return "/static-views/report_assets/" + target.name


def _perspective_image_src() -> str | None:
    source = _first_image([INPUT_DIR / "images" / "perspective_image"])
    if source:
        return _copy_report_image(source, "perspective_image")
    return None


def _image_src(report: dict) -> str | None:
    perspective = _perspective_image_src()
    if perspective:
        return perspective
    visual = report.get("visual_preview") or report.get("details", {}).get("visual_preview", {})
    screenshot = visual.get("static_screenshot_path")
    if screenshot:
        path = Path(screenshot)
        if not path.is_absolute():
            path = OUTPUT_DIR / path
        if path.exists() and OUTPUT_DIR in path.resolve().parents:
            return "/static-views/" + path.resolve().relative_to(OUTPUT_DIR.resolve()).as_posix()
    return None


def _target_walls(option: dict) -> list[str]:
    walls = []
    for targets in option.get("problem_targets", {}).values():
        for target in targets:
            wall_id = target.get("wall_id")
            if wall_id and wall_id not in walls:
                walls.append(wall_id)
    return walls


def _short_wall_label(wall_id: str) -> str:
    try:
        return "W" + str(int(wall_id.rsplit("_", 1)[1]) + 1).zfill(2)
    except (ValueError, IndexError):
        return wall_id


def _comparison_rows(option: dict) -> str:
    rows = []
    for item in option.get("numerical_comparison", [])[:6]:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('indicator', 'indicator')))}</td>"
            f"<td>{escape(_display_value(item.get('baseline', '')))}</td>"
            f"<td>{escape(_display_value(item.get('proposed', '')))}</td>"
            f"<td>{escape(_display_value(item.get('change', '')))}</td>"
            "</tr>"
        )
    if not rows:
        return '<tr><td colspan="4">benchmark comparison pending</td></tr>'
    return "".join(rows)



def _package_rows(package: dict) -> str:
    rows = []
    for item in package.get("before_after", [])[:6]:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('indicator', 'indicator')))}</td>"
            f"<td>{escape(_display_value(item.get('before', '')))} {escape(str(item.get('unit', '')))}</td>"
            f"<td>{escape(_display_value(item.get('after', '')))} {escape(str(item.get('unit', '')))}</td>"
            "</tr>"
        )
    return "".join(rows) or '<tr><td colspan="3">package comparison pending</td></tr>'


def _package_card(package: dict, index: int) -> str:
    components = ", ".join(package.get("visual_generation", {}).get("component_ids", []))
    strategies = ", ".join(package.get("selected_strategy_names", [])[:5])
    return f"""
      <section class="section optionCard" data-strategy-id="{escape(str(package.get('package_id') or f'package_{index}'))}" data-option-key="option{index}" data-option-alt="option_{index}">
        <div class="label">option {index}</div>
        <div class="value optionTitle">{escape(str(package.get('package_name', f'option {index}')))}</div>
        <div class="metaLine">benchmark: {escape(str(package.get('benchmark_status', 'pending')))} | confidence: {escape(str(package.get('confidence_level', 'screening')))}</div>
        <div class="value">{escape(str(package.get('user_label', 'review this package.')))}</div>
        <table>
          <thead><tr><th>indicator</th><th>before</th><th>after</th></tr></thead>
          <tbody>{_package_rows(package)}</tbody>
        </table>
        <div class="metaLine">strategies: {escape(str(strategies or 'pending'))}</div>
        <div class="metaLine">3D components: {escape(str(components or 'pending'))}</div>
      </section>
    """


def _selected_package_detail(package: dict | None) -> str:
    if not package:
        return ""
    components = ", ".join(package.get("visual_generation", {}).get("component_ids", []))
    strategies = ", ".join(package.get("selected_strategy_names", []))
    rows = _package_rows(package)
    return f"""
      <section class="section selectedOptionReport">
        <div class="label">selected option report</div>
        <div class="value optionTitle">option 1</div>
        <div class="value">{escape(str(package.get('package_name', 'selected package')))}</div>
        <div class="metaLine">benchmark: {escape(str(package.get('benchmark_status', 'pending')))} | confidence: {escape(str(package.get('confidence_level', 'screening')))}</div>
        <div class="value">{escape(str(package.get('user_label', 'ranked option for this room diagnosis')))}</div>
        <table>
          <thead><tr><th>indicator</th><th>before</th><th>after</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        <div class="metaLine">strategies: {escape(str(strategies or 'pending'))}</div>
        <div class="metaLine">3D components: {escape(str(components or 'pending'))}</div>
      </section>
    """

def _option_card(option: dict, index: int) -> str:
    strategy = option.get("strategy", {})
    benchmark = option.get("benchmark_result", {})
    confidence = option.get("confidence", {})
    walls = ", ".join(_short_wall_label(wall_id) for wall_id in _target_walls(option)) or "room-wide"
    name = strategy.get("strategy_name") or f"option {index}"
    recommendation = option.get("recommendation") or "review this option with the room diagnosis."
    return f"""
      <section class="section optionCard" data-strategy-id="{escape(str(strategy.get("strategy_id") or f"option_{index}"))}" data-option-key="option{index}" data-option-alt="option_{index}">
        <div class="label">option {index}</div>
        <div class="value optionTitle">{escape(str(name))}</div>
        <div class="metaLine">benchmark: {escape(str(benchmark.get('overall', 'pending')))} | confidence: {escape(str(confidence.get('level', 'pending')))} | target: {escape(walls)}</div>
        <div class="value">{escape(str(recommendation))}</div>
        <table>
          <thead><tr><th>indicator</th><th>before</th><th>after</th><th>change</th></tr></thead>
          <tbody>{_comparison_rows(option)}</tbody>
        </table>
      </section>
    """


def export_html(report: dict) -> str:
    selected = report.get("selected_package") or report.get("selected_strategy", {})
    details = report.get("details", {})
    risk_level = str(report.get("risk_level", "not available")).replace("_", " ")
    score = _display_value(report.get("composite_room_risk_score", "not available"))
    strategy_name = selected.get("package_name") or selected.get("strategy_name", "not selected")
    summary = report.get("summary", "No summary available.")
    visual_preview = report.get("visual_preview") or details.get("visual_preview", {})
    description = visual_preview.get("note", "")
    image_src = _image_src(report)
    packages = details.get("top_packages", [])[:3]
    validation_options = []
    selected_validation = details.get("selected_validation", {})
    selected_walls = ", ".join(_short_wall_label(wall_id) for wall_id in _target_walls(selected_validation)) or "see room view"
    selected_option_report = _selected_package_detail((details.get("top_packages") or [selected])[0] if (details.get("top_packages") or [selected]) else selected)
    option_cards = (
        "".join(_package_card(package, index) for index, package in enumerate(packages, start=1))
        if packages
        else "".join(_option_card(option, index) for index, option in enumerate(validation_options, start=1))
    )
    preview_src = visual_preview.get("src") or "/static-views/spatial/room_3d_component_view.html"
    image_block = (
        f'<img id="reportPreviewImage" src="{escape(image_src)}" alt="3D retrofit preview">'
        if image_src
        else f'<iframe id="reportPreviewFrame" src="{escape(str(preview_src))}" title="3D retrofit preview"></iframe>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>final report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400&family=DM+Sans:wght@400&display=swap" rel="stylesheet">
  <style>
    :root {{ --ink-primary: #0a0a0a; --ink-tertiary: #b0b0b0; --surface-primary: #ffffff; --surface-secondary: #f5f4f2; --border: rgba(0,0,0,0.08); --accent: #2d7a5f; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--surface-primary); color: var(--ink-primary); font: 400 13px "DM Sans", Arial, sans-serif; }}
    header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 46px; padding: 0 14px; border-bottom: 1px solid var(--border); font: 400 10.5px "DM Mono", monospace; letter-spacing: 0.10em; color: var(--ink-tertiary); }}
    .headerActions {{ display: flex; align-items: center; gap: 10px; }}
    button {{ border: 1px solid var(--border); background: var(--surface-primary); color: var(--ink-primary); padding: 7px 10px; font: 400 10px "DM Mono", monospace; letter-spacing: 0.08em; cursor: pointer; }}
    button:hover {{ border-color: rgba(0,0,0,0.28); }}
    main {{ display: grid; grid-template-columns: minmax(0, 1fr) 390px; gap: 14px; height: calc(100vh - 46px); padding: 14px; }}
    .imagePane {{ min-height: 0; background: var(--surface-secondary); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; overflow: hidden; }}
    img, iframe {{ display: block; width: 100%; height: 100%; object-fit: contain; border: 0; }}
    .placeholder {{ color: var(--ink-tertiary); font: 400 10px "DM Mono", monospace; }}
    aside {{ min-height: 0; overflow: auto; border-left: 1px solid var(--border); padding-left: 14px; }}
    .section {{ border-bottom: 1px solid var(--border); padding: 12px 0; }}
    .label, th {{ color: var(--ink-tertiary); font: 400 10px "DM Mono", monospace; text-align: left; }}
    .value, td {{ margin-top: 5px; font: 400 13px "DM Sans", Arial, sans-serif; color: var(--ink-primary); }}
    .optionTitle {{ color: var(--accent); }}
    .metaLine {{ margin: 6px 0 9px; color: var(--ink-tertiary); font: 400 10px "DM Mono", monospace; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 9px; }}
    th, td {{ border-top: 1px solid var(--border); padding: 6px 4px; vertical-align: top; }}
    @media (max-width: 860px) {{ main {{ grid-template-columns: 1fr; height: auto; }} .imagePane {{ min-height: 52vh; }} aside {{ border-left: 0; padding-left: 0; }} }}
    @media print {{
      header {{ position: static; }}
      button {{ display: none; }}
      main {{ display: block; height: auto; padding: 10mm; }}
      .imagePane {{ height: 58vh; page-break-inside: avoid; margin-bottom: 8mm; }}
      aside {{ border-left: 0; padding-left: 0; overflow: visible; }}
      .section {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <header>
    <span>final report</span>
    <div class="headerActions">
      <span>{escape(str(report.get("case_id", "case")))}</span>
      <button id="downloadPdf" type="button">download PDF</button>
    </div>
  </header>
  <main>
    <section class="imagePane">{image_block}</section>
    <aside>
      <section class="section">
        <div class="label">report image</div><div class="value" id="reportImageNote">Using the saved component-view image for this option when available; otherwise using the default perspective image.</div></section><section class="section"><div class="label">risk</div>
        <div class="value">{escape(risk_level)}</div>
      </section>
      <section class="section">
        <div class="label">score</div>
        <div class="value">{escape(str(score))}</div>
      </section>
      <section class="section">
        <div class="label">selected package</div>
        <div class="value">{escape(str(strategy_name))}</div>
        <div class="metaLine">target walls: {escape(selected_walls)}</div>
      </section>
      {selected_option_report}
      <section class="section">
        <div class="label">summary</div>
        <div class="value">{escape(str(summary))}</div>
      </section>
      {option_cards or '<section class="section"><div class="label">upgrade options</div><div class="value">validation options pending</div></section>'}
      <section class="section">
        <div class="label">visual note</div>
        <div class="value">{escape(str(description or "Use save image in the component view to update this report visual for the selected option."))}</div>
      </section>
    </aside>
  </main>
  <script>
    document.getElementById("downloadPdf")?.addEventListener("click", () => window.print());
    const params = new URLSearchParams(window.location.search);
    const selectedStrategyId = params.get("strategy_id") || params.get("package_id") || "";
    const normalize = (value) => String(value || "").replace(/_/g, "").toLowerCase();
const optionCards = Array.from(document.querySelectorAll(".optionCard[data-strategy-id]"));
    if (selectedStrategyId && optionCards.length) {{
      let matched = false;
      optionCards.forEach((card) => {{
        const active = card.dataset.strategyId === selectedStrategyId
          || normalize(card.dataset.optionKey) === normalize(selectedStrategyId)
          || normalize(card.dataset.optionAlt) === normalize(selectedStrategyId)
          || selectedStrategyId.includes(card.dataset.strategyId || "__no_match__");
        card.hidden = !active;
        matched = matched || active;
      }});
      if (!matched) optionCards.forEach((card) => card.hidden = true);
    }}
    try {{
      const optionFromSelection = () => {{
        const compact = normalize(selectedStrategyId);
        if (/^option[0-9]+$/.test(compact)) return compact;
        const activeCard = optionCards.find((card) => !card.hidden);
        return normalize(activeCard?.dataset.optionKey || "option1") || "option1";
      }};
      const optionKey = optionFromSelection();
      const loadSavedPreview = () => {{
        const savedPreview = localStorage.getItem("hvra_report_component_preview_" + optionKey);
        if (!savedPreview) {{ const note = document.getElementById("reportImageNote"); if (note) note.textContent = "No saved 3D screenshot found yet for " + optionKey + ". Use save image in the component view, then return to report."; return false; }}
        const imagePane = document.querySelector(".imagePane");
        const existing = document.getElementById("reportPreviewImage");
        const img = existing || document.createElement("img");
        img.id = "reportPreviewImage";
        img.alt = "saved 3D room preview for " + optionKey;
        img.src = savedPreview;
        if (!existing && imagePane) {{
          imagePane.innerHTML = "";
          imagePane.appendChild(img);
        }}
        const note = document.getElementById("reportImageNote");
        if (note) note.textContent = "Using the saved 3D room/component screenshot for " + optionKey + ".";
        return true;
      }};
      if (!loadSavedPreview()) {{
        let attempts = 0;
        const timer = setInterval(() => {{
          attempts += 1;
          if (loadSavedPreview() || attempts > 20) clearInterval(timer);
        }}, 250);
      }}
    }} catch (error) {{
      console.warn("Saved report preview unavailable", error);
    }}
  </script>
</body>
</html>
"""
