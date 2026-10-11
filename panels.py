"""N-panel UI: one panel with the add-on name, a row of module tabs and the
content of the selected tab."""

import sys

import bpy
from bpy.props import EnumProperty
from bpy.types import Panel
from .uv_geom import _AXIS_ORDER, _flip_side_buttons, _resolve_priority_axes
from .vertex_paint import _is_vertex_paint_ready


TABS = (
    ('TILE_GRID', "Tile Grid", "Cut a mesh into tile cells and project UVs from a reference tile"),
    ('CYLINDER', "Cylinder", "Cylinder projection with height and angular cuts"),
    ('UVW', "UVW Map", "UVW-style projection from a gizmo without cutting the mesh"),
    ('VERTEX_PAINT', "Vertex Paint", "Vertex color painting helpers"),
)


def register_tab_property():
    """Selected tab is UI state: kept on the window manager, not saved."""
    bpy.types.WindowManager.tc_active_tab = EnumProperty(
        name="Module",
        items=TABS,
        default='TILE_GRID',
        options={'SKIP_SAVE'},
    )


def unregister_tab_property():
    if hasattr(bpy.types.WindowManager, "tc_active_tab"):
        del bpy.types.WindowManager.tc_active_tab


def _addon_version():
    pkg = sys.modules.get(__package__)
    info = getattr(pkg, "bl_info", None)
    if info:
        return ".".join(str(v) for v in info.get("version", ()))
    return "?"


def _draw_tile_grid(layout, context):
    """Tile Grid tab: inputs, texture direction and priority layers."""
    s = context.scene.tc_settings

    layout.prop(s, "target_object", icon='MESH_DATA')
    layout.prop(s, "reference_tile", icon='UV')

    layout.prop(s, "duplicate_before_apply")

    if s.proj_box is not None:
        layout.separator()
        layout.label(text="Proj Box: move / scale / rotate it")
        layout.operator("tilecutter.reset_proj_box",
                        text="Reset Proj Box", icon='LOOP_BACK')

    layout.separator()
    layout.label(text="Texture direction")
    row = layout.row(align=True)
    left = row.operator("tilecutter.rotate_texture", text="", icon='LOOP_BACK')
    left.direction = -1
    row.prop(s, "texture_rotation", text="")
    right = row.operator("tilecutter.rotate_texture", text="", icon='LOOP_FORWARDS')
    right.direction = 1

    layout.separator()
    layout.prop(s, "use_priority_axis")
    if not s.use_priority_axis:
        layout.label(text="Off: faces near 45 deg may project chaotically",
                     icon='ERROR')
        return

    a1, a2, a3 = _resolve_priority_axes(s)

    def side_row(box, prop, layer, axis, enabled=True):
        col = box.column(align=True)
        col.enabled = enabled
        col.label(text="Flip side:")
        row = col.row(align=True)
        for value, text in _flip_side_buttons(layer, axis):
            row.prop_enum(s, prop, value, text=text)

    # ── Layer 1 ──
    layout.separator(factor=1.5)
    box1 = layout.box()
    box1.label(text=f"Layer 1  ·  Top-Bottom  ·  axis {a1}")
    box1.prop(s, "priority_axis", expand=True)
    row = box1.row(align=True)
    row.prop(s, "priority_angle_from")
    row.prop(s, "priority_angle_to")
    box1.prop(s, "priority_flip_back")
    side_row(box1, "priority_flip_side", 1, a1, s.priority_flip_back)

    # ── Layer 2 ──
    layout.separator(factor=1.5)
    box2 = layout.box()
    box2.prop(s, "use_secondary_axis", text=f"Layer 2  ·  Front-Back  ·  axis {a2}")
    if not s.use_secondary_axis:
        box2.label(text="Off: faces near 45 deg may project chaotically",
                   icon='ERROR')
    col2 = box2.column()
    col2.enabled = s.use_secondary_axis
    row = col2.row(align=True)
    for ax in _AXIS_ORDER:
        if ax != a1:
            row.prop_enum(s, "secondary_axis", ax)
    row = col2.row(align=True)
    row.prop(s, "secondary_angle_from")
    row.prop(s, "secondary_angle_to")
    col2.prop(s, "secondary_flip_back")
    side_row(col2, "secondary_flip_side", 2, a2, s.secondary_flip_back)

    # ── Layer 3 ──
    layout.separator(factor=1.5)
    box3 = layout.box()
    row3 = box3.row()
    row3.enabled = s.use_secondary_axis
    row3.prop(s, "use_remainder_axis",
              text=f"Layer 3  ·  Left-Right  ·  axis {a3}")
    if not s.use_secondary_axis:
        box3.label(text="Needs Layer 2", icon='INFO')
    elif not s.use_remainder_axis:
        box3.label(text="Off: nearest-axis rule, may be chaotic near 45 deg",
                   icon='ERROR')
    col3 = box3.column()
    col3.enabled = s.use_secondary_axis and s.use_remainder_axis
    col3.prop(s, "remainder_flip_back")
    side_row(col3, "remainder_flip_side", 3, a3, s.remainder_flip_back)


def _draw_tile_grid_apply(layout, context):
    """Tile Grid tab, bottom: seams and the Apply button."""
    s = context.scene.tc_settings

    layout.prop(s, "mark_seams")
    seam_col = layout.column(align=True)
    seam_col.enabled = s.mark_seams
    seam_col.prop(s, "dissolve_non_seamed_edges")
    seam_col.prop(s, "seam_angle", text="Corner Angle (deg)")

    layout.separator()
    row = layout.row()
    row.scale_y = 1.4
    row.operator("tilecutter.apply", icon='MESH_GRID')


def _draw_cylinder(layout, context):
    """Cylinder tab."""
    s = context.scene.tc_settings

    layout.prop(s, "cylinder_target", icon='MESH_DATA')
    layout.prop(s, "cylinder_reference_tile", icon='UV')

    col = layout.column(align=True)
    col.prop(s, "cylinder_axis")
    col.prop(s, "cylinder_tiles_around")
    col.prop(s, "cylinder_stretch_around")
    col.prop(s, "cylinder_tile_height_source")
    height_row = col.row(align=True)
    height_row.enabled = s.cylinder_tile_height_source == 'MANUAL'
    height_row.prop(s, "cylinder_tile_height")
    col.prop(s, "cylinder_cut_height_bands")

    if s.cylinder_control is not None:
        layout.label(text="Cylinder Control: move / rotate / scale it")
        layout.operator("tilecutter.select_cylinder_control",
                        text="Select Cylinder Control", icon='EMPTY_ARROWS')

    layout.prop(s, "cylinder_project_caps")
    layout.prop(s, "cylinder_duplicate_before_apply")

    row = layout.row()
    row.scale_y = 1.4
    row.operator("tilecutter.apply_cylinder", icon='MESH_CYLINDER')


def _draw_uvw(layout, context):
    """UVW Map tab."""
    s = context.scene.tc_settings

    layout.prop(s, "uvw_target", icon='MESH_DATA')
    layout.prop(s, "uvw_reference_tile", icon='UV')
    layout.prop(s, "uvw_mapping_type")
    if s.uvw_mapping_type == 'CYLINDER':
        layout.prop(s, "uvw_cylinder_tiles_around")

    row = layout.row(align=True)
    row.prop(s, "uvw_flip_u", toggle=True)
    row.prop(s, "uvw_flip_v", toggle=True)

    layout.prop(s, "uvw_duplicate_before_apply")
    layout.prop(s, "uvw_copy_material")

    if s.uvw_gizmo is not None:
        layout.label(text="UVW Gizmo: move / rotate / scale it")
    layout.operator("tilecutter.select_uvw_gizmo",
                    text="Select / Create UVW Gizmo", icon='EMPTY_ARROWS')

    row = layout.row()
    row.scale_y = 1.4
    row.operator("tilecutter.apply_uvw_map", icon='MOD_UVPROJECT')


def _draw_vertex_paint(layout, context):
    """Vertex Paint tab."""
    s = context.scene.tc_settings
    ready = _is_vertex_paint_ready(context)

    mode_row = layout.row(align=True)
    if ready:
        mode_row.operator("tilecutter.exit_vertex_paint_mode", text="Object Mode", icon='OBJECT_DATA')
    else:
        layout.label(text="Switch to Vertex Paint mode", icon='INFO')
        mode_row.operator("tilecutter.enter_vertex_paint_mode", text="Enter Vertex Paint", icon='VPAINT_HLT')

    controls = layout.column(align=True)
    controls.enabled = ready

    row = controls.row(align=True)
    row.scale_x = 1.7
    row.scale_y = 3.0
    red = row.operator("tilecutter.set_vertex_paint_color", text="R", icon='COLORSET_01_VEC')
    red.color_name = 'RED'
    green = row.operator("tilecutter.set_vertex_paint_color", text="G", icon='COLORSET_03_VEC')
    green.color_name = 'GREEN'
    blue = row.operator("tilecutter.set_vertex_paint_color", text="B", icon='COLORSET_04_VEC')
    blue.color_name = 'BLUE'
    white = row.operator("tilecutter.set_vertex_paint_color", text="White")
    white.color_name = 'WHITE'
    black = row.operator("tilecutter.set_vertex_paint_color", text="Black")
    black.color_name = 'BLACK'

    custom_row = controls.row(align=True)
    custom_row.prop(s, "vp_custom_color", text="")
    custom = custom_row.operator("tilecutter.set_vertex_paint_color", text="Custom", icon='EYEDROPPER')
    custom.color_name = 'CUSTOM'

    col = controls.column(align=True)
    col.prop(s, "vp_brush_size")
    col.prop(s, "vp_brush_hardness")
    col.prop(s, "vp_brush_strength")
    col.prop(s, "vp_alpha")
    col.operator("tilecutter.sync_vertex_paint_brush", icon='BRUSH_DATA')

    fill_row = controls.row(align=True)
    selected = fill_row.operator("tilecutter.fill_vertex_paint_color", text="Fill Selected", icon='RESTRICT_SELECT_OFF')
    selected.selected_only = True
    obj = fill_row.operator("tilecutter.fill_vertex_paint_color", text="Fill Object", icon='SHADING_SOLID')
    obj.selected_only = False


class TC_PT_Main(Panel):
    bl_label = "modwall_gn (Simple Tile Cutter)"
    bl_idname = "TC_PT_MAIN"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'modwall_gn'

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        layout.label(text=f"v{_addon_version()}")

        # Tab buttons; they wrap onto a second row when the panel is narrow.
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, align=True)
        for ident, label, _desc in TABS:
            flow.prop_enum(wm, "tc_active_tab", ident, text=label)
        layout.separator()

        tab = wm.tc_active_tab
        if tab == 'TILE_GRID':
            _draw_tile_grid(layout, context)
            _draw_tile_grid_apply(layout, context)
        elif tab == 'CYLINDER':
            _draw_cylinder(layout, context)
        elif tab == 'UVW':
            _draw_uvw(layout, context)
        elif tab == 'VERTEX_PAINT':
            _draw_vertex_paint(layout, context)
