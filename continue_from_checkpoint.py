from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from checkpoint_engine import apply_checkpoint_decision, run_llm_checkpoint_decision
from gemini_engine.gemini_prompt_builder import build_visual_prompt
from gemini_engine.image_generator import generate_visual
from knowledge_graph.graph_writer import write_checkpoint_graph, write_decision_graph
from llm_agent.review_loop import run_review_loop
from report_engine.html_exporter import export_html
from report_engine.markdown_exporter import export_markdown
from report_engine.report_compiler import compile_report
from scripts.build_phase3_strategy_packages import build_packages
from validation_engine.html_exporter import export_validation_html
from validation_engine.strategy_scenario_generator import generate_retrofit_generation_scenarios
from utils.config import CHECKPOINT_DIR, INPUT_DIR, INTERMEDIATE_DIR, OUTPUT_DIR, load_settings
from utils.file_io import read_json, write_json, write_text
from utils.logger import step


def _load_optional(path: Path) -> dict:
    return read_json(path) if path.exists() else {}


def _write_checkpoint_graph(checkpoint_name: str, settings) -> None:
    package_dir = CHECKPOINT_DIR / checkpoint_name
    checkpoint = read_json(package_dir / "checkpoint.json")
    stage_result = read_json(package_dir / "stage_result.json")
    user_decision = read_json(package_dir / "user_decision.json")
    try:
        write_checkpoint_graph(checkpoint, stage_result, user_decision, settings)
    except Exception as error:
        write_json(
            INTERMEDIATE_DIR / "checkpoint_graph_write_warning.json",
            {
                "status": "warning",
                "message": "Checkpoint graph write failed; JSON pipeline continuation can still proceed.",
                "error": str(error),
            },
        )


def _continue_after_selection(settings) -> None:
    interpreted_case = read_json(INTERMEDIATE_DIR / "interpreted_case.json")
    spatial_index = _load_optional(INTERMEDIATE_DIR / "spatial_index_with_overrides.json") or read_json(
        INTERMEDIATE_DIR / "spatial_index.json"
    )
    problem_map = read_json(INTERMEDIATE_DIR / "problem_map.json")
    user_selection = read_json(INTERMEDIATE_DIR / "user_selection.json")

    step("Refreshing Phase 3 retrofit packages")
    diagnosis_result = read_json(INTERMEDIATE_DIR / "diagnosis_result.json")
    strategy_options = read_json(INTERMEDIATE_DIR / "strategy_options.json")
    retrofit_validation_options = read_json(INTERMEDIATE_DIR / "retrofit_validation_options.json")
    retrofit_generation_scenarios = generate_retrofit_generation_scenarios(diagnosis_result, strategy_options, limit=9)
    write_json(INTERMEDIATE_DIR / "retrofit_generation_scenarios.json", retrofit_generation_scenarios)
    phase3_strategy_packages = build_packages()
    write_json(INTERMEDIATE_DIR / "phase3_strategy_packages.json", phase3_strategy_packages)
    validation_view_payload = dict(phase3_strategy_packages)
    validation_view_payload["baseline"] = retrofit_validation_options.get("baseline", {})
    write_text(OUTPUT_DIR / "validation_view.html", export_validation_html(validation_view_payload))

    step("Writing checkpoint-selected decision graph")
    try:
        write_decision_graph(user_selection, settings)
    except Exception as error:
        write_json(
            INTERMEDIATE_DIR / "decision_graph_write_warning.json",
            {
                "status": "warning",
                "message": "Decision graph write failed; JSON/report continuation can still proceed.",
                "error": str(error),
            },
        )

    step("Building Gemini visual prompt from checkpoint selection")
    gemini_prompt = build_visual_prompt(interpreted_case, problem_map, user_selection, spatial_index)
    write_json(INTERMEDIATE_DIR / "gemini_prompt.json", gemini_prompt)

    step("Generating Gemini visual result from checkpoint selection")
    gemini_result = generate_visual(gemini_prompt, settings)
    write_json(INTERMEDIATE_DIR / "gemini_result.json", gemini_result)

    step("Running LLM review after checkpoint selection")
    llm_review = run_review_loop(
        {
            "problem_map": problem_map,
            "user_selection": user_selection,
            "gemini_result": gemini_result,
            "retrofit_validation": read_json(INTERMEDIATE_DIR / "retrofit_validation.json"),
        },
        settings,
    )
    write_json(INTERMEDIATE_DIR / "llm_review.json", llm_review)

    step("Compiling final report after checkpoint selection")
    report_payload = {
        "interpreted_case": interpreted_case,
        "spatial_index": spatial_index,
        "risk_map": _load_optional(INTERMEDIATE_DIR / "risk_map.json"),
        "diagnosis_result": diagnosis_result,
        "problem_map": problem_map,
        "manual_check": _load_optional(INTERMEDIATE_DIR / "manual_check_result.json"),
        "strategy_options": strategy_options,
        "retrofit_validation_options": retrofit_validation_options,
        "retrofit_generation_scenarios": retrofit_generation_scenarios,
        "phase3_strategy_packages": phase3_strategy_packages,
        "strategy_validation_checkpoint": read_json(CHECKPOINT_DIR / "08_strategy_validation" / "checkpoint.json"),
        "user_selection": user_selection,
        "retrofit_validation": read_json(INTERMEDIATE_DIR / "retrofit_validation.json"),
        "gemini_prompt": gemini_prompt,
        "gemini_result": gemini_result,
        "llm_review": llm_review,
    }
    final_report = compile_report(report_payload)
    write_json(OUTPUT_DIR / "final_report.json", final_report)
    write_text(OUTPUT_DIR / "final_report.md", export_markdown(final_report))
    write_text(OUTPUT_DIR / "final_report_view.html", export_html(final_report))


def main() -> None:
    parser = argparse.ArgumentParser(description="Continue the HVRA pipeline from a checkpoint decision.")
    parser.add_argument("--checkpoint", default="08_strategy_validation")
    parser.add_argument("--llm", action="store_true", help="Ask the configured LLM to write user_decision.json first.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply user_decision.json. Without this flag, only writes/prints the LLM recommendation.",
    )
    parser.add_argument("--mock-llm", action="store_true", help="Force mock LLM for this continuation run.")
    parser.add_argument("--mock-gemini", action="store_true", help="Force mock Gemini for this continuation run.")
    parser.add_argument("--mock-neo4j", action="store_true", help="Force mock Neo4j graph writes for this run.")
    args = parser.parse_args()
    settings = load_settings()
    if args.mock_llm:
        settings = replace(settings, use_mock_llm=True)
    if args.mock_gemini:
        settings = replace(settings, use_mock_gemini=True)
    if args.mock_neo4j:
        settings = replace(settings, use_mock_neo4j=True)

    if args.llm:
        step("Running LLM checkpoint decision")
        decision = run_llm_checkpoint_decision(args.checkpoint, settings)
        print(decision)

    if not args.apply:
        return

    step("Applying checkpoint decision")
    route = apply_checkpoint_decision(args.checkpoint)
    print(route)

    step("Writing checkpoint graph summary")
    _write_checkpoint_graph(args.checkpoint, settings)

    if route.get("status") == "applied":
        _continue_after_selection(settings)
    else:
        step(f"Checkpoint routed to {route.get('rerun_from_stage')}; no downstream continuation was run.")


if __name__ == "__main__":
    main()
