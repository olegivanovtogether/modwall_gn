"""Cylinder Projection operators."""

import bpy
import bmesh
import math
from bpy.types import Operator
from .bmesh_baker import get_tile_bounds
from .uv_geom import _process_seams
from .cylinder import _create_cylinder_control, _cyl_axis_idx, _cyl_decompose, _cyl_projection_frame, _cyl_tile_height, _cyl_tile_plane_sizes, _delete_cylinder_control, _slice_cylinder_around_sectors, _slice_cylinder_caps_grid, _slice_cylinder_height_bands


class TC_OT_SelectCylinderControl(Operator):
    bl_idname = "tilecutter.select_cylinder_control"
    bl_label = "Select Cylinder Control"
    bl_description = "Select the Cylinder Control empty for move / rotate / scale"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        s = context.scene.tc_settings
        return s.cylinder_target is not None and s.cylinder_reference_tile is not None

    def execute(self, context):
        s = context.scene.tc_settings
        control = s.cylinder_control or _create_cylinder_control(context, s)
        if control is None:
            self.report({'WARNING'}, "Cylinder Control is not available")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        control.select_set(True)
        context.view_layer.objects.active = control
        self.report({'INFO'}, "Cylinder Control selected")
        return {'FINISHED'}


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
        control_inv, height_axis, control_mat = _cyl_projection_frame(s, target)
        axis_idx      = _cyl_axis_idx(s)
        tiles_around  = max(s.cylinder_tiles_around, 1)
        tile_h        = _cyl_tile_height(s)
        cap_tile_u, cap_tile_v = _cyl_tile_plane_sizes(s)
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

        if s.cylinder_cut_height_bands:
            _slice_cylinder_height_bands(
                bm, control_inv, control_mat, axis_idx, tile_h,
            )
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
            bm.normal_update()

        if not s.cylinder_stretch_around:
            _slice_cylinder_around_sectors(
                bm, control_mat, axis_idx, tiles_around,
            )
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
            bm.normal_update()

        if s.cylinder_project_caps:
            _slice_cylinder_caps_grid(
                bm, control_inv, control_mat, axis_idx,
                cap_tile_u, cap_tile_v,
            )
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
            bm.normal_update()

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
                cu = math.floor(p1c / cap_tile_u + 0.5)
                cv = math.floor(p2c / cap_tile_v + 0.5)
                for loop in face.loops:
                    p1v, p2v, _ = cyl_coords(loop.vert.co)
                    uf = (p1v - (cu - 0.5) * cap_tile_u) / cap_tile_u
                    vf = (p2v - (cv - 0.5) * cap_tile_v) / cap_tile_v
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

                # Height bands are cut around the Cylinder Control origin, so a
                # full tile spans [-0.5h, +0.5h]. Match that center-origin model
                # when assigning V, otherwise the first band maps to half a tile.
                cell_v = math.floor(hc / tile_h + 0.5)

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
                    vf = (hv - (cell_v - 0.5) * tile_h) / tile_h
                    loop[uv_layer].uv = remap(uf, vf)

        if s.mark_seams:
            uv_layer = bm.loops.layers.uv.get("UVMap")
            if uv_layer:
                _process_seams(
                    bm,
                    uv_layer,
                    s.seam_angle,
                    dissolve_non_seamed_edges=s.dissolve_non_seamed_edges,
                )

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
