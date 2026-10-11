# ModwallGN

*(formerly Simple Tile Cutter)*

A Blender add-on for a mobile-game asset workflow: it cuts meshes into tile-sized pieces and projects UVs from a reference tile, with controllers you can move, rotate and scale.

- Version: **0.7.4** (alpha, test build)
- Blender: **4.5 or newer**
- Where: `3D Viewport > N-panel > ModwallGN`

> This is a test build. Please keep a backup of your scenes and report anything odd (see "Reporting problems").

## Install

1. Download `modwall_gn_0.7.4.zip` (do not unzip it).
2. In Blender open `Edit > Preferences > Add-ons`, click the small arrow menu in the top right corner of the Add-ons tab and choose **Install from Disk...**, then pick the zip.
3. Enable **ModwallGN (Simple Tile Cutter)**.
4. Press `N` in the 3D Viewport and open the **ModwallGN** tab. The version is shown at the top of the panel.

To update: in Preferences remove the old version, **restart Blender**, install the new zip, enable it and check the version at the top of the panel.

## The idea in one minute

You give the add-on a **Target** (the mesh to texture) and a **Reference Tile** (a flat plane with the tile material and UVs). A **Controller** (a wire box, cylinder or gizmo) defines where and how big one tile is. The semi-transparent cube you see is only a **preview** that follows the controller. Press **Apply** to get the result.

Every module (Tile Grid, Cylinder, UVW Map) uses the same layout:

1. **Setup**: Target, Reference Tile and the **Controller** block (`Select Controller`, so you can grab it even when it is hidden inside the mesh).
2. **Settings** of the module.
3. **Options / Apply**: options, then the **Apply** button at the bottom.

By default the original is kept and the result is a copy (`Duplicate Before Apply`).

## Tile Grid

Cuts the target into tile-sized pieces and gives each piece UVs from the reference tile. Move, rotate or scale the controller first.

- **Controller**: `Select Controller` selects it; `Reset Proj Box` puts it back to the origin of the target with the tile size.
- **Texture direction**: 0 / 90 / 180 / 270 degrees. Use *Vertical* when the texture is stored on its side. Use the arrows to step.
- **Priority layers**: decide which axis a face is projected from, so faces that sit between two axes (around 45 degrees) do not flip chaotically.
  - Layer 1 (default Z) is used for faces whose normal is between *From* and *To* degrees from its axis. Layer 2 does the same for the second axis. Layer 3 is the third axis; it needs Layer 2 to be on.
  - Faces that fall outside the ranges of layers 1 and 2 go to the **nearest** of the three axes, and an exact tie goes to the higher layer (so a bevelled cube corner, equally far from all axes, follows Layer 1). With Layer 2 or Layer 3 switched off the panel shows a warning: faces near 45 degrees may then project unpredictably.
  - **Flip Back Faces** + **Flip side** turn the pattern over on one side of an axis (for example the floor or the ceiling).
  - Pick an axis already used by another layer and the two layers swap axes.
- **Seams**: mark seams and optionally dissolve edges that are not seams.

## Cylinder

Projects a tile around a cylindrical mesh and can cut it into height bands and angular sectors. Settings: axis, tiles around, stretch around, tile height, cut height bands, project caps.

## UVW Map

Projects UVs from a gizmo **without cutting** the mesh. Mapping types: **Box**, **Planar**, **Cylinder**. `U Flip` / `V Flip` mirror the result.

- **Box** also has the priority layers and texture direction described above.
- Move, rotate and scale the gizmo to place and size the tiles.

## Vertex Paint

Quick helpers: enter / leave Vertex Paint, R / G / B / White / Black / custom colour, brush size, hardness, strength, alpha, and fill (selected or whole object).

## Good to know

- Works best with a flat reference tile lying on the ground; square tiles are the safest, rectangular tiles are supported but check them visually.
- UVW Cylinder projects only the side wrap (no cap projection yet).
- Texel density can differ between modes; check it by eye.
- Preview and Apply can differ slightly when the UVW gizmo has very different X and Z scales.
- Settings are stored in the scene. Files saved with versions 0.6.14 and 0.7.1 were checked to open with all settings intact; the new UVW priority settings start at their defaults (on).

## Reporting problems

Open an issue: https://github.com/olegivanovtogether/modwall_gn/issues

Please include:

1. Blender version and the add-on version shown at the top of the panel (`ModwallGN v0.7.4`).
2. Which tab and mode you used and the steps.
3. What you expected and what happened (a screenshot helps a lot).
4. A small `.blend` that reproduces it, if you can.
5. Any red error text: on Windows from `Window > Toggle System Console`, otherwise start Blender from a terminal and copy its output.

## License

Test license, see `LICENSE.txt`: you may install, run and evaluate this build and send feedback; you may not redistribute it or use it commercially without the author's consent.
