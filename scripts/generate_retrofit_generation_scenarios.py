from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from validation_engine.strategy_scenario_generator import generate_retrofit_generation_scenarios

DIAGNOSIS_PATH = ROOT / "data" / "intermediate" / "diagnosis_result.json"
STRATEGY_PATH = ROOT / "data" / "intermediate" / "strategy_options.json"
OUTPUT_PATH = ROOT / "data" / "intermediate" / "retrofit_generation_scenarios.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    result = generate_retrofit_generation_scenarios(
        diagnosis_result=load_json(DIAGNOSIS_PATH),
        strategy_options=load_json(STRATEGY_PATH),
        limit=9,
    )
    OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    for index, scenario in enumerate(result["generated_scenarios"], start=1):
        effect = scenario["combined_effect_profile"]
        print(
            f"{index}. {scenario['scenario_name']} | priority={scenario['priority_score']} | "
            f"dT={effect.get('operative_temp_reduction_c')} C | "
            f"components={', '.join(scenario['visual_generation']['component_ids'])}"
        )


if __name__ == "__main__":
    main()