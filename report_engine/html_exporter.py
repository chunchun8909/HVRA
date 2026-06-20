from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from html import escape
from pathlib import Path

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


def _image_src(report: dict) -> str | None:
    gemini_result = report.get("details", {}).get("gemini_result", {})
    image_path = gemini_result.get("image_path")
    if image_path:
        path = Path(image_path)
        if not path.is_absolute():
            path = OUTPUT_DIR / path
        if path.exists() and OUTPUT_DIR in path.resolve().parents:
            return "/static-views/" + path.resolve().relative_to(OUTPUT_DIR.resolve()).as_posix()

    generated = _first_image([OUTPUT_DIR / "generated_images"])
    if generated:
        return "/static-views/" + generated.resolve().relative_to(OUTPUT_DIR.resolve()).as_posix()

    reference = _first_image([INPUT_DIR / "images" / "perspective_image"])
    if reference:
        return "/input-assets/" + reference.resolve().relative_to(INPUT_DIR.resolve()).as_posix()

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


def _option_card(option: dict, index: int) -> str:
    strategy = option.get("strategy", {})
    benchmark = option.get("benchmark_result", {})
    confidence = option.get("confidence", {})
    walls = ", ".join(_short_wall_label(wall_id) for wall_id in _target_walls(option)) or "room-wide"
    name = strategy.get("strategy_name") or f"option {index}"
    recommendation = option.get("recommendation") or "review this option with the room diagnosis."
    return f"""
      <section class="section optionCard" data-strategy-id="{escape(str(strategy.get("strategy_id") or f"option_{index}"))}">
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
    selected = report.get("selected_strategy", {})
    details = report.get("details", {})
    risk_level = str(report.get("risk_level", "not available")).replace("_", " ")
    score = _display_value(report.get("composite_room_risk_score", "not available"))
    strategy_name = selected.get("strategy_name", "not selected")
    summary = report.get("summary", "No summary available.")
    description = details.get("gemini_result", {}).get("description", "")
    image_src = _image_src(report)
    validation_options = details.get("retrofit_validation_options", {}).get("validated_options", [])[:3]
    selected_validation = details.get("retrofit_validation", {}).get("validation", {}) or details.get("retrofit_validation", {})
    selected_walls = ", ".join(_short_wall_label(wall_id) for wall_id in _target_walls(selected_validation)) or "see room view"
    option_cards = "".join(_option_card(option, index) for index, option in enumerate(validation_options, start=1))
    image_block = (
        f'<img src="{escape(image_src)}" alt="generated perspective">'
        if image_src
        else '<div class="placeholder">generated perspective pending</div>'
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
    header {{ display: flex; align-items: center; justify-content: space-between; min-height: 46px; padding: 0 14px; border-bottom: 1px solid var(--border); font: 400 10.5px "DM Mono", monospace; letter-spacing: 0.10em; color: var(--ink-tertiary); }}
    main {{ display: grid; grid-template-columns: minmax(0, 1fr) 390px; gap: 14px; height: calc(100vh - 46px); padding: 14px; }}
    .imagePane {{ min-height: 0; background: var(--surface-secondary); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; overflow: hidden; }}
    img {{ display: block; width: 100%; height: 100%; object-fit: contain; }}
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
  </style>
</head>
<body>
  <header>
    <span>final report</span>
    <span>{escape(str(report.get("case_id", "case")))}</span>
  </header>
  <main>
    <section class="imagePane">{image_block}</section>
    <aside>
      <section class="section">
        <div class="label">risk</div>
        <div class="value">{escape(risk_level)}</div>
      </section>
      <section class="section">
        <div class="label">score</div>
        <div class="value">{escape(str(score))}</div>
      </section>
      <section class="section">
        <div class="label">selected fix</div>
        <div class="value">{escape(str(strategy_name))}</div>
        <div class="metaLine">target walls: {escape(selected_walls)}</div>
      </section>
      <section class="section">
        <div class="label">summary</div>
        <div class="value">{escape(str(summary))}</div>
      </section>
      {option_cards or '<section class="section"><div class="label">upgrade options</div><div class="value">validation options pending</div></section>'}
      <section class="section">
        <div class="label">image note</div>
        <div class="value">{escape(str(description or "No generated image note yet."))}</div>
      </section>
    </aside>
  </main>
  <script>
    const selectedStrategyId = new URLSearchParams(window.location.search).get("strategy_id") || "";
    const optionCards = Array.from(document.querySelectorAll(".optionCard[data-strategy-id]"));
    if (selectedStrategyId && optionCards.length) {{
      let matched = false;
      optionCards.forEach((card) => {{
        const active = card.dataset.strategyId === selectedStrategyId;
        card.hidden = !active;
        matched = matched || active;
      }});
      if (!matched) optionCards.forEach((card) => card.hidden = false);
    }}
  </script>
</body>
</html>
"""










