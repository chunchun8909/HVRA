from __future__ import annotations

from checkpoint_engine import create_spatial_vv_checkpoint, create_strategy_validation_checkpoint
from diagnosis_engine.environmental_diagnosis import compute_diagnosis
from diagnosis_engine.problem_map_builder import build_problem_map
from gemini_engine.gemini_prompt_builder import build_visual_prompt
from gemini_engine.image_generator import generate_visual
from knowledge_graph.graph_writer import (
    initialize_graph,
    write_decision_graph,
    write_diagnosis_graph,
    write_spatial_graph,
)
from llm_agent.agent import interpret_user_case, rank_retrofit_options
from llm_agent.review_loop import run_review_loop
from report_engine.html_exporter import export_html
from rag_engine.manual_checker import check_manuals
from report_engine.markdown_exporter import export_markdown
from report_engine.report_compiler import compile_report
from risk_map.risk_map_builder import build_risk_map
from spatial_engine.overrides import apply_spatial_overrides, load_spatial_overrides, spatial_orientation_confirmed
from spatial_engine.spatial_indexer import create_spatial_index
from spatial_engine.wall_diagnosis_state import export_wall_diagnosis_state
from utils.config import INPUT_DIR, INTERMEDIATE_DIR, OUTPUT_DIR, load_settings
from utils.file_io import read_json, write_json, write_text
from utils.logger import step
from validation_engine import validate_retrofit, validate_retrofit_options
from validation_engine.html_exporter import export_validation_html


def _save_intermediate(name: str, payload: dict) -> dict:
    write_json(INTERMEDIATE_DIR / name, payload)
    return payload


def _save_pipeline_status(payload: dict) -> dict:
    return _save_intermediate("pipeline_status.json", payload)


def main() -> None:
    settings = load_settings()

    step("Loading input JSON files")
    user_case = read_json(INPUT_DIR / "user_case.json")
    building_info = read_json(INPUT_DIR / "building_info.json")
    region_context = read_json(INPUT_DIR / "region_context.json")
    constraints = read_json(INPUT_DIR / "retrofit_constraints.json")

    step("Interpreting user case")
    interpreted_case = _save_intermediate(
        "interpreted_case.json",
        interpret_user_case(user_case, building_info, constraints, settings),
    )

    step("Creating spatial index")
    spatial_index = _save_intermediate("spatial_index.json", create_spatial_index(building_info, settings))
    spatial_vv_checkpoint = create_spatial_vv_checkpoint(spatial_index)
    spatial_overrides = load_spatial_overrides()
    spatial_index = _save_intermediate(
        "spatial_index_with_overrides.json",
        apply_spatial_overrides(spatial_index, spatial_overrides),
    )
    if not spatial_orientation_confirmed(spatial_index, spatial_overrides):
        _save_pipeline_status(
            {
                "status": "waiting_for_user",
                "current_stage": "spatial_vv",
                "checkpoint": "01_spatial_vv",
                "message": (
                    "Room geometry is ready. Please open the room view, confirm each wall orientation, "
                    "check the detected windows, then press Continue to run diagnosis."
                ),
                "primary_output": "data/output/spatial/room_3d_view.html",
                "required_before": ["risk_map", "spatial_graph", "diagnosis_engine", "knowledge_graph"],
            }
        )
        step("Spatial orientation confirmation required before diagnosis and KG")
        return

    step("Building risk map")
    risk_map = _save_intermediate(
        "risk_map.json",
        build_risk_map(
            building_info,
            region_context,
            bbox_radius_m=settings.risk_map_bbox_radius_m,
            data_root=settings.risk_map_data_root,
            use_infrared_city=settings.use_infrared_city,
            infrared_cache_json=settings.infrared_cache_json,
            infrared_api_key=settings.infrared_api_key,
            infrared_base_url=settings.infrared_base_url,
            infrared_force_refresh=settings.infrared_force_refresh,
        ),
    )

    step("Writing spatial graph")
    initialize_graph(settings)
    write_spatial_graph(spatial_index, settings)

    step("Computing deterministic diagnosis")
    diagnosis_result = _save_intermediate(
        "diagnosis_result.json",
        compute_diagnosis(
            interpreted_case,
            building_info,
            spatial_index,
            user_case,
            urban_context=risk_map,
        ),
    )

    step("Building problem map")
    problem_map = _save_intermediate("problem_map.json", build_problem_map(diagnosis_result, spatial_index))
    export_wall_diagnosis_state(problem_map, spatial_index)

    step("Writing diagnosis graph")
    write_diagnosis_graph(problem_map, settings)

    step("Checking local RAG manuals")
    manual_check = _save_intermediate("manual_check_result.json", check_manuals(problem_map, constraints))

    step("Ranking retrofit options")
    strategy_options = _save_intermediate(
        "strategy_options.json",
        rank_retrofit_options(problem_map, manual_check, constraints, settings),
    )

    ranked = strategy_options.get("ranked_strategies", [])
    if not ranked:
        raise RuntimeError("No retrofit strategies were ranked.")

    step("Validating retrofit options against thermal benchmarks")
    retrofit_validation_options = _save_intermediate(
        "retrofit_validation_options.json",
        validate_retrofit_options(diagnosis_result, problem_map, strategy_options, spatial_index),
    )
    write_text(OUTPUT_DIR / "validation_view.html", export_validation_html(retrofit_validation_options))
    strategy_validation_checkpoint = create_strategy_validation_checkpoint(retrofit_validation_options)
    validated_options = retrofit_validation_options.get("validated_options", [])
    if not validated_options:
        raise RuntimeError("No retrofit options were validated.")
    recommended_strategy = validated_options[0]["strategy"]

    step("Saving automatic test user selection")
    user_selection = _save_intermediate(
        "user_selection.json",
        {
            "id": f"{interpreted_case['case_id']}_SELECTION_001",
            "case_id": interpreted_case["case_id"],
            "selected_strategy": recommended_strategy,
            "responds_to_problem_ids": [problem["id"] for problem in problem_map.get("problems", [])],
            "selection_mode": "automatic_validation_recommended_option",
        },
    )

    step("Validating selected retrofit against thermal benchmarks")
    retrofit_validation = _save_intermediate(
        "retrofit_validation.json",
        validate_retrofit(diagnosis_result, problem_map, user_selection, spatial_index),
    )

    step("Writing decision graph")
    write_decision_graph(user_selection, settings)

    step("Building Gemini visual prompt")
    gemini_prompt = _save_intermediate(
        "gemini_prompt.json",
        build_visual_prompt(interpreted_case, problem_map, user_selection, spatial_index),
    )

    step("Generating Gemini visual result")
    gemini_result = _save_intermediate("gemini_result.json", generate_visual(gemini_prompt, settings))

    step("Running LLM review loop")
    review_payload = {
        "problem_map": problem_map,
        "user_selection": user_selection,
        "gemini_result": gemini_result,
    }
    llm_review = _save_intermediate("llm_review.json", run_review_loop(review_payload, settings))

    step("Compiling final report")
    report_payload = {
        "interpreted_case": interpreted_case,
        "spatial_index": spatial_index,
        "spatial_vv_checkpoint": spatial_vv_checkpoint,
        "risk_map": risk_map,
        "diagnosis_result": diagnosis_result,
        "problem_map": problem_map,
        "manual_check": manual_check,
        "strategy_options": strategy_options,
        "retrofit_validation_options": retrofit_validation_options,
        "strategy_validation_checkpoint": strategy_validation_checkpoint,
        "user_selection": user_selection,
        "retrofit_validation": retrofit_validation,
        "gemini_prompt": gemini_prompt,
        "gemini_result": gemini_result,
        "llm_review": llm_review,
    }
    final_report = compile_report(report_payload)
    write_json(OUTPUT_DIR / "final_report.json", final_report)
    write_text(OUTPUT_DIR / "final_report.md", export_markdown(final_report))
    write_text(OUTPUT_DIR / "final_report_view.html", export_html(final_report))

    _save_pipeline_status(
        {
            "status": "complete",
            "current_stage": "complete",
            "message": "Pipeline complete.",
            "primary_output": "data/output/final_report_view.html",
        }
    )
    step("Pipeline complete")


if __name__ == "__main__":
    main()

