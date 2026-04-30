# Simple Tile Cutter

Blender addon for cutting any mesh with a tile grid and assigning UV coordinates from a reference tile object.

## Status

Alpha tool for a focused mobile-game asset workflow. Use a flat, lying reference tile plane.

## Recent Changes

- Added **Stretch Around** for Cylinder Projection. Disabled by default, it keeps the current angular-cut workflow; enabled, it restores the older stretched wrap behavior without changing height cuts or cap projection.
- Reworked the viewport UI into collapsible Blender sub-panels: **Tile Grid** and **Cylinder Projection**.

## Modes

### Tile Grid
Cuts the target mesh with a bisect grid and projects UVs using a moveable Projection Box empty. The box can be moved, rotated, and scaled in the viewport to align the tiling.

### Cylinder Projection
Cuts the mesh into height bands and angular sectors, then assigns cylindrical UVs. A Cylinder Control empty drives the projection frame.

### UVW Map Projection _(new — first iteration)_
Projects UVs onto a target mesh **without cutting the geometry**. Works like 3ds Max UVW Map: a gizmo object defines the projection frame and can be freely moved, rotated, and scaled in the viewport before applying.

**Mapping types:**
- **Box** — cubic projection; each face picks the nearest box face by its normal, then receives UVs from the two perpendicular local axes. Handles any mesh orientation correctly.
- **Planar** — flat projection from the gizmo's local XY plane.
- **Cylinder** — wraps UVs around the gizmo's local Z axis; `Tiles Around` controls how many reference tiles repeat around the full circumference, and V repeats by tile height.

**Workflow:**
1. Pick Target Mesh and Reference Tile — a gizmo preview object appears automatically.
2. Select the UVW Gizmo and move / rotate / scale it to position the projection.
3. Set the shared Tile Size X / Tile Size Y values in the Tile Grid section. UVW Map Projection uses the same tile size, without separate U/V size fields.
4. For Cylinder mapping, set `Tiles Around` to choose how many tiles wrap around the full circumference.
5. Toggle U Flip / V Flip if needed.
6. Enable *Duplicate Before Apply* to keep the original untouched.
7. Enable *Copy Material From Reference* to transfer the tile material onto the result.
8. Click **Apply UVW Map** — UVs are written to the `UVMap` layer and the gizmo is removed.

## Known Limitations

- Texel density is not fully normalized yet. Wall/box and cylinder projection can still need manual checking when matching texture scale across different shapes.
- UVW Map Projection does not cut the mesh; texture repeats through UV tiling, so seam placement depends on existing geometry edges.
