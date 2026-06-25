from validation_engine.strategy_scenario_generator import generate_retrofit_generation_scenarios


def test_generate_retrofit_generation_scenarios_has_six_balanced_options():
    diagnosis = {
        "case_id": "CASE_TEST",
        "room_id": "ROOM_TEST",
        "component_scores": {
            "solar_gain": 0.7,
            "ventilation_deficit": 0.8,
            "envelope": 0.75,
            "nocturnal_recovery": 0.9,
            "occupant_vulnerability": 1.0,
        },
        "room_diagnosis": {"final_score": 1.0},
        "calculation_details": {"envelope": {"roof_exposed": True}},
    }
    strategies = {
        "ranked_strategies": [
            {"strategy_id": "night_purge_ventilation", "strategy_name": "Night purge"},
            {"strategy_id": "wall_insulation_reinforcement_layer", "strategy_name": "Wall insulation reinforcement layer"},
            {"strategy_id": "external_shading", "strategy_name": "External shading"},
            {"strategy_id": "ceiling_fan_air_movement", "strategy_name": "Ceiling fan"},
            {"strategy_id": "interior_biophilic_cooling_zone", "strategy_name": "Interior biophilic zone"},
        ]
    }

    result = generate_retrofit_generation_scenarios(diagnosis, strategies)

    assert len(result["generated_scenarios"]) == 6
    assert result["generated_scenarios"][0]["priority_score"] >= result["generated_scenarios"][-1]["priority_score"]
    for scenario in result["generated_scenarios"]:
        visual = scenario["visual_generation"]
        assert visual["component_ids"]
        assert "combined_effect_profile" in scenario
        assert "operative_temp_reduction_c" in scenario["combined_effect_profile"]