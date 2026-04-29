bl_info = {
    "name": "Simple Tile Cutter",
    "author": "Oleh Strykitchenko",
    "version": (0, 5, 2),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Tile Cutter",
    "description": "Alpha tool for a focused mobile-game asset workflow: cut meshes into tile-sized sections and project UVs from a reference tile",
    "category": "Mesh",
}

import bpy
import bmesh
import math
import importlib
from mathutils import Matrix, Vector
from bpy.props import FloatProperty, BoolProperty, PointerProperty, IntProperty, EnumProperty
from bpy.types import Panel, Operator, PropertyGroup

from . import bmesh_baker
importlib.reload(bmesh_baker)
from .bmesh_baker import get_tile_bounds, slice_mesh_with_grid


# ── UV projection ─────────────────────────────────────────────────────────────
#
# Box-projection model (same as UVW Map in 3ds Max):
#   ax_x, ax_y, ax_z  — unit vectors of the box's local axes in target-local space
#   box_origin        — box center in target-local space
#   tile_u, tile_v    — tile sizes (= box.scale.x / .z)
#
# For each face we dot its normal against all three box axes to decide which
# box-face it is most parallel to, then project vertices onto the two remaining
# axes.  Rotation of the box rotates the axes → projection rotates with it.

def _apply_tile_uvs(bm, b_min, b_max, tile_u, tile_v,
                    box_origin, ax_x, ax_y, ax_z):
    uv_layer = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    tile_u = max(tile_u, 0.001)
    tile_v = max(tile_v, 0.001)

    stats = {'quads': 0, 'triangles': 0, 'ngons': 0}

    for face in bm.faces:
        n = len(face.verts)
        if n == 3:   stats['triangles'] += 1
        elif n == 4: stats['quads'] += 1
        else:        stats['ngons'] += 1

        fn = face.normal
        dot_x = abs(fn.dot(ax_x))
        dot_y = abs(fn.dot(ax_y))
        dot_z = abs(fn.dot(ax_z))

        # Which box face is this mesh face most parallel to?
        if dot_y >= dot_x and dot_y >= dot_z:
            # ≈ parallel to box XZ plane → project U along ax_x, V along ax_z
            ua = -ax_x if fn.dot(ax_y) > 0 else ax_x
            va = ax_z
        elif dot_z >= dot_x:
            # ≈ parallel to box XY plane → U along ax_x, V along ax_y
            ua = ax_x
            va = ax_y
        else:
            # ≈ parallel to box YZ plane → U along ax_y, V along ax_z
            ua = -ax_y if fn.dot(ax_x) < 0 else ax_y
            va = ax_z

        # Face center → tile cell (keeps all verts of one face in same cell).
        # Projection Box origin is the center of the preview tile, so cell
        # boundaries live at half-tile offsets from the origin.
        c = face.calc_center_median() - box_origin
        cu = math.floor(c.dot(ua) / tile_u + 0.5)
        cv = math.floor(c.dot(va) / tile_v + 0.5)

        for loop in face.loops:
            p  = loop.vert.co - box_origin
            pu = p.dot(ua)
            pv = p.dot(va)
            uf = max(0.0, min(1.0, (pu - (cu - 0.5) * tile_u) / tile_u))
            vf = max(0.0, min(1.0, (pv - (cv - 0.5) * tile_v) / tile_v))
            loop[uv_layer].uv = (b_min[0] + uf * (b_max[0] - b_min[0]),
                                 b_min[1] + vf * (b_max[1] - b_min[1]))

    return stats


# ── Seam processing ───────────────────────────────────────────────────────────

def _process_seams(bm, uv_layer, angle_deg, dissolve_non_seamed_edges=False):
    corner_rad = math.radians(angle_deg)
    tol = 0.001
    to_dissolve = []

    for edge in bm.edges:
        if len(edge.link_faces) != 2:
            edge.seam = True
            continue
        if edge.calc_face_angle(0.0) > corner_rad:
            edge.seam = True
            continue

        f0, f1 = edge.link_faces
        f0_uv = {l.vert: l[uv_layer].uv for l in f0.loops}
        f1_uv = {l.vert: l[uv_layer].uv for l in f1.loops}

        uv_differs = False
        for v in edge.verts:
            if v in f0_uv and v in f1_uv:
                du = abs(f0_uv[v][0] - f1_uv[v][0])
                dv = abs(f0_uv[v][1] - f1_uv[v][1])
                if du > tol or dv > tol:
                    uv_differs = True
                    break

        if uv_differs:
            edge.seam = True
        else:
            edge.seam = False
            if dissolve_non_seamed_edges:
                to_dissolve.append(edge)

    if dissolve_non_seamed_edges and to_dissolve:
        bmesh.ops.dissolve_edges(bm, edges=to_dissolve,
                                 use_verts=True, use_face_split=False)


# ── Projection Box helpers ────────────────────────────────────────────────────

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
    box.scale = (ts_x, ts_x, ts_y)


def _make_material_transparent(mat, alpha=0.55):
    mat.diffuse_color = (mat.diffuse_color[0], mat.diffuse_color[1],
                         mat.diffuse_color[2], alpha)
    mat.blend_method = 'BLEND'
    if hasattr(mat, "use_backface_culling"):
        mat.use_backface_culling = True
    if hasattr(mat, "show_transparent_back"):
        mat.show_transparent_back = True
    if hasattr(mat, "use_screen_refraction"):
        mat.use_screen_refraction = True

    if mat.use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            if "Alpha" in bsdf.inputs:
                bsdf.inputs["Alpha"].default_value = alpha
            if "Base Color" in bsdf.inputs and not bsdf.inputs["Base Color"].is_linked:
                color = bsdf.inputs["Base Color"].default_value
                bsdf.inputs["Base Color"].default_value = (
                    color[0], color[1], color[2], alpha,
                )


def _preview_material(ref_tile):
    src_mat = None
    if ref_tile is not None and ref_tile.data.materials:
        src_mat = ref_tile.data.materials[0]

    if src_mat is not None:
        mat_name = f"TC_Preview_{src_mat.name}"
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = src_mat.copy()
            mat.name = mat_name
        _make_material_transparent(mat)
        return mat

    mat = bpy.data.materials.get("TC_Tile_Preview_Material")
    if mat is None:
        mat = bpy.data.materials.new("TC_Tile_Preview_Material")
        mat.diffuse_color = (0.2, 0.65, 1.0, 0.55)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            bsdf.inputs["Base Color"].default_value = (0.2, 0.65, 1.0, 0.55)
            bsdf.inputs["Alpha"].default_value = 0.55
    _make_material_transparent(mat)
    return mat


def _wire_material():
    mat = bpy.data.materials.get("TC_Tile_Preview_Wire_Material")
    if mat is None:
        mat = bpy.data.materials.new("TC_Tile_Preview_Wire_Material")
        mat.diffuse_color = (0.0, 1.0, 0.1, 1.0)
    return mat


# ── Cylinder Projection helpers ───────────────────────────────────────────────

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
        control.empty_display_type = 'CIRCLE'
        context.collection.objects.link(control)

    control.empty_display_size = 1.0
    control.parent = target
    control.matrix_parent_inverse.identity()
    if s.cylinder_control is None or s.cylinder_control != control:
        control.location = (0.0, 0.0, 0.0)
        control.rotation_euler = (0.0, 0.0, 0.0)
        control.scale = (1.0, 1.0, 1.0)
    control.hide_render = True
    s.cylinder_control = control
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
        control_inv = Matrix.Identity(4)
        axes = (
            Vector((1.0, 0.0, 0.0)),
            Vector((0.0, 1.0, 0.0)),
            Vector((0.0, 0.0, 1.0)),
        )

    axis_idx = _cyl_axis_idx(s)
    height_axis = axes[axis_idx]
    return control_inv, height_axis


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


# ── Box Tile Preview (existing) ───────────────────────────────────────────────

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

    def preview_uv(mode, co):
        x = co.x + 0.5
        y = co.y + 0.5
        z = co.z + 0.5

        if mode == "back":
            return remap_uv(1.0 - x, z)
        if mode == "right":
            return remap_uv(y, z)
        if mode == "left":
            return remap_uv(1.0 - y, z)
        if mode in {"top", "bottom"}:
            return remap_uv(x, y)
        return remap_uv(x, z)

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


# ── Properties ────────────────────────────────────────────────────────────────

def _poll_mesh(self, obj):
    return obj.type == 'MESH'


def _sync_seam_options(self, context):
    if not self.mark_seams:
        self.dissolve_non_seamed_edges = False


class TC_Settings(PropertyGroup):
    target_object: PointerProperty(
        name="Target Wall",
        type=bpy.types.Object,
        poll=_poll_mesh,
        update=_sync_proj_box,
    )
    reference_tile: PointerProperty(
        name="Reference Tile",
        type=bpy.types.Object,
        poll=_poll_mesh,
        update=_sync_proj_box,
    )
    tile_size_x: FloatProperty(
        name="Tile Size X",
        default=0.5, min=0.001, max=100.0,
        unit='LENGTH',
        update=_sync_proj_box,
    )
    tile_size_y: FloatProperty(
        name="Tile Size Y",
        default=0.25, min=0.001, max=100.0,
        unit='LENGTH',
        update=_sync_proj_box,
    )
    proj_box: PointerProperty(
        name="Projection Box",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'EMPTY',
    )
    tile_preview: PointerProperty(
        name="Tile Preview",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    tile_preview_wire: PointerProperty(
        name="Tile Preview Wire",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    duplicate_before_apply: BoolProperty(
        name="Duplicate Before Apply",
        description="Work on a copy; original mesh is left untouched",
        default=True,
    )
    mark_seams: BoolProperty(
        name="Mark Seams",
        description="Mark seams on tile borders / sharp corners / boundary edges",
        default=False,
        update=_sync_seam_options,
    )
    dissolve_non_seamed_edges: BoolProperty(
        name="Dissolve non-seamed edges",
        description="After marking seams, remove edges that were not marked as seams",
        default=False,
    )
    seam_angle: FloatProperty(
        name="Corner Angle",
        description="Edges sharper than this angle get a seam",
        default=45.0, min=0.0, max=180.0,
        subtype='NONE', unit='NONE',
    )

    # ── Cylinder Projection ───────────────────────────────────────────────────
    cylinder_target: PointerProperty(
        name="Target Mesh",
        type=bpy.types.Object,
        poll=_poll_mesh,
        update=_sync_cylinder_preview,
    )
    cylinder_reference_tile: PointerProperty(
        name="Reference Tile",
        type=bpy.types.Object,
        poll=_poll_mesh,
        update=_sync_cylinder_preview,
    )
    cylinder_axis: EnumProperty(
        name="Cylinder Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='Z',
        update=_sync_cylinder_preview,
    )
    cylinder_tiles_around: IntProperty(
        name="Tiles Around",
        description="How many tiles repeat around the full circumference",
        default=1, min=1, max=64,
        update=_sync_cylinder_preview,
    )
    cylinder_tile_height_source: EnumProperty(
        name="Tile Height Source",
        description="Choose how cylinder tile height is measured",
        items=[
            ('AUTO', "Auto from Tile", "Use the smallest non-zero dimension of the flat reference tile"),
            ('MANUAL', "Manual", "Use the manual Tile Height field"),
            ('X', "Reference X", "Use reference tile X dimension"),
            ('Y', "Reference Y", "Use reference tile Y dimension"),
            ('Z', "Reference Z", "Use reference tile Z dimension"),
        ],
        default='AUTO',
        update=_sync_cylinder_preview,
    )
    cylinder_tile_height: FloatProperty(
        name="Tile Height",
        description="Manual tile height along the cylinder axis",
        default=1.0, min=0.001, max=100.0,
        unit='LENGTH',
        update=_sync_cylinder_preview,
    )
    cylinder_project_caps: BoolProperty(
        name="Project Caps",
        description="Apply planar UV to cap faces (faces whose normal is mostly along the axis)",
        default=True,
        update=_sync_cylinder_preview,
    )
    cylinder_duplicate_before_apply: BoolProperty(
        name="Duplicate Before Apply",
        description="Work on a copy; original mesh is left untouched",
        default=True,
    )
    cylinder_preview: PointerProperty(
        name="Cylinder Preview",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    cylinder_preview_wire: PointerProperty(
        name="Cylinder Preview Wire",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    cylinder_control: PointerProperty(
        name="Cylinder Control",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'EMPTY',
    )


# ── Operator: Apply ───────────────────────────────────────────────────────────

class TC_OT_Apply(Operator):
    bl_idname = "tilecutter.apply"
    bl_label = "Apply Tile Grid"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        s = context.scene.tc_settings
        return s.target_object is not None and s.reference_tile is not None

    def execute(self, context):
        s = context.scene.tc_settings
        target   = s.target_object
        ref_tile = s.reference_tile

        b_min, b_max = get_tile_bounds(ref_tile)

        ts_x = ref_tile.dimensions.x
        ts_y = ref_tile.dimensions.z if ref_tile.dimensions.z > 0.001 else ref_tile.dimensions.y
        if ts_x < 0.001: ts_x = s.tile_size_x
        if ts_y < 0.001: ts_y = s.tile_size_y

        # ── Read Projection Box: axes, origin, tile sizes ─────────────────────
        # Default: world-aligned axes, no offset
        ax_x = Vector((1.0, 0.0, 0.0))
        ax_y = Vector((0.0, 1.0, 0.0))
        ax_z = Vector((0.0, 0.0, 1.0))
        box_origin = Vector((0.0, 0.0, 0.0))
        tile_u = ts_x
        tile_v = ts_y

        box = s.proj_box
        if box is not None and box.type == 'EMPTY':
            local_mat  = target.matrix_world.inverted() @ box.matrix_world
            scl        = local_mat.to_scale()
            rot_mat    = local_mat.to_3x3()

            ax_x = rot_mat.col[0].normalized()
            ax_y = rot_mat.col[1].normalized()
            ax_z = rot_mat.col[2].normalized()
            box_origin = local_mat.to_translation()
            tile_u     = max(abs(scl.x), 0.001)
            tile_v     = max(abs(scl.z), 0.001)

        # ── Duplicate or work in-place ────────────────────────────────────────
        if s.duplicate_before_apply:
            new_data = target.data.copy()
            work_obj = target.copy()
            work_obj.data = new_data
            work_obj.name = target.name + "_tiled"
            context.collection.objects.link(work_obj)
            target.hide_set(True)
        else:
            work_obj = target

        # ── BMesh processing ──────────────────────────────────────────────────
        bm = bmesh.new()
        bm.from_mesh(work_obj.data)

        faces_before = len(bm.faces)
        slice_mesh_with_grid(
            bm,
            (tile_u, tile_v),
            origin=box_origin,
            axes=(ax_x, ax_y, ax_z),
            center_origin=True,
        )
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)

        uv_stats = _apply_tile_uvs(
            bm, b_min, b_max,
            tile_u, tile_v,
            box_origin, ax_x, ax_y, ax_z,
        )

        if s.mark_seams:
            uv_layer = bm.loops.layers.uv.get("UVMap")
            if uv_layer:
                _process_seams(
                    bm,
                    uv_layer,
                    s.seam_angle,
                    dissolve_non_seamed_edges=s.dissolve_non_seamed_edges,
                )

        faces_after = len(bm.faces)

        bm.to_mesh(work_obj.data)
        bm.free()
        work_obj.data.update()

        if ref_tile.data.materials:
            work_obj.data.materials.clear()
            for mat in ref_tile.data.materials:
                work_obj.data.materials.append(mat)

        bpy.ops.object.select_all(action='DESELECT')
        work_obj.select_set(True)
        context.view_layer.objects.active = work_obj

        # ── Cleanup ───────────────────────────────────────────────────────────
        _delete_proj_box(s)
        s.proj_box       = None
        s.target_object  = None
        s.reference_tile = None

        self.report(
            {'INFO'},
            f"Done: {faces_before}→{faces_after} faces | "
            f"tile:{tile_u:.3f}x{tile_v:.3f} | "
            f"quads:{uv_stats['quads']} "
            f"tri:{uv_stats['triangles']} "
            f"ngon:{uv_stats['ngons']}"
        )
        return {'FINISHED'}


# ── Operator: Reset Projection Box ────────────────────────────────────────────

class TC_OT_ResetProjBox(Operator):
    bl_idname = "tilecutter.reset_proj_box"
    bl_label = "Reset Proj Box"
    bl_description = "Reset the Projection Box to the target wall's local origin with tile dimensions"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        s = context.scene.tc_settings
        return s.proj_box is not None and s.proj_box.type == 'EMPTY'

    def execute(self, context):
        s = context.scene.tc_settings
        box = s.proj_box

        box.location       = (0.0, 0.0, 0.0)
        box.rotation_euler = (0.0, 0.0, 0.0)
        _set_proj_box_to_tile_size(box, s)
        if s.tile_preview is None or s.tile_preview.parent != box:
            _create_tile_preview(context, s)

        self.report({'INFO'}, "Projection Box reset")
        return {'FINISHED'}


# ── Operator: Apply Cylinder Projection ──────────────────────────────────────

class TC_OT_ApplyCylinder(Operator):
    bl_idname = "tilecutter.apply_cylinder"
    bl_label = "Apply Cylinder Projection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        s = context.scene.tc_settings
        return s.cylinder_target is not None and s.cylinder_reference_tile is not None

    def execute(self, context):
        s        = context.scene.tc_settings
        target   = s.cylinder_target
        ref_tile = s.cylinder_reference_tile

        b_min, b_max  = get_tile_bounds(ref_tile)
        if s.cylinder_control is None:
            _create_cylinder_control(context, s)
        control_inv, height_axis = _cyl_projection_frame(s, target)
        axis_idx      = _cyl_axis_idx(s)
        tiles_around  = max(s.cylinder_tiles_around, 1)
        tile_h        = _cyl_tile_height(s)
        tile_angle    = 2.0 * math.pi / tiles_around

        # ── Duplicate or work in-place ────────────────────────────────────────
        if s.cylinder_duplicate_before_apply:
            new_data = target.data.copy()
            work_obj = target.copy()
            work_obj.data = new_data
            work_obj.name = target.name + "_cyl"
            context.collection.objects.link(work_obj)
            target.hide_set(True)
        else:
            work_obj = target

        # ── BMesh UV projection ───────────────────────────────────────────────
        bm = bmesh.new()
        bm.from_mesh(work_obj.data)

        uv_layer = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")

        def remap(u, v):
            u = max(0.0, min(1.0, u))
            v = max(0.0, min(1.0, v))
            return (b_min[0] + u * (b_max[0] - b_min[0]),
                    b_min[1] + v * (b_max[1] - b_min[1]))

        def cyl_coords(co):
            return _cyl_decompose(control_inv @ co, axis_idx)

        for face in bm.faces:
            fn = face.normal
            dot_axis = abs(fn.dot(height_axis))
            is_cap   = dot_axis > 0.7  # normal mostly along axis → cap face

            fc = face.calc_center_median()
            p1c, p2c, hc = cyl_coords(fc)

            if is_cap and s.cylinder_project_caps:
                # ── Planar cap projection ─────────────────────────────────────
                # Estimate the local radius from this face's vertices
                rmax = max(
                    math.sqrt(
                        cyl_coords(loop.vert.co)[0] ** 2 +
                        cyl_coords(loop.vert.co)[1] ** 2
                    )
                    for loop in face.loops
                ) or 1.0
                for loop in face.loops:
                    p1v, p2v, _ = cyl_coords(loop.vert.co)
                    uf = p1v / (2.0 * rmax) + 0.5
                    vf = p2v / (2.0 * rmax) + 0.5
                    loop[uv_layer].uv = remap(uf, vf)

            elif is_cap:
                # Project Caps disabled: leave cap UVs unchanged.
                continue

            else:
                # ── Cylindrical side projection ───────────────────────────────
                angle_c = math.atan2(p2c, p1c)
                if angle_c < 0.0:
                    angle_c += 2.0 * math.pi
                cell_u = math.floor(angle_c / tile_angle)
                cell_start = cell_u * tile_angle

                cell_v = math.floor(hc / tile_h)

                for loop in face.loops:
                    p1v, p2v, hv = cyl_coords(loop.vert.co)

                    # Unwrap around the face center so the 0/360 seam can live on
                    # a mesh edge without collapsing one polygon's UVs.
                    angle_v = math.atan2(p2v, p1v)
                    if angle_v < 0.0:
                        angle_v += 2.0 * math.pi
                    delta = angle_v - angle_c
                    if delta >  math.pi: delta -= 2.0 * math.pi
                    if delta < -math.pi: delta += 2.0 * math.pi

                    angle_unwrapped = angle_c + delta
                    uf = (angle_unwrapped - cell_start) / tile_angle
                    vf = (hv - cell_v * tile_h) / tile_h
                    loop[uv_layer].uv = remap(uf, vf)

        bm.to_mesh(work_obj.data)
        bm.free()
        work_obj.data.update()

        if ref_tile.data.materials:
            work_obj.data.materials.clear()
            for mat in ref_tile.data.materials:
                work_obj.data.materials.append(mat)

        bpy.ops.object.select_all(action='DESELECT')
        work_obj.select_set(True)
        context.view_layer.objects.active = work_obj

        # ── Cleanup ───────────────────────────────────────────────────────────
        _delete_cylinder_control(s)
        s.cylinder_target           = None
        s.cylinder_reference_tile   = None

        self.report({'INFO'}, f"Cylinder UV applied → {work_obj.name}")
        return {'FINISHED'}


# ── Panel ─────────────────────────────────────────────────────────────────────

class TC_PT_Main(Panel):
    bl_label = "Tile Cutter"
    bl_idname = "TC_PT_MAIN"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tile Cutter'

    def draw(self, context):
        layout = self.layout
        s = context.scene.tc_settings

        info = layout.column(align=True)
        info.label(text="Alpha mobile-game tiling tool.", icon='INFO')
        info.label(text="Use a flat, lying reference tile plane.")
        info.label(text="Rectangular tiles work; square tiles are safer.")

        layout.separator()
        layout.prop(s, "target_object",  icon='MESH_DATA')
        layout.prop(s, "reference_tile", icon='UV')

        layout.separator()
        col = layout.column(align=True)
        col.prop(s, "tile_size_x")
        col.prop(s, "tile_size_y")

        layout.prop(s, "duplicate_before_apply")

        if s.proj_box is not None:
            layout.separator()
            layout.label(text="Proj Box: move / scale / rotate it")
            layout.operator("tilecutter.reset_proj_box",
                            text="Reset Proj Box", icon='LOOP_BACK')

        layout.separator()
        layout.prop(s, "mark_seams")
        seam_col = layout.column(align=True)
        seam_col.enabled = s.mark_seams
        seam_col.prop(s, "dissolve_non_seamed_edges")
        seam_col.prop(s, "seam_angle", text="Corner Angle (°)")

        layout.separator()
        row = layout.row()
        row.scale_y = 1.4
        row.operator("tilecutter.apply", icon='MESH_GRID')

        # ── Cylinder Projection ───────────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="Cylinder Projection", icon='MESH_CYLINDER')

        box.prop(s, "cylinder_target",          icon='MESH_DATA')
        box.prop(s, "cylinder_reference_tile",  icon='UV')

        col = box.column(align=True)
        col.prop(s, "cylinder_axis")
        col.prop(s, "cylinder_tiles_around")
        col.prop(s, "cylinder_tile_height_source")
        height_row = col.row(align=True)
        height_row.enabled = s.cylinder_tile_height_source == 'MANUAL'
        height_row.prop(s, "cylinder_tile_height")
        if s.cylinder_control is not None:
            box.label(text="Cylinder Control: move / rotate / scale it")
        box.prop(s, "cylinder_project_caps")
        box.prop(s, "cylinder_duplicate_before_apply")

        row = box.row()
        row.scale_y = 1.4
        row.operator("tilecutter.apply_cylinder", icon='MESH_CYLINDER')


# ── Registration ──────────────────────────────────────────────────────────────

classes = (
    TC_Settings,
    TC_OT_Apply,
    TC_OT_ResetProjBox,
    TC_OT_ApplyCylinder,
    TC_PT_Main,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.tc_settings = PointerProperty(type=TC_Settings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.tc_settings


if __name__ == "__main__":
    register()
