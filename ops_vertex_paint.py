"""Vertex Paint operators."""

import bpy
from bpy.types import Operator
from bpy.props import (
    BoolProperty,
    EnumProperty,
)
from .vertex_paint import _active_mesh_object, _apply_vertex_paint_brush, _current_vertex_paint_color, _ensure_vertex_color_attribute, _is_vertex_paint_ready, _prepare_vertex_paint


class TC_OT_SetVertexPaintColor(Operator):
    bl_idname = "tilecutter.set_vertex_paint_color"
    bl_label = "Set Vertex Paint Color"
    bl_description = "Set the active vertex paint brush to this color"
    bl_options = {'REGISTER', 'UNDO'}

    color_name: EnumProperty(
        items=[
            ('RED', "Red", "Use pure red"),
            ('GREEN', "Green", "Use pure green"),
            ('BLUE', "Blue", "Use pure blue"),
            ('WHITE', "White", "Use pure white"),
            ('BLACK', "Black", "Use pure black"),
            ('CUSTOM', "Custom", "Use the custom color"),
        ],
        default='RED',
    )

    @classmethod
    def poll(cls, context):
        return _is_vertex_paint_ready(context)

    def execute(self, context):
        s = context.scene.tc_settings
        colors = {
            'RED': (1.0, 0.0, 0.0, s.vp_alpha),
            'GREEN': (0.0, 1.0, 0.0, s.vp_alpha),
            'BLUE': (0.0, 0.0, 1.0, s.vp_alpha),
            'WHITE': (1.0, 1.0, 1.0, s.vp_alpha),
            'BLACK': (0.0, 0.0, 0.0, s.vp_alpha),
            'CUSTOM': tuple(s.vp_custom_color),
        }
        obj, brush = _prepare_vertex_paint(context, colors[self.color_name])
        if obj is None or brush is None:
            self.report({'WARNING'}, "Switch to Vertex Paint mode first")
            return {'CANCELLED'}
        self.report({'INFO'}, "Vertex paint color ready")
        return {'FINISHED'}


class TC_OT_SyncVertexPaintBrush(Operator):
    bl_idname = "tilecutter.sync_vertex_paint_brush"
    bl_label = "Apply Brush Settings"
    bl_description = "Apply radius, inner falloff, and strength to the active vertex paint brush"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _is_vertex_paint_ready(context)

    def execute(self, context):
        color = _current_vertex_paint_color(context)[:3]
        obj, brush = _prepare_vertex_paint(context, color)
        if obj is None or brush is None:
            self.report({'WARNING'}, "Switch to Vertex Paint mode first")
            return {'CANCELLED'}
        self.report({'INFO'}, "Vertex paint brush settings applied")
        return {'FINISHED'}


class TC_OT_EnterVertexPaintMode(Operator):
    bl_idname = "tilecutter.enter_vertex_paint_mode"
    bl_label = "Enter Vertex Paint"
    bl_description = "Switch the active mesh to Vertex Paint mode"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = _active_mesh_object(context)
        return obj is not None and obj.mode != 'VERTEX_PAINT'

    def execute(self, context):
        obj = _active_mesh_object(context)
        if obj is None:
            self.report({'WARNING'}, "Select a mesh object first")
            return {'CANCELLED'}
        if obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        _ensure_vertex_color_attribute(obj)
        bpy.ops.object.mode_set(mode='VERTEX_PAINT')
        self.report({'INFO'}, "Vertex Paint mode enabled")
        return {'FINISHED'}


class TC_OT_ExitVertexPaintMode(Operator):
    bl_idname = "tilecutter.exit_vertex_paint_mode"
    bl_label = "Object Mode"
    bl_description = "Switch the active mesh back to Object Mode"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _is_vertex_paint_ready(context)

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "Object Mode enabled")
        return {'FINISHED'}


class TC_OT_FillVertexPaintColor(Operator):
    bl_idname = "tilecutter.fill_vertex_paint_color"
    bl_label = "Fill Vertex Color"
    bl_description = "Fill vertex colors with the active paint color"
    bl_options = {'REGISTER', 'UNDO'}

    selected_only: BoolProperty(
        name="Selected Only",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return _is_vertex_paint_ready(context)

    def execute(self, context):
        obj = _active_mesh_object(context)
        if obj is None:
            self.report({'WARNING'}, "Switch to Vertex Paint mode first")
            return {'CANCELLED'}

        original_mode = obj.mode
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        attr = _ensure_vertex_color_attribute(obj)
        color = _current_vertex_paint_color(context)
        mesh = obj.data

        selected_verts = set()
        selected_loops = set()
        if self.selected_only:
            selected_verts = {v.index for v in mesh.vertices if v.select}
            selected_polys = [p for p in mesh.polygons if p.select]
            for poly in selected_polys:
                selected_loops.update(poly.loop_indices)
                selected_verts.update(poly.vertices)
            if selected_verts:
                for poly in mesh.polygons:
                    for loop_index in poly.loop_indices:
                        if mesh.loops[loop_index].vertex_index in selected_verts:
                            selected_loops.add(loop_index)
            if not selected_verts and not selected_loops:
                self.report({'WARNING'}, "No selected vertices or faces to fill")
                if original_mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode=original_mode)
                return {'CANCELLED'}

        if attr.domain == 'CORNER':
            indices = selected_loops if self.selected_only else range(len(attr.data))
            for index in indices:
                if 0 <= index < len(attr.data):
                    attr.data[index].color = color
        elif attr.domain == 'POINT':
            indices = selected_verts if self.selected_only else range(len(mesh.vertices))
            for index in indices:
                if 0 <= index < len(attr.data):
                    attr.data[index].color = color
        else:
            self.report({'WARNING'}, f"Unsupported color attribute domain: {attr.domain}")
            if original_mode != 'OBJECT':
                bpy.ops.object.mode_set(mode=original_mode)
            return {'CANCELLED'}

        mesh.update()
        _apply_vertex_paint_brush(context, color)
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode=original_mode)

        self.report({'INFO'}, "Vertex color filled")
        return {'FINISHED'}
