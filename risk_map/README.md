# Risk Map

The `risk_map/` module creates location and climate context for the diagnosis engine.

## Current Role

The risk map reads:

```text
data/input/region_context.json
risk_map/dataset/
```

and outputs:

```text
data/intermediate/risk_map.json
```

The diagnosis engine uses this output as site context. The Risk Map does not produce the final room-level heat-risk decision; it gathers location-specific climate, urban, vegetation, exposure, and cooling-access data for downstream diagnosis.

## Data Sources

Current supported local data:

- EPW weather archive for Barcelona.
- OSM/geospatial files when available.
- Tree inventory files when available.
- Optional cached Infrared City API export.
- UHI or thermal reference layers when available; synthetic UHI should only be a fallback when real neighbourhood deltas are missing.

## Infrared City Assist

Infrared City is treated as an optional Risk Map provider. Save an API/export payload here:

```text
risk_map/dataset/infrared_city/infrared_city_context.json
```

Enable it with:

```env
USE_INFRARED_CITY=true
INFRARED_CITY_API_KEY=your_key_here
INFRARED_CITY_BASE_URL=https://api.infrared.city/v2
INFRARED_CITY_CACHE_JSON=C:\Users\Morris\OneDrive\Desktop\hvra_test_run\risk_map\dataset\infrared_city\infrared_city_context.json
INFRARED_CITY_FORCE_REFRESH=false
```

The normalizer can use Infrared City grids/results for:

- solar radiation
- direct sun hours
- sky view factor
- wind speed
- UTCI / outdoor thermal comfort

These values update `risk_map.json` and are passed to the diagnosis engine as urban context. EPW and local datasets remain the traceable fallback.

When `INFRARED_CITY_FORCE_REFRESH=false`, the pipeline uses the cached JSON first and only calls the live API if no valid cache exists. Set it to `true` when you intentionally want to spend API tokens and refresh the cache.

Implementation references copied from the Infrared SDK examples live in:

```text
risk_map/infrared_reference/
```

## Missing Data To Complete

After Infrared City is enabled, the remaining missing items are mainly official/local datasets and traceability files:

```text
risk_map/dataset/weather/
  city_or_site.epw

risk_map/dataset/neighbourhoods/
  neighbourhood_boundaries.geojson

risk_map/dataset/uhi/
  neighbourhood_uhi_deltas.json

risk_map/dataset/trees/
  optional_tree_inventory_or_canopy.geojson

risk_map/dataset/infrared_city/
  infrared_city_context.json

risk_map/dataset/cooling_refuges/
  optional_parks_cooling_centres.geojson
```

Minimum useful fields:

- `weather`: EPW file for the exact city or closest airport/weather station.
- `neighbourhoods`: polygon geometry plus neighbourhood name or ID.
- `uhi`: neighbourhood name or ID, daytime/night-time UHI delta in degrees C, source citation.
- `infrared_city`: exported grids/results for solar radiation, direct sun hours, sky view factor, wind speed, and UTCI.
- `trees`: tree point/canopy polygon geometry, canopy radius or crown diameter if Infrared City vegetation layers are not enough.
- `cooling_refuges`: parks, cooling centres, or green/blue spaces with geometry and type.

If only one file can be added first, add the EPW. If three can be added, add EPW, neighbourhood UHI deltas, and the Infrared City export.

Current local dataset coverage:

```text
EPW/weather                    covered
MeteoCat station data          covered
neighbourhood/admin units      covered by BCN_UNITATS_ADM.zip
tree inventory                 covered by ab_vw_arbrat_geometries.csv
building footprints            covered by OSM Catalunya files
building heights               covered by MTM_GPKG_alÃ§ades.zip
cooling refuges                covered by *_refugi.gpkg files
vulnerability                  covered by *_vulnera*.gpkg files
thermal comfort reference      covered by confort_termic_od.gpkg
Infrared City context          covered by infrared_city_context.json
```

Still weakest item:

```text
neighbourhood_uhi_deltas.json
```

The `ijerph-17-02553-s001.zip` file may contain supporting UHI/heat-risk reference tables, but it still needs manual extraction into machine-readable JSON/CSV before the engine can use it directly.

## Source Metadata

RAG/manual PDFs use:

```text
data/source_metadata.json
```

Risk Map datasets should use:

```text
risk_map/dataset/source_metadata.json
```

Each Risk Map dataset should record source title, publisher, year, URL/download page, license, spatial coverage, CRS if known, update date, and the local filename.

## Pipeline

```text
region_context.json
        |
        v
risk_map_builder.build_risk_map()
        |
        v
risk_map.json
        |
        v
diagnosis_engine.compute_diagnosis(..., urban_context=risk_map)
```

## Quick Test

```powershell
.\.venv\Scripts\python.exe tests\test_risk_map_integration.py
```

Expected behavior:

- loads input JSON
- builds risk map
- compares diagnosis without and with urban context
- writes intermediate test outputs

## Full Pipeline

```powershell
.\.venv\Scripts\python.exe main.py
```

## Important Settings

```env
USE_MOCK_RISK_MAP=false
RISK_MAP_DATA_ROOT=C:\Users\Morris\OneDrive\Desktop\hvra_test_run\risk_map\dataset
RISK_MAP_BOUNDING_BOX_RADIUS_M=250
USE_SYNTHETIC_UHI=false
USE_INFRARED_CITY=true
INFRARED_CITY_FORCE_REFRESH=false
```

## Future Work

- real building-height extraction
- real tree canopy percentage calculation
- real cooling refuge distance
- real UHI satellite integration
- time-series/seasonal UHI modifier
- per-building microclimate refinement

## Risk Map 3D Visual Test

The standalone visual test lives at:

```text
interface/public/interface/risk_map_3d_test/index.html
interface/public/risk_map_3d_test.html
```

It consumes `/api/risk-map/context` when the backend is restarted with the latest code. If an older backend process is still running, the page falls back to:

```text
interface/public/interface/risk_map_3d_test/risk_map_context.json
```

Current geometry behavior:

- Barcelona-wide road and building contours are parsed from `cataluna-260528-free.shp.zip`.
- The local 500 m study area uses real OSM road/building footprints from the same shapefile.
- 3D buildings use real local OSM footprints with estimated heights because this shapefile has no height attribute.
- Infrared City mesh geometry is preferred when available, but the current API response returned `SUBSCRIPTION_INACTIVE`, so the viewer falls back to local OSM geometry.
- Infrared City analysis is still represented numerically from the cached summary: wind speed, sky view factor, direct sun hours, solar radiation, and UTCI.
- True Infrared raster heat maps require cached raw `merged_grid` cells, not only min/mean/max summaries.

## Risk Map Checkpoint Stage

The Risk Map visual is treated as a precomputed checkpoint between Phase 1 case setup and Phase 2 room/spatial verification. The backend prepares a simplified visual payload first, then the interface only displays the result: simple local map geometry, separate heat-analysis layers, and optional aligned 3D buildings after the site is chosen. This avoids live browser-side analysis and keeps map, boundary, and building geometry in one consistent coordinate frame.

Current display contract:

```text
risk map backend/cache -> risk_map_context.json -> risk map checkpoint viewer
```

The checkpoint uses local OSM footprints for visual alignment and Infrared City for analysis values. True pixel-accurate Infrared raster layers still require storing raw merged-grid cells from the Infrared SDK output; the current cache provides summary statistics, bounds, and grid shape.
