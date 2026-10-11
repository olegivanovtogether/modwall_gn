"""Tile Grid operators."""

import bpy
import bmesh
from mathutils import Vector
from bpy.types import Operator
from bpy.props import (
    IntProperty,
)
from .bmesh_baker import get_tile_bounds, slice_mesh_with_grid
from .uv_geom import _apply_tile_uvs, _priority_layers, _process_seams
from .tile_grid import (
    _create_proj_box,
    _create_tile_preview,
    _delete_proj_box,
    _set_proj_box_to_tile_size,
)


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

        rotation = int(s.texture_rotation)
        if (box is None or box.type != 'EMPTY') and rotation in (90, 270):
            tile_u, tile_v = tile_v, tile_u

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

        layers = _priority_layers(s)

        uv_stats = _apply_tile_uvs(
            bm, b_min, b_max,
            tile_u, tile_v,
            box_origin, ax_x, ax_y, ax_z,
            layers=layers,
            rotation=rotation,
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


class TC_OT_SelectController(Operator):
    """Select the Tile Grid controller (the Projection Box empty).

    The controller is the wire cube (empty) that defines the grid; the
    semi-transparent preview cube is a child of it and is not selectable.
    Useful when the controller sits inside the target mesh and cannot be
    picked with the mouse.
    """
    bl_idname = "tilecutter.select_controller"
    bl_label = "Select Controller"
    bl_description = ("Select the Tile Grid controller (Projection Box) to move, "
                      "rotate or scale it, even when it is inside the mesh")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        s = context.scene.tc_settings
        return s.target_object is not None and s.reference_tile is not None

    def execute(self, context):
        s = context.scene.tc_settings
        target = s.target_object
        view_objects = context.view_layer.objects

        # Find the controller without changing anything yet.
        box = s.proj_box if (s.proj_box is not None and s.proj_box.type == 'EMPTY') else None
        created = False
        if box is None:
            orphan = bpy.data.objects.get(f"TC_Box_{target.name}")
            if orphan is not None and orphan.type == 'EMPTY':
                # an earlier controller that lost its link: reuse it as it is
                if orphan.name not in view_objects:
                    self.report({'WARNING'}, "Controller is not in the current view layer")
                    return {'CANCELLED'}
                s.proj_box = orphan
                box = orphan
                if s.tile_preview is None or s.tile_preview.parent != box:
                    _create_tile_preview(context, s)
            else:
                _create_proj_box(context, s)
                box = s.proj_box
                created = True
                # a freshly linked object appears in view_layer.objects
                # only after the view layer is updated
                context.view_layer.update()
        elif box.name not in view_objects:
            self.report({'WARNING'}, "Controller is not in the current view layer")
            return {'CANCELLED'}

        def fail(message):
            if created:
                _delete_proj_box(s)
                s.proj_box = None
            self.report({'WARNING'}, message)
            return {'CANCELLED'}

        if box is None or box.type != 'EMPTY' or box.name not in view_objects:
            return fail("Controller is not available")

        # Leave Edit / Sculpt / Paint mode first, otherwise selection changes
        # would apply to the wrong mode.
        if context.mode != 'OBJECT' and context.object is not None:
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                pass
            if context.mode != 'OBJECT':
                return fail("Could not leave the current mode")

        box.hide_select = False
        try:
            box.hide_set(False)
        except RuntimeError:
            pass
        box.hide_viewport = False

        for obj in view_objects:
            if obj.select_get():
                obj.select_set(False)
        box.select_set(True)
        context.view_layer.objects.active = box

        if not box.select_get() or not box.visible_get():
            return fail("Controller cannot be selected (hidden collection or object?)")

        self.report({'INFO'}, "Controller selected")
        return {'FINISHED'}


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


class TC_OT_RotateTexture(Operator):
    bl_idname = "tilecutter.rotate_texture"
    bl_label = "Rotate Texture"
    bl_description = "Step the texture direction by 90 degrees"
    bl_options = {'REGISTER', 'UNDO'}

    direction: IntProperty(default=1, min=-1, max=1)

    def execute(self, context):
        s = context.scene.tc_settings
        idx = (int(s.texture_rotation) // 90 + self.direction) % 4
        s.texture_rotation = str(idx * 90)
        return {'FINISHED'}
