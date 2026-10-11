"""Tile Grid: Projection Box, preview object, texture direction callbacks."""

import bpy
from mathutils import Vector
from .bmesh_baker import get_tile_bounds
from .uv_geom import (
    _cell_uv_rotate,
    _choose_axis_and_flip,
    _priority_layers,
    _swap_cell_scale,
    _uv_axes_for,
)
from .preview_mat import _preview_material, _wire_material


def _tile_size_from_settings(s):
    ts_x = s.tile_size_x
    ts_y = s.tile_size_y
    ref = s.reference_tile
    if ref is not None:
        if ref.dimensions.x > 0.001: ts_x = ref.dimensions.x
        if ref.dimensions.z > 0.001: ts_y = ref.dimensions.z
        elif ref.dimensions.y > 0.001: ts_y = ref.dimensions.y
    return ts_x, ts_y


def _set_proj_box_to_tile_size(box, s):
    ts_x, ts_y = _tile_size_from_settings(s)
    vertical = int(s.texture_rotation) in (90, 270)
    if vertical:
        # texture is stored turned by 90 degrees: the cell on the wall is
        # tile height wide and tile width tall
        box.scale = (ts_y, ts_y, ts_x)
    else:
        box.scale = (ts_x, ts_x, ts_y)
    box["tc_vertical"] = vertical


def _delete_tile_preview(s):
    for attr in ("tile_preview", "tile_preview_wire"):
        preview = getattr(s, attr)
        if preview is None:
            continue
        try:
            mesh = preview.data
            bpy.data.objects.remove(preview, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        except Exception:
            pass
        setattr(s, attr, None)


def _create_tile_preview(context, s):
    box = s.proj_box
    if box is None:
        return

    _delete_tile_preview(s)

    mesh = bpy.data.meshes.new(f"TC_PreviewMesh_{box.name}")
    verts = (
        (-0.5, -0.5, -0.5),
        ( 0.5, -0.5, -0.5),
        ( 0.5,  0.5, -0.5),
        (-0.5,  0.5, -0.5),
        (-0.5, -0.5,  0.5),
        ( 0.5, -0.5,  0.5),
        ( 0.5,  0.5,  0.5),
        (-0.5,  0.5,  0.5),
    )
    faces = (
        (0, 3, 2, 1),  # bottom
        (4, 5, 6, 7),  # top
        (0, 1, 5, 4),  # front
        (1, 2, 6, 5),  # right
        (2, 3, 7, 6),  # back
        (3, 0, 4, 7),  # left
    )
    mesh.from_pydata(verts, [], faces)
    mesh.validate(clean_customdata=False)
    mesh.update(calc_edges=True)

    uv_layer = mesh.uv_layers.new(name="UVMap")
    b_min, b_max = get_tile_bounds(s.reference_tile)
    face_modes = ("bottom", "top", "front", "right", "back", "left")

    def remap_uv(u, v):
        return (
            b_min[0] + u * (b_max[0] - b_min[0]),
            b_min[1] + v * (b_max[1] - b_min[1]),
        )

    layers = _priority_layers(s)
    rotation = int(s.texture_rotation)
    box_axes = (Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0)))
    face_normals = {
        "bottom": Vector((0.0, 0.0, -1.0)),
        "top":    Vector((0.0, 0.0, 1.0)),
        "front":  Vector((0.0, -1.0, 0.0)),
        "right":  Vector((1.0, 0.0, 0.0)),
        "back":   Vector((0.0, 1.0, 0.0)),
        "left":   Vector((-1.0, 0.0, 0.0)),
    }

    def preview_uv(mode, co):
        # Same decision as Apply: which axis/layer owns this face and whether
        # it is turned over, so toggles are visible on the preview.
        fn = face_normals[mode]
        major, flip, eps, opp = _choose_axis_and_flip(fn, layers, *box_axes)
        ua, va = _uv_axes_for(major, fn, flip, *box_axes, eps, opp)
        u, v = _cell_uv_rotate(co.dot(ua) + 0.5, co.dot(va) + 0.5, rotation)
        return remap_uv(u, v)

    for poly, mode in zip(mesh.polygons, face_modes):
        for loop_index in poly.loop_indices:
            vert = mesh.vertices[mesh.loops[loop_index].vertex_index]
            uv_layer.data[loop_index].uv = preview_uv(mode, vert.co)

    preview = bpy.data.objects.new(f"TC_Preview_{box.name}", mesh)
    context.collection.objects.link(preview)
    preview.parent = box
    preview.matrix_parent_inverse.identity()
    preview.location = (0.0, 0.0, 0.0)
    preview.rotation_euler = (0.0, 0.0, 0.0)
    preview.scale = (1.0, 1.0, 1.0)
    preview.hide_render = True
    preview.hide_select = True
    preview.display_type = 'TEXTURED'
    preview.data.materials.append(_preview_material(s.reference_tile))
    s.tile_preview = preview

    wire_mesh = bpy.data.meshes.new(f"TC_PreviewWireMesh_{box.name}")
    edges = (
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    )
    wire_mesh.from_pydata(verts, edges, [])
    wire_mesh.update(calc_edges=True)

    wire = bpy.data.objects.new(f"TC_PreviewWire_{box.name}", wire_mesh)
    context.collection.objects.link(wire)
    wire.parent = box
    wire.matrix_parent_inverse.identity()
    wire.location = (0.0, 0.0, 0.0)
    wire.rotation_euler = (0.0, 0.0, 0.0)
    wire.scale = (1.0, 1.0, 1.0)
    wire.hide_render = True
    wire.hide_select = True
    wire.display_type = 'WIRE'
    wire.show_in_front = True
    wire.data.materials.append(_wire_material())
    s.tile_preview_wire = wire


def _create_proj_box(context, s):
    target = s.target_object

    box_name = f"TC_Box_{target.name}"
    box = bpy.data.objects.get(box_name)
    if box is not None and box.type != 'EMPTY':
        box = None   # a foreign object has this name: make our own (unique name)
    if box is None:
        box = bpy.data.objects.new(box_name, None)
        box.empty_display_type = 'CUBE'
        context.collection.objects.link(box)

    box.empty_display_size = 1.0
    box.parent = target
    box.matrix_parent_inverse.identity()   # box lives in parent's local space
    box.location       = (0.0, 0.0, 0.0)
    box.rotation_euler = (0.0, 0.0, 0.0)
    _set_proj_box_to_tile_size(box, s)
    box.hide_render    = True
    s.proj_box = box
    _create_tile_preview(context, s)


def _delete_proj_box(s):
    _delete_tile_preview(s)
    box = s.proj_box
    if box is not None:
        try:
            bpy.data.objects.remove(box, do_unlink=True)
        except Exception:
            pass


def _sync_proj_box(self, context):
    s = context.scene.tc_settings
    if s.target_object is not None and s.reference_tile is not None:
        if s.proj_box is None or s.proj_box.parent != s.target_object:
            if s.proj_box is not None:
                _delete_proj_box(s)
                s.proj_box = None
            _create_proj_box(context, s)
        else:
            _set_proj_box_to_tile_size(s.proj_box, s)
            _create_tile_preview(context, s)
    else:
        if s.proj_box is not None:
            _delete_proj_box(s)
            s.proj_box = None
        else:
            _delete_tile_preview(s)


def _on_texture_rotation(self, context):
    """Switching between horizontal and vertical swaps the cell width/height
    of the existing Projection Box; then the preview is rebuilt."""
    s = context.scene.tc_settings
    box = s.proj_box
    if box is not None:
        vertical = int(s.texture_rotation) in (90, 270)
        if bool(box.get("tc_vertical", False)) != vertical:
            _swap_cell_scale(box, vertical)
    _refresh_tile_preview(self, context)


def _refresh_tile_preview(self, context):
    s = context.scene.tc_settings
    if s.proj_box is not None and s.reference_tile is not None:
        _create_tile_preview(context, s)
