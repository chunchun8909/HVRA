# HVRA Architecture and Pipeline

This document describes the current backend architecture. It replaces the older MVP scaffold notes.

## Core Principle

```text
canonical JSON -> generated Neo4j view
canonical JSON -> generated HTML views
canonical JSON -> LLM checkpoint prompt
canonical JSON -> report output
```

JSON files remain the source of truth. Neo4j and HTML are generated views used for traceability, debugging, and the current stage-aware interface.

## Active Pipeline

```text
data/input/user_case.json
data/input/building_info.json
data/input/region_context.json
data/input/retrofit_constraints.json
data/input/images/
        |
        v
LLM Agent
- interprets user case
- selects diagnosis profile
        |
        v
Spatial Engine
- finds pano image
- runs LGTNet
- scales layout to room area and height
- extracts wall/floor/ceiling textures
- runs SAM3 on wall fragments
- builds spatial_index.json
        |
        v
Spatial V&V Checkpoint
- data/checkpoints/01_spatial_vv
- room_3d_view.html
- user confirms wall orientation after LGTNet geometry
- optional component/surface include-exclude edits
- saves spatial_user_overrides.json
        |
        v
Spatial Override Application
- applies confirmed orientations
- applies component/surface edits
- writes spatial_index_with_overrides.json
        |
        v
Risk Map
- reads region_context.json
- extracts EPW climate summary
- optionally runs/caches Infrared City microclimate context
- builds site context for diagnosis, not the final room risk score
        |
        v
Neo4j Spatial Graph
- Building -> Room -> Wall -> Component
        |
        v
Diagnosis Engine
- deterministic calculations
- no hidden LLM scoring
- outputs diagnosis_result.json
        |
        v
Problem Map
- assigns problems to room surfaces
- outputs problem_map.json
        |
        v
Neo4j Diagnosis Graph
- Room -> Problem
- Wall/Component -> Problem
        |
        v
RAG Manual Check
- local PDFs and source metadata
- keyword/vector/hybrid retrieval
- outputs manual_check_result.json
        |
        v
LLM Strategy Ranking
- ranks eligible strategies
- outputs strategy_options.json
        |
        v
Retrofit Validation Engine
- validates every option
- compares baseline vs proposed indicators
- applies benchmark pass/partial/fail checks
- records combo screening method from docs/thermal_combo_screening.md
- future combo packages use validation_engine/combo_effects.py, not naive additive Delta T
- outputs retrofit_validation_options.json
        |
        v
Strategy Validation Checkpoint
- data/checkpoints/08_strategy_validation
- LLM/user chooses, combines, revises, reruns, accepts, or stops
- interface exposes the top three validated options as phase 3 buttons
        |
        v
Selected Retrofit Validation
- outputs user_selection.json
- outputs retrofit_validation.json
        |
        v
Neo4j Decision and Checkpoint Graph
- Strategy -> ValidationResult
- Checkpoint -> ValidationResult
- UserSelection -> Strategy
        |
        v
Gemini Engine
- builds visual prompt
- mock or real image generation
        |
        v
LLM Review Loop
- consistency review
        |
        v
Report Engine
- final_report.json
- final_report.md
```

## Major Modules

### `llm_agent/`

Owns local LLM coordination through Ollama.

Responsibilities:

- interpret user case
- rank strategies
- review consistency
- write checkpoint decisions when requested

Rule: the LLM may guide, rank, and review. It must not invent environmental scores.

### `spatial_engine/`

Owns image-to-room understanding.

Current flow:

```text
pano image -> LGTNet -> scaling -> surface textures -> wall fragments -> SAM3 -> spatial index -> room viewer -> user orientation confirmation
```

Important outputs:

```text
data/intermediate/spatial_index.json
data/intermediate/spatial_user_overrides.json
data/intermediate/spatial_index_with_overrides.json
data/output/spatial/room_3d_view.html
```

The LGTNet output determines geometry. Wall orientation is treated as provisional until the user confirms it in the generated room viewer. `main.py` stops before risk map, diagnosis, and KG graph writes if orientation is not confirmed.

### `3D_test/`

Owns a non-interactive smoke test for future 3D component asset integration.

Current flow:

```text
LGTNet prediction JSON -> room/wall geometry summary -> optional asset registry API call -> asset manifest JSON
```

Default input:

```text
data/output/spatial/lgtnet/demo1_pred.json
```

Default output:

```text
3D_test/lgtnet_asset_manifest.json
```

Optional `.env` values:

```text
ASSET_REGISTRY_API_URL=
ASSET_REGISTRY_API_KEY=
```

This test does not create an interface and does not inject assets into the main room viewer yet. It only verifies that LGTNet geometry can be paired with web-optimized 3D asset metadata in a backend-safe way.
### `risk_map/`

Owns location, climate, urban, vegetation, exposure, and cooling-access context.

The Risk Map is a contextual data collector. It does not make the final room-level risk decision. Its output is passed to the diagnosis engine, where the room geometry, wall/window orientation, envelope conditions, occupant profile, and climate context are combined into deterministic diagnosis indicators.

Current inputs:

```text
data/input/region_context.json
risk_map/dataset/
```

Current outputs:

```text
data/intermediate/risk_map.json
risk_map/dataset/infrared_city/infrared_city_context.json
```

Infrared City support is live when `USE_INFRARED_CITY=true`. The provider uses `infrared-sdk` to fetch buildings, vegetation, ground materials, nearest weather, wind speed, sky view factor, direct sun hours, solar radiation, and UTCI for the site polygon. Results are cached unless `INFRARED_CITY_FORCE_REFRESH=true`.

### `diagnosis_engine/`

Owns deterministic heat-risk calculations.

Current calculation families:

- solar gain
- window-to-wall ratio
- cross ventilation
- ACH
- ventilation deficit
- envelope risk
- operative temperature
- WBGT
- nocturnal recovery
- overheating hours
- occupant vulnerability
- composite room risk score
- urban-adjusted final risk score


Diagnosis weighting is now documented as a literature-informed screening method:

```text
composite_room_risk_score =
    0.40 * solar_gain_score
  + 0.35 * ventilation_deficit_score
  + 0.15 * envelope_score
  + 0.10 * occupant_vulnerability_score
```

Nocturnal recovery is still calculated as a health-critical KPI, but it is applied downstream in the final risk modifier and validation benchmarks rather than double-counted inside the base composite. These weights are documented screening assumptions informed by Samuelson et al. 2020, UKHSA/Public Health England, WHO Heat and Health, ISO 7243, ASHRAE 55, EN ISO 7726, and the Barcelona heat-vulnerability framing.

### `validation_engine/`

Owns retrofit validation.

It extracts baseline indicators from diagnosis results, applies strategy effect profiles, computes proposed indicators, and compares them against benchmark gates.

Current benchmark sources include:

- ASHRAE 55
- EN ISO 7726
- ISO 7243
- CIBSE TM59 bedroom/night overheating logic
- Samuelson et al. 2020 heat vulnerability framing
- UKHSA/Public Health England indoor heat guidance
- CTE DB-HE envelope logic
- EN 15242 / ASHRAE 62.1 ventilation logic

### `checkpoint_engine/`

Owns stage review packages and continuation logic.

Current checkpoints:

```text
01_spatial_vv
08_strategy_validation
```

Every checkpoint package contains:

```text
checkpoint.json
stage_result.json
kg_update_summary.json
viewer_update_summary.json
llm_review_prompt.json
user_decision.json
```

Allowed strategy validation actions:

```text
choose_option
combine_options
revise_intent
rerun_strategy_ranking
accept_partial_pass
stop
```

### `knowledge_graph/`

Owns Neo4j writes and KG test visualization.

Generated local KG view:

```text
data/output/kg/kg_view.html
data/output/kg/kg_view_data.json
```

### `rag_engine/`

Owns local evidence retrieval from PDFs/manuals.

Important inputs:

```text
data/raw_pdfs/
data/source_metadata.json
```

Important generated artifacts:

```text
data/processed/
data/vector_db/
```

### `gemini_engine/`

Owns visual prompt creation and mock/real image generation.

### `report_engine/`

Owns report compilation only. It should not add hidden reasoning or new calculations.

## Inspection Views

### Room Viewer

```text
http://127.0.0.1:8010/static-views/spatial/room_3d_view.html
```

Used to inspect:

- 3D room geometry
- wall/floor/ceiling textures
- component detection
- wall orientation confirmation
- spatial V&V include/exclude overrides

Modes:

```text
room_3d_view.html?viewer_mode=spatial_vv
room_3d_view.html?viewer_mode=review
```

`spatial_vv` mode hides diagnosis and validation panels because those engines have not run yet.

Phase progression is automatic once each required checkpoint is satisfied:

- Phase 1 input gathering collects address or coordinates, room basics, resident context, and the two images.
- Phase 1.5 site-context review displays the backend-precomputed risk-map checkpoint before room verification.
- Phase 2 room review saves spatial overrides, confirms wall orientation/window inclusion, runs the remaining pipeline, and moves to Phase 3.
- Phase 3 shows the top three retrofit options, room overlays, knowledge-graph links, numerical validation, and the final report.

The interface uses loading transitions between phases so the user sees the backend work instead of a frozen screen:

```text
Phase 1 -> checking site context -> Phase 1.5
Phase 1.5 -> building room model -> Phase 2
Phase 2 -> running diagnosis and upgrades -> Phase 3
```

`review` mode hides the phase 2 spatial edit controls:

```text
orientation
room check
```

### KG Viewer

```text
http://127.0.0.1:8010/static-views/kg/kg_view.html
```

Used to inspect:

- room and wall graph
- detected components
- problem map relationships
- strategy validation options
- checkpoint and user selection path

### Phase 3 Strategy Selector

In the interface review phase, the top-left of the visualization panel shows three retrofit option buttons:

```text
option 1
option 2
option 3
```

They are populated from:

```text
data/intermediate/retrofit_validation_options.json
```

through:

```text
GET /api/strategy-options
```

The top-right view buttons remain:

```text
room
links
check
report
```

## Commands

Run full pipeline:

```powershell
.\.venv\Scripts\python.exe main.py
```

Continue from checkpoint:

```powershell
.\.venv\Scripts\python.exe continue_from_checkpoint.py --llm --apply
```

Export KG HTML:

```powershell
.\.venv\Scripts\python.exe scripts\export_kg_view.py
```

Serve generated HTML:

```powershell
.\.venv\Scripts\python.exe -m http.server 8000 -d data\output
```

Run FastAPI backend for the interface:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

Run frontend:

```powershell
cd interface
npm run dev
```

Interface QA pages:

```text
http://localhost:5173/format_check.html
http://localhost:5173/phase_check.html
```

Compile check:

```powershell
.\.venv\Scripts\python.exe -m compileall checkpoint_engine diagnosis_engine knowledge_graph llm_agent rag_engine risk_map spatial_engine validation_engine main.py continue_from_checkpoint.py scripts\export_kg_view.py
```
### Risk Map 3D Visual Test

The Risk Map 3D test view is a backend visual-inspection page for Phase 1 location context. It now receives backend-prepared visual geometry: Barcelona-wide road/building contours, local 500 m road/building contours, and local 3D building extrusions. The current local geometry source is `cataluna-260528-free.shp.zip`; footprints are real OSM geometry, while heights are estimated unless Infrared City mesh geometry becomes available.

Infrared City remains integrated for analysis context through the cached `infrared_city_context.json` summary. The current cache contains min/mean/max, bounds, and grid shape for wind speed, sky view factor, direct sun hours, solar radiation, and UTCI. A true pixel-accurate Infrared heat map will require storing the raw `merged_grid` arrays from the SDK output.

## Risk Map Checkpoint Stage

The Risk Map visual is treated as Phase 1.5: a precomputed checkpoint between Phase 1 case setup and Phase 2 room/spatial verification. The backend prepares a simplified visual payload first, then the interface only displays the result: simple local map geometry, separate heat-analysis layers, and optional aligned 3D buildings after the site is chosen. This avoids live browser-side analysis and keeps map, boundary, and building geometry in one consistent coordinate frame.

The current interface embeds this checkpoint inside the same split layout used by later phases: LLM chat on the left, and an integrated site panel plus 3D/canvas view on the right. The standalone risk-map page remains a development view, but Phase 1.5 is now part of the normal phase flow.

Current display contract:

```text
risk map backend/cache -> risk_map_context.json -> risk map checkpoint viewer
```

The checkpoint uses local OSM footprints for visual alignment and Infrared City for analysis values. True pixel-accurate Infrared raster layers still require storing raw merged-grid cells from the Infrared SDK output; the current cache provides summary statistics, bounds, and grid shape.






