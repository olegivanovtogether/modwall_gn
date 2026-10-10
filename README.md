# Simple Tile Cutter

Blender addon for a focused mobile-game asset workflow: tile-based UV projection, mesh cutting, and reference-tile material transfer.

## Status

Alpha version for a narrow production task. The addon is actively tested on flat, lying reference tile planes. Square tiles are the safest option; rectangular tiles are supported, but should be checked visually after projection.

Current version: `0.6.9`

## What Works Now

- Tile Grid mode cuts target meshes into tile-sized sections and projects UVs from a reference tile.
- Mark Seams and Dissolve non-seamed edges are separate options. Dissolve only works after Mark Seams is enabled.
- Projection Box can be moved, rotated, and scaled in the viewport.
- Projection Box preview is built from the reference tile material and matches the projection frame.
- Cylinder Projection supports height cuts, angular cuts, optional Stretch Around behavior, cap projection, seams, and a viewport Cylinder Control.
- UVW Map Projection adds no-cut UV projection modes for Box, Planar, and Cylinder.
- UVW Box and Planar now use no-clamp UV tiling, so large faces repeat the reference tile instead of stretching one tile over the whole face.
- Vertex Paint Tools panel: enter/exit Vertex Paint mode, R/G/B/White/Black/Custom brush colors, brush size/hardness/strength/alpha, and Fill Selected / Fill Object for vertex colors (point and face-corner color attribute domains).
- Default tile size is `1x1`.

## Modes

### Tile Grid

Cuts the target mesh with a bisect grid, then assigns UVs from the reference tile.

Use this mode when the mesh should physically receive tile-sized geometry cuts. The Projection Box empty defines the projection frame. Move, rotate, or scale it before applying.

### Cylinder Projection

Projects a tile texture onto cylindrical meshes and can cut the mesh into height bands and angular sectors.

Use this mode when the cylinder should be prepared with real geometry cuts and seams. The Cylinder Control empty defines the projection frame. `Tiles Around` controls how many tiles wrap around the circumference.

### UVW Map Projection

Projects UVs without cutting the mesh.

Use this mode when you want classic UVW-style projection from a viewport gizmo while leaving the mesh topology unchanged.

Mapping types:

- `Box`: cubic projection from the UVW Gizmo local axes.
- `Planar`: flat projection from the UVW Gizmo local XY plane.
- `Cylinder`: cylindrical projection around the UVW Gizmo local Z axis.

Workflow:

1. Pick `Target Mesh`.
2. Pick a flat, lying `Reference Tile`.
3. Choose `Box`, `Planar`, or `Cylinder`.
4. Use `Select / Create UVW Gizmo`.
5. Move, rotate, or scale the UVW Gizmo in the viewport.
6. Set `Tiles Around` for UVW Cylinder if needed.
7. Toggle `U Flip` or `V Flip` if the texture direction is wrong.
8. Keep `Duplicate Before Apply` enabled if the original mesh should stay untouched.
9. Keep `Copy Material From Reference` enabled if the result should receive the reference material.
10. Click `Apply UVW Map`.

### Vertex Paint Tools

Helper panel for painting vertex colors on the active mesh without leaving the Tile Cutter sidebar.

1. Select a mesh and click `Enter Vertex Paint` (`Object Mode` returns to Object Mode).
2. Pick a color: `R`, `G`, `B`, `White`, `Black`, or `Custom` with the color swatch.
3. Set brush `Size`, `Hardness`, `Strength`, `Alpha` and click `Apply Brush Settings`.
4. Use `Fill Selected` (selected vertices/faces) or `Fill Object` (whole mesh) to fill the active color.

## Known Limitations / TODO

- UVW Cylinder currently projects the side wrap only. Cap projection for UVW Cylinder still needs to be added.
- Texel density across different projection modes still needs manual checking in some scenes.
- UVW Map Projection does not create new geometry cuts, so visible texture boundaries depend on the existing mesh and the material's repeat behavior.
- Rectangular tiles are supported, but square tiles remain the recommended production-safe path.

## Installation

The addon targets Blender 4.5+. The installed folder name is `modwall_gn`.

1. Remove the old `modwall_gn` addon folder from Blender's addon directory if needed.
2. Install the zip through Blender Preferences > Add-ons > Install.
3. Enable `Simple Tile Cutter`.
4. If Blender keeps old code in memory, use `F3 > Reload Scripts` or restart Blender.

## Tickets / Roadmap

Work is tracked on GitHub: [Issues](https://github.com/olegivanovtogether/modwall_gn/issues) and the project board linked from the repository. Open items are also summarised in `TODO.md`.

## Development Notes

- Branches: `develop` is the working branch, `master` holds released states.

- Do not change Tile Grid or Cylinder Projection when working on UVW Map Projection unless the task explicitly requires it.
- Tile Grid and Cylinder Projection are working production modes and should be treated as reference behavior.
- UVW Map Projection should stay additive: it writes UVs and optionally copies material, but does not cut geometry.
