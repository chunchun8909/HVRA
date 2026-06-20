# HVRA Terminal Commands

Use these commands from PowerShell. Prefer the real project folder, not the `Desktop\Test` junction, especially for the interface.

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run
```

## Backend API

Start the HVRA API:

```powershell
.\.venv\Scripts\python.exe app.py
```

Default backend URL:

```text
http://127.0.0.1:8010
```

Check backend status:

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8010/api/status -UseBasicParsing
```

Check that the room-check Continue route exists:

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8010/openapi.json -UseBasicParsing
```

If port `8010` is already in use, the backend is probably already running. To restart it:

```powershell
$owners = Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($owner in $owners) { Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue }
.\.venv\Scripts\python.exe app.py
```

## Frontend Interface

Start the interface:

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run\interface
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

Force specific phases:

```text
http://127.0.0.1:5173/?phase=input
http://127.0.0.1:5173/?phase=site
http://127.0.0.1:5173/?phase=spatial
http://127.0.0.1:5173/?phase=review
```

Format and phase check pages:

```text
http://127.0.0.1:5173/format_check.html
http://127.0.0.1:5173/phase_check.html
```

Build the interface:

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run\interface
npm run build
```

## Full Pipeline

Run the main pipeline:

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run
.\.venv\Scripts\python.exe main.py
```

Continue after checkpoint with LLM enabled:

```powershell
.\.venv\Scripts\python.exe continue_from_checkpoint.py --llm --apply
```

Continue with Gemini mocked and local/mock KG mode:

```powershell
.\.venv\Scripts\python.exe continue_from_checkpoint.py --llm --apply --mock-gemini --mock-neo4j
```

## Spatial Room Check

Regenerate the room viewer from the latest spatial index:

```powershell
.\.venv\Scripts\python.exe -c "import json; from pathlib import Path; from spatial_engine.room_viewer import export_room_view; model=json.loads(Path('data/intermediate/spatial_index_with_overrides.json').read_text(encoding='utf-8')); print(export_room_view(model, Path('data/output/spatial/room_3d_view.html')))"
```

Open the generated room view through the backend:

```text
http://127.0.0.1:8010/static-views/spatial/room_3d_view.html
```

## Knowledge Graph View

Current default uses local generated KG JSON/HTML. Neo4j is not required unless you explicitly set `USE_MOCK_NEO4J=false`.

Regenerate the KG HTML view:

```powershell
.\.venv\Scripts\python.exe scripts\export_kg_view.py
```

Open:

```text
http://127.0.0.1:8010/static-views/kg/kg_view.html
```

## RAG

Rebuild the RAG index:

```powershell
.\.venv\Scripts\python.exe -m rag_engine.build_index
```

Run a RAG query:

```powershell
.\.venv\Scripts\python.exe -m rag_engine.query_rag "night overheating external shading" --top-k 3
```

Main RAG source files:

```text
data/raw_pdfs/
data/source_metadata.json
data/processed/corpus_pages.jsonl
data/processed/corpus_chunks.jsonl
data/vector_db/chroma/
docs/rag_sources_inventory.md
```

## Risk Map

Run the risk map integration test:

```powershell
.\.venv\Scripts\python.exe tests\test_risk_map_integration.py
```

Show the risk map dataset inventory:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from risk_map.data_loader import inventory_risk_map_sources; import json; print(json.dumps(inventory_risk_map_sources(Path('risk_map/dataset')), indent=2, ensure_ascii=False))"
```

Risk map source files:

```text
risk_map/dataset/
risk_map/dataset/source_metadata.json
docs/risk_map_data_inventory.md
```

## Code Checks

Compile main Python modules:

```powershell
.\.venv\Scripts\python.exe -m compileall checkpoint_engine diagnosis_engine knowledge_graph llm_agent rag_engine risk_map spatial_engine validation_engine main.py continue_from_checkpoint.py scripts\export_kg_view.py
```

Run selected smoke checks:

```powershell
.\.venv\Scripts\python.exe tests\test_risk_map_integration.py
.\.venv\Scripts\python.exe -m rag_engine.query_rag "external shading overheating" --top-k 2
```

## Common Issues

If `8010` says it is already in use:

```text
The backend is already running, or an old backend is stuck.
Use the restart command in the Backend API section.
```

If the interface still looks old:

```text
Hard refresh the browser with Ctrl + Shift + R.
Use http://127.0.0.1:5173 instead of a stale localhost tab.
```

If the interface says it cannot reach the backend:

```text
Start the backend first, then start the frontend.
Backend:  http://127.0.0.1:8010
Frontend: http://127.0.0.1:5173
```




