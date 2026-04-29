# Simple Tile Cutter

Blender addon for cutting any mesh with a tile grid and assigning UV coordinates from a reference tile object.

## Status

Alpha tool for a focused mobile-game asset workflow. Use a flat, lying reference tile plane.

## Recent Changes

- Added **Stretch Around** for Cylinder Projection. Disabled by default, it keeps the current angular-cut workflow; enabled, it restores the older stretched wrap behavior without changing height cuts or cap projection.
- Reworked the viewport UI into collapsible Blender sub-panels: **Tile Grid** and **Cylinder Projection**.

## Known Limitations

- Texel density is not fully normalized yet. Wall/box and cylinder projection can still need manual checking when matching texture scale across different shapes.
