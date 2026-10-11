# ModwallGN

*(formerly Simple Tile Cutter)*

Blender addon (4.5+) for a focused mobile-game asset workflow: tile-based UV projection, mesh cutting, reference-tile material transfer and vertex color painting helpers.

- Version: `0.7.4` (alpha)
- Blender: 4.5.0+
- Location: `View3D > Sidebar > ModwallGN`
- Category: Mesh
- Author: Oleh Strykitchenko

The addon is tested on flat, lying reference tile planes. Square tiles are the safest option; rectangular tiles are supported, but should be checked visually after projection.

## Tickets and plans

All plans, open work and bugs live on GitHub, not in this repository:

- Issues: https://github.com/olegivanovtogether/modwall_gn/issues
- Project board: https://github.com/users/olegivanovtogether/projects/2

`TODO.md` only points to the tracker.

## Panels

The sidebar tab `ModwallGN` has one panel with the add-on name and version on top, then a bar of module tabs (one row; two rows of two when the panel is narrow): **Tile Grid**, **Cylinder**, **UVW Map**, **Vertex Paint**. The selected tab shows the controls of that module, each group on its own plate (sub-panel). The three cutting / projecting modules share one layout: **Setup** (Target, Reference Tile and the **Controller** block with `Select Controller`), the module's settings, then **Options / Apply** with the Apply button always last. The selected tab is UI state and is not saved with the file.

### Tile Grid (tab)

Cuts the target mesh with a bisect grid, then assigns UVs from the reference tile.

Use this mode when the mesh should physically receive tile-sized geometry cuts. A Projection Box empty defines the projection frame: move, rotate or scale it before applying. A semi-transparent preview built from the reference tile material matches the projection frame and disappears after Apply.

Options:

- `Target Wall`, `Reference Tile`
- `Duplicate Before Apply` (default on): work on a copy.
- `Select Controller`: selects the controller (the wire cube, i.e. the Projection Box) even when it sits inside the mesh. The semi-transparent preview cube is a separate, smaller object that follows the controller and cannot be selected.
- `Reset Proj Box`
- `Priority Axis` (default on) with three priority layers, see below.
- `Mark Seams`: seams on tile borders, sharp corners and boundary edges. `Corner Angle` sets the sharpness threshold.
- `Dissolve non-seamed edges`: removes edges without a seam. Only active when `Mark Seams` is on.

#### Texture direction (Tile Grid)

The tile layout is read as stored by default (`0° · Horizontal`). If the texture image is stored turned on its side, rotate the reading in 90 degree steps so the wall comes out laid the usual way:

- `0° · Horizontal`, `90° · Vertical`, `180° · Horizontal, upside down`, `270° · Vertical, upside down`.
- `-90°` / `+90°` buttons step through the four positions.
- At 90° and 270° the cell width and height are swapped (matters only for rectangular tiles). The Projection Box and its preview follow.

#### Priority layers (Tile Grid)

Faces whose normal sits near 45 degrees between two Projection Box axes used to flip between axes face by face. The priority layers make the choice deterministic. Each face goes to the first layer that matches:

1. **Layer 1**: axis `X | Y | Z` (default `Z`), angle `From / To` (default 0 / 50 degrees) between the face normal and the axis, sign ignored, boundary included. Faces in range always project along this axis.
2. **Layer 2** (own checkbox, default on): one of the two remaining axes (default `X`), own `From / To` (0 / 50). Applies only to faces not caught by layer 1.
3. **Layer 3** (own checkbox, default on): the fallback for faces not caught by the ranges of layers 1 and 2. Such a face goes to the **nearest** of the three axes; when two or three axes are exactly equally near (a bevelled cube corner is 54.7 degrees from all three), the **higher layer wins**. Its Flip settings are those of the layer that owns the chosen axis.

Notes: `From / To` is a range in which the axis is forced; it does not ban the axis outside it (a face nearer to the axis than `From` is still chosen by the nearest-axis rule). Layer 3 is therefore the nearest-axis fallback, not "everything that is left". With layer 2 or layer 3 off, or with `Priority Axis` off, the old nearest-axis rule is used.

Each layer has **Flip Back Faces**: the faces of that layer that look away from the axis are turned over (U mirrored), like gluing the paper on its other side. Off = straight-through projection. Defaults: layer 1 off, layers 2 and 3 on.

Each layer also has **Flip side**: which side of the layer's axis is turned over. The words belong to the layer role, the sign and letter come from the layer's current axis:

- Layer 1 is Top-Bottom: `Bottom (-axis)` / `Top (+axis)`.
- Layer 2 is Front-Back: `Back (-axis)` / `Front (+axis)`.
- Layer 3 is Left-Right: `Right (-axis)` / `Left (+axis)`.

The default side is the one used before (Z: -Z, X: -X, Y: +Y). Choosing the other button flips the opposite side, so you decide whether the floor or the ceiling is turned over.

Axes swap between layers: if you pick for layer 1 the axis that layer 2 uses, layer 2 takes the axis layer 1 just left. Layer 3 always is the remaining axis.

Each layer is its own box in the panel with its enable checkbox next to the title. Layer 2 and 3 depend on the parent `Priority Axis` checkbox. With any of them off, faces near 45 degrees may project chaotically (the panel shows a warning). The Projection Box preview follows these settings, so the pattern direction on the preview cube changes when you toggle Flip or change axes.

### Cylinder (tab)

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
- `Select Controller`: selects the Cylinder Control empty, even when it sits inside the mesh

### UVW Map (tab)

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
4. Use `Select Controller` (creates the UVW Gizmo if needed).
5. Move, rotate or scale the UVW Gizmo in the viewport.
6. Set `Tiles Around` for UVW Cylinder if needed.
7. Toggle `U Flip` / `V Flip` if the texture direction is wrong.
8. Keep `Duplicate Before Apply` enabled (default) to leave the original untouched.
9. Keep `Copy Material From Reference` enabled (default) to give the result the reference material.
10. Click `Apply UVW Map`.

#### Priority layers (Box)

For the `Box` mapping the UVW Map tab has the same **Priority layers** plate as Tile Grid (three layers, angle range, `Flip Back Faces` with side, axes swap between layers) and a `Texture direction` control. The settings are separate from Tile Grid (`uvw_*`) and on by default, so faces near 45 degrees no longer flip between projections. Only the axis choice changes: the continuous (repeating) UV projection, the gizmo scale and the global `U Flip` / `V Flip` work as before. Planar and Cylinder do not choose an axis and do not have this plate. Re-apply to recompute an already projected mesh.

### Vertex Paint (tab)

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

## Changelog

- **0.7.4**: one layout for Tile Grid, Cylinder and UVW Map: Setup (inputs + `Select Controller`), module settings, Options / Apply with Apply always last; the controller button has the same name and place in every module.
- **0.7.3**: priority layers fixed for faces between the axes: outside the ranges of layers 1 and 2 a face goes to the nearest axis and an exact tie (e.g. a bevelled cube corner, 54.7 deg to all three axes) goes to the higher layer instead of the lowest one. Applies to Tile Grid and UVW Box.
- **0.7.2**: UVW Map (Box) gets the same priority layers, Flip Back Faces with side and texture direction as Tile Grid (own `uvw_*` settings, on by default), live gizmo preview follows them; reversible cell width/height swap; angle ranges refresh the previews.
- **0.7.1**: Tile Grid `Select Controller` button; controller and preview cube are clearly separated in the panel.
- **0.7.0**: code split into modules; single panel `ModwallGN` with module tabs and plates; name `ModwallGN (Simple Tile Cutter)`; safe register / unregister / reload.
- **0.6.14**: layers swap axes; flip side labels by layer role (Top-Bottom, Front-Back, Left-Right).
- **0.6.13**: `Flip side` per layer (floor or ceiling), layers as separate boxes.
- **0.6.12**: texture direction 0 / 90 / 180 / 270.
- **0.6.11 and earlier**: three priority layers with Flip Back Faces and live preview, vertex paint tools, UVW Map, Cylinder Projection.

## Installation

1. Remove the old `modwall_gn` addon folder from Blender's addon directory if needed.
2. Install the zip through Blender Preferences > Add-ons > Install, or copy the folder to `Blender\4.5\scripts\addons\modwall_gn`.
3. Enable `ModwallGN (Simple Tile Cutter)`.
4. If Blender keeps old code in memory, use `F3 > Reload Scripts` or restart Blender.

## Repository layout

The package is split by responsibility; a module only imports modules listed above it.

- `__init__.py`: `bl_info`, module list with reload, class list, `register` / `unregister`.
- `bmesh_baker.py`: grid slicing and reference-tile UV bounds helpers.
- `uv_geom.py`: pure UV geometry: priority layers, axis choice, flip rules, cell rotation, seams.
- `preview_mat.py`: materials for the preview objects.
- `vertex_paint.py`: Vertex Paint helper functions.
- `tile_grid.py`: Projection Box, Tile Grid preview, texture direction callbacks.
- `cylinder.py`: Cylinder Projection (cuts, control empty, preview).
- `uvw.py`: UVW Map Projection (gizmo, previews, UV projection).
- `callbacks.py`: small property update callbacks and poll functions.
- `props.py`: `TC_Settings` with every add-on property (`scene.tc_settings`).
- `ops_tile_grid.py`, `ops_cylinder.py`, `ops_uvw.py`, `ops_vertex_paint.py`: operators per module.
- `panels.py`: the N-panel with the tab row.
- `test_tile_cutter.py`: manual smoke script for the Blender Text Editor (outdated, see tracker).
- `archive/`: local release zips, not tracked by git.

## Development notes

- Branches: `develop` is the working branch, `master` holds released states.
- Do not change Tile Grid or Cylinder Projection when working on UVW Map Projection unless the task explicitly requires it.
- Tile Grid and Cylinder Projection are working production modes and should be treated as reference behavior.
- UVW Map Projection stays additive: it writes UVs and optionally copies material, but does not cut geometry.
