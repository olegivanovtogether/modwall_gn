bl_info = {
    "name": "Simple Tile Cutter",
    "version": (0, 4, 4),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Tile Cutter",
    "description": "Cut any mesh with a tile grid and assign UV from a reference tile",
    "category": "Mesh",
}

import bpy
import bmesh
import math
import importlib
from mathutils import Vector
from bpy.props import FloatProperty, BoolProperty, PointerProperty
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


def _make_material_transparent(mat, alpha=0.35):
    mat.diffuse_color = (mat.diffuse_color[0], mat.diffuse_color[1],
                         mat.diffuse_color[2], alpha)
    mat.blend_method = 'BLEND'
    if hasattr(mat, "use_backface_culling"):
        mat.use_backface_culling = False
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
        mat.diffuse_color = (0.2, 0.65, 1.0, 0.35)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            bsdf.inputs["Base Color"].default_value = (0.2, 0.65, 1.0, 0.35)
            bsdf.inputs["Alpha"].default_value = 0.35
        _make_material_transparent(mat)
    return mat


def _delete_tile_preview(s):
    preview = s.tile_preview
    if preview is not None:
        try:
            mesh = preview.data
            bpy.data.objects.remove(preview, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        except Exception:
            pass
    s.tile_preview = None


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


# ── Registration ──────────────────────────────────────────────────────────────

classes = (
    TC_Settings,
    TC_OT_Apply,
    TC_OT_ResetProjBox,
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
