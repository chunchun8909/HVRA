# Diagnosis Weighting

HVRA uses literature-informed screening weights for the room-level heat-risk composite score. The current base composite follows the Stage 2d methodology in `risk_map/dataset/HVRA_build_reference_4.md`:

```text
composite_room_risk_score =
    0.40 * solar_gain_score
  + 0.35 * ventilation_deficit_score
  + 0.15 * envelope_score
  + 0.10 * occupant_vulnerability_score
```

## Current Weights

| Driver | Weight | Role |
| --- | ---: | --- |
| Solar gain | 0.40 | Primary Mediterranean overheating driver, especially for exposed glazed facades. |
| Ventilation deficit | 0.35 | Primary heat-rejection and night-purge limitation driver. |
| Envelope | 0.15 | Construction age, roof/wall exposure, and thermal buffering risk. |
| Occupant vulnerability | 0.10 | Health susceptibility and exposure modifier. |
| Nocturnal recovery | 0.00 in base composite | Calculated separately and applied downstream in final risk and validation checks. |

## Source Rationale

The structure is informed by overheating and heat-health literature rather than copied from a single official coefficient table. Supporting references include:

- Samuelson et al. (2020), housing heat vulnerability framing.
- UKHSA / Public Health England heat-health and indoor temperature guidance.
- WHO (2011), Heat and Health.
- ISO 7243:2017 WBGT heat-stress screening.
- ASHRAE 55 and EN ISO 7726 operative-temperature framing.
- UPC Barcelona heat-vulnerability framing for Mediterranean exposure drivers.

## Important Caveat

These are documented screening weights, not regulatory pass/fail coefficients. They should be recalibrated if measured monitoring data, EnergyPlus results, or locally validated epidemiological weights become available.
