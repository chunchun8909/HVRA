# HVRA Documentation

This folder contains the human-facing documentation for the HVRA backend and interface prototype.

## Start Here

| Document | Purpose |
| --- | --- |
| [HVRA Project Handbook](hvra_project_handbook.md) | Single combined project handbook containing all major documentation sections. |
| [System Overview](system_overview.md) | What HVRA does, which engines exist, and which ML/AI models are implemented. |
| [Pipeline](system_pipeline.md) | End-to-end stage order, checkpoint gates, and generated artifacts. |
| [Data Flow](data_flow.md) | How inputs, intermediate JSON, checkpoints, outputs, RAG files, and generated views are stored. |
| [Data Sources Inventory](data_sources_inventory.md) | Dataset inventory organized by implemented segment: spatial, risk map, RAG, strategy catalogue, and generated outputs. |
| [RAG Sources Inventory](rag_sources_inventory.md) | Raw PDF inventory, metadata coverage, extraction status, and RAG rebuild notes. |
| [Risk Map Data Inventory](risk_map_data_inventory.md) | GIS, EPW, Infrared City, and contextual heat-risk datasets. |
| [Strategy Catalogue](strategy_catalogue.md) | Static retrofit strategy catalogue and how it enters ranking/validation. |
| [Diagnosis Weighting](diagnosis_weighting.md) | Literature-informed heat-risk composite weights and rationale. |
| [Thermal Combo Screening](thermal_combo_screening.md) | Screening method for combined retrofit strategy effects. |
| [Interface Spec](interface_spec.md) | Current interface phases, formatting, and checkpoint review direction. |
| [Terminal Commands](terminal_commands.md) | Startup, test, RAG, risk map, KG, and recovery commands. |

## Canonical Principle

```text
canonical JSON -> generated Neo4j view
canonical JSON -> generated HTML views
canonical JSON -> LLM checkpoint prompt
canonical JSON -> report output
```

JSON files under `data/input/`, `data/intermediate/`, `data/checkpoints/`, and `data/output/` are the source of truth for current test runs. Neo4j and HTML are generated views for review and traceability.


