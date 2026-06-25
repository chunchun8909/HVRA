# 3D Test Workspace

This folder is split into two tracks so the current working prototype stays stable while the higher-quality asset pipeline is developed.

## Folder Structure

```text
3D_test/
  test/      quick procedural/proxy visual tests
  advanced/  GLB-ready asset planning and registry integration
```

## Test Track

Use `3D_test/test/` when you want to check geometry, placement, decision gates, and visual logic quickly. It uses procedural curtains, blinds, shades, plants, and overlays.

```powershell
.\.venv\Scripts\python.exe 3D_test\test\build_retrofit_room_test.py --biophilic-test --opening-type sliding_glass_door
```

Open after serving the project root:

```text
http://127.0.0.1:8123/3D_test/test/retrofit_room_test.html
```

## Advanced Track

Use `3D_test/advanced/` when you want to plan realistic web-optimized assets before GLB models are injected into the viewer. This track does not render by itself yet; it chooses suitable, conditional, and blocked assets based on the room opening and retrofit constraints.

```powershell
.\.venv\Scripts\python.exe 3D_test\advanced\build_advanced_asset_plan.py --opening-type sliding_glass_door
```

Output:

```text
3D_test/advanced/advanced_asset_plan.json
```

## Design Rule

The advanced track should only send `allowed` and reviewed `conditional` assets into future 3D rendering. Blocked assets stay visible in the JSON plan for traceability but should not be rendered as recommendations.

## Advanced Visualizer

After building the advanced asset plan, generate the visual page:

```powershell
.\.venv\Scripts\python.exe 3D_test\advanced\build_advanced_asset_view.py
```

Open:

```text
http://127.0.0.1:8123/3D_test/advanced/advanced_asset_view.html
```


## Biophilic Retrofit Notes

The advanced track includes expanded biophilic design logic. See `advanced/biophilic_design_notes.md` for the design basis, source notes, and the air-quality caveat.


## Test Catalogues

The 3D test branch now keeps visual strategy and plant selection rules separate from the renderer:

```text
3D_test/catalogues/retrofit_strategy_visual_catalogue.json
3D_test/catalogues/plant_visual_catalogue.json
```

These catalogues define how objects should be hosted before visual generation: wall/opening/rail/floor placement, door-clearance checks, old-building boundaries, renter constraints, and plant size classes. The main system should not import them yet; they are being tested here first.


## Hosted Placement Update

The advanced visualizer now uses a `sideHost` placement rule for wall-adjacent assets. This chooses the available wall strip beside the detected opening, then hosts shelves, hanging rails, plant ladders, and trellis screens close to the interior wall face instead of placing them randomly over the window.

Temporary support placeholders are intentional: brackets, rails, shelf plates, ladder frames, and trellis frames explain how future GLB assets should be mounted before realistic components are injected.


## Vegetation Variety Update

The plant catalogue now defines scale ranges and visual styles for mini, small, medium, large, and trailing vegetation. The advanced viewer renders different plant habits rather than repeating one generic plant: tall palm, small tree, broadleaf cluster, fern, spider/grass form, trailing vine, and succulent/rosette shelf plants.


## Design-Significant Vegetation Scale

The 3D test now scales vegetation as a visible retrofit layer rather than small decoration. Tiny shelf plants are treated as secondary details; main biophilic options should be large enough to read in the room model, such as floor clusters, vertical plant ladders, hanging greenery, or trellis planting.


## Indoor Wall-Frame Correction

The advanced viewer now uses a shared wall-frame transform for the opening, insulation preview, and all wall-hosted assets. Local `+Z` is forced to point into the indoor room space, so shelves, rails, trellis panels, and plants should no longer flip to the outdoor side or drift through the glazing.
