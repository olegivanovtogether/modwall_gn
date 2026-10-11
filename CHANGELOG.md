# Changelog

- **0.7.4**: one layout for Tile Grid, Cylinder and UVW Map: Setup (inputs + `Select Controller`), module settings, Options / Apply with Apply always last; the controller button has the same name and place in every module.
- **0.7.3**: priority layers fixed for faces between the axes: outside the ranges of layers 1 and 2 a face goes to the nearest axis and an exact tie (e.g. a bevelled cube corner, 54.7 deg to all three axes) goes to the higher layer instead of the lowest one. Applies to Tile Grid and UVW Box.
- **0.7.2**: UVW Map (Box) gets the same priority layers, Flip Back Faces with side and texture direction as Tile Grid (own `uvw_*` settings, on by default), live gizmo preview follows them; reversible cell width/height swap; angle ranges refresh the previews.
- **0.7.1**: Tile Grid `Select Controller` button; controller and preview cube are clearly separated in the panel.
- **0.7.0**: code split into modules; single panel `ModwallGN` with module tabs and plates; name `ModwallGN (Simple Tile Cutter)`; safe register / unregister / reload.
- **0.6.14**: layers swap axes; flip side labels by layer role (Top-Bottom, Front-Back, Left-Right).
- **0.6.13**: `Flip side` per layer (floor or ceiling), layers as separate boxes.
- **0.6.12**: texture direction 0 / 90 / 180 / 270.
- **0.6.11 and earlier**: three priority layers with Flip Back Faces and live preview, vertex paint tools, UVW Map, Cylinder Projection.
