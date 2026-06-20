# Risk Map 3D Visual Test

Standalone Risk Map backend visual test for searching a location and previewing implemented Risk Map data. This page is intentionally not wired into the full phase 1/2/3 interface flow yet.

Location:

```text
interface/public/interface/risk_map_3d_test/
```

Preferred backend-only test route:

```text
http://127.0.0.1:8010/risk-map-3d-test/
```

Backend endpoint used by the page:

```text
http://127.0.0.1:8010/api/risk-map/context
```

The backend response is assembled from:

```text
data/intermediate/risk_map.json
risk_map/dataset/source_metadata.json
```

## Current Visual Features

- Proper WebGL / Three.js 3D urban-context model.
- Drag to orbit the model.
- Right-drag to pan.
- Mouse wheel zooms.
- Layer toggles control heat pixels, buildings, trees, cooling refuge, and ground plane.
- 3D building blocks are generated from available building density, average height, and street-canyon indicators.
- Pixel heat-map grid is generated from peak dry-bulb temperature, solar radiation, UTCI, H/W ratio, tree canopy, and cooling-refuge access.
- Tree canopy and cooling-refuge markers are shown as separate spatial layers.
- Metrics that are not spatially meaningful are shown in the side panel instead of forcing them into the heat map.

## Important Limitation

This is a screening visual. The 3D building blocks are proportional urban-context proxies until parcel-level building footprints and exact heights are mapped into the viewer. The numerical data remains the source of truth.

## Optional Vite Route

If testing through Vite instead of FastAPI:

```text
http://127.0.0.1:5173/interface/risk_map_3d_test/
```

The page falls back to the local snapshot if the backend is not running:

```text
interface/public/interface/risk_map_3d_test/risk_map_context.json
```

## Three.js Runtime

Three.js is served locally by the FastAPI backend from:

```text
interface/node_modules/three
```

Backend static route:

```text
/vendor/three/
```

After changing this file, hard-refresh the browser with `Ctrl + F5` to avoid cached HTML.

## Map and City Context

The current WebGL view now includes:

- A square 250 m site frame.
- A satellite image base layer using Esri World Imagery tiles.
- A street-map base layer using OpenStreetMap tiles.
- A local 250 m building-height proxy model generated from current Risk Map metrics.
- A wider Barcelona proxy massing layer around the focus square.

Important: the wider Barcelona model is still a proxy massing layer, not yet exact city geometry. A true whole-Barcelona 3D model requires extracting and tiling building footprints/heights from the GIS/OSM/MTM datasets into a browser-friendly LOD format.

Google Maps imagery is not hard-coded here because it should be integrated through an official Google Maps API key and provider terms, not unofficial tile URLs.

## Current Correction

The visual has been reset to a map-first model:

- Default map tiles only; satellite is removed from the default test view.
- The Risk Map extent is a true 250 m x 250 m square in Web Mercator coordinates.
- 3D buildings are fetched from OpenStreetMap through Overpass for the selected Barcelona square.
- Building footprints and map tiles use the same coordinate conversion, so the geometry aligns to the map.
- If Overpass is unavailable, the page shows a fallback block set and marks the building source as `fallback` in the side panel.

## Whole-Barcelona 3D Note

Showing all Barcelona buildings as real 3D geometry should not be done by loading the entire city directly into this test page. The correct next step is a backend tiling/export pipeline from the available OSM/MTM/GIS building datasets into browser-ready geometry tiles, then loading only the visible tiles in the viewer.
