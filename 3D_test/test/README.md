# 3D Procedural Test Track

This folder contains the stable, fast visual smoke tests. It is intentionally procedural: the geometry is simple, but it is useful for testing room placement, wall targeting, opacity, strategy masks, and suitability rules.

## Main Test

```powershell
.\.venv\Scripts\python.exe 3D_test\test\build_retrofit_room_test.py --biophilic-test --opening-type sliding_glass_door
```

Generated files:

```text
3D_test/test/retrofit_visual_plan.json
3D_test/test/retrofit_room_test.html
```

Serve from the project root:

```powershell
.\.venv\Scripts\python.exe -m http.server 8123 -d .
```

Open:

```text
http://127.0.0.1:8123/3D_test/test/retrofit_room_test.html
```

## What This Track Tests

- Current LGTNet room geometry
- Retrofit option placement
- Window and wall targeting
- Sliding-glass-door versus window suitability
- Procedural curtains, blinds, shades, and plant proxies
- Boundary rules for renter, old-building, facade, balcony, and roof constraints

## Phase 3 Interface Integration

The React Phase 3 review view embeds this test through the backend route:

```text
http://127.0.0.1:8010/3d-test/test/retrofit_room_test.html
```

This page is a development reference for tested retrofit components and placement rules. The production Phase 3 `room` view should remain `room_3d_view.html`; selected `strategy_id` or `strategy_ids` are passed to that room viewer so these tested components can be integrated there without replacing the room iframe.
