# Simple Tile Cutter

Blender addon (4.5+) for a focused mobile-game asset workflow: tile-based UV projection, mesh cutting, reference-tile material transfer and vertex color painting helpers.

- Version: `0.6.9` (alpha)
- Blender: 4.5.0+
- Location: `View3D > Sidebar > Tile Cutter`
- Category: Mesh
- Author: Oleh Strykitchenko

The addon is tested on flat, lying reference tile planes. Square tiles are the safest option; rectangular tiles are supported, but should be checked visually after projection.

## Tickets and plans

All plans, open work and bugs live on GitHub, not in this repository:

- Issues: https://github.com/olegivanovtogether/modwall_gn/issues
- Project board: https://github.com/users/olegivanovtogether/projects/2

`TODO.md` only points to the tracker.

## Panels

The sidebar has a parent panel `Tile Cutter` with four sub-panels.

### Tile Grid

Cuts the target mesh with a bisect grid, then assigns UVs from the reference tile.

Use this mode when the mesh should physically receive tile-sized geometry cuts. A Projection Box empty defines the projection frame: move, rotate or scale it before applying. A semi-transparent preview built from the reference tile material matches the projection frame and disappears after Apply.

Options:

- `Target Wall`, `Reference Tile`
- `Duplicate Before Apply` (default on): work on a copy.
- `Reset Proj Box`
- `Mark Seams`: seams on tile borders, sharp corners and boundary edges. `Corner Angle` sets the sharpness threshold.
- `Dissolve non-seamed edges`: removes edges without a seam. Only active when `Mark Seams` is on.

### Cylinder Projection

Projects a tile texture onto cylindrical meshes and can cut the mesh into height bands and angular sectors. A Cylinder Control empty defines the projection frame.

Options:

- `Target Mesh`, `Reference Tile`
- `Cylinder Axis`
- `Tiles Around`: tiles across the full circumference (1-64).
- `Stretch Around`: older wrap behavior, no angular cuts.
- `Tile Height Source` (auto from the reference tile, or manual) and `Tile Height`.
- `Cut Height Bands` (default on).
- `Project Caps` (default on): cuts cap faces into a grid and applies planar UVs.
- `Duplicate Before Apply` (default on).
- `Select Cylinder Control`

### UVW Map Projection

Projects UVs without cutting the mesh. Classic UVW-style projection from a viewport gizmo; the topology stays unchanged.

Mapping types:

- `Box`: cubic projection from the UVW Gizmo local axes.
- `Planar`: flat projection from the UVW Gizmo local XY plane.
- `Cylinder`: cylindrical projection around the UVW Gizmo local Z axis (side wrap only).

Box and Planar use no-clamp UV tiling, so large faces repeat the reference tile instead of stretching it.

Workflow:

1. Pick `Target Mesh`.
2. Pick a flat, lying `Reference Tile`.
3. Choose `Box`, `Planar`, or `Cylinder`.
4. Use `Select / Create UVW Gizmo`.
5. Move, rotate or scale the UVW Gizmo in the viewport.
6. Set `Tiles Around` for UVW Cylinder if needed.
7. Toggle `U Flip` / `V Flip` if the texture direction is wrong.
8. Keep `Duplicate Before Apply` enabled (default) to leave the original untouched.
9. Keep `Copy Material From Reference` enabled (default) to give the result the reference material.
10. Click `Apply UVW Map`.

### Vertex Paint Tools

Helper panel for painting vertex colors on the active mesh without leaving the sidebar.

1. Select a mesh and click `Enter Vertex Paint` (`Object Mode` returns to Object Mode).
2. Pick a color: `R`, `G`, `B`, `White`, `Black`, or `Custom` with the color swatch.
3. Set brush `Radius`, `Inner`, `Strength`, `Alpha` and click `Apply Brush Settings`.
4. Use `Fill Selected` (selected vertices/faces) or `Fill Object` (whole mesh) to fill the active color. Point and face-corner color attribute domains are handled.

## Known limitations

- UVW Cylinder projects the side wrap only; cap projection is not implemented.
- Texel density across different projection modes needs manual checking in some scenes.
- Angular cuts in Cylinder Projection when `Tiles Around` does not divide the side count evenly are implemented but not visually verified.
- UVW Map Projection does not cut geometry, so visible texture boundaries depend on the existing mesh and the material repeat behavior.
- Rectangular tiles are supported, but square tiles remain the production-safe path.

See the issue tracker for the current state of each item.

## Installation

1. Remove the old `modwall_gn` addon folder from Blender's addon directory if needed.
2. Install the zip through Blender Preferences > Add-ons > Install, or copy the folder to `Blender\4.5\scripts\addons\modwall_gn`.
3. Enable `Simple Tile Cutter`.
4. If Blender keeps old code in memory, use `F3 > Reload Scripts` or restart Blender.

## Repository layout

- `__init__.py`: addon (settings, operators, panels, registration).
- `bmesh_baker.py`: grid slicing and reference-tile UV bounds helpers.
- `test_tile_cutter.py`: manual smoke script for the Blender Text Editor (outdated, see tracker).
- `archive/`: local release zips, not tracked by git.

## Development notes

- Branches: `develop` is the working branch, `master` holds released states.
- Do not change Tile Grid or Cylinder Projection when working on UVW Map Projection unless the task explicitly requires it.
- Tile Grid and Cylinder Projection are working production modes and should be treated as reference behavior.
- UVW Map Projection stays additive: it writes UVs and optionally copies material, but does not cut geometry.
