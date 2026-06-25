# Advanced 3D Asset Track

This folder is for the higher-quality 3D generation direction. Instead of drawing everything procedurally, it prepares a GLB-ready asset plan that can later drive curated realistic objects in the room viewer.

## Files

```text
advanced_asset_catalogue.json      quality-controlled retrofit asset catalogue
build_advanced_asset_plan.py       non-interactive suitability planner
advanced_asset_plan.json           generated output after running the planner
run_lgtnet_asset_registry_test.py  optional external asset-registry smoke test
lgtnet_asset_manifest.json         registry/placement manifest output
```

## Build The Advanced Plan

```powershell
.\.venv\Scripts\python.exe 3D_test\advanced\build_advanced_asset_plan.py --opening-type sliding_glass_door
```

The planner classifies realistic asset slots as:

```text
allowed      safe to send to future GLB rendering
conditional  possible, but needs user or technical confirmation
blocked      unsuitable for the current room/opening/constraint case
```

## Why This Exists

The final retrofit visual system should not randomly place attractive objects. It should first decide whether each object is suitable for the opening type, facade permission, balcony access, renter status, and old-building constraints. Only after that should it load or generate high-quality `.glb` assets.

## Visualize The Advanced Plan

Generate the visual page after building the asset plan:

```powershell
.\.venv\Scripts\python.exe 3D_test\advanced\build_advanced_asset_view.py
```

Open after serving the project root:

```text
http://127.0.0.1:8123/3D_test/advanced/advanced_asset_view.html
```

The page renders allowed and conditional assets as higher-quality placeholders while keeping future `.glb` asset slots visible in the decision trace.


## Biophilic Layer

The advanced catalogue now includes a broader biophilic interior layer: mixed plant clusters, daylight planter shelves, hanging planter rails, vertical plant ladders, preserved moss panels, and trellis climber screens. These are decision-gated by daylight, maintenance, damp risk, renter status, circulation clearance, and whether the selected opening is an active sliding/balcony door.

Plant assets are visual/restorative support, not the primary air-quality or thermal system. See `biophilic_design_notes.md` for the source notes and caveats.


## Placement Revision

The current viewer uses hosted-object placement rather than decorative free placement. Window-covering rails sit close to the interior wall face, planter shelves are raised and side-shifted away from active sliding-door paths, hanging planters are larger and rail-hosted, plant ladders and trellis screens sit close to the wall, and moss panels are excluded from this test branch.


## Hosted Placement Update

The advanced visualizer now uses a `sideHost` placement rule for wall-adjacent assets. This chooses the available wall strip beside the detected opening, then hosts shelves, hanging rails, plant ladders, and trellis screens close to the interior wall face instead of placing them randomly over the window.

Temporary support placeholders are intentional: brackets, rails, shelf plates, ladder frames, and trellis frames explain how future GLB assets should be mounted before realistic components are injected.


## Vegetation Variety Update

The plant catalogue now defines scale ranges and visual styles for mini, small, medium, large, and trailing vegetation. The advanced viewer renders different plant habits rather than repeating one generic plant: tall palm, small tree, broadleaf cluster, fern, spider/grass form, trailing vine, and succulent/rosette shelf plants.


## Design-Significant Vegetation Scale

The 3D test now scales vegetation as a visible retrofit layer rather than small decoration. Tiny shelf plants are treated as secondary details; main biophilic options should be large enough to read in the room model, such as floor clusters, vertical plant ladders, hanging greenery, or trellis planting.


## Indoor Wall-Frame Correction

The advanced viewer now uses a shared wall-frame transform for the opening, insulation preview, and all wall-hosted assets. Local `+Z` is forced to point into the indoor room space, so shelves, rails, trellis panels, and plants should no longer flip to the outdoor side or drift through the glazing.
