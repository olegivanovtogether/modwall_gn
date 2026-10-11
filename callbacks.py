"""Small property update callbacks and poll functions."""

from .uv_geom import _AXIS_ORDER
from .tile_grid import _refresh_tile_preview


def _poll_mesh(self, obj):
    return obj.type == 'MESH'


def _sync_priority_axes(self, context):
    """Layer 1 axis changed. If layer 2 already used that axis, the two layers
    swap axes (layer 2 takes the axis layer 1 just left). Layer 3 always is
    the remaining axis, so it follows automatically."""
    new = self.priority_axis
    old = self.priority_axis_prev
    if self.secondary_axis == new:
        if old in _AXIS_ORDER and old != new:
            self.secondary_axis = old
        else:
            self.secondary_axis = next(a for a in _AXIS_ORDER if a != new)
    self.priority_axis_prev = new
    _refresh_tile_preview(self, context)


def _sync_seam_options(self, context):
    if not self.mark_seams:
        self.dissolve_non_seamed_edges = False


def _sync_vertex_paint_settings(self, context):
    obj = context.object
    if obj is None or obj.type != 'MESH' or obj.mode != 'VERTEX_PAINT':
        return

    brush = getattr(context, "brush", None)
    if brush is None:
        brush = context.tool_settings.vertex_paint.brush
    if brush is None:
        return

    unified = context.tool_settings.unified_paint_settings
    if hasattr(unified, "use_unified_size"):
        unified.use_unified_size = True
    if hasattr(unified, "use_unified_strength"):
        unified.use_unified_strength = True
    unified.size = self.vp_brush_size
    unified.strength = self.vp_brush_strength

    brush.size = self.vp_brush_size
    brush.strength = self.vp_brush_strength
    if hasattr(brush, "hardness"):
        brush.hardness = self.vp_brush_hardness
    if hasattr(brush, "use_alpha"):
        brush.use_alpha = True

    for area in context.screen.areas:
        area.tag_redraw()
