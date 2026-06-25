# Risk Map 3D Visual Test

Standalone visual checkpoint for the Risk Map stage. It checks whether site-context data is visible before the room/spatial phase continues.

## Location

```text
interface/public/interface/risk_map_3d_test/
```

## Preferred Route

Run the FastAPI backend and open:

```text
http://127.0.0.1:8010/risk-map-3d-test/
```

The page now tries the backend first:

```text
/api/risk-map/context
```

If the backend is not available, it falls back to the static snapshot:

```text
interface/public/interface/risk_map_3d_test/risk_map_context.json
```

## What The Visual Must Show

- Backend-connected Risk Map context when FastAPI is running.
- Numerical urban-analysis summaries for outdoor heat stress, air temperature, solar radiation, direct sun hours, low-wind/stagnation, sky-view obstruction, and canopy relief.
- A 500 m analysis boundary inside a 1000 m map context.
- OSM road/building contours aligned to the same local coordinate frame.
- 3D building massing from OSM-aligned footprints.
- Numerical Infrared City summary values in the side panel. Raster layers render only when a successful live Infrared refresh caches downsampled `merged_grid` cells.

## Current Verified Payload

The visual contract test currently verifies:

```text
Infrared heat exposure: 0.235
Sky-view factor: 0.572
Analysis layers: 7
Rendered raster cells: 0
3D buildings: 450
Road contours: 700
```

Sky-view factor is normalized to `0-1` before visualization and diagnosis. Older cached Infrared City exports may store it as a `0-100` percent value.

## Test Command

```powershell
cd C:\Users\Morris\OneDrive\Desktop\hvra_test_run
.\.venv\Scripts\python.exe tests\test_risk_map_visualization.py
```

## Notes

This is a screening visual, not a parcel-certified city model. The visual does not generate fake heat-map pixels from summary values. The provider now supports compact `merged_grid` cell caching, but the current snapshot is summary-only until a live Infrared refresh succeeds.



