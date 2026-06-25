# Data Flow

HVRA uses file-based JSON as the canonical backend state during the prototype phase.

## Input Data

| Path | Purpose |
| --- | --- |
| `data/input/user_case.json` | Resident, comfort, vulnerability, and user-note input. |
| `data/input/building_info.json` | Room dimensions, building context, glazing, floor/height, baseline info. |
| `data/input/region_context.json` | Address/coordinates, city, neighbourhood, climate context. |
| `data/input/retrofit_constraints.json` | Budget, disruption, permission, ownership, preferred/excluded strategy types. |
| data/input/strategy_catalogue.json | Static retrofit strategy source of truth. |
| data/input/strategy_evidence_map.json | Evidence role, confidence, and source IDs for each strategy. |
| data/input/visual_retrofit_catalogue.json | 3D placement, asset type, material, and render-layer rules for each strategy. |
| `data/input/images/pano_image/` | Pano images for LGTNet layout extraction. |
| `data/input/images/perspective_image/` | Legacy/deactivated; current final visual output uses the 3D room preview with retrofit components. |

## RAG Data

| Path | Purpose |
| --- | --- |
| `data/raw_pdfs/` | Academic, standards, guide, policy, and retrofit source PDFs. |
| `data/source_metadata.json` | Source metadata for each RAG PDF. |
| `data/processed/corpus_pages.jsonl` | Extracted page-level text. |
| `data/processed/corpus_chunks.jsonl` | Chunked retrieval text. |
| `data/vector_db/chroma/` | Local vector database. |

## Risk Map Data

| Path | Purpose |
| --- | --- |
| `risk_map/dataset/` | EPW, GIS, vulnerability, vegetation, building, refuge, and contextual data. |
| `risk_map/dataset/source_metadata.json` | Dataset metadata and provenance. |
| `risk_map/dataset/infrared_city/` | Cached or exported Infrared City context. |

## Intermediate Outputs

| Path | Purpose |
| --- | --- |
| `data/intermediate/interpreted_case.json` | LLM-interpreted case profile. |
| `data/intermediate/spatial_index.json` | Raw spatial output. |
| `data/intermediate/spatial_user_overrides.json` | User-confirmed room orientation/surface/component edits. |
| `data/intermediate/spatial_index_with_overrides.json` | Spatial state after checkpoint edits. |
| `data/intermediate/risk_map.json` | Site/environmental context for diagnosis. |
| `data/intermediate/diagnosis_result.json` | Deterministic heat-risk diagnosis. |
| `data/intermediate/problem_map.json` | Problems assigned to room/surface targets. |
| `data/intermediate/manual_check_result.json` | RAG/manual evidence and eligible/restricted strategies. |
| `data/intermediate/strategy_options.json` | LLM-ranked strategy options. |
| `data/intermediate/retrofit_validation_options.json` | Validated options with benchmark results. |
| `data/intermediate/user_selection.json` | Selected strategy or checkpoint decision. |
| `data/intermediate/retrofit_validation.json` | Validation for selected option. |
| `data/intermediate/gemini_prompt.json` | Visual prompt payload. |
| `data/intermediate/gemini_result.json` | Visual generation result or mock. |
| `data/intermediate/llm_review.json` | Consistency review. |

## Checkpoint and Output Data

| Path | Purpose |
| --- | --- |
| `data/checkpoints/` | Checkpoint packages and user decisions. |
| `data/output/spatial/room_3d_view.html` | Interactive room inspection view. |
| `data/output/kg/kg_view.html` | Interactive knowledge graph test view. |
| `data/output/validation_view.html` | Numerical before/after validation check. |
| `data/output/final_report.json` | Machine-readable final report. |
| `data/output/final_report.md` | Markdown final report. |
| `data/output/final_report_view.html` | HTML final report. |

Generated data folders are ignored by git except placeholders/configuration files where needed.
