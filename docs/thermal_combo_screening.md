# Screening Formula for Combined Retrofit Effects

## Purpose

This note defines the screening-level method HVRA can use when a retrofit option contains more than one strategy, such as shading plus night ventilation plus wall insulation. It is intended for early option comparison and checkpoint review, not final compliance or detailed design.

There is no official standard that supports a universal rule such as:

```text
Delta T package = Delta T strategy A + Delta T strategy B + Delta T strategy C
```

That naive sum can overestimate performance because strategies interact. The defensible approach is to start from a simple room heat balance and calculate the package effect from the heat drivers that each strategy changes.

## Heat Balance Basis

A simplified free-running room balance can be written as:

```text
T_indoor = T_outdoor + Q_gain / H_total
```

Where:

```text
Q_gain  = Q_solar + Q_internal + Q_envelope_gain
H_total = H_vent + H_trans + H_storage_effective
```

For screening, HVRA groups retrofit effects into four drivers:

```text
solar gain
ventilation deficit
envelope heat transfer
nocturnal recovery / storage
```

This is aligned with the logic of ISO 13790 / 5R1C, ISO 52016-1 hourly calculation, and heat-balance simulation tools such as EnergyPlus, but it is not a substitute for those full calculations.

## Why Naive Additivity Fails

Strategies affect different parts of the heat balance:

```text
Shading / solar-control glazing -> reduces solar gains
Insulation / thermal lining     -> changes envelope heat transfer
Night purge / cross ventilation -> changes ventilation heat removal
PCM / thermal mass              -> changes storage and timing
```

Gain-side reductions can be approximately additive in watts. Temperature reductions are not generally additive, because the denominator and storage terms change the resulting indoor temperature.

## First-Order Screening Method

Around the baseline room state:

```text
T = T_outdoor + Q / H
```

A small package change can be approximated with a first-order Taylor expansion:

```text
Delta T_reduction = Delta Q_reduction / H_baseline
                  + Q_baseline * Delta H_effective / H_baseline^2
```

Where:

```text
Delta T_reduction   positive value means indoor temperature is reduced
Delta Q_reduction   reduction in gains, W
Delta H_effective   effective increase in heat-removal or damping capacity, W/K
Q_baseline          baseline heat gain, W
H_baseline          baseline heat-transfer/removal coefficient, W/K
```

Important sign convention:

```text
Positive Delta Q_reduction reduces indoor temperature.
Positive Delta H_effective increases the room's ability to reject or damp heat.
```

For insulation in summer, do not blindly treat reduced U-value as increased heat loss. Its effect depends on whether the outside/surface condition is hotter than the room and whether the room needs night-time heat rejection. In HVRA screening, wall insulation and reinforced lining are therefore represented through conservative envelope and nocturnal-recovery multipliers, not as a simple additive denominator term.

## Backend Driver Method

The diagnosis base composite currently uses solar gain, ventilation deficit, envelope, and occupant vulnerability weights. Nocturnal recovery is still included in retrofit screening as a separate health-critical driver for proposed-condition checks.

When the backend does not have enough physical data for watts and W/K, use normalized drivers:

```text
baseline_pressure =
    solar_gain_score          * w_solar
  + envelope_score            * w_envelope
  + ventilation_deficit_score * w_ventilation
  + nocturnal_recovery_score  * w_night
```

For a package:

```text
solar_new      = solar_gain_score          * combined_solar_multiplier
envelope_new   = envelope_score            * combined_envelope_multiplier
vent_new       = ventilation_deficit_score * combined_ventilation_multiplier
night_new      = nocturnal_recovery_score  * combined_night_multiplier
```

Then:

```text
proposed_pressure =
    solar_new    * w_solar
  + envelope_new * w_envelope
  + vent_new     * w_ventilation
  + night_new    * w_night
```

And:

```text
pressure_reduction_ratio = (baseline_pressure - proposed_pressure) / baseline_pressure
```

This ratio can drive proposed indicators such as peak operative temperature, overheating hours, and composite room risk score with conservative caps.

## Combining Multipliers

For strategies affecting the same driver, combine multipliers multiplicatively:

```text
combined_solar_multiplier = m_solar_1 * m_solar_2 * ...
```

Then apply floors/caps:

```text
minimum solar multiplier:       0.25
minimum envelope multiplier:    0.45
minimum ventilation multiplier: 0.35
minimum nocturnal multiplier:   0.35
```

These floors prevent an unrealistic package from eliminating an entire risk driver.

## Temperature Reduction Cap

For screening:

```text
maximum peak operative temperature reduction = 5.0 C
maximum WBGT reduction                       = 2.0 C-WBGT
maximum overheating-hours reduction          = 70 percent
minimum final risk score                     = 0.15
```

If the calculated package exceeds these limits, HVRA should flag the result as requiring simulation or product-specific engineering evidence.

## Confidence Rule

Combo confidence should be lower than the best single-strategy confidence unless combo-specific evidence exists:

```text
combo_confidence = average(single_strategy_confidences) - 0.05 * (number_of_strategies - 1)
```

Increase confidence only when RAG evidence directly supports the combined package.

## Valid Use

Appropriate for:

```text
early-stage option comparison
checkpoint review
ranking three candidate packages
explaining expected direction of improvement
```

Not appropriate for:

```text
regulatory compliance
final comfort certification
product specification
large claimed reductions above 5 C
HVAC-controlled rooms without a separate model
```

## Escalation Rule

Escalate to ISO 52016-1 calculation, EnergyPlus, IESVE, DesignBuilder, or equivalent dynamic simulation when:

```text
claimed peak reduction exceeds 5 C
three or more loss/storage-side strategies are combined
thermal mass or PCM is central to the result
the room has active HVAC
the user needs compliance-grade evidence
```

## References

| Source | Relevance |
| --- | --- |
| ISO 13790 / EN ISO 13790 | 5R1C thermal network basis for simplified heat balance |
| ISO 52016-1 | Successor method for hourly zone temperature and load calculation |
| EnergyPlus Engineering Reference | Full heat-balance simulation reference |
| CIBSE Guide A | Practical building-physics guidance for comfort and heat gains |

## HVRA Position

HVRA should not present an additive Delta T sum as an official formula. It should present combined retrofit performance as a screening estimate derived from heat-balance logic, normalized risk drivers, conservative caps, and confidence gates.
