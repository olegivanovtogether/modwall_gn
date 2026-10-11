"""Vertex Paint helper functions."""

import bpy


def _active_mesh_object(context):
    obj = context.object
    if obj is None or obj.type != 'MESH':
        return None
    return obj


def _ensure_vertex_color_attribute(obj, name="TC_VertexColor"):
    mesh = obj.data
    attr = mesh.color_attributes.active_color
    if attr is None:
        attr = mesh.color_attributes.get(name)
    if attr is None:
        attr = mesh.color_attributes.new(
            name=name,
            type='BYTE_COLOR',
            domain='CORNER',
        )

    for index, color_attr in enumerate(mesh.color_attributes):
        if color_attr == attr:
            mesh.color_attributes.active_color_index = index
            mesh.color_attributes.render_color_index = index
            break
    mesh.color_attributes.active_color_name = attr.name
    mesh.color_attributes.default_color_name = attr.name
    return attr


def _is_vertex_paint_ready(context):
    obj = _active_mesh_object(context)
    return obj is not None and obj.mode == 'VERTEX_PAINT'


def _vertex_paint_brush(context):
    brush = getattr(context, "brush", None)
    if brush is None:
        brush = context.tool_settings.vertex_paint.brush
    if brush is None:
        return None
    try:
        brush.use_paint_vertex = True
    except Exception:
        pass
    return brush


def _apply_vertex_paint_brush(context, color):
    s = context.scene.tc_settings
    brush = _vertex_paint_brush(context)
    if brush is None:
        return None

    rgb = color[:3]
    alpha = color[3] if len(color) > 3 else s.vp_alpha
    unified = context.tool_settings.unified_paint_settings
    unified.use_unified_color = True
    if hasattr(unified, "use_unified_size"):
        unified.use_unified_size = True
    if hasattr(unified, "use_unified_strength"):
        unified.use_unified_strength = True
    unified.color = rgb
    unified.size = s.vp_brush_size
    unified.strength = s.vp_brush_strength

    brush.color_type = 'COLOR'
    brush.color = rgb
    brush.size = s.vp_brush_size
    brush.strength = s.vp_brush_strength
    if hasattr(brush, "use_alpha"):
        brush.use_alpha = True
    if hasattr(brush, "hardness"):
        brush.hardness = s.vp_brush_hardness
    if hasattr(brush, "vertex_tool"):
        brush.vertex_tool = 'DRAW'
    s.vp_alpha = alpha
    for area in context.screen.areas:
        area.tag_redraw()
    return brush


def _prepare_vertex_paint(context, color):
    obj = _active_mesh_object(context)
    if obj is None or obj.mode != 'VERTEX_PAINT':
        return None, None
    bpy.ops.object.mode_set(mode='OBJECT')
    _ensure_vertex_color_attribute(obj)
    bpy.ops.object.mode_set(mode='VERTEX_PAINT')
    brush = _apply_vertex_paint_brush(context, color)
    return obj, brush


def _current_vertex_paint_color(context):
    alpha = context.scene.tc_settings.vp_alpha
    unified = context.tool_settings.unified_paint_settings
    if unified.use_unified_color:
        return (unified.color.r, unified.color.g, unified.color.b, alpha)
    brush = _vertex_paint_brush(context)
    if brush is not None:
        return (brush.color.r, brush.color.g, brush.color.b, alpha)
    color = context.scene.tc_settings.vp_custom_color
    return (color[0], color[1], color[2], color[3])
