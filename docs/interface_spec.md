# HVRA Interface Contract

This document describes the current interface contract for HVRA. It replaces the older interface blueprint notes.

## Purpose

The interface is a stage-aware review shell for the backend engines. It does not own the calculations. It gathers user inputs, triggers the backend, displays generated inspection views, and pauses at checkpoints where the user must confirm or adjust data before the next engine runs.

## Source Of Truth

```text
canonical JSON -> backend engines
canonical JSON -> generated room view
canonical JSON -> generated KG view
canonical JSON -> LLM checkpoint prompt
canonical JSON -> final report
```

Generated HTML/KG views are views. JSON remains canonical. Neo4j is optional and not required for the current test setup.

## Active UI Phases

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


## Backend / Frontend Architecture

HVRA runs as two development servers plus generated backend views.

```text
React frontend   -> http://127.0.0.1:5173
FastAPI backend  -> http://127.0.0.1:8010
Generated views  -> served by FastAPI from data/output/
```

The React frontend is the user-facing control and review shell. It does not calculate heat risk, run LGTNet, write a live Neo4j graph, or validate retrofit performance directly. It collects user input, sends requests to FastAPI, displays status, and embeds generated room/KG/report views.

The FastAPI backend is the bridge between the interface and the backend engines. It receives form data and image uploads, writes canonical JSON input files, triggers `main.py` or checkpoint continuation, exposes generated files through static routes, and returns structured API responses to React.

### Development Server Roles

| Server | Location | Role |
| --- | --- | --- |
| React / Vite | `interface/` | Browser UI, phase layout, chat shell, option buttons, embedded generated views. |
| FastAPI | `app.py` | API layer, pipeline trigger, file writer, checkpoint continuation, static generated-view server. |
| Backend engines | Python packages in root folders | Spatial, risk map, diagnosis, RAG, validation, local KG export, Gemini, report generation. |
| Generated HTML views | `data/output/` | Room viewer, KG viewer, validation view, final report view. |

### Request Flow

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
  -> FastAPI runs main.py until the next checkpoint
  -> Risk Map prepares the site-context checkpoint payload
  -> Spatial Engine writes spatial_index.json and room_3d_view.html
  -> FastAPI reports current_stage=spatial_vv
  -> React shows phase 1.5 site context, then continues to phase 2 for room verification
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

### React Responsibilities

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

### FastAPI Responsibilities

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

### Generated Views and Static Serving

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

### Phase State and Status

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

### Production Direction

The current setup is a development architecture:

```text
Vite dev server + FastAPI server + local generated files
```

A future deployable version could serve the built React app through FastAPI or another web server, while FastAPI continues to expose API routes and static generated views. The backend engine boundary should remain the same: React requests actions, FastAPI coordinates, engines write canonical JSON, generated views update from JSON.

## Backend API

### `POST /api/chat`

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

### `GET /api/status`

Returns the latest pipeline status from:

```text
data/intermediate/pipeline_status.json
```

The UI uses this to reopen in the correct phase after refresh.

### `POST /api/spatial/overrides`

Writes:

```text
data/intermediate/spatial_user_overrides.json
```

Used by `room_3d_view.html` when the user clicks `save` or `continue`.

### `GET /api/strategy-options`

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

### `POST /api/checkpoint/action`

Runs:

```text
continue_from_checkpoint.py
```

Used for later checkpoint continuation, especially strategy validation.

## Spatial Orientation Gate

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

## Generated Views

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

Site context view:

```text
interface/public/risk_map_3d_test.html
```

The site context view is embedded by React in phase 1.5. It uses precomputed backend context and keeps map layers, analysis layers, and optional 3D buildings separate so the user can review the site before room diagnosis.

KG view:

```text
data/output/kg/kg_view.html
```

Final report view:

```text
data/output/final_report_view.html
```
## QA Pages

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

## Design Rules

The interface follows a strict three-level type hierarchy:

```text
level 1: DM Mono, 10.5px, 400, 0.10em, tertiary ink
level 2: DM Sans, 13px, 400, primary ink
level 3: DM Mono, 10px, 400, tertiary ink
```

No other UI text sizes or weights should be introduced without updating this contract.

## Build Notes

Run Vite commands from the real project path:

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run\interface
npm run build
```

Do not run Vite through the `Desktop\Test` junction. Rollup may emit invalid relative chunk paths from that location.






