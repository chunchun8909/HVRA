# HVRA Project Handbook

This consolidated handbook combines the current HVRA system overview, pipeline, engine descriptions, data flow, source inventories, RAG sources, retrofit strategy catalogue, thermal combo screening method, and interface/backend architecture.

For run commands, startup, testing, and recovery, use `docs/terminal_commands.md`. This file is intended as a single conceptual handoff/reference document for reviewers, collaborators, and future GitHub readers.

## Table of Contents

- [System Overview](#system-overview)
- [Architecture and Pipeline](#architecture-and-pipeline)
- [Data Flow](#data-flow)
- [Data Sources by Segment](#data-sources-by-segment)
- [RAG Academic Source Categories](#rag-academic-source-categories)
- [RAG Source Inventory](#rag-source-inventory)
- [Risk Map Data Inventory](#risk-map-data-inventory)
- [Retrofit Strategy Catalogue](#retrofit-strategy-catalogue)
- [Thermal Combo Screening Method](#thermal-combo-screening-method)
- [Interface Contract](#interface-contract)

---

## System Overview


HVRA is a backend-first Heat Vulnerability Retrofit Assistant. It helps inspect a room, diagnose heat-risk drivers, retrieve supporting design evidence, rank retrofit options, validate proposed improvements, and expose checkpoint views for user review.

### Implemented Engines

| Engine | Folder | Role | Main outputs |
| --- | --- | --- | --- |
| Interface API | `app.py` | FastAPI backend for the React interface and checkpoint save/continue routes. | API responses, saved overrides |
| LLM Agent | `llm_agent/` | Ollama-backed or mock JSON generation for case interpretation, strategy ranking, and consistency review. | `interpreted_case.json`, `strategy_options.json`, `llm_review.json` |
| Spatial Engine | `spatial_engine/` | Pano image processing, LGTNet layout, scaling, SAM3 wall-fragment segmentation, wall/floor/ceiling textures, 3D room view. | `spatial_index.json`, `room_3d_view.html` |
| Risk Map | `risk_map/` | EPW and urban-context extraction, optional Infrared City context, site/environmental context for diagnosis. | `risk_map.json` |
| Diagnosis Engine | `diagnosis_engine/` | Deterministic heat-risk calculations. No hidden LLM scoring. | `diagnosis_result.json` |
| Problem Map | `diagnosis_engine/problem_map_builder.py` | Assigns calculated problems to room/surface targets. | `problem_map.json` |
| RAG Engine | `rag_engine/` | PDF loading, chunking, vector/keyword/hybrid retrieval, manual evidence checking. | `manual_check_result.json`, vector DB |
| Validation Engine | `validation_engine/` | Baseline/proposed indicator comparison, benchmark pass/fail, confidence gate, combo screening method. | `retrofit_validation_options.json`, `retrofit_validation.json` |
| Checkpoint Engine | `checkpoint_engine/` | Creates stage checkpoint packages and routes decisions. | `data/checkpoints/*` |
| Knowledge Graph | `knowledge_graph/` | local KG JSON/HTML generation; optional Neo4j graph writing. | `kg_view_data.json`, `kg_view.html` |
| Gemini Engine | `gemini_engine/` | Visual prompt/result layer for future generated design images. | `gemini_prompt.json`, `gemini_result.json` |
| Report Engine | `report_engine/` | Final JSON, Markdown, and HTML report compilation. | `final_report.json`, `final_report.md`, `final_report_view.html` |

### ML / AI Models and External Systems

| Component | Current role | Mode |
| --- | --- | --- |
| LGTNet | Pano room layout extraction. | Real or mock via `.env` |
| SAM3 | Window/component segmentation on wall fragments. | External environment, real or fallback/mock |
| Ollama | Local LLM JSON reasoning for interpretation, ranking, review. | Real or mock |
| Gemini | Visual generation/prompt layer. | Real or mock |
| Chroma/vector retrieval | Local RAG vector store. | Local |
| Neo4j | Optional external graph database for future/live traceability. Current default uses mock/local KG export. | Disabled/mock |
| Infrared City | Optional microclimate API/context assist. | Real/cache/mock |

### Interface Phases

```text
Phase 1: user input through chat/instructions
Phase 1.5: site context / risk-map checkpoint
Phase 2: spatial V&V, wall orientation, window inclusion check
Phase 3: top three retrofit options, room/KG/check/report review
```

The system is designed so each checkpoint can update three synchronized views: canonical JSON, generated KG view, and HTML/3D review views. The interface now uses a compact 60 percent production scale, while `phase_check.html` keeps 50/60/75/100 scale buttons only for QA.

---

## Architecture and Pipeline


This document describes the current backend architecture. It replaces the older MVP scaffold notes.

### Core Principle

```text
canonical JSON -> generated KG JSON/HTML view
canonical JSON -> generated HTML views
canonical JSON -> LLM checkpoint prompt
canonical JSON -> report output
```

JSON files remain the source of truth. KG HTML and other HTML outputs are generated views used for traceability, debugging, and the current stage-aware interface.

### Active Pipeline

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
Knowledge Graph Export
- generated JSON/HTML trace: Building -> Room -> Wall -> Component
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
Diagnosis KG Export
- generated JSON/HTML trace: Room -> Problem
- generated JSON/HTML trace: Wall/Component -> Problem
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
Decision and Checkpoint KG Export
- generated JSON/HTML trace: Strategy -> ValidationResult
- generated JSON/HTML trace: Checkpoint -> ValidationResult
- generated JSON/HTML trace: UserSelection -> Strategy
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

### Major Modules

#### `llm_agent/`

Owns local LLM coordination through Ollama.

Responsibilities:

- interpret user case
- rank strategies
- review consistency
- write checkpoint decisions when requested

Rule: the LLM may guide, rank, and review. It must not invent environmental scores.

#### `spatial_engine/`

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

#### `3D_test/`

Owns a non-interactive smoke test for future web-optimized 3D component asset integration. It reads `data/output/spatial/lgtnet/demo1_pred.json`, optionally calls an asset registry using `ASSET_REGISTRY_API_URL` and `ASSET_REGISTRY_API_KEY`, and writes `3D_test/lgtnet_asset_manifest.json`.
#### `risk_map/`

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

#### `diagnosis_engine/`

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

#### `validation_engine/`

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

#### `checkpoint_engine/`

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

#### `knowledge_graph/`

Owns local KG JSON/HTML visualization; optional Neo4j writes remain available but are disabled by default.

Generated local KG view:

```text
data/output/kg/kg_view.html
data/output/kg/kg_view_data.json
```

#### `rag_engine/`

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

#### `gemini_engine/`

Owns visual prompt creation and mock/real image generation.

#### `report_engine/`

Owns report compilation only. It should not add hidden reasoning or new calculations.

### Inspection Views

#### Room Viewer

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

`review` mode hides the phase 2 spatial edit controls:

```text
orientation
room check
```

#### KG Viewer

```text
http://127.0.0.1:8010/static-views/kg/kg_view.html
```

Used to inspect:

- room and wall graph
- detected components
- problem map relationships
- strategy validation options
- checkpoint and user selection path

#### Phase 3 Strategy Selector

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


---

## Data Flow


HVRA uses file-based JSON as the canonical backend state during the prototype phase.

### Input Data

| Path | Purpose |
| --- | --- |
| `data/input/user_case.json` | Resident, comfort, vulnerability, and user-note input. |
| `data/input/building_info.json` | Room dimensions, building context, glazing, floor/height, baseline info. |
| `data/input/region_context.json` | Address/coordinates, city, neighbourhood, climate context. |
| `data/input/retrofit_constraints.json` | Budget, disruption, permission, ownership, preferred/excluded strategy types. |
| `data/input/strategy_catalogue.json` | Static retrofit strategy source of truth. |
| `data/input/images/pano_image/` | Pano images for LGTNet layout extraction. |
| `data/input/images/perspective_image/` | Perspective/reference images for final visual/report workflows. |

### RAG Data

| Path | Purpose |
| --- | --- |
| `data/raw_pdfs/` | Academic, standards, guide, policy, and retrofit source PDFs. |
| `data/source_metadata.json` | Source metadata for each RAG PDF. |
| `data/processed/corpus_pages.jsonl` | Extracted page-level text. |
| `data/processed/corpus_chunks.jsonl` | Chunked retrieval text. |
| `data/vector_db/chroma/` | Local vector database. |

### Risk Map Data

| Path | Purpose |
| --- | --- |
| `risk_map/dataset/` | EPW, GIS, vulnerability, vegetation, building, refuge, and contextual data. |
| `risk_map/dataset/source_metadata.json` | Dataset metadata and provenance. |
| `risk_map/dataset/infrared_city/` | Cached or exported Infrared City context. |

### Intermediate Outputs

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

### Checkpoint and Output Data

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

---

## Data Sources by Segment


This document gives a project-level source inventory. Detailed source tables live in [RAG Sources Inventory](rag_sources_inventory.md) and [Risk Map Data Inventory](risk_map_data_inventory.md).

### Spatial Engine Sources

| Segment | Current source/input | Use |
| --- | --- | --- |
| Pano image | `data/input/images/pano_image/` | LGTNet room layout, wall count, floor/ceiling/wall texture extraction. |
| Perspective image | `data/input/images/perspective_image/` | Final visual reference and future generated perspective comparison. |
| LGTNet output | `data/output/spatial/lgtnet/` | Room polygon/layout used by scaling and viewer. |
| SAM3 output | `data/output/spatial/sam3/` | Window segmentation on wall fragments. Furniture/door are not required for calculation. |

### Risk Map Sources

| Segment | Current source/input | Use |
| --- | --- | --- |
| EPW weather | Barcelona EPW/SWEC/TMYx files in `risk_map/dataset/` | Outdoor dry-bulb, humidity, wind, solar, night temperatures. |
| Administrative boundaries | `BCN_UNITATS_ADM.zip` | District/neighbourhood lookup. |
| Building footprints/heights | OSM/GPKG/SHP and `MTM_GPKG_alcades.zip` | Urban density, obstruction, street-canyon context. |
| Vegetation/trees | `2017_vegetacio.gpkg`, `ab_vw_arbrat_geometries.csv` | Local cooling and shade proxies. |
| Cooling refuge/parks | refuge GeoPackages | Access to cooling support. |
| Vulnerability/exposure | vulnerability and elderly-density GeoPackages | Social/health exposure context. |
| Infrared City | `risk_map/dataset/infrared_city/infrared_city_context.json` | Solar radiation, direct sun hours, sky-view factor, UTCI, wind context when available. |

### RAG Sources

| Segment | Current source/input | Use |
| --- | --- | --- |
| Design codes and standards | ASHRAE, ISO, CTE, EN/CIBSE PDF sources | Benchmark thresholds, comfort, ventilation, measurement logic. |
| Retrofit manuals and strategy books | Annex 50, solution booklets, retrofit playbooks, Passive House/EnerPHit sources | Strategy evidence and implementation notes. |
| Climate adaptation and policy | EU renovation strategy, local/policy documents | Retrofit context and public-sector relevance. |
| Research papers | overheating, passive cooling, reflective/cool materials, thermal strategy papers | Effect assumptions and citations. |

### Strategy Catalogue Sources

| Segment | Current source/input | Use |
| --- | --- | --- |
| Static catalogue | `data/input/strategy_catalogue.json` | Source of truth for strategy IDs, names, categories, constraints, cost/carbon ranges, and effect-profile mapping. |
| Catalogue documentation | [Strategy Catalogue](strategy_catalogue.md) | Human-readable list of the 20 strategy entries. |
| Combo method | [Thermal Combo Screening](thermal_combo_screening.md) | Screening formula for future combined strategy packages. |

### Generated Views

| Segment | Current source/input | Use |
| --- | --- | --- |
| Room viewer | `data/output/spatial/room_3d_view.html` | Spatial V&V and future strategy overlays. |
| KG viewer | `data/output/kg/kg_view.html` | Traceability graph review. |
| Validation view | `data/output/validation_view.html` | Numerical before/after option comparison. |
| Report view | `data/output/final_report_view.html` | Final user-facing report preview. |

---

## RAG Academic Source Categories


The RAG engine is fed with raw PDFs in `data/raw_pdfs/` and metadata in `data/source_metadata.json`. The current source set covers these academic and professional categories.

### Categories

| Category | Examples in current corpus | Why it matters |
| --- | --- | --- |
| Thermal comfort standards | ASHRAE 55, ISO 7726, ISO 7243, EN/ISO comfort references | Operative temperature, WBGT, measurement and comfort benchmarks. |
| Ventilation standards | ASHRAE 62.1, EN 15242 / EN 16798-related sources | Ventilation logic and natural ventilation assumptions. |
| Overheating guidance | CIBSE TM59, housing overheating documents | Overheating-hour logic and residential risk framing. |
| Building energy/design codes | CTE DB-HE and regulation documents | Envelope thresholds and local/regional compliance context. |
| Retrofit design manuals | IEA Annex 50, envelope retrofit solution booklets, Passive House/EnerPHit manuals | Strategy implementation, envelope/shading/ventilation design guidance. |
| Climate adaptation and policy | EU long-term renovation strategy and local/policy PDFs | Public-sector retrofit and climate adaptation context. |
| Passive cooling and materials research | cool roof/facade, PCM, shading, natural ventilation, thermal mass papers | Supports effect assumptions and strategy categories. |
| Product/system references | glazing, shading, reflective coating, insulation and retrofit system references | Helps the LLM distinguish feasible systems and constraints. |

### Current Status

See [RAG Sources Inventory](rag_sources_inventory.md) for the full raw PDF list, extraction count, fallback parsing note, and rebuild commands.

### Rule for Future Additions

Every new PDF should be added to:

```text
data/raw_pdfs/
data/source_metadata.json
```

Then rebuild:

```powershell
.\.venv\Scripts\python.exe -m rag_engine.build_index
```

---

## RAG Source Inventory


This file tracks the current raw PDF sources for the HVRA RAG engine.

Canonical metadata file:

```text
data/source_metadata.json
```

Raw PDF folder:

```text
data/raw_pdfs/
```

### Validation Summary

Checked on 2026-06-02. The current folder contains 23 PDFs. All 23 sources extract successfully. `ISO-7726-1998.pdf` requires the `pdfminer.six` fallback because `pypdf` cannot parse that local copy.

The latest ingestion produced:

```text
data/processed/corpus_pages.jsonl   1,882 records
data/processed/corpus_chunks.jsonl  1,895 records
data/vector_db/chroma/              rebuilt
```

| Status | Count | Notes |
| --- | ---: | --- |
| Raw PDFs | 23 | Files currently in `data/raw_pdfs/`. |
| Extractable sources | 23 | All sources produced text for RAG ingestion. |
| Fallback extraction | 1 | `ISO-7726-1998.pdf` uses `pdfminer.six` fallback. |
| Source errors | 0 | Latest RAG rebuild completed with no source errors. |
| Metadata entries | 23 | Every current raw PDF has an entry in `data/source_metadata.json`. |
| Metadata missing | 0 | Some entries still have blank direct URLs where the PDF did not expose them clearly. |

### Current Raw PDFs

| File | Pages | Size MB | Text | Current status |
| --- | ---: | ---: | --- | --- |
| `230113-solution_booklet-building_envelope_retrofit.pdf` | 47 | 25.37 | Yes | Ready |
| `55_2017_d_20200731.pdf` | 23 | 2.13 | Yes | Ready |
| `62_1_2013_p_20150707.pdf` | 10 | 0.63 | Yes | Ready |
| `ASHRAE-Standard-55.pdf` | 76 | 5.65 | Yes | Ready |
| `assessment-of-the-first-long-term-renovation-strategies.pdf` | 191 | 3.63 | Yes | Ready |
| `CIBSE TM59 2017 Overheating.pdf` | 17 | 1.79 | Yes | Ready |
| `D.B3--Handbook.pdf` | 54 | 2.56 | Yes | Ready |
| `DBHE.pdf` | 56 | 0.51 | Yes | Ready |
| `EBC_Annex_50_Retrofit_Strategies_Design_Guide.pdf` | 109 | 5.48 | Yes | Ready |
| `edg_89_cp_edited_2.pdf` | 17 | 9.92 | Yes | Ready |
| `en_ltserb.pdf` | 476 | 20.92 | Yes | Ready |
| `enerphit_renovating_with_passive_house_components (1).pdf` | 112 | 2.62 | Yes | Ready |
| `ES2010-90036_final.pdf` | 7 | 0.29 | Yes | Ready |
| `EuroPHit_brochure_final_PHI.pdf` | 77 | 1.77 | Yes | Ready |
| `ilide.info-uni-en-16798-1-note-1-pr_df2e0b2e6672cb314bba3e706150d616.pdf` | 11 | 2.59 | Yes | Ready |
| `ISO-7243-2017.pdf` | 11 | 0.40 | Yes | Ready |
| `ISO-7726-1998.pdf` | 15 | 0.66 | Yes | Ready via pdfminer fallback |
| `lbnl-6131e.pdf` | 19 | 10.16 | Yes | Ready |
| `PassivhausDesignersManualHopfe.pdf` | 346 | 21.57 | Yes | Ready |
| `Renovation-Strategies-EU-BPIE-2014.pdf` | 68 | 2.46 | Yes | Ready |
| `Retrofit-Playbook.pdf` | 81 | 7.34 | Yes | Ready |
| `scis_solution_booklet_building_envelope_retrofit.pdf` | 47 | 5.30 | Yes | Ready |
| `ta cctp 9imc fullpaper holisticstrategies final.pdf` | 12 | 0.56 | Yes | Ready |

### Metadata Coverage

All current raw PDFs have metadata entries in `data/source_metadata.json`.

```text
230113-solution_booklet-building_envelope_retrofit.pdf
55_2017_d_20200731.pdf
62_1_2013_p_20150707.pdf
ASHRAE-Standard-55.pdf
assessment-of-the-first-long-term-renovation-strategies.pdf
CIBSE TM59 2017 Overheating.pdf
D.B3--Handbook.pdf
DBHE.pdf
EBC_Annex_50_Retrofit_Strategies_Design_Guide.pdf
edg_89_cp_edited_2.pdf
en_ltserb.pdf
enerphit_renovating_with_passive_house_components (1).pdf
ES2010-90036_final.pdf
EuroPHit_brochure_final_PHI.pdf
ilide.info-uni-en-16798-1-note-1-pr_df2e0b2e6672cb314bba3e706150d616.pdf
ISO-7243-2017.pdf
ISO-7726-1998.pdf
lbnl-6131e.pdf
PassivhausDesignersManualHopfe.pdf
Renovation-Strategies-EU-BPIE-2014.pdf
Retrofit-Playbook.pdf
scis_solution_booklet_building_envelope_retrofit.pdf
ta cctp 9imc fullpaper holisticstrategies final.pdf
```

### Required Metadata Fields

Each source should have this shape in `data/source_metadata.json`:

```json
{
  "filename.pdf": {
    "source_id": "SHORT_STABLE_ID",
    "source_title": "Full source title",
    "authors": "Author, institution, or standards body",
    "year": 2026,
    "document_type": "design_code | standard | design_guide | policy | research_paper | retrofit_manual",
    "citation": "Formal citation text.",
    "doi_or_url": "https://..."
  }
}
```

### Priority Gaps

1. Add exact source URLs where currently blank.
2. Keep sources grouped conceptually during retrieval: standards, thermal comfort, ventilation, overheating, retrofit manuals, policy, and research evidence.
3. Rebuild the RAG index after adding, replacing, or removing any raw PDF.

### Validation Commands

Validate source extraction using the same loader as the RAG indexer:

```powershell
@'
from rag_engine.source_catalog import discover_sources
from rag_engine.document_loader import extract_pages

for source in discover_sources():
    pages = extract_pages(source)
    sample = "".join(page["text"] for page in pages[:2])
    print(source["source"], len(pages), bool(sample.strip()))
'@ | .\.venv\Scripts\python.exe -
```

Rebuild RAG index:

```powershell
.\.venv\Scripts\python.exe -m rag_engine.build_index
```

---

## Risk Map Data Inventory


This file tracks the datasets currently used or staged for the HVRA Risk Map. The canonical source metadata file is:

```text
risk_map/dataset/source_metadata.json
```

Use this inventory for quick human review. Use `source_metadata.json` for machine-readable citation, license, CRS, and provenance fields.

### Current Coverage

| Category | Status | Local files | Purpose |
| --- | --- | --- | --- |
| EPW weather | Available | `ESP_Barcelona.081810_SWEC.epw`, `ESP_CT_Barcelona-El.Prat.AP.081810_TMYx.2011-2025.zip` | Outdoor climate, peak temperature, humidity, solar radiation, wind speed, night temperature. |
| MeteoCat weather | Available | `2020_MeteoCat_Estacions.csv`, `2025_MeteoCat_Detall_Estacions.csv` | Local station metadata and observed weather records. |
| Administrative boundaries | Available | `BCN_UNITATS_ADM.zip` | District, neighbourhood, or administrative spatial lookup. |
| Tree inventory | Available | `ab_vw_arbrat_geometries.csv` | Local tree count and nearby canopy proxy. |
| Vegetation cover | Available | `2017_vegetacio.gpkg` | Vegetation / NDVI-style local cooling proxy. |
| Building footprints | Available | `cataluna-260528-free.gpkg.zip`, `cataluna-260528-free.shp.zip`, `cataluna-260528.osm.pbf`, `cataluna-260530-free.gpkg.zip` | Surrounding building geometry and urban density context. |
| Building heights | Available | `MTM_GPKG_alcades.zip` | Surrounding obstruction height and street-canyon context. Actual filename contains the accented form `alcades`. |
| Cooling refuges | Available | `2017_cobertura_espaisrefugi.gpkg`, `2017_equip_refugi.gpkg`, `2017_parcs_refugi.gpkg`, `2017_vulnera_espaisrefugi.gpkg` | Access to cooling refuges, parks, and refuge coverage. |
| Vulnerability | Available | `2017_factors_vulnera.gpkg`, `2017_vulnera_espaisrefugi.gpkg`, `ate_vulnera_75plus_od.gpkg` | Vulnerable population and social exposure context. |
| Heat-exposed population | Available | `2018_ate_densitat_75plus_od.gpkg` | Elderly exposed-population density for heat-risk weighting. |
| Heat-exposed facilities | Available | `ate_equip_20-34_od.gpkg`, `ate_equip_35-74_od.gpkg` | Supplementary age-group exposure/facility layers. |
| Thermal comfort reference | Available | `confort_termic_od.gpkg` | Outdoor thermal comfort / heat reference layer. |
| Research supplement | Available | `ijerph-17-02553-s001.zip` | Supporting heat-risk or UHI evidence. Needs extraction into structured values if used computationally. |
| Infrared City context | Available | `infrared_city/infrared_city_context.json` | Site microclimate context: solar, sun hours, wind, sky-view factor, UTCI. |

### Validated Layers

These GeoPackages were opened and inspected successfully.

| File | Layer | Features | Key fields |
| --- | --- | ---: | --- |
| `2017_cobertura_espaisrefugi.gpkg` | `2017_cobertura_espaisrefugi` | 308 | `ToBreak` |
| `2017_equip_refugi.gpkg` | `2017_equip_refugi` | 77 | `nom`, `carrer`, `barri`, `districte` |
| `2017_parcs_refugi.gpkg` | `2017_parcs_refugi` | 49 | `Nom`, `Districte`, `Tipus`, `Area_Ha` |
| `2017_vulnera_espaisrefugi.gpkg` | `2017_vulnera_espaisrefugi` | 77 | `SUM_pob75` |
| `2017_factors_vulnera.gpkg` | `2017_factors_vulnera` | 1061 | `Rec_CP1` |
| `ate_vulnera_75plus_od.gpkg` | `ate_vulnera_75plus_od` | 1504 | `nRisc` |
| `confort_termic_od.gpkg` | `confort_termic_od` | 381 | `gridcode` |
| `2017_vegetacio.gpkg` | `2017_vegetacio` | 1061 | `PercNDVINo` |
| `2018_ate_densitat_75plus_od.gpkg` | `ate_densitat_75plus_od` | 1708 | `d_75plus` |
| `ate_equip_20-34_od.gpkg` | `ate_equip_20-34_od` | 19 | `gridcode` |
| `ate_equip_35-74_od.gpkg` | `ate_equip_35-74_od` | 17 | `gridcode` |

### Still Needed

| Item | Priority | Notes |
| --- | --- | --- |
| Neighbourhood UHI deltas | High | Add a clean JSON or CSV such as `neighbourhood_uhi_deltas.json` with measured or cited UHI delta by neighbourhood. |
| Complete source metadata | High | Fill `source_metadata.json` with exact source URL, publisher, license, update date, CRS, and citation for every dataset. |
| Heatwave/design period definition | Medium | Define Barcelona heatwave week or standard summer design period used by the diagnosis and validation engines. |
| Fine obstruction details | Medium | Balconies, overhangs, awnings, window reveals, and facade-specific obstruction are not fully represented by city-scale datasets. |
| Building-specific user input | Required per case | Exact address or coordinates, floor level, room type, room height, window orientation, glazing, shading, and occupant vulnerability. |

### Source Metadata Requirements

Every dataset used in Risk Map calculations should have an entry in `risk_map/dataset/source_metadata.json`:

```json
{
  "local_file.ext": {
    "source_id": "SHORT_STABLE_ID",
    "source_title": "Human-readable dataset title",
    "publisher": "Dataset publisher",
    "year": 2026,
    "document_type": "gis_dataset",
    "local_file": "local_file.ext",
    "doi_or_url": "https://...",
    "license": "CC BY 4.0",
    "spatial_coverage": "Barcelona",
    "crs": "EPSG code or CRS notes",
    "update_date": "YYYY-MM-DD",
    "citation": "Formal citation or source statement"
  }
}
```

### Validation Commands

Quick inventory check:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from risk_map.data_loader import inventory_risk_map_sources; import json; print(json.dumps(inventory_risk_map_sources(Path('risk_map/dataset')), indent=2, ensure_ascii=False))"
```

Compile check:

```powershell
.\.venv\Scripts\python.exe -m py_compile risk_map\data_loader.py
```

---

## Retrofit Strategy Catalogue


`data/input/strategy_catalogue.json` is the static retrofit strategy source of truth. The LLM ranks strategies from this catalogue after RAG/manual evidence checking; it should not invent strategy IDs or thermal delta values.

### Current Catalogue

| ID | Plain name | Category | Scope |
| --- | --- | --- | --- |
| external_shading_louvers | External louvers / brise-soleil | shading | room |
| internal_blinds | Internal roller blinds | shading | room |
| solar_control_glazing | Solar control glazing replacement | glazing | room |
| green_pergola | Green pergola / climbing vegetation | green_shading | room |
| window_enlargement | Window enlargement | ventilation | room |
| interior_opening_improvement | Interior opening / transom addition | ventilation | room |
| stack_effect_roof_vent | Stack-effect roof vent | ventilation | room |
| night_purge_ventilation | Night purge ventilation behavioural protocol | ventilation | room |
| external_wall_insulation_etics | External wall insulation - ETICS system | envelope | room |
| roof_insulation | Roof insulation membrane | envelope | room |
| cool_roof_coating | Cool roof reflective coating | cool_surface | room |
| phase_change_materials | Phase-change materials in wall assembly | thermal_mass | room |
| courtyard_greening | Courtyard greening | urban_greening | building_shared |
| shared_cooling_refuge | Shared ground-floor cooling refuge | resilience | portfolio |
| street_tree_canopy | Street tree canopy on SW elevation | urban_greening | urban_context |
| internal_wall_insulation | Internal wall insulation | envelope | room |
| wall_insulation_reinforcement_layer | Wall insulation reinforcement layer | envelope | room |
| cool_facade_paint | Cool / reflective facade paint | cool_surface | room |
| window_external_shutters | External shutters | shading | room |
| cross_ventilation_behaviour | Cross-ventilation behavioural protocol | ventilation | room |

### Pipeline Use

1. `rag_engine/manual_checker.py` loads this catalogue.
2. User constraints split catalogue entries into eligible and restricted options.
3. Hybrid retrieval attaches RAG evidence to each strategy.
4. `llm_agent/agent.py` ranks eligible strategies into `data/intermediate/strategy_options.json`.
5. `validation_engine/retrofit_effects.py` maps each strategy ID to a screening effect profile.
6. `validation_engine/thermal_validation.py` calculates before/after indicators and benchmark results.

### Notes

The catalogue currently contains 20 strategies. The delta-T, cost, and carbon fields are screening assumptions from the reference library. They are not a substitute for dynamic simulation or product-specific design data.




---

## Thermal Combo Screening Method


### Purpose

This note defines the screening-level method HVRA can use when a retrofit option contains more than one strategy, such as shading plus night ventilation plus wall insulation. It is intended for early option comparison and checkpoint review, not final compliance or detailed design.

There is no official standard that supports a universal rule such as:

```text
Delta T package = Delta T strategy A + Delta T strategy B + Delta T strategy C
```

That naive sum can overestimate performance because strategies interact. The defensible approach is to start from a simple room heat balance and calculate the package effect from the heat drivers that each strategy changes.

### Heat Balance Basis

A simplified free-running room balance can be written as:

```text
T_indoor = T_outdoor + Q_gain / H_total
```

Where:

```text
Q_gain  = Q_solar + Q_internal + Q_envelope_gain
H_total = H_vent + H_trans + H_storage_effective
```

For screening, HVRA groups retrofit effects into four drivers:

```text
solar gain
ventilation deficit
envelope heat transfer
nocturnal recovery / storage
```

This is aligned with the logic of ISO 13790 / 5R1C, ISO 52016-1 hourly calculation, and heat-balance simulation tools such as EnergyPlus, but it is not a substitute for those full calculations.

### Why Naive Additivity Fails

Strategies affect different parts of the heat balance:

```text
Shading / solar-control glazing -> reduces solar gains
Insulation / thermal lining     -> changes envelope heat transfer
Night purge / cross ventilation -> changes ventilation heat removal
PCM / thermal mass              -> changes storage and timing
```

Gain-side reductions can be approximately additive in watts. Temperature reductions are not generally additive, because the denominator and storage terms change the resulting indoor temperature.

### First-Order Screening Method

Around the baseline room state:

```text
T = T_outdoor + Q / H
```

A small package change can be approximated with a first-order Taylor expansion:

```text
Delta T_reduction = Delta Q_reduction / H_baseline
                  + Q_baseline * Delta H_effective / H_baseline^2
```

Where:

```text
Delta T_reduction   positive value means indoor temperature is reduced
Delta Q_reduction   reduction in gains, W
Delta H_effective   effective increase in heat-removal or damping capacity, W/K
Q_baseline          baseline heat gain, W
H_baseline          baseline heat-transfer/removal coefficient, W/K
```

Important sign convention:

```text
Positive Delta Q_reduction reduces indoor temperature.
Positive Delta H_effective increases the room's ability to reject or damp heat.
```

For insulation in summer, do not blindly treat reduced U-value as increased heat loss. Its effect depends on whether the outside/surface condition is hotter than the room and whether the room needs night-time heat rejection. In HVRA screening, wall insulation and reinforced lining are therefore represented through conservative envelope and nocturnal-recovery multipliers, not as a simple additive denominator term.

### Backend Driver Method

When the backend does not have enough physical data for watts and W/K, use normalized drivers:

```text
baseline_pressure =
    solar_gain_score          * w_solar
  + envelope_score            * w_envelope
  + ventilation_deficit_score * w_ventilation
  + nocturnal_recovery_score  * w_night
```

For a package:

```text
solar_new      = solar_gain_score          * combined_solar_multiplier
envelope_new   = envelope_score            * combined_envelope_multiplier
vent_new       = ventilation_deficit_score * combined_ventilation_multiplier
night_new      = nocturnal_recovery_score  * combined_night_multiplier
```

Then:

```text
proposed_pressure =
    solar_new    * w_solar
  + envelope_new * w_envelope
  + vent_new     * w_ventilation
  + night_new    * w_night
```

And:

```text
pressure_reduction_ratio = (baseline_pressure - proposed_pressure) / baseline_pressure
```

This ratio can drive proposed indicators such as peak operative temperature, overheating hours, and composite room risk score with conservative caps.

### Combining Multipliers

For strategies affecting the same driver, combine multipliers multiplicatively:

```text
combined_solar_multiplier = m_solar_1 * m_solar_2 * ...
```

Then apply floors/caps:

```text
minimum solar multiplier:       0.25
minimum envelope multiplier:    0.45
minimum ventilation multiplier: 0.35
minimum nocturnal multiplier:   0.35
```

These floors prevent an unrealistic package from eliminating an entire risk driver.

### Temperature Reduction Cap

For screening:

```text
maximum peak operative temperature reduction = 5.0 C
maximum WBGT reduction                       = 2.0 C-WBGT
maximum overheating-hours reduction          = 70 percent
minimum final risk score                     = 0.15
```

If the calculated package exceeds these limits, HVRA should flag the result as requiring simulation or product-specific engineering evidence.

### Confidence Rule

Combo confidence should be lower than the best single-strategy confidence unless combo-specific evidence exists:

```text
combo_confidence = average(single_strategy_confidences) - 0.05 * (number_of_strategies - 1)
```

Increase confidence only when RAG evidence directly supports the combined package.

### Valid Use

Appropriate for:

```text
early-stage option comparison
checkpoint review
ranking three candidate packages
explaining expected direction of improvement
```

Not appropriate for:

```text
regulatory compliance
final comfort certification
product specification
large claimed reductions above 5 C
HVAC-controlled rooms without a separate model
```

### Escalation Rule

Escalate to ISO 52016-1 calculation, EnergyPlus, IESVE, DesignBuilder, or equivalent dynamic simulation when:

```text
claimed peak reduction exceeds 5 C
three or more loss/storage-side strategies are combined
thermal mass or PCM is central to the result
the room has active HVAC
the user needs compliance-grade evidence
```

### References

| Source | Relevance |
| --- | --- |
| ISO 13790 / EN ISO 13790 | 5R1C thermal network basis for simplified heat balance |
| ISO 52016-1 | Successor method for hourly zone temperature and load calculation |
| EnergyPlus Engineering Reference | Full heat-balance simulation reference |
| CIBSE Guide A | Practical building-physics guidance for comfort and heat gains |

### HVRA Position

HVRA should not present an additive Delta T sum as an official formula. It should present combined retrofit performance as a screening estimate derived from heat-balance logic, normalized risk drivers, conservative caps, and confidence gates.

---

## Interface Contract


This document describes the current interface contract for HVRA. It replaces the older interface blueprint notes.

### Purpose

The interface is a stage-aware review shell for the backend engines. It does not own the calculations. It gathers user inputs, triggers the backend, displays generated inspection views, and pauses at checkpoints where the user must confirm or adjust data before the next engine runs.

### Source Of Truth

```text
canonical JSON -> backend engines
canonical JSON -> generated room view
canonical JSON -> generated KG view
canonical JSON -> LLM checkpoint prompt
canonical JSON -> final report
```

Generated HTML/KG views are views. JSON remains canonical. Neo4j is optional and not required for the current test setup.

### Active UI Phases

```text
phase 1: input
  chat-first case setup
  collects address or coordinates, room type, area, height, pano image, window view, resident profile, and comfort note

phase 1.5: site context
  chat + precomputed risk-map view
  user checks the selected location, map context, and environmental layers before room verification

phase 2: spatial check
  chat + room model
  user confirms wall orientation and window inclusion after LGTNet geometry is visible
  orientation, room check, and surface controls live in one left-side room-check panel
  no validation panel
  no wall diagnosis panel

phase 3: review
  top three retrofit option buttons + chat + room / links / check / report views
  diagnosis, problem map, KG, retrofit validation, and report review are visible
  orientation and room check controls are hidden
```

The test-only phase URLs are:

```text
/?phase=input
/?phase=site
/?phase=spatial
/?phase=review
```

The phase QA page is:

```text
http://localhost:5173/phase_check.html
```

The production-style app is fixed to a compact 60 percent visual scale. The scale buttons only appear in `phase_check.html` for QA comparison; they are not part of the normal website.


### Backend / Frontend Architecture

HVRA runs as two development servers plus generated backend views.

```text
React frontend   -> http://127.0.0.1:5173
FastAPI backend  -> http://127.0.0.1:8010
Generated views  -> served by FastAPI from data/output/
```

The React frontend is the user-facing control and review shell. It does not calculate heat risk, run LGTNet, write a live Neo4j graph, or validate retrofit performance directly. It collects user input, sends requests to FastAPI, displays status, and embeds generated room/KG/report views.

The FastAPI backend is the bridge between the interface and the backend engines. It receives form data and image uploads, writes canonical JSON input files, triggers `main.py` or checkpoint continuation, exposes generated files through static routes, and returns structured API responses to React.

#### Development Server Roles

| Server | Location | Role |
| --- | --- | --- |
| React / Vite | `interface/` | Browser UI, phase layout, chat shell, option buttons, embedded generated views. |
| FastAPI | `app.py` | API layer, pipeline trigger, file writer, checkpoint continuation, static generated-view server. |
| Backend engines | Python packages in root folders | Spatial, risk map, diagnosis, RAG, validation, local KG export, Gemini, report generation. |
| Generated HTML views | `data/output/` | Room viewer, KG viewer, validation view, final report view. |

#### Request Flow

```text
User action in React
  -> API request to FastAPI
  -> FastAPI writes/reads canonical JSON
  -> FastAPI runs pipeline stage or checkpoint action
  -> backend engine writes intermediate/output JSON
  -> backend exporters regenerate HTML views
  -> React polls status or reloads the relevant view
```

For example, when a user submits the first room description and images:

```text
React POST /api/chat
  -> FastAPI saves text + images
  -> FastAPI updates data/input/*.json
  -> FastAPI runs main.py until the spatial gate
  -> Spatial Engine writes spatial_index.json and room_3d_view.html
  -> FastAPI reports current_stage=spatial_vv
  -> React moves to phase 2 and displays the room model
```

When the user confirms room orientation in phase 2:

```text
room_3d_view.html saves orientation overrides
  -> POST /api/spatial/overrides
  -> FastAPI writes data/intermediate/spatial_user_overrides.json
  -> React/FastAPI continue the pipeline
  -> risk map, diagnosis, problem map, RAG, validation, local KG export, report run
  -> React moves to phase 3
```

#### React Responsibilities

React owns presentation and user interaction:

```text
phase state display
chat input box
image upload controls
spatial review iframe/embed
strategy option buttons
site context view, room / links / check / report view switching
loading/progress messaging
calling backend API endpoints
```

React should not own:

```text
thermal calculations
risk scoring
RAG retrieval
strategy validation
live Neo4j graph logic
LGTNet/SAM3 execution
canonical data mutation outside backend APIs
```

#### FastAPI Responsibilities

FastAPI owns coordination and persistence:

```text
accept user text and image uploads
write data/input/user_case.json
write data/input/building_info.json
write data/input/region_context.json
write data/input/retrofit_constraints.json
serve data/output files as static inspection views
read data/intermediate/pipeline_status.json
save spatial_user_overrides.json
trigger main.py or continue_from_checkpoint.py
return strategy options and checkpoint actions to React
```

The backend therefore acts as a controlled file/API bridge. This keeps all canonical pipeline state in JSON files and avoids letting the frontend silently modify calculation state.

#### Generated Views and Static Serving

The room viewer, KG viewer, validation view, and final report view are generated by backend exporters. React displays them, usually as embedded static pages or linked views.

```text
data/output/spatial/room_3d_view.html
  -> /static-views/spatial/room_3d_view.html

data/output/kg/kg_view.html
  -> /static-views/kg/kg_view.html

data/output/validation_view.html
  -> /static-views/validation_view.html

data/output/final_report_view.html
  -> /static-views/final_report_view.html
```

This separation is intentional. The generated views are inspection products of the backend. React is the stage-aware container that decides which view to show.

#### Phase State and Status

The frontend should derive stage state from backend status wherever possible:

```text
data/intermediate/pipeline_status.json
GET /api/status
```

This allows refresh/reopen behavior to be stable. During testing, the UI may also accept phase query parameters:

```text
/?phase=input
/?phase=spatial
/?phase=review
```

Those query parameters are QA tools, not the long-term source of truth.

#### Production Direction

The current setup is a development architecture:

```text
Vite dev server + FastAPI server + local generated files
```

A future deployable version could serve the built React app through FastAPI or another web server, while FastAPI continues to expose API routes and static generated views. The backend engine boundary should remain the same: React requests actions, FastAPI coordinates, engines write canonical JSON, generated views update from JSON.

### Backend API

#### `POST /api/chat`

Accepts multipart form data:

```text
text
room_type
facing_direction
room_area_m2
room_height_m
pano_image
perspective_image
```

Behavior:

```text
incomplete inputs -> current_stage=input_gathering
complete inputs -> run main.py until the next gate
spatial orientation missing -> current_stage=spatial_vv
completed pipeline -> current_stage=processing or complete status
```

#### `GET /api/status`

Returns the latest pipeline status from:

```text
data/intermediate/pipeline_status.json
```

The UI uses this to reopen in the correct phase after refresh.

#### `POST /api/spatial/overrides`

Writes:

```text
data/intermediate/spatial_user_overrides.json
```

Used by `room_3d_view.html` when the user clicks `save` or `continue`.

#### `GET /api/strategy-options`

Returns the top three validated retrofit options for phase 3:

```json
{
  "options": [
    {
      "rank": 1,
      "id": "night_purge_ventilation",
      "label": "option 1",
      "name": "Night purge ventilation routine",
      "status": "partial_pass",
      "confidence": "medium"
    }
  ]
}
```

The phase 3 visualization bar renders these as three buttons on the top-left. The `room`, `links`, `check`, and `report` buttons remain on the top-right, and each view updates according to the selected strategy option.

#### `POST /api/checkpoint/action`

Runs:

```text
continue_from_checkpoint.py
```

Used for later checkpoint continuation, especially strategy validation.

### Spatial Orientation Gate

LGTNet creates geometry first. Orientation is not trusted until the user confirms it in the room viewer.

Required user action in phase 2:

```text
1. open room view
2. select the main outside/window wall
3. assign direction to every wall
4. click save
5. the interface continues to phase 3 after the backend checkpoint finishes
```

Saved payload:

```text
data/intermediate/spatial_user_overrides.json
```

Required fields:

```json
{
  "stage": "spatial_vv",
  "orientation_confirmed": true,
  "orientation_overrides": [
    {
      "id": "ROOM_001_WALL_00",
      "wall_index": 0,
      "orientation": "SW",
      "is_external": true,
      "source": "user_confirmed_in_room_3d_view"
    }
  ]
}
```

Until orientation is confirmed, `main.py` stops before:

```text
risk map
spatial KG write
diagnosis
problem map
strategy validation
report generation
```

### Generated Views

Room view:

```text
data/output/spatial/room_3d_view.html
```

Modes:

```text
viewer_mode=spatial_vv
viewer_mode=review
```

Phase 2 uses:

```text
room_3d_view.html?viewer_mode=spatial_vv
```

Phase 3 uses:

```text
room_3d_view.html?viewer_mode=review
```

In review mode, the room viewer hides phase 2 controls:

```text
orientation
room check
```

KG view:

```text
data/output/kg/kg_view.html
```

Final report view:

```text
data/output/final_report_view.html
```

### QA Pages

Run the frontend:

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run\interface
npm run dev
```

Open:

```text
http://localhost:5173/format_check.html
http://localhost:5173/phase_check.html
```

`format_check.html` checks typography, labels, collapsible panels, and viewer formatting.

`phase_check.html` checks stage layout behavior one phase at a time.

### Design Rules

The interface follows a strict three-level type hierarchy:

```text
level 1: DM Mono, 10.5px, 400, 0.10em, tertiary ink
level 2: DM Sans, 13px, 400, primary ink
level 3: DM Mono, 10px, 400, tertiary ink
```

No other UI text sizes or weights should be introduced without updating this contract.

### Build Notes

Run Vite commands from the real project path:

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run\interface
npm run build
```

Do not run Vite through the `Desktop\Test` junction. Rollup may emit invalid relative chunk paths from that location.









