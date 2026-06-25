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

Fast full checkpoint smoke test with all expensive external calls mocked:

```powershell
.\.venv\Scripts\python.exe continue_from_checkpoint.py --llm --apply --mock-llm --mock-gemini --mock-neo4j
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

Clean and rebuild the semantic GraphRAG index. This deletes only generated RAG outputs, not raw PDFs or metadata:

```powershell
.\.venv\Scripts\python.exe -m rag_engine.build_index --clean
```

Rebuild without cleaning generated files:

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
data/processed/corpus_chunks.jsonl   semantic chunks
data/vector_db/chroma/              rebuilt vector index
docs/rag_sources_inventory.md
```

## Risk Map

Run the risk map integration test. This checks cached/live Infrared City availability, normalized sky-view factor units, and diagnosis propagation:

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

Risk-map visualisation is deactivated from the user-facing phase checker. The standalone visual experiment remains available only for development when the backend is running:

```text
http://127.0.0.1:8010/risk-map-3d-test/
```

## 3D Retrofit Test

Build the Phase 3 procedural 3D retrofit test view:

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run
.\.venv\Scripts\python.exe 3D_test\test\build_retrofit_room_test.py --biophilic-test --opening-type sliding_glass_door
```

When the backend API server is running, open the embedded route directly:

```text
http://127.0.0.1:8010/3d-test/test/retrofit_room_test.html
```

For standalone local viewing without the backend:

```powershell
.\.venv\Scripts\python.exe -m http.server 8123 -d .
```

```text
http://127.0.0.1:8123/3D_test/test/retrofit_room_test.html
```

Advanced GLB-ready asset planning and visualizer:

```powershell
.\.venv\Scripts\python.exe 3D_test\advanced\build_advanced_asset_plan.py --opening-type sliding_glass_door
.\.venv\Scripts\python.exe 3D_test\advanced\build_advanced_asset_view.py
```

```text
http://127.0.0.1:8123/3D_test/advanced/advanced_asset_view.html
```

3D test catalogue files:

```text
3D_test/catalogues/retrofit_strategy_visual_catalogue.json
3D_test/catalogues/plant_visual_catalogue.json
3D_test/test/retrofit_visual_plan.json
3D_test/test/retrofit_room_test.html
3D_test/advanced/advanced_asset_plan.json
```

## Perspective Image Test

Paused/deactivated for the current workflow. The final visual should come from the Phase 3 textured 3D room/component preview, not from a separate image-regeneration service.

Keep `perspective_test/` only as an experimental archive unless the project later reopens cloud image generation.

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

