# Data Sources Inventory by Segment

This document gives a project-level source inventory. Detailed source tables live in [RAG Sources Inventory](rag_sources_inventory.md) and [Risk Map Data Inventory](risk_map_data_inventory.md).

## Spatial Engine Sources

| Segment | Current source/input | Use |
| --- | --- | --- |
| Pano image | `data/input/images/pano_image/` | LGTNet room layout, wall count, floor/ceiling/wall texture extraction. |
| Perspective image | `data/input/images/perspective_image/` | Final visual reference and future generated perspective comparison. |
| LGTNet output | `data/output/spatial/lgtnet/` | Room polygon/layout used by scaling and viewer. |
| SAM3 output | `data/output/spatial/sam3/` | Window segmentation on wall fragments. Furniture/door are not required for calculation. |

## Risk Map Sources

| Segment | Current source/input | Use |
| --- | --- | --- |
| EPW weather | Barcelona EPW/SWEC/TMYx files in `risk_map/dataset/` | Outdoor dry-bulb, humidity, wind, solar, night temperatures. |
| Administrative boundaries | `BCN_UNITATS_ADM.zip` | District/neighbourhood lookup. |
| Building footprints/heights | OSM/GPKG/SHP and `MTM_GPKG_alcades.zip` | Urban density, obstruction, street-canyon context. |
| Vegetation/trees | `2017_vegetacio.gpkg`, `ab_vw_arbrat_geometries.csv` | Local cooling and shade proxies. |
| Cooling refuge/parks | refuge GeoPackages | Access to cooling support. |
| Vulnerability/exposure | vulnerability and elderly-density GeoPackages | Social/health exposure context. |
| Infrared City | `risk_map/dataset/infrared_city/infrared_city_context.json` | Solar radiation, direct sun hours, sky-view factor, UTCI, wind context when available. |

## RAG Sources

| Segment | Current source/input | Use |
| --- | --- | --- |
| Design codes and standards | ASHRAE, ISO, CTE, EN/CIBSE PDF sources | Benchmark thresholds, comfort, ventilation, measurement logic. |
| Retrofit manuals and strategy books | Annex 50, solution booklets, retrofit playbooks, Passive House/EnerPHit sources | Strategy evidence and implementation notes. |
| Climate adaptation and policy | EU renovation strategy, local/policy documents | Retrofit context and public-sector relevance. |
| Research papers | overheating, passive cooling, reflective/cool materials, thermal strategy papers | Effect assumptions and citations. |

## Strategy Catalogue Sources

| Segment | Current source/input | Use |
| --- | --- | --- |
| Static catalogue | `data/input/strategy_catalogue.json` | Source of truth for strategy IDs, names, categories, constraints, cost/carbon ranges, and effect-profile mapping. |
| Catalogue documentation | [Strategy Catalogue](strategy_catalogue.md) | Human-readable list of the 20 strategy entries. |
| Combo method | [Thermal Combo Screening](thermal_combo_screening.md) | Screening formula for future combined strategy packages. |

## Generated Views

| Segment | Current source/input | Use |
| --- | --- | --- |
| Room viewer | `data/output/spatial/room_3d_view.html` | Spatial V&V and future strategy overlays. |
| KG viewer | `data/output/kg/kg_view.html` | Traceability graph review. |
| Validation view | `data/output/validation_view.html` | Numerical before/after option comparison. |
| Report view | `data/output/final_report_view.html` | Final user-facing report preview. |
