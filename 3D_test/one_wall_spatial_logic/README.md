# One Wall Spatial Logic Test

This folder is an isolated 3D placement test. It does not use LGTNet geometry.

Coordinate rules:
- Wall plane: `z = 0`
- Interior side: `+z`
- Exterior side: `-z`
- Window coverings attach to the opening.
- Wall plantation systems attach beside the opening on the interior wall face.
- Floor plants and ladders remain inside the room.

Run from project root with a static server, then open:

```text
http://127.0.0.1:8020/3D_test/one_wall_spatial_logic/index.html
```

## Component Rebuild Notes

Plant components now use size-aware species placeholders instead of one generic plant shape. The test includes palm, broadleaf, fern, spider/grass, succulent, trailing vine, and small-tree forms.

Placement remains intentionally simple:
- all plants stay on the interior side of the wall;
- shelf plants sit on shelf surfaces;
- hanging plants hang from visible cords below the rail;
- ladder plants sit on ladder shelves;
- trellis foliage grows from a wall-mounted frame;
- floor plants stay on the floor-side daylight zone.
## Main Pipeline Use

The main HVRA room viewer is not replaced by this test. The production pipeline now uses these rules as the placement reference for `data/output/spatial/room_3d_component_view.html`, a second Phase 3 room view beside the original `room_3d_view.html`.

