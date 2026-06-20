# System Overview

HVRA is a backend-first Heat Vulnerability Retrofit Assistant. It helps inspect a room, diagnose heat-risk drivers, retrieve supporting design evidence, rank retrofit options, validate proposed improvements, and expose checkpoint views for user review.

## Implemented Engines

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

## ML / AI Models and External Systems

| Component | Current role | Mode |
| --- | --- | --- |
| LGTNet | Pano room layout extraction. | Real or mock via `.env` |
| SAM3 | Window/component segmentation on wall fragments. | External environment, real or fallback/mock |
| Ollama | Local LLM JSON reasoning for interpretation, ranking, review. | Real or mock |
| Gemini | Visual generation/prompt layer. | Real or mock |
| Chroma/vector retrieval | Local RAG vector store. | Local |
| Neo4j | Optional external graph database for future/live traceability. Current default uses mock/local KG export. | Disabled/mock |
| Infrared City | Optional microclimate API/context assist. | Real/cache/mock |

## Interface Phases

```text
Phase 1: user input through chat/instructions
Phase 1.5: site context / risk-map checkpoint
Phase 2: spatial V&V, wall orientation, window inclusion check
Phase 3: top three retrofit options, room/KG/check/report review
```

The system is designed so each checkpoint can update three synchronized views: canonical JSON, generated KG view, and HTML/3D review views. The interface now uses a compact 60 percent production scale, while `phase_check.html` keeps 50/60/75/100 scale buttons only for QA.


