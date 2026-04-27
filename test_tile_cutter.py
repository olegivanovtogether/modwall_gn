"""
Run in Blender's Text Editor (with Simple Tile Cutter addon enabled) to verify the pipeline.

Creates:
  TestWall  — a plane scaled to wall proportions (target)
  RefTile   — a unit plane with UV (reference tile)

Then calls tilecutter.apply and prints results to the System Console.
"""

import bpy


def run_test():
    print("\n--- Simple Tile Cutter test ---")

    # Target wall: plane scaled to 4 x 3 m wall shape
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, 0))
    wall = bpy.context.active_object
    wall.name = "TestWall"
    wall.scale = (4.0, 0.2, 3.0)
    bpy.ops.object.transform_apply(scale=True)
    print(f"Created wall: {wall.name}")

    # Reference tile: unit plane with UV at (6, 0, 0)
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(6, 0, 0))
    tile = bpy.context.active_object
    tile.name = "RefTile"
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"Created reference tile: {tile.name}")

    # Configure
    s = bpy.context.scene.tc_settings
    s.target_object = wall
    s.reference_tile = tile
    s.tile_size_x = 1.0
    s.tile_size_y = 1.0
    s.rotation = '0'
    s.duplicate_before_apply = True

    # Run
    result = bpy.ops.tilecutter.apply()
    print(f"Operator result: {result}")

    tiled = bpy.context.active_object
    mesh = tiled.data
    print(f"Output object: {tiled.name}")
    print(f"Faces: {len(mesh.polygons)}")
    print(f"UV layers: {[l.name for l in mesh.uv_layers]}")

    if mesh.uv_layers:
        uvs = [l.uv[:] for l in mesh.uv_layers[0].data]
        u_vals = [uv[0] for uv in uvs]
        v_vals = [uv[1] for uv in uvs]
        print(f"UV U range: [{min(u_vals):.3f}, {max(u_vals):.3f}]")
        print(f"UV V range: [{min(v_vals):.3f}, {max(v_vals):.3f}]")

    print("--- Test complete ---\n")


run_test()
