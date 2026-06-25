# Biophilic 3D Retrofit Notes

The advanced 3D test now treats biophilic retrofit design as more than adding a single plant cluster. The catalogue includes direct vegetation, vertical greenery, planter shelves, hanging rails, preserved moss panels, and trellis screens, while keeping each option bounded by opening type, door operation, daylight, maintenance, damp risk, renter status, and old-building retrofit limits.

## Design Basis

The approach follows the common biophilic design split between direct nature, natural analogues, and spatial experience. For the room viewer this means:

- direct nature: mixed plant clusters, shelf planters, hanging planters, trellis greenery;
- natural analogues: preserved moss panels and natural texture layers;
- spatial quality: keeping prospect, door operation, and circulation clear instead of filling the opening with decoration.

## Air Quality Caveat

Plant assets are shown as comfort, restoration, and visual-nature interventions. They are not counted as the main air-quality system, because realistic occupied rooms usually need ventilation or filtration rather than relying on potted plants alone.

## Current Visual Families

```text
interior_window_covering
  soft drapes
  vertical blinds
  split roller shade
  venetian blind for punched windows only

external_shading
  external louver
  fabric awning

biophilic_shading
  balcony planter shade
  mixed indoor plant cluster

biophilic_interior_layers
  daylight planter shelf
  hanging planter rail
  vertical plant ladder
  preserved moss wall panel
  interior trellis climber screen
```

## Sources Used

- Biofit article supplied by the user, used as an inspiration source for plant-oriented biophilic interiors: https://biofit.io/news/air-purifying-plants-in-biophilic-interiors
- Terrapin Bright Green, *14 Patterns of Biophilic Design*, used for the direct nature / natural analogue / spatial-experience structure: https://www.terrapinbrightgreen.com/reports/14-patterns/
- Cummings and Waring, *Potted plants do not improve indoor air quality*, used to avoid overclaiming air purification from decorative plants: https://doi.org/10.1038/s41370-019-0175-9


## Current Revision Notes

Moss wall panels were removed from the active visual test because they need separate validation for damp risk, adhesive/fixing method, surface condition, and user preference. The active test now prioritizes movable or low-disruption planted layers: floor cluster, shelf planters, hanging rail, plant ladder, and trellis screen.

The placement model now treats these as hosted objects: rails belong to the opening head, shelf and trellis belong near the interior wall face, and floor plants belong beside the opening or corner without blocking the active path.


## Hosted Placement Update

The advanced visualizer now uses a `sideHost` placement rule for wall-adjacent assets. This chooses the available wall strip beside the detected opening, then hosts shelves, hanging rails, plant ladders, and trellis screens close to the interior wall face instead of placing them randomly over the window.

Temporary support placeholders are intentional: brackets, rails, shelf plates, ladder frames, and trellis frames explain how future GLB assets should be mounted before realistic components are injected.


## Vegetation Variety Update

The plant catalogue now defines scale ranges and visual styles for mini, small, medium, large, and trailing vegetation. The advanced viewer renders different plant habits rather than repeating one generic plant: tall palm, small tree, broadleaf cluster, fern, spider/grass form, trailing vine, and succulent/rosette shelf plants.


## Design-Significant Vegetation Scale

The 3D test now scales vegetation as a visible retrofit layer rather than small decoration. Tiny shelf plants are treated as secondary details; main biophilic options should be large enough to read in the room model, such as floor clusters, vertical plant ladders, hanging greenery, or trellis planting.


## Indoor Wall-Frame Correction

The advanced viewer now uses a shared wall-frame transform for the opening, insulation preview, and all wall-hosted assets. Local `+Z` is forced to point into the indoor room space, so shelves, rails, trellis panels, and plants should no longer flip to the outdoor side or drift through the glazing.
