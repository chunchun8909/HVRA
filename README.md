# HVRA Test Run

HVRA is a modular backend prototype for a Heat Vulnerability Retrofit Assistant. It combines image-based room understanding, deterministic heat-risk diagnosis, local RAG/manual checking, Neo4j graph traceability, LLM checkpoint decisions, retrofit validation, and generated inspection views.

The repository is backend-first with a working stage-aware interface shell. The backend produces canonical JSON outputs and generated HTML views for visual verification; the interface drives input gathering and checkpoint review.

## Documentation

Start with the documentation hub:

```text
docs/README.md
```

Key docs:

| Document | Purpose |
| --- | --- |
| [HVRA Project Handbook](docs/hvra_project_handbook.md) | Single combined project handoff/reference document. |
| [System Overview](docs/system_overview.md) | Engines, ML/AI models, interface phases. |
| [Pipeline](docs/system_pipeline.md) | Full backend pipeline and checkpoint flow. |
| [Data Flow](docs/data_flow.md) | Input, intermediate, checkpoint, and output file structure. |
| [Data Sources Inventory](docs/data_sources_inventory.md) | Data sources organized by implemented segment. |
| [RAG Academic Sources](docs/rag_academic_sources.md) | Types of academic/professional sources feeding RAG. |
| [Strategy Catalogue](docs/strategy_catalogue.md) | Retrofit strategy catalogue. |
| [Terminal Commands](docs/terminal_commands.md) | Startup, testing, RAG, and recovery commands. |

## Current Capability

- Real or mock Ollama LLM coordination.
- Real or mock Neo4j graph writing.
- Real LGTNet room layout extraction with scaling.
- Real SAM3 window/component detection when the external SAM3 environment is available.
- EPW-based risk map and climate context.
- Optional Infrared City Risk Map assist from cached API/export results.
- Deterministic diagnosis calculations.
- Problem map assignment to room surfaces.
- Local RAG/manual checking.
- Retrofit option validation against benchmark gates.
- Combo retrofit screening method documented in [Thermal Combo Screening](docs/thermal_combo_screening.md).
- Checkpoint packages for spatial V&V and strategy validation.
- Interactive room viewer and KG viewer.
- Stage-aware React/FastAPI interface with phase QA pages.
- Final JSON, Markdown, and HTML report export.

## Clean Repository Layout

```text
hvra_test_run/
  README.md                       GitHub entry point
  main.py                         full pipeline orchestrator
  app.py                          FastAPI adapter for the interface
  continue_from_checkpoint.py     checkpoint continuation command
  requirements.txt                Python dependencies
  docs/                           project documentation hub
  scripts/                        helper scripts
  tests/                          smoke/integration tests
  checkpoint_engine/              checkpoint packages, LLM decision routing
  diagnosis_engine/               deterministic heat-risk calculations
  gemini_engine/                  visual prompt and mock/real Gemini layer
  knowledge_graph/                Neo4j writers and HTML KG visualizer
  llm_agent/                      Ollama prompts, clients, schema checks
  rag_engine/                     document loading, retrieval, manual checking
  report_engine/                  final report compilation/export
  risk_map/                       EPW/urban context loading
  spatial_engine/                 LGTNet, scaling, SAM3, room viewer
  utils/                          config, file IO, logging
  validation_engine/              retrofit validation, combo screening, benchmark gates
  interface/                      React interface and QA pages
  data/                           input, intermediate, output, RAG, and checkpoint data
```

## Quick Start

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run backend API:

```powershell
.\.venv\Scripts\python.exe app.py
```

Run frontend:

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run\interface
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

Run full pipeline:

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run
.\.venv\Scripts\python.exe main.py
```

Continue after checkpoint:

```powershell
.\.venv\Scripts\python.exe continue_from_checkpoint.py --llm --apply
```

More commands are in [Terminal Commands](docs/terminal_commands.md).

## Inputs

Required JSON inputs:

```text
data/input/user_case.json
data/input/building_info.json
data/input/region_context.json
data/input/retrofit_constraints.json
data/input/strategy_catalogue.json
```

Image inputs:

```text
data/input/images/pano_image/
data/input/images/perspective_image/
```

RAG inputs:

```text
data/raw_pdfs/
data/source_metadata.json
```

Risk map inputs:

```text
risk_map/dataset/
risk_map/dataset/source_metadata.json
```

## Generated Outputs

Important generated files:

```text
data/intermediate/*.json
data/checkpoints/*/*.json
data/output/final_report.json
data/output/final_report.md
data/output/spatial/room_3d_view.html
data/output/kg/kg_view.html
```

These are generated artifacts and should normally stay out of git.

## GitHub Notes

Before pushing:

- Keep `.env` out of git.
- Keep `.venv/` out of git.
- Keep generated `data/intermediate/`, `data/checkpoints/`, `data/output/`, `data/vector_db/`, and `data/raw_pdfs/` out of git.
- Commit source code, docs, config examples, and `.gitkeep` placeholders only.


