from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from html import escape



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

def _display_text_numbers(value) -> str:
    import re

    text = str(value or "")
    def format_match(match):
        number = Decimal(match.group(1))
        if number == 0:
            return "0"
        exponent = Decimal("1e{}".format(number.adjusted() - 2))
        rounded = number.quantize(exponent, rounding=ROUND_HALF_UP)
        return format(rounded.normalize(), "f")
    return re.sub(r"(?<!\d)(\d+\.\d+)(?!\d)", format_match, text)
def _status_class(status: str | None) -> str:
    value = str(status or "pending").lower()
    if value == "pass":
        return "pass"
    if "partial" in value:
        return "warn"
    if value == "fail":
        return "fail"
    return "pending"


def _comparison_rows(option: dict) -> str:
    rows = []
    for item in option.get("numerical_comparison", []):
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('indicator', 'indicator')))}</td>"
            f"<td>{escape(_display_value(item.get('baseline', '')))} {escape(str(item.get('unit', '')))}</td>"
            f"<td>{escape(_display_value(item.get('proposed', '')))} {escape(str(item.get('unit', '')))}</td>"
            f"<td>{escape(_display_value(item.get('change', '')))}</td>"
            "</tr>"
        )
    return "".join(rows) or '<tr><td colspan="4">comparison pending</td></tr>'


def _benchmark_rows(option: dict) -> str:
    rows = []
    checks = option.get("benchmark_result", {}).get("checks", {})
    for check in checks.values():
        status = check.get("status")
        rows.append(
            "<tr>"
            f"<td>{escape(str(check.get('indicator', 'benchmark')))}</td>"
            f"<td><span class=\"badge {_status_class(status)}\">{escape(str(status or 'pending'))}</span></td>"
            f"<td>{escape(_display_value(check.get('value', check.get('proposed_hours', ''))))}</td>"
            f"<td>{escape(_display_text_numbers(check.get('pass_threshold', '')))}</td>"
            "</tr>"
        )
    return "".join(rows) or '<tr><td colspan="4">benchmark checks pending</td></tr>'


def _option_section(option: dict, index: int) -> str:
    strategy = option.get("strategy", {})
    name = strategy.get("strategy_name") or f"option {index}"
    status = option.get("benchmark_result", {}).get("overall")
    confidence = option.get("confidence", {}).get("level")
    return f"""
      <section class="option" id="option-{index}" data-strategy-id="{escape(str(strategy.get("strategy_id") or f"option_{index}"))}">
        <header class="optionHeader">
          <span>option {index}</span>
          <span>{escape(str(status or 'pending'))} | {escape(str(confidence or 'confidence pending'))}</span>
        </header>
        <h2>{escape(str(name))}</h2>
        <p>{escape(str(option.get('expected_retrofit_impact', {}).get('plain_language_summary') or option.get('recommendation') or 'review this option against the baseline.'))}</p>
        <div class="tableTitle">before and after</div>
        <table>
          <thead><tr><th>indicator</th><th>original</th><th>with upgrade</th><th>change</th></tr></thead>
          <tbody>{_comparison_rows(option)}</tbody>
        </table>
        <div class="tableTitle">benchmark check</div>
        <table>
          <thead><tr><th>check</th><th>result</th><th>value</th><th>pass target</th></tr></thead>
          <tbody>{_benchmark_rows(option)}</tbody>
        </table>
      </section>
    """


def export_validation_html(validation_options: dict) -> str:
    baseline = validation_options.get("baseline", {})
    options = validation_options.get("validated_options", [])[:3]
    option_sections = "".join(_option_section(option, index) for index, option in enumerate(options, start=1))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>validation view</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400&family=DM+Sans:wght@400&display=swap" rel="stylesheet">
  <style>
    :root {{ --ink-primary: #0a0a0a; --ink-tertiary: #8a8a8a; --surface-primary: #ffffff; --surface-secondary: #f5f4f2; --border: rgba(0,0,0,0.08); --pass: #166534; --warn: #8a5a00; --fail: #9f1d1d; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--surface-primary); color: var(--ink-primary); font: 400 13px "DM Sans", Arial, sans-serif; }}
    body > header {{ align-items: center; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; min-height: 46px; padding: 0 14px; font: 400 10.5px "DM Mono", monospace; letter-spacing: 0.10em; color: var(--ink-tertiary); }}
    main {{ height: calc(100vh - 46px); overflow: auto; padding: 14px; }}
    .baseline {{ display: grid; gap: 8px; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 14px; }}
    .metric, .option {{ border: 1px solid var(--border); background: var(--surface-secondary); padding: 12px; }}
    .label, th, .tableTitle {{ color: var(--ink-tertiary); font: 400 10px "DM Mono", monospace; text-align: left; }}
    .value, td, p, h2 {{ color: var(--ink-primary); font: 400 13px "DM Sans", Arial, sans-serif; }}
    h2 {{ margin: 8px 0; }}
    p {{ margin: 0 0 12px; line-height: 1.55; }}
    .option {{ margin-bottom: 14px; }}
    .optionHeader {{ display: flex; justify-content: space-between; gap: 12px; color: var(--ink-tertiary); font: 400 10.5px "DM Mono", monospace; letter-spacing: 0.10em; }}
    table {{ border-collapse: collapse; margin: 8px 0 14px; width: 100%; }}
    th, td {{ border-top: 1px solid var(--border); padding: 7px 5px; vertical-align: top; }}
    .badge {{ font: 400 10px "DM Mono", monospace; }}
    .pass {{ color: var(--pass); }} .warn {{ color: var(--warn); }} .fail {{ color: var(--fail); }} .pending {{ color: var(--ink-tertiary); }}
    @media (max-width: 900px) {{ .baseline {{ grid-template-columns: 1fr 1fr; }} }}
  </style>
</head>
<body>
  <header><span>validation</span><span>before / after benchmark</span></header>
  <main>
    <section class="baseline">
      <div class="metric"><div class="label">original risk</div><div class="value">{escape(str(baseline.get('risk_level', 'pending')))}</div></div>
      <div class="metric"><div class="label">operative temp</div><div class="value">{escape(_display_value(baseline.get('peak_indoor_operative_temperature_c', '')))} C</div></div>
      <div class="metric"><div class="label">overheating</div><div class="value">{escape(_display_value(baseline.get('overheating_hours', '')))} h</div></div>
      <div class="metric"><div class="label">room score</div><div class="value">{escape(_display_value(baseline.get('composite_room_risk_score', '')))}</div></div>
    </section>
    {option_sections or '<section class="option"><h2>validation pending</h2><p>Run retrofit validation to populate before/after comparison.</p></section>'}
  </main>
  <script>
    const selectedStrategyId = new URLSearchParams(window.location.search).get("strategy_id") || "";
    const options = Array.from(document.querySelectorAll(".option[data-strategy-id]"));
    if (selectedStrategyId && options.length) {{
      let matched = false;
      options.forEach((option) => {{
        const active = option.dataset.strategyId === selectedStrategyId;
        option.hidden = !active;
        matched = matched || active;
      }});
      if (!matched) options.forEach((option) => option.hidden = false);
    }}
  </script>
</body>
</html>
"""
















