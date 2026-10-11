"""UVW Map Projection operators."""

import bpy
import bmesh
from bpy.types import Operator
from .bmesh_baker import get_tile_bounds
from .uv_geom import _priority_layers
from .uvw import _apply_uvw_box_uv, _apply_uvw_cylinder_uv, _apply_uvw_planar_uv, _create_uvw_gizmo, _delete_uvw_gizmo


class TC_OT_SelectUVWGizmo(Operator):
    bl_idname = "tilecutter.select_uvw_gizmo"
    bl_label = "Select Controller"
    bl_description = "Select the controller (UVW Gizmo) to move / rotate / scale it, creating it first if it does not exist"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        s = context.scene.tc_settings
        return s.uvw_target is not None and s.uvw_reference_tile is not None

    def execute(self, context):
        s = context.scene.tc_settings
        gizmo = s.uvw_gizmo or _create_uvw_gizmo(context, s)
        if gizmo is None:
            self.report({'WARNING'}, "UVW Gizmo is not available")
            return {'CANCELLED'}
        bpy.ops.object.select_all(action='DESELECT')
        gizmo.select_set(True)
        context.view_layer.objects.active = gizmo
        self.report({'INFO'}, "UVW Gizmo selected")
        return {'FINISHED'}


class TC_OT_ApplyUVWMap(Operator):
    bl_idname = "tilecutter.apply_uvw_map"
    bl_label = "Apply UVW Map"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        s = context.scene.tc_settings
        return s.uvw_target is not None and s.uvw_reference_tile is not None

    def execute(self, context):
        s        = context.scene.tc_settings
        target   = s.uvw_target
        ref_tile = s.uvw_reference_tile

        gizmo = s.uvw_gizmo
        if gizmo is None:
            self.report({'WARNING'}, "UVW Gizmo not found: press 'Select Controller' first")
            return {'CANCELLED'}

        b_min, b_max = get_tile_bounds(ref_tile)

        gizmo_local_mat = target.matrix_world.inverted() @ gizmo.matrix_world
        gizmo_scale     = gizmo_local_mat.to_scale()

        # ── Duplicate or work in-place ────────────────────────────────────────
        if s.uvw_duplicate_before_apply:
            new_data = target.data.copy()
            work_obj = target.copy()
            work_obj.data = new_data
            work_obj.name = target.name + "_uvw"
            context.collection.objects.link(work_obj)
            target.hide_set(True)
        else:
            work_obj = target

        bm = bmesh.new()
        bm.from_mesh(work_obj.data)

        mapping = s.uvw_mapping_type
        if mapping == 'BOX':
            tile_u = max(abs(gizmo_scale.x), 0.001)
            tile_v = max(abs(gizmo_scale.z), 0.001)
            _apply_uvw_box_uv(
                bm, b_min, b_max, tile_u, tile_v, gizmo_local_mat,
                s.uvw_flip_u, s.uvw_flip_v,
                layers=_priority_layers(s, "uvw_"),
                rotation=int(s.uvw_texture_rotation),
            )
        elif mapping == 'PLANAR':
            tile_u = max(abs(gizmo_scale.x), 0.001)
            tile_v = max(abs(gizmo_scale.y), 0.001)
            _apply_uvw_planar_uv(
                bm, b_min, b_max, tile_u, tile_v, gizmo_local_mat,
                s.uvw_flip_u, s.uvw_flip_v,
            )
        else:  # CYLINDER
            tile_v = max(abs(gizmo_scale.z), 0.001)
            _apply_uvw_cylinder_uv(
                bm, gizmo_local_mat, s.uvw_cylinder_tiles_around, tile_v,
                s.uvw_flip_u, s.uvw_flip_v, b_min, b_max,
            )

        bm.to_mesh(work_obj.data)
        bm.free()
        work_obj.data.update()

        if s.uvw_copy_material and ref_tile.data.materials:
            work_obj.data.materials.clear()
            for mat in ref_tile.data.materials:
                work_obj.data.materials.append(mat)

        bpy.ops.object.select_all(action='DESELECT')
        work_obj.select_set(True)
        context.view_layer.objects.active = work_obj

        # ── Cleanup ───────────────────────────────────────────────────────────
        _delete_uvw_gizmo(s)
        s.uvw_target         = None
        s.uvw_reference_tile = None

        self.report({'INFO'}, f"UVW Map ({mapping}) applied → {work_obj.name}")
        return {'FINISHED'}
