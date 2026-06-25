# RAG Academic Source Categories

The RAG engine is fed with raw PDFs in `data/raw_pdfs/` and metadata in `data/source_metadata.json`. The current source set covers these academic and professional categories.

## Categories

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

## Current Status

See [RAG Sources Inventory](rag_sources_inventory.md) for the full raw PDF list, extraction count, fallback parsing note, and rebuild commands.

## Rule for Future Additions

Every new PDF should be added to:

```text
data/raw_pdfs/
data/source_metadata.json
```

Then rebuild:

```powershell
.\.venv\Scripts\python.exe -m rag_engine.build_index
```

