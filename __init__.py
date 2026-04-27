bl_info = {
    "name": "Simple Tile Cutter",
    "version": (0, 2, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Tile Cutter",
    "description": "Cut any mesh with a tile grid and assign UV from a reference tile",
    "category": "Mesh",
}

import bpy
import bmesh
import math
from bpy.props import FloatProperty, BoolProperty, EnumProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup

from .bmesh_baker import get_tile_bounds, slice_mesh_with_grid


# ── UV projection ─────────────────────────────────────────────────────────────

def _apply_tile_uvs(bm, b_min, b_max, tile_size_x, tile_size_y, rotation_deg):
    uv_layer = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    ts_x = max(tile_size_x, 0.001)
    ts_y = max(tile_size_y, 0.001)
    rot = int(rotation_deg)

    stats = {'quads': 0, 'triangles': 0, 'ngons': 0}

    for face in bm.faces:
        n = len(face.verts)
        if n == 3:   stats['triangles'] += 1
        elif n == 4: stats['quads'] += 1
        else:        stats['ngons'] += 1

        nx = abs(face.normal.x)
        ny = abs(face.normal.y)
        nz = abs(face.normal.z)

        # Face center determines which tile cell this face belongs to.
        # All vertices then offset relative to that cell → guaranteed [0,1].
        # This fixes wrap-around distortion when per-vertex modulo crosses
        # a tile boundary on the same face (0.99 → 0.01 interpolation artifact).
        c = face.calc_center_median()

        if ny >= nx and ny >= nz:
            su = 1.0 if face.normal.y < 0 else -1.0
            cu = math.floor(su * c.x / ts_x)
            cv = math.floor(c.z / ts_y)
            for loop in face.loops:
                co = loop.vert.co
                uf = (su * co.x - cu * ts_x) / ts_x
                vf = (co.z   - cv * ts_y) / ts_y
                uf = max(0.0, min(1.0, uf))
                vf = max(0.0, min(1.0, vf))
                if rot == 90:    uf, vf = 1.0 - vf, uf
                elif rot == 180: uf, vf = 1.0 - uf, 1.0 - vf
                elif rot == 270: uf, vf = vf, 1.0 - uf
                loop[uv_layer].uv = (b_min[0] + uf * (b_max[0] - b_min[0]),
                                     b_min[1] + vf * (b_max[1] - b_min[1]))

        elif nz >= nx:
            cu = math.floor(c.x / ts_x)
            cv = math.floor(c.y / ts_y)
            for loop in face.loops:
                co = loop.vert.co
                uf = (co.x - cu * ts_x) / ts_x
                vf = (co.y - cv * ts_y) / ts_y
                uf = max(0.0, min(1.0, uf))
                vf = max(0.0, min(1.0, vf))
                if rot == 90:    uf, vf = 1.0 - vf, uf
                elif rot == 180: uf, vf = 1.0 - uf, 1.0 - vf
                elif rot == 270: uf, vf = vf, 1.0 - uf
                loop[uv_layer].uv = (b_min[0] + uf * (b_max[0] - b_min[0]),
                                     b_min[1] + vf * (b_max[1] - b_min[1]))

        else:
            su = 1.0 if face.normal.x > 0 else -1.0
            cu = math.floor(su * c.y / ts_x)
            cv = math.floor(c.z / ts_y)
            for loop in face.loops:
                co = loop.vert.co
                uf = (su * co.y - cu * ts_x) / ts_x
                vf = (co.z     - cv * ts_y) / ts_y
                uf = max(0.0, min(1.0, uf))
                vf = max(0.0, min(1.0, vf))
                if rot == 90:    uf, vf = 1.0 - vf, uf
                elif rot == 180: uf, vf = 1.0 - uf, 1.0 - vf
                elif rot == 270: uf, vf = vf, 1.0 - uf
                loop[uv_layer].uv = (b_min[0] + uf * (b_max[0] - b_min[0]),
                                     b_min[1] + vf * (b_max[1] - b_min[1]))

    return stats


# ── Properties ────────────────────────────────────────────────────────────────

def _poll_mesh(self, obj):
    return obj.type == 'MESH'

class TC_Settings(PropertyGroup):
    target_object: PointerProperty(
        name="Target Wall",
        type=bpy.types.Object,
        poll=_poll_mesh,
    )
    reference_tile: PointerProperty(
        name="Reference Tile",
        type=bpy.types.Object,
        poll=_poll_mesh,
    )
    tile_size_x: FloatProperty(
        name="Tile Size X",
        default=0.5, min=0.001, max=100.0,
        unit='LENGTH',
    )
    tile_size_y: FloatProperty(
        name="Tile Size Y",
        default=0.25, min=0.001, max=100.0,
        unit='LENGTH',
    )
    rotation: EnumProperty(
        name="Rotation",
        items=[
            ('0',   "0°",   ""),
            ('90',  "90°",  ""),
            ('180', "180°", ""),
            ('270', "270°", ""),
        ],
        default='0',
    )
    duplicate_before_apply: BoolProperty(
        name="Duplicate Before Apply",
        description="Work on a copy; original mesh is left untouched",
        default=True,
    )


# ── Operator ──────────────────────────────────────────────────────────────────

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
        target = s.target_object
        ref_tile = s.reference_tile

        b_min, b_max = get_tile_bounds(ref_tile)

        # Tile size from reference object world dimensions; manual fields are fallback
        ts_x = ref_tile.dimensions.x
        ts_y = ref_tile.dimensions.z if ref_tile.dimensions.z > 0.001 else ref_tile.dimensions.y
        if ts_x < 0.001: ts_x = s.tile_size_x
        if ts_y < 0.001: ts_y = s.tile_size_y

        if s.duplicate_before_apply:
            new_data = target.data.copy()
            work_obj = target.copy()
            work_obj.data = new_data
            work_obj.name = target.name + "_tiled"
            context.collection.objects.link(work_obj)
            target.hide_set(True)
        else:
            work_obj = target

        bm = bmesh.new()
        bm.from_mesh(work_obj.data)

        faces_before = len(bm.faces)
        slice_mesh_with_grid(bm, (ts_x, ts_y))
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
        faces_after = len(bm.faces)

        uv_stats = _apply_tile_uvs(
            bm, b_min, b_max,
            ts_x, ts_y,
            s.rotation,
        )

        bm.to_mesh(work_obj.data)
        bm.free()
        work_obj.data.update()

        # Transfer material from reference tile
        if ref_tile.data.materials:
            work_obj.data.materials.clear()
            for mat in ref_tile.data.materials:
                work_obj.data.materials.append(mat)

        bpy.ops.object.select_all(action='DESELECT')
        work_obj.select_set(True)
        context.view_layer.objects.active = work_obj

        self.report(
            {'INFO'},
            f"Done: {faces_before}→{faces_after} faces | "
            f"tile:{ts_x:.3f}x{ts_y:.3f} | "
            f"quads:{uv_stats['quads']} "
            f"tri:{uv_stats['triangles']} "
            f"ngon:{uv_stats['ngons']}"
        )
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

        layout.prop(s, "target_object", icon='MESH_DATA')
        layout.prop(s, "reference_tile", icon='UV')

        layout.separator()
        col = layout.column(align=True)
        col.prop(s, "tile_size_x")
        col.prop(s, "tile_size_y")

        layout.prop(s, "rotation")
        layout.prop(s, "duplicate_before_apply")

        layout.separator()
        row = layout.row()
        row.scale_y = 1.4
        row.operator("tilecutter.apply", icon='MESH_GRID')


# ── Registration ──────────────────────────────────────────────────────────────

classes = (
    TC_Settings,
    TC_OT_Apply,
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
