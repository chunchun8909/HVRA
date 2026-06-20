# Strategy Catalogue Inventory

`data/input/strategy_catalogue.json` is the static retrofit strategy source of truth. The LLM ranks strategies from this catalogue after RAG/manual evidence checking; it should not invent strategy IDs or thermal delta values.

## Current Catalogue

| ID | Plain name | Category | Scope |
| --- | --- | --- | --- |
| external_shading_louvers | External louvers / brise-soleil | shading | room |
| internal_blinds | Internal roller blinds | shading | room |
| solar_control_glazing | Solar control glazing replacement | glazing | room |
| green_pergola | Green pergola / climbing vegetation | green_shading | room |
| window_enlargement | Window enlargement | ventilation | room |
| interior_opening_improvement | Interior opening / transom addition | ventilation | room |
| stack_effect_roof_vent | Stack-effect roof vent | ventilation | room |
| night_purge_ventilation | Night purge ventilation behavioural protocol | ventilation | room |
| external_wall_insulation_etics | External wall insulation - ETICS system | envelope | room |
| roof_insulation | Roof insulation membrane | envelope | room |
| cool_roof_coating | Cool roof reflective coating | cool_surface | room |
| phase_change_materials | Phase-change materials in wall assembly | thermal_mass | room |
| courtyard_greening | Courtyard greening | urban_greening | building_shared |
| shared_cooling_refuge | Shared ground-floor cooling refuge | resilience | portfolio |
| street_tree_canopy | Street tree canopy on SW elevation | urban_greening | urban_context |
| internal_wall_insulation | Internal wall insulation | envelope | room |
| wall_insulation_reinforcement_layer | Wall insulation reinforcement layer | envelope | room |
| cool_facade_paint | Cool / reflective facade paint | cool_surface | room |
| window_external_shutters | External shutters | shading | room |
| cross_ventilation_behaviour | Cross-ventilation behavioural protocol | ventilation | room |

## Pipeline Use

1. `rag_engine/manual_checker.py` loads this catalogue.
2. User constraints split catalogue entries into eligible and restricted options.
3. Hybrid retrieval attaches RAG evidence to each strategy.
4. `llm_agent/agent.py` ranks eligible strategies into `data/intermediate/strategy_options.json`.
5. `validation_engine/retrofit_effects.py` maps each strategy ID to a screening effect profile.
6. `validation_engine/thermal_validation.py` calculates before/after indicators and benchmark results.

## Notes

The catalogue currently contains 20 strategies. The delta-T, cost, and carbon fields are screening assumptions from the reference library. They are not a substitute for dynamic simulation or product-specific design data.



