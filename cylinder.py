"""Cylinder Projection: cuts, control empty, preview."""

import bpy
import bmesh
import math
from mathutils import Matrix, Vector
from .bmesh_baker import get_tile_bounds
from .preview_mat import _preview_material, _wire_material


_CYL_AXIS_MAP = {'X': 0, 'Y': 1, 'Z': 2}


def _cyl_axis_idx(s):
    return _CYL_AXIS_MAP.get(s.cylinder_axis, 2)


def _cyl_decompose(co, axis_idx):
    """Split a coordinate into (perp1, perp2, height) for the given cylinder axis."""
    if axis_idx == 0:   # X axis: height=x, perp=yz
        return co.y, co.z, co.x
    elif axis_idx == 1: # Y axis: height=y, perp=xz
        return co.x, co.z, co.y
    else:               # Z axis: height=z, perp=xy
        return co.x, co.y, co.z


def _cyl_ref_dim(ref, axis_key):
    if ref is None:
        return 0.0
    if axis_key == 'X':
        return ref.dimensions.x
    if axis_key == 'Y':
        return ref.dimensions.y
    if axis_key == 'Z':
        return ref.dimensions.z
    return 0.0


def _cyl_tile_height(s):
    """Return cylinder tile height from the selected source."""
    ref = s.cylinder_reference_tile

    if s.cylinder_tile_height_source == 'MANUAL':
        return max(s.cylinder_tile_height, 0.001)

    if s.cylinder_tile_height_source in {'X', 'Y', 'Z'}:
        dim = _cyl_ref_dim(ref, s.cylinder_tile_height_source)
        if dim > 0.001:
            return dim
        return max(s.cylinder_tile_height, 0.001)

    if ref is not None:
        dims = [ref.dimensions.x, ref.dimensions.y, ref.dimensions.z]
        usable = sorted(dim for dim in dims if dim > 0.001)
        if usable:
            return usable[0]

    return max(s.cylinder_tile_height, 0.001)


def _cyl_tile_plane_sizes(s):
    ref = s.cylinder_reference_tile
    if ref is not None:
        dims = [ref.dimensions.x, ref.dimensions.y, ref.dimensions.z]
        usable = [dim for dim in dims if dim > 0.001]
        if len(usable) >= 2:
            return usable[0], usable[1]
        if len(usable) == 1:
            return usable[0], usable[0]
    fallback = _cyl_tile_height(s)
    return fallback, fallback


def _delete_cylinder_preview(s):
    for attr in ('cylinder_preview', 'cylinder_preview_wire'):
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


def _delete_cylinder_control(s):
    _delete_cylinder_preview(s)
    control = s.cylinder_control
    if control is not None:
        try:
            bpy.data.objects.remove(control, do_unlink=True)
        except Exception:
            pass
    s.cylinder_control = None


def _create_cylinder_control(context, s):
    target = s.cylinder_target
    if target is None:
        return None

    control_name = f"TC_CylControl_{target.name}"
    control = bpy.data.objects.get(control_name)
    if control is None or control.parent != target:
        if control is not None:
            try:
                bpy.data.objects.remove(control, do_unlink=True)
            except Exception:
                pass
        control = bpy.data.objects.new(control_name, None)
        control.empty_display_type = 'CUBE'
        context.collection.objects.link(control)

    control.empty_display_type = 'CUBE'
    control.empty_display_size = 1.5
    control.parent = target
    control.matrix_parent_inverse.identity()
    if s.cylinder_control is None or s.cylinder_control != control:
        control.location = (0.0, 0.0, 0.0)
        control.rotation_euler = (0.0, 0.0, 0.0)
        control.scale = (1.0, 1.0, 1.0)
    control.hide_render = True
    control.show_in_front = True
    s.cylinder_control = control
    try:
        control.select_set(True)
        context.view_layer.objects.active = control
    except Exception:
        pass
    return control


def _cyl_projection_frame(s, target):
    control = s.cylinder_control
    if control is not None:
        local_mat = target.matrix_world.inverted() @ control.matrix_world
        control_inv = local_mat.inverted()
        rot_mat = local_mat.to_3x3()
        axes = (
            rot_mat.col[0].normalized(),
            rot_mat.col[1].normalized(),
            rot_mat.col[2].normalized(),
        )
    else:
        local_mat = Matrix.Identity(4)
        control_inv = Matrix.Identity(4)
        axes = (
            Vector((1.0, 0.0, 0.0)),
            Vector((0.0, 1.0, 0.0)),
            Vector((0.0, 0.0, 1.0)),
        )

    axis_idx = _cyl_axis_idx(s)
    height_axis = axes[axis_idx]
    return control_inv, height_axis, local_mat


def _cyl_local_point(axis_idx, radial_a, radial_b, height):
    if axis_idx == 0:
        return Vector((height, radial_a, radial_b))
    if axis_idx == 1:
        return Vector((radial_a, height, radial_b))
    return Vector((radial_a, radial_b, height))


def _slice_cylinder_height_bands(bm, control_inv, control_mat, axis_idx, tile_h):
    if tile_h <= 0.001:
        return

    values = [
        _cyl_decompose(control_inv @ vert.co, axis_idx)[2]
        for vert in bm.verts
    ]
    if not values:
        return

    start_mult = math.floor(min(values) / tile_h - 0.5)
    end_mult   = math.ceil(max(values) / tile_h - 0.5)
    plane_no = control_mat.to_3x3().col[axis_idx].normalized()

    for mult in range(start_mult, end_mult + 1):
        dist = (mult + 0.5) * tile_h
        plane_co = control_mat @ _cyl_local_point(axis_idx, 0.0, 0.0, dist)
        bmesh.ops.bisect_plane(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=plane_co,
            plane_no=plane_no,
            clear_inner=False,
            clear_outer=False,
        )


def _slice_cylinder_around_sectors(bm, control_mat, axis_idx, tiles_around):
    tiles_around = max(tiles_around, 1)
    if tiles_around <= 1:
        return

    radial_indices = [idx for idx in range(3) if idx != axis_idx]
    tile_angle = 2.0 * math.pi / tiles_around
    plane_co = control_mat.to_translation()
    rot_mat = control_mat.to_3x3()

    for mult in range(tiles_around):
        angle = mult * tile_angle
        local_no = Vector((0.0, 0.0, 0.0))
        local_no[radial_indices[0]] = -math.sin(angle)
        local_no[radial_indices[1]] = math.cos(angle)
        plane_no = (rot_mat @ local_no).normalized()

        bmesh.ops.bisect_plane(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=plane_co,
            plane_no=plane_no,
            clear_inner=False,
            clear_outer=False,
        )


def _slice_cylinder_caps_grid(bm, control_inv, control_mat, axis_idx,
                              tile_u, tile_v):
    radial_indices = [idx for idx in range(3) if idx != axis_idx]
    radial_axes = [
        control_mat.to_3x3().col[radial_indices[0]].normalized(),
        control_mat.to_3x3().col[radial_indices[1]].normalized(),
    ]
    steps = (tile_u, tile_v)

    for radial_axis_idx, step in zip(radial_indices, steps):
        if step <= 0.001:
            continue

        values = []
        for vert in bm.verts:
            local = control_inv @ vert.co
            values.append(local[radial_axis_idx])
        if not values:
            continue

        start_mult = math.floor(min(values) / step - 0.5)
        end_mult = math.ceil(max(values) / step - 0.5)
        plane_no = radial_axes[0 if radial_axis_idx == radial_indices[0] else 1]

        for mult in range(start_mult, end_mult + 1):
            dist = (mult + 0.5) * step
            local_co = Vector((0.0, 0.0, 0.0))
            local_co[radial_axis_idx] = dist
            plane_co = control_mat @ local_co

            cap_faces = [
                face for face in bm.faces
                if abs(face.normal.dot(control_mat.to_3x3().col[axis_idx].normalized())) > 0.7
            ]
            geom = set()
            for face in cap_faces:
                geom.add(face)
                for edge in face.edges:
                    geom.add(edge)
                for vert in face.verts:
                    geom.add(vert)
            if not geom:
                continue

            bmesh.ops.bisect_plane(
                bm,
                geom=list(geom),
                plane_co=plane_co,
                plane_no=plane_no,
                clear_inner=False,
                clear_outer=False,
            )


def _build_cylinder_verts(n, h, r, axis_idx):
    """Generate (bottom_ring, top_ring) vertex lists for a prism with n sides."""
    bottom, top = [], []
    for i in range(n):
        angle = 2.0 * math.pi * i / n
        c = r * math.cos(angle)
        sv = r * math.sin(angle)
        if axis_idx == 2:   # Z
            bottom.append(( c,  sv, -h * 0.5))
            top.append(   ( c,  sv,  h * 0.5))
        elif axis_idx == 1: # Y
            bottom.append(( c, -h * 0.5,  sv))
            top.append(   ( c,  h * 0.5,  sv))
        else:               # X
            bottom.append((-h * 0.5,  c,  sv))
            top.append(   ( h * 0.5,  c,  sv))
    return bottom, top


def _create_cylinder_preview(context, s):
    target = s.cylinder_target
    ref    = s.cylinder_reference_tile
    if target is None or ref is None:
        return

    control = s.cylinder_control or _create_cylinder_control(context, s)
    if control is None:
        return

    _delete_cylinder_preview(s)

    tiles      = max(s.cylinder_tiles_around, 1)
    n          = 3 if tiles == 1 else (4 if tiles == 2 else tiles)
    axis_idx   = _cyl_axis_idx(s)
    h          = _cyl_tile_height(s)
    r          = 1.0  # schematic radius
    b_min, b_max = get_tile_bounds(ref)

    bottom, top = _build_cylinder_verts(n, h, r, axis_idx)
    verts = bottom + top   # indices 0..n-1 = bottom ring, n..2n-1 = top ring

    # Side quads: one per tile → each gets the full reference tile UV
    side_faces = []
    for i in range(n):
        j = (i + 1) % n
        side_faces.append((i, j, n + j, n + i))

    # Cap polygons (N-gons)
    bot_cap = list(range(n - 1, -1, -1))   # reversed winding → normal points down
    top_cap = list(range(n, 2 * n))

    # ── Solid preview ─────────────────────────────────────────────────────
    all_faces = side_faces[:]
    if s.cylinder_project_caps:
        all_faces += [bot_cap, top_cap]

    mesh = bpy.data.meshes.new("TC_CylPreviewMesh")
    mesh.from_pydata(verts, [], all_faces)
    mesh.validate(clean_customdata=False)
    mesh.update(calc_edges=True)

    uv_layer = mesh.uv_layers.new(name="UVMap")

    def remap(u, v):
        return (b_min[0] + u * (b_max[0] - b_min[0]),
                b_min[1] + v * (b_max[1] - b_min[1]))

    loop_idx = 0
    # Side preview: distribute Tiles Around repeats across the whole preview.
    segments_per_tile = n / tiles
    for i, _ in enumerate(side_faces):
        u0 = (i / segments_per_tile) % 1.0
        u1 = ((i + 1) / segments_per_tile) % 1.0
        if u1 == 0.0 and u0 != 0.0:
            u1 = 1.0
        for u, v in ((u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)):
            uv_layer.data[loop_idx].uv = remap(u, v)
            loop_idx += 1

    if s.cylinder_project_caps:
        # Bottom cap: planar, perpendicular coords normalised to [0,1]
        for vi in bot_cap:
            co = Vector(verts[vi])
            p1, p2, _ = _cyl_decompose(co, axis_idx)
            uv_layer.data[loop_idx].uv = remap(
                (p1 / r * 0.5 + 0.5),
                (p2 / r * 0.5 + 0.5),
            )
            loop_idx += 1
        # Top cap
        for vi in top_cap:
            co = Vector(verts[vi])
            p1, p2, _ = _cyl_decompose(co, axis_idx)
            uv_layer.data[loop_idx].uv = remap(
                (p1 / r * 0.5 + 0.5),
                (p2 / r * 0.5 + 0.5),
            )
            loop_idx += 1

    preview = bpy.data.objects.new("TC_CylPreview", mesh)
    context.collection.objects.link(preview)
    preview.parent              = control
    preview.matrix_parent_inverse.identity()
    preview.location            = (0.0, 0.0, 0.0)
    preview.rotation_euler      = (0.0, 0.0, 0.0)
    preview.scale               = (1.0, 1.0, 1.0)
    preview.hide_render         = True
    preview.hide_select         = True
    preview.display_type        = 'TEXTURED'
    preview.data.materials.append(_preview_material(ref))
    s.cylinder_preview = preview

    # ── Wire preview ──────────────────────────────────────────────────────
    wire_edges = []
    for i in range(n):
        j = (i + 1) % n
        wire_edges += [(i, j), (n + i, n + j), (i, n + i)]

    wire_mesh = bpy.data.meshes.new("TC_CylPreviewWireMesh")
    wire_mesh.from_pydata(verts, wire_edges, [])
    wire_mesh.update(calc_edges=True)

    wire = bpy.data.objects.new("TC_CylPreviewWire", wire_mesh)
    context.collection.objects.link(wire)
    wire.parent              = control
    wire.matrix_parent_inverse.identity()
    wire.location            = (0.0, 0.0, 0.0)
    wire.rotation_euler      = (0.0, 0.0, 0.0)
    wire.scale               = (1.0, 1.0, 1.0)
    wire.hide_render         = True
    wire.hide_select         = True
    wire.display_type        = 'WIRE'
    wire.show_in_front       = True
    wire.data.materials.append(_wire_material())
    s.cylinder_preview_wire = wire


def _sync_cylinder_preview(self, context):
    """Update callback for all cylinder-related properties."""
    s = context.scene.tc_settings
    if s.cylinder_target is not None and s.cylinder_reference_tile is not None:
        if s.cylinder_control is None or s.cylinder_control.parent != s.cylinder_target:
            if s.cylinder_control is not None:
                _delete_cylinder_control(s)
            _create_cylinder_control(context, s)
        _create_cylinder_preview(context, s)
    else:
        _delete_cylinder_control(s)
