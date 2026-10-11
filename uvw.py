"""UVW Map Projection: gizmo, previews and UV projection functions."""

import bpy
import math
from mathutils import Vector
from .bmesh_baker import get_tile_bounds
from .preview_mat import _preview_material, _wire_material
from .uv_geom import (
    _AXIS_ORDER,
    _cell_uv_rotate,
    _choose_axis_and_flip,
    _priority_layers,
    _swap_cell_scale,
    _uv_axes_for,
)


def _delete_uvw_gizmo(s):
    for attr in ('uvw_gizmo_preview', 'uvw_gizmo_preview_wire'):
        obj = getattr(s, attr, None)
        if obj is None:
            continue
        try:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        except Exception:
            pass
        try:
            setattr(s, attr, None)
        except Exception:
            pass
    gizmo = s.uvw_gizmo
    if gizmo is not None:
        try:
            bpy.data.objects.remove(gizmo, do_unlink=True)
        except Exception:
            pass
    try:
        s.uvw_gizmo = None
    except Exception:
        pass


def _remap_preview_uv(ref, u, v):
    b_min, b_max = get_tile_bounds(ref)
    return (
        b_min[0] + u * (b_max[0] - b_min[0]),
        b_min[1] + v * (b_max[1] - b_min[1]),
    )


def _uvw_reference_tile_sizes(ref):
    if ref is None:
        return 1.0, 1.0
    tile_u = ref.dimensions.x
    tile_v = ref.dimensions.z if ref.dimensions.z > 0.001 else ref.dimensions.y
    if tile_u < 0.001:
        tile_u = 1.0
    if tile_v < 0.001:
        tile_v = tile_u
    return tile_u, tile_v


def _uvw_tile_sizes_from_settings(s):
    return max(s.tile_size_x, 0.001), max(s.tile_size_y, 0.001)


def _uvw_preview_box(context, s, gizmo, ref):
    verts = (
        (-0.5, -0.5, -0.5), ( 0.5, -0.5, -0.5),
        ( 0.5,  0.5, -0.5), (-0.5,  0.5, -0.5),
        (-0.5, -0.5,  0.5), ( 0.5, -0.5,  0.5),
        ( 0.5,  0.5,  0.5), (-0.5,  0.5,  0.5),
    )
    faces = (
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (1, 2, 6, 5),
        (2, 3, 7, 6), (3, 0, 4, 7),
    )
    mesh = bpy.data.meshes.new("TC_UVWPreviewMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.validate(clean_customdata=False)
    mesh.update(calc_edges=True)
    uv_layer = mesh.uv_layers.new(name="UVMap")
    face_modes = ("bottom", "top", "front", "right", "back", "left")

    layers = _priority_layers(s, "uvw_") if s.uvw_use_priority_axis else None
    rotation = int(s.uvw_texture_rotation)
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
        # Same decision as Apply: axis/layer of this face, local flip, then
        # texture direction and the global U / V flips.
        fn = face_normals[mode]
        major, flip, eps, opp = _choose_axis_and_flip(fn, layers, *box_axes)
        ua, va = _uv_axes_for(major, fn, flip, *box_axes, eps, opp)
        u, v = _cell_uv_rotate(co.dot(ua) + 0.5, co.dot(va) + 0.5, rotation)
        if s.uvw_flip_u:
            u = 1.0 - u
        if s.uvw_flip_v:
            v = 1.0 - v
        return _remap_preview_uv(ref, u, v)

    for poly, mode in zip(mesh.polygons, face_modes):
        for loop_index in poly.loop_indices:
            vert = mesh.vertices[mesh.loops[loop_index].vertex_index]
            uv_layer.data[loop_index].uv = preview_uv(mode, vert.co)

    preview = bpy.data.objects.new("TC_UVWPreview", mesh)
    context.collection.objects.link(preview)
    preview.parent = gizmo
    preview.matrix_parent_inverse.identity()
    preview.location = preview.rotation_euler = (0.0, 0.0, 0.0)
    preview.scale = (1.0, 1.0, 1.0)
    preview.hide_render = preview.hide_select = True
    preview.display_type = 'TEXTURED'
    preview.data.materials.append(_preview_material(ref))
    s.uvw_gizmo_preview = preview

    edges = (
        (0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7),
    )
    wire_mesh = bpy.data.meshes.new("TC_UVWPreviewWireMesh")
    wire_mesh.from_pydata(verts, edges, [])
    wire_mesh.update(calc_edges=True)
    wire = bpy.data.objects.new("TC_UVWPreviewWire", wire_mesh)
    context.collection.objects.link(wire)
    wire.parent = gizmo
    wire.matrix_parent_inverse.identity()
    wire.location = wire.rotation_euler = (0.0, 0.0, 0.0)
    wire.scale = (1.0, 1.0, 1.0)
    wire.hide_render = wire.hide_select = True
    wire.display_type = 'WIRE'
    wire.show_in_front = True
    wire.data.materials.append(_wire_material())
    s.uvw_gizmo_preview_wire = wire


def _uvw_preview_plane(context, s, gizmo, ref):
    verts = ((-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (0.5, 0.5, 0.0), (-0.5, 0.5, 0.0))
    mesh = bpy.data.meshes.new("TC_UVWPreviewMesh")
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.validate(clean_customdata=False)
    mesh.update(calc_edges=True)
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            vert = mesh.vertices[mesh.loops[loop_index].vertex_index]
            uv_layer.data[loop_index].uv = _remap_preview_uv(
                ref, vert.co.x + 0.5, vert.co.y + 0.5,
            )

    preview = bpy.data.objects.new("TC_UVWPreview", mesh)
    context.collection.objects.link(preview)
    preview.parent = gizmo
    preview.matrix_parent_inverse.identity()
    preview.location = preview.rotation_euler = (0.0, 0.0, 0.0)
    preview.scale = (1.0, 1.0, 1.0)
    preview.hide_render = preview.hide_select = True
    preview.display_type = 'TEXTURED'
    preview.data.materials.append(_preview_material(ref))
    s.uvw_gizmo_preview = preview

    wire_mesh = bpy.data.meshes.new("TC_UVWPreviewWireMesh")
    wire_mesh.from_pydata(verts, ((0,1),(1,2),(2,3),(3,0)), [])
    wire_mesh.update(calc_edges=True)
    wire = bpy.data.objects.new("TC_UVWPreviewWire", wire_mesh)
    context.collection.objects.link(wire)
    wire.parent = gizmo
    wire.matrix_parent_inverse.identity()
    wire.location = wire.rotation_euler = (0.0, 0.0, 0.0)
    wire.scale = (1.0, 1.0, 1.0)
    wire.hide_render = wire.hide_select = True
    wire.display_type = 'WIRE'
    wire.show_in_front = True
    wire.data.materials.append(_wire_material())
    s.uvw_gizmo_preview_wire = wire


def _uvw_preview_cylinder(context, s, gizmo, ref):
    n = 16
    r = 0.5
    verts_b = [(r * math.cos(2*math.pi*i/n), r * math.sin(2*math.pi*i/n), -0.5) for i in range(n)]
    verts_t = [(r * math.cos(2*math.pi*i/n), r * math.sin(2*math.pi*i/n),  0.5) for i in range(n)]
    verts = verts_b + verts_t
    faces = [(i, (i+1)%n, n+(i+1)%n, n+i) for i in range(n)]

    mesh = bpy.data.meshes.new("TC_UVWPreviewMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.validate(clean_customdata=False)
    mesh.update(calc_edges=True)
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for poly_index, poly in enumerate(mesh.polygons):
        u0 = poly_index / n
        u1 = (poly_index + 1) / n
        for corner, loop_index in enumerate(poly.loop_indices):
            vert = mesh.vertices[mesh.loops[loop_index].vertex_index]
            u = u0 if corner in {0, 3} else u1
            v = vert.co.z + 0.5
            uv_layer.data[loop_index].uv = _remap_preview_uv(ref, u, v)

    preview = bpy.data.objects.new("TC_UVWPreview", mesh)
    context.collection.objects.link(preview)
    preview.parent = gizmo
    preview.matrix_parent_inverse.identity()
    preview.location = preview.rotation_euler = (0.0, 0.0, 0.0)
    preview.scale = (1.0, 1.0, 1.0)
    preview.hide_render = preview.hide_select = True
    preview.display_type = 'TEXTURED'
    preview.data.materials.append(_preview_material(ref))
    s.uvw_gizmo_preview = preview

    wire_edges = []
    for i in range(n):
        j = (i+1) % n
        wire_edges += [(i, j), (n+i, n+j), (i, n+i)]
    wire_mesh = bpy.data.meshes.new("TC_UVWPreviewWireMesh")
    wire_mesh.from_pydata(verts, wire_edges, [])
    wire_mesh.update(calc_edges=True)
    wire = bpy.data.objects.new("TC_UVWPreviewWire", wire_mesh)
    context.collection.objects.link(wire)
    wire.parent = gizmo
    wire.matrix_parent_inverse.identity()
    wire.location = wire.rotation_euler = (0.0, 0.0, 0.0)
    wire.scale = (1.0, 1.0, 1.0)
    wire.hide_render = wire.hide_select = True
    wire.display_type = 'WIRE'
    wire.show_in_front = True
    wire.data.materials.append(_wire_material())
    s.uvw_gizmo_preview_wire = wire


def _create_uvw_gizmo(context, s):
    target = s.uvw_target
    ref    = s.uvw_reference_tile
    if target is None or ref is None:
        return None

    _delete_uvw_gizmo(s)

    mapping = s.uvw_mapping_type
    gizmo_name = f"TC_UVWGizmo_{target.name}"
    gizmo = bpy.data.objects.new(gizmo_name, None)
    gizmo.empty_display_type = {'BOX': 'CUBE', 'PLANAR': 'SINGLE_ARROW', 'CYLINDER': 'CIRCLE'}.get(mapping, 'CUBE')
    gizmo.empty_display_size = 1.0
    context.collection.objects.link(gizmo)
    gizmo.parent = target
    gizmo.matrix_parent_inverse.identity()
    gizmo.location = gizmo.rotation_euler = (0.0, 0.0, 0.0)

    tile_u, tile_v = _uvw_reference_tile_sizes(ref)
    if mapping == 'PLANAR':
        gizmo.scale = (tile_u, tile_v, 1.0)
    elif mapping == 'BOX':
        if int(s.uvw_texture_rotation) in (90, 270):
            gizmo.scale = (tile_v, tile_v, tile_u)
            gizmo["tc_vertical"] = True
        else:
            gizmo.scale = (tile_u, tile_u, tile_v)
            gizmo["tc_vertical"] = False
    else:  # CYLINDER
        radius = max((tile_u * max(s.uvw_cylinder_tiles_around, 1)) / (2.0 * math.pi), 0.001)
        gizmo.scale = (radius, radius, tile_v)

    gizmo.hide_render = True
    gizmo.show_in_front = True
    s.uvw_gizmo = gizmo

    if mapping == 'BOX':
        _uvw_preview_box(context, s, gizmo, ref)
    elif mapping == 'PLANAR':
        _uvw_preview_plane(context, s, gizmo, ref)
    else:
        _uvw_preview_cylinder(context, s, gizmo, ref)

    try:
        gizmo.select_set(True)
        context.view_layer.objects.active = gizmo
    except Exception:
        pass
    return gizmo


def _sync_uvw_gizmo(self, context):
    s = context.scene.tc_settings
    if s.uvw_target is not None and s.uvw_reference_tile is not None:
        _create_uvw_gizmo(context, s)
    else:
        _delete_uvw_gizmo(s)


def _apply_uvw_box_uv(bm, b_min, b_max, tile_u, tile_v, gizmo_local_mat,
                      flip_u=False, flip_v=False, layers=None, rotation=0):
    """Box projection from the gizmo axes.

    layers=None keeps the classic rule (axis with the largest normal
    component, ties Y > Z > X). With `layers` (see uv_geom._priority_layers)
    the axis of each face is chosen by the priority layers, with per-layer
    flip. Order: axis + local flip, continuous projection, texture direction
    (rotation about the cell centre), global U / V flip, remap.
    """
    uv_layer = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    tile_u = max(tile_u, 0.001)
    tile_v = max(tile_v, 0.001)

    rot_mat = gizmo_local_mat.to_3x3()
    ax_x = rot_mat.col[0].normalized()
    ax_y = rot_mat.col[1].normalized()
    ax_z = rot_mat.col[2].normalized()
    box_origin = gizmo_local_mat.to_translation()
    bm.normal_update()

    for face in bm.faces:
        fn = face.normal
        major, flip, eps, opp = _choose_axis_and_flip(fn, layers, ax_x, ax_y, ax_z)
        ua, va = _uv_axes_for(major, fn, flip, ax_x, ax_y, ax_z, eps, opp)

        for loop in face.loops:
            p = loop.vert.co - box_origin
            uf = p.dot(ua) / tile_u + 0.5
            vf = p.dot(va) / tile_v + 0.5
            uf, vf = _cell_uv_rotate(uf, vf, rotation)
            if flip_u:
                uf = 1.0 - uf
            if flip_v:
                vf = 1.0 - vf
            loop[uv_layer].uv = (
                b_min[0] + uf * (b_max[0] - b_min[0]),
                b_min[1] + vf * (b_max[1] - b_min[1]),
            )


def _apply_uvw_planar_uv(bm, b_min, b_max, tile_u, tile_v, gizmo_local_mat,
                         flip_u=False, flip_v=False):
    uv_layer = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    tile_u = max(tile_u, 0.001)
    tile_v = max(tile_v, 0.001)

    rot_mat = gizmo_local_mat.to_3x3()
    ax_u = rot_mat.col[0].normalized()
    ax_v = rot_mat.col[1].normalized()
    origin = gizmo_local_mat.to_translation()

    for face in bm.faces:
        for loop in face.loops:
            p = loop.vert.co - origin
            uf = p.dot(ax_u) / tile_u + 0.5
            vf = p.dot(ax_v) / tile_v + 0.5
            if flip_u:
                uf = 1.0 - uf
            if flip_v:
                vf = 1.0 - vf
            loop[uv_layer].uv = (
                b_min[0] + uf * (b_max[0] - b_min[0]),
                b_min[1] + vf * (b_max[1] - b_min[1]),
            )


def _apply_uvw_cylinder_uv(bm, gizmo_local_mat, tiles_around, tile_v,
                            flip_u, flip_v, b_min, b_max):
    """Cylindrical projection around local Z of gizmo.
    tiles_around = number of texture repeats around the full circumference.
    tile_v = target-local height of one V tile.
    """
    uv_layer = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    tiles_around = max(tiles_around, 1)
    tile_v = max(tile_v, 0.001)
    angle_per_tile = 2.0 * math.pi / tiles_around

    rot_mat = gizmo_local_mat.to_3x3()
    ax_x = rot_mat.col[0].normalized()
    ax_y = rot_mat.col[1].normalized()
    ax_z = rot_mat.col[2].normalized()
    origin = gizmo_local_mat.to_translation()

    for face in bm.faces:
        fc = face.calc_center_median() - origin
        fc_x = fc.dot(ax_x)
        fc_y = fc.dot(ax_y)
        angle_c = math.atan2(fc_y, fc_x)
        if angle_c < 0.0:
            angle_c += 2.0 * math.pi

        for loop in face.loops:
            p = loop.vert.co - origin
            p_x = p.dot(ax_x)
            p_y = p.dot(ax_y)
            p_z = p.dot(ax_z)
            angle_v = math.atan2(p_y, p_x)
            if angle_v < 0.0:
                angle_v += 2.0 * math.pi
            delta = angle_v - angle_c
            if delta >  math.pi:
                delta -= 2.0 * math.pi
            if delta < -math.pi:
                delta += 2.0 * math.pi
            uf = (angle_c + delta) / angle_per_tile
            vf = p_z / tile_v + 0.5
            if flip_u:
                uf = 1.0 - uf
            if flip_v:
                vf = 1.0 - vf
            loop[uv_layer].uv = (
                b_min[0] + uf * (b_max[0] - b_min[0]),
                b_min[1] + vf * (b_max[1] - b_min[1]),
            )


# ── Priority layers: callbacks (do not recreate the gizmo) ────────────────────

def _delete_uvw_preview_objects(s):
    for attr in ('uvw_gizmo_preview', 'uvw_gizmo_preview_wire'):
        obj = getattr(s, attr, None)
        if obj is None:
            continue
        try:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        except Exception:
            pass
        try:
            setattr(s, attr, None)
        except Exception:
            pass


def _refresh_uvw_preview(self, context):
    """Rebuild only the preview objects; the gizmo and its transform stay."""
    s = context.scene.tc_settings
    gizmo = s.uvw_gizmo
    ref = s.uvw_reference_tile
    if gizmo is None or ref is None:
        return
    _delete_uvw_preview_objects(s)
    mapping = s.uvw_mapping_type
    if mapping == 'BOX':
        _uvw_preview_box(context, s, gizmo, ref)
    elif mapping == 'PLANAR':
        _uvw_preview_plane(context, s, gizmo, ref)
    else:
        _uvw_preview_cylinder(context, s, gizmo, ref)


def _sync_uvw_priority_axes(self, context):
    """Layer 1 axis changed: swap with layer 2 if it used that axis."""
    new = self.uvw_priority_axis
    old = self.uvw_priority_axis_prev
    if self.uvw_secondary_axis == new:
        if old in _AXIS_ORDER and old != new:
            self.uvw_secondary_axis = old
        else:
            self.uvw_secondary_axis = next(a for a in _AXIS_ORDER if a != new)
    self.uvw_priority_axis_prev = new
    _refresh_uvw_preview(self, context)


def _on_uvw_texture_rotation(self, context):
    """Horizontal <-> vertical swaps the cell width / height of a Box gizmo."""
    s = context.scene.tc_settings
    gizmo = s.uvw_gizmo
    if gizmo is not None and s.uvw_mapping_type == 'BOX':
        vertical = int(s.uvw_texture_rotation) in (90, 270)
        if bool(gizmo.get("tc_vertical", False)) != vertical:
            _swap_cell_scale(gizmo, vertical)
    _refresh_uvw_preview(self, context)
