# Strategy Catalogue Inventory

`data/input/strategy_catalogue.json` is the static retrofit strategy source of truth. The LLM ranks strategies from this catalogue after RAG/manual evidence checking; it should not invent strategy IDs or thermal delta values.

The catalogue is now split into three linked files:

```text
data/input/strategy_catalogue.json          calculation, constraints, eligibility, and strategy IDs
data/input/strategy_evidence_map.json       source/evidence role and confidence per strategy
data/input/visual_retrofit_catalogue.json   3D and image-generation placement rules per strategy
```

## Current Catalogue

| ID | Plain name | Category | Scope | Evidence confidence | Visual profile |
| --- | --- | --- | --- | --- | --- |
| external_shading_louvers | External louvers / brise-soleil | shading | room | medium | external_shading_louvers |
| internal_blinds | Internal roller blinds | shading | room | medium | internal_blinds |
| solar_control_glazing | Solar control glazing replacement | glazing | room | medium | solar_control_glazing |
| green_pergola | Green pergola / climbing vegetation | green_shading | room | low_medium | green_pergola |
| window_enlargement | Window enlargement | ventilation | room | medium_low | window_enlargement |
| interior_opening_improvement | Interior opening / transom addition | ventilation | room | medium_low | interior_opening_improvement |
| stack_effect_roof_vent | Stack-effect roof vent | ventilation | room | medium_low | stack_effect_roof_vent |
| night_purge_ventilation | Night purge ventilation behavioural protocol | ventilation | room | medium_low | night_purge_ventilation |
| external_wall_insulation_etics | External wall insulation - ETICS system | envelope | room | medium | external_wall_insulation_etics |
| roof_insulation | Roof insulation membrane | envelope | room | medium | roof_insulation |
| cool_roof_coating | Cool roof reflective coating | cool_surface | room | medium | cool_roof_coating |
| phase_change_materials | Phase-change materials in wall assembly | thermal_mass | room | medium_low | phase_change_materials |
| courtyard_greening | Courtyard greening | urban_greening | building_shared | low_medium | courtyard_greening |
| shared_cooling_refuge | Shared ground-floor cooling refuge | resilience | portfolio | contextual | shared_cooling_refuge |
| street_tree_canopy | Street tree canopy on SW elevation | urban_greening | urban_context | low_medium | street_tree_canopy |
| internal_wall_insulation | Internal wall insulation | envelope | room | medium | internal_wall_insulation |
| wall_insulation_reinforcement_layer | Wall insulation reinforcement layer | envelope | room | medium | wall_insulation_reinforcement_layer |
| cool_facade_paint | Cool / reflective facade paint | cool_surface | room | medium | cool_facade_paint |
| window_external_shutters | External shutters | shading | room | medium | window_external_shutters |
| cross_ventilation_behaviour | Cross-ventilation behavioural protocol | ventilation | room | medium_low | cross_ventilation_behaviour |
| ceiling_fan_air_movement | Ceiling fan | air_movement | room | medium | ceiling_fan_air_movement |
| secure_night_vent_limiter | Secure night ventilation | ventilation | room | medium | secure_night_vent_limiter |
| balcony_planter_shading | Balcony planting shade | biophilic_shading | room | low_medium | balcony_planter_shading |
| interior_biophilic_cooling_zone | Plant cooling corner | biophilic_resilience | room | low | interior_biophilic_cooling_zone |

## Retrofit Feasibility Boundaries

HVRA now treats strategy feasibility as a first-class boundary before ranking, validation, and visual generation. Roof and ceiling-roof measures only apply when the unit is confirmed as top-floor and roof-exposed, and they remain conditional when owner or building-level approval is required.

For older buildings, external facade, roof, structural, and full-window interventions are not treated as immediate unit-level fixes unless permissions and building-physics checks are satisfied. Wall insulation reinforcement is represented as an interior-side lining over the existing wall surface, not as an outward extension beyond the facade.
## Pipeline Use

1. `rag_engine/manual_checker.py` loads `strategy_catalogue.json` and attaches `strategy_evidence_map.json` entries to every eligible/restricted strategy.
2. User constraints split catalogue entries into eligible and restricted options.
3. Hybrid retrieval attaches local RAG evidence to each strategy.
4. `llm_agent/agent.py` ranks eligible strategies into `data/intermediate/strategy_options.json`.
5. `validation_engine/retrofit_effects.py` maps each strategy ID to a screening effect profile.
6. `validation_engine/thermal_validation.py` calculates before/after indicators and benchmark results.
7. `gemini_engine/gemini_prompt_builder.py` reads `visual_retrofit_catalogue.json` so visual prompts use controlled placement rules.

## Notes

The catalogue currently contains 24 strategies. Delta-T, cost, carbon, and multiplier fields are screening assumptions supported by source categories, not a substitute for dynamic simulation or product-specific design data.

Biophilic strategies are included for 3D/visual suggestion and comfort-resilience support. They should not be presented as guaranteed benchmark-passing thermal fixes unless paired with stronger solar, envelope, ventilation, or air-movement measures.


