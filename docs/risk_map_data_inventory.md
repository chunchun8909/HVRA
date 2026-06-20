# Risk Map Data Inventory

This file tracks the datasets currently used or staged for the HVRA Risk Map. The canonical source metadata file is:

```text
risk_map/dataset/source_metadata.json
```

Use this inventory for quick human review. Use `source_metadata.json` for machine-readable citation, license, CRS, and provenance fields.

## Current Coverage

| Category | Status | Local files | Purpose |
| --- | --- | --- | --- |
| EPW weather | Available | `ESP_Barcelona.081810_SWEC.epw`, `ESP_CT_Barcelona-El.Prat.AP.081810_TMYx.2011-2025.zip` | Outdoor climate, peak temperature, humidity, solar radiation, wind speed, night temperature. |
| MeteoCat weather | Available | `2020_MeteoCat_Estacions.csv`, `2025_MeteoCat_Detall_Estacions.csv` | Local station metadata and observed weather records. |
| Administrative boundaries | Available | `BCN_UNITATS_ADM.zip` | District, neighbourhood, or administrative spatial lookup. |
| Tree inventory | Available | `ab_vw_arbrat_geometries.csv` | Local tree count and nearby canopy proxy. |
| Vegetation cover | Available | `2017_vegetacio.gpkg` | Vegetation / NDVI-style local cooling proxy. |
| Building footprints | Available | `cataluna-260528-free.gpkg.zip`, `cataluna-260528-free.shp.zip`, `cataluna-260528.osm.pbf`, `cataluna-260530-free.gpkg.zip` | Surrounding building geometry and urban density context. |
| Building heights | Available | `MTM_GPKG_alcades.zip` | Surrounding obstruction height and street-canyon context. Actual filename contains the accented form `alcades`. |
| Cooling refuges | Available | `2017_cobertura_espaisrefugi.gpkg`, `2017_equip_refugi.gpkg`, `2017_parcs_refugi.gpkg`, `2017_vulnera_espaisrefugi.gpkg` | Access to cooling refuges, parks, and refuge coverage. |
| Vulnerability | Available | `2017_factors_vulnera.gpkg`, `2017_vulnera_espaisrefugi.gpkg`, `ate_vulnera_75plus_od.gpkg` | Vulnerable population and social exposure context. |
| Heat-exposed population | Available | `2018_ate_densitat_75plus_od.gpkg` | Elderly exposed-population density for heat-risk weighting. |
| Heat-exposed facilities | Available | `ate_equip_20-34_od.gpkg`, `ate_equip_35-74_od.gpkg` | Supplementary age-group exposure/facility layers. |
| Thermal comfort reference | Available | `confort_termic_od.gpkg` | Outdoor thermal comfort / heat reference layer. |
| Research supplement | Available | `ijerph-17-02553-s001.zip` | Supporting heat-risk or UHI evidence. Needs extraction into structured values if used computationally. |
| Infrared City context | Available | `infrared_city/infrared_city_context.json` | Site microclimate context: solar, sun hours, wind, sky-view factor, UTCI. |

## Validated Layers

These GeoPackages were opened and inspected successfully.

| File | Layer | Features | Key fields |
| --- | --- | ---: | --- |
| `2017_cobertura_espaisrefugi.gpkg` | `2017_cobertura_espaisrefugi` | 308 | `ToBreak` |
| `2017_equip_refugi.gpkg` | `2017_equip_refugi` | 77 | `nom`, `carrer`, `barri`, `districte` |
| `2017_parcs_refugi.gpkg` | `2017_parcs_refugi` | 49 | `Nom`, `Districte`, `Tipus`, `Area_Ha` |
| `2017_vulnera_espaisrefugi.gpkg` | `2017_vulnera_espaisrefugi` | 77 | `SUM_pob75` |
| `2017_factors_vulnera.gpkg` | `2017_factors_vulnera` | 1061 | `Rec_CP1` |
| `ate_vulnera_75plus_od.gpkg` | `ate_vulnera_75plus_od` | 1504 | `nRisc` |
| `confort_termic_od.gpkg` | `confort_termic_od` | 381 | `gridcode` |
| `2017_vegetacio.gpkg` | `2017_vegetacio` | 1061 | `PercNDVINo` |
| `2018_ate_densitat_75plus_od.gpkg` | `ate_densitat_75plus_od` | 1708 | `d_75plus` |
| `ate_equip_20-34_od.gpkg` | `ate_equip_20-34_od` | 19 | `gridcode` |
| `ate_equip_35-74_od.gpkg` | `ate_equip_35-74_od` | 17 | `gridcode` |

## Still Needed

| Item | Priority | Notes |
| --- | --- | --- |
| Neighbourhood UHI deltas | High | Add a clean JSON or CSV such as `neighbourhood_uhi_deltas.json` with measured or cited UHI delta by neighbourhood. |
| Complete source metadata | High | Fill `source_metadata.json` with exact source URL, publisher, license, update date, CRS, and citation for every dataset. |
| Heatwave/design period definition | Medium | Define Barcelona heatwave week or standard summer design period used by the diagnosis and validation engines. |
| Fine obstruction details | Medium | Balconies, overhangs, awnings, window reveals, and facade-specific obstruction are not fully represented by city-scale datasets. |
| Building-specific user input | Required per case | Exact address or coordinates, floor level, room type, room height, window orientation, glazing, shading, and occupant vulnerability. |

## Source Metadata Requirements

Every dataset used in Risk Map calculations should have an entry in `risk_map/dataset/source_metadata.json`:

```json
{
  "local_file.ext": {
    "source_id": "SHORT_STABLE_ID",
    "source_title": "Human-readable dataset title",
    "publisher": "Dataset publisher",
    "year": 2026,
    "document_type": "gis_dataset",
    "local_file": "local_file.ext",
    "doi_or_url": "https://...",
    "license": "CC BY 4.0",
    "spatial_coverage": "Barcelona",
    "crs": "EPSG code or CRS notes",
    "update_date": "YYYY-MM-DD",
    "citation": "Formal citation or source statement"
  }
}
```

## Validation Commands

Quick inventory check:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from risk_map.data_loader import inventory_risk_map_sources; import json; print(json.dumps(inventory_risk_map_sources(Path('risk_map/dataset')), indent=2, ensure_ascii=False))"
```

Compile check:

```powershell
.\.venv\Scripts\python.exe -m py_compile risk_map\data_loader.py
```
