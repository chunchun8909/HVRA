from __future__ import annotations


def export_markdown(report: dict) -> str:
    selected = report["selected_strategy"]
    lines = [
        f"# HVRA Final Report: {report['case_id']}",
        "",
        f"Risk level: **{report['risk_level']}**",
        f"Composite room risk score: `{report['composite_room_risk_score']}`",
        "",
        "## Selected Strategy",
        "",
        f"- Strategy: {selected['strategy_name']}",
        f"- Strategy ID: `{selected['strategy_id']}`",
        "",
        "## Summary",
        "",
        report["summary"],
        "",
    ]
    return "\n".join(lines)

