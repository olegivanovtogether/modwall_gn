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
    bpy.types.WindowManager.modwall_gn_tab = EnumProperty(
        name="Module",
        items=TABS,
        default='TILE_GRID',
        options={'SKIP_SAVE'},
    )


def unregister_tab_property():
    if hasattr(bpy.types.WindowManager, "modwall_gn_tab"):
        del bpy.types.WindowManager.modwall_gn_tab


def _addon_version():
    pkg = sys.modules.get(__package__)
    info = getattr(pkg, "bl_info", None)
    if info:
        return ".".join(str(v) for v in info.get("version", ()))
    return "?"


# ── Shared blocks: every module tab uses the same order ──────────────────────
#
#   Setup          inputs (Target, Reference Tile) + Controller
#   <settings>     module specific plate(s)
#   Options/Apply  options of the module, then the Apply button (always last)

def _draw_inputs(layout, s, target_prop, reference_prop):
    layout.prop(s, target_prop, icon='MESH_DATA')
    layout.prop(s, reference_prop, icon='UV')


def _draw_controller(layout, select_idname, extra=None):
    """The controller block, identical in every module. `extra` is an optional
    (operator id, text, icon) shown under the Select button."""
    layout.separator()
    layout.label(text="Controller: move / scale / rotate it")
    col = layout.column(align=True)
    col.operator(select_idname, text="Select Controller", icon='EMPTY_ARROWS')
    if extra is not None:
        idname, text, icon = extra
        col.operator(idname, text=text, icon=icon)


def _draw_apply_button(layout, idname, icon):
    layout.separator()
    row = layout.row()
    row.scale_y = 1.4
    row.operator(idname, icon=icon)


# ── Setup plate (all three modules) ──────────────────────────────────────────

def _draw_setup(layout, context, tab):
    s = context.scene.tc_settings
    if tab == 'TILE_GRID':
        _draw_inputs(layout, s, "target_object", "reference_tile")
        _draw_controller(layout, "tilecutter.select_controller",
                         ("tilecutter.reset_proj_box", "Reset Proj Box", 'LOOP_BACK'))
    elif tab == 'CYLINDER':
        _draw_inputs(layout, s, "cylinder_target", "cylinder_reference_tile")
        _draw_controller(layout, "tilecutter.select_cylinder_control")
    elif tab == 'UVW':
        _draw_inputs(layout, s, "uvw_target", "uvw_reference_tile")
        _draw_controller(layout, "tilecutter.select_uvw_gizmo")


# ── Settings plates (module specific) ────────────────────────────────────────

def _draw_texture_direction(layout, s, prop):
    layout.label(text="Texture direction")
    row = layout.row(align=True)
    left = row.operator("tilecutter.rotate_texture", text="", icon='LOOP_BACK')
    left.direction = -1
    left.prop = prop
    row.prop(s, prop, text="")
    right = row.operator("tilecutter.rotate_texture", text="", icon='LOOP_FORWARDS')
    right.direction = 1
    right.prop = prop


def _draw_tile_settings(layout, context):
    """Tile Grid settings plate: texture direction and priority layers."""
    s = context.scene.tc_settings
    _draw_texture_direction(layout, s, "texture_rotation")
    layout.separator()
    _draw_priority_layers(layout, s, "")


def _draw_cylinder_settings(layout, context):
    """Cylinder settings plate."""
    s = context.scene.tc_settings
    col = layout.column(align=True)
    col.prop(s, "cylinder_axis")
    col.prop(s, "cylinder_tiles_around")
    col.prop(s, "cylinder_stretch_around")
    col.prop(s, "cylinder_tile_height_source")
    height_row = col.row(align=True)
    height_row.enabled = s.cylinder_tile_height_source == 'MANUAL'
    height_row.prop(s, "cylinder_tile_height")
    col.prop(s, "cylinder_cut_height_bands")
    layout.prop(s, "cylinder_project_caps")


def _draw_uvw_settings(layout, context):
    """UVW Map settings plate: mapping type and global U / V flip."""
    s = context.scene.tc_settings
    layout.prop(s, "uvw_mapping_type")
    if s.uvw_mapping_type == 'CYLINDER':
        layout.prop(s, "uvw_cylinder_tiles_around")
    row = layout.row(align=True)
    row.prop(s, "uvw_flip_u", toggle=True)
    row.prop(s, "uvw_flip_v", toggle=True)


def _draw_uvw_layers(layout, context):
    """UVW Map (Box): texture direction and priority layers."""
    s = context.scene.tc_settings
    _draw_texture_direction(layout, s, "uvw_texture_rotation")
    layout.separator()
    _draw_priority_layers(layout, s, "uvw_")


# ── Options / Apply plate (all three modules, Apply always last) ──────────────

def _draw_options_apply(layout, context, tab):
    s = context.scene.tc_settings
    if tab == 'TILE_GRID':
        layout.prop(s, "duplicate_before_apply")
        layout.prop(s, "mark_seams")
        seam_col = layout.column(align=True)
        seam_col.enabled = s.mark_seams
        seam_col.prop(s, "dissolve_non_seamed_edges")
        seam_col.prop(s, "seam_angle", text="Corner Angle (deg)")
        _draw_apply_button(layout, "tilecutter.apply", 'MESH_GRID')
    elif tab == 'CYLINDER':
        layout.prop(s, "cylinder_duplicate_before_apply")
        _draw_apply_button(layout, "tilecutter.apply_cylinder", 'MESH_CYLINDER')
    elif tab == 'UVW':
        layout.prop(s, "uvw_duplicate_before_apply")
        layout.prop(s, "uvw_copy_material")
        _draw_apply_button(layout, "tilecutter.apply_uvw_map", 'MOD_UVPROJECT')


def _draw_priority_layers(layout, s, prefix=""):
    """Priority axis checkbox and the three layer boxes for the settings set
    selected by `prefix` ("" Tile Grid, "uvw_" UVW Map)."""
    layout.prop(s, prefix + "use_priority_axis")
    if not getattr(s, prefix + "use_priority_axis"):
        layout.label(text="Off: faces near 45 deg may project chaotically",
                     icon='ERROR')
        return

    a1, a2, a3 = _resolve_priority_axes(s, prefix)

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
    axis_row = box1.row(align=True)
    for ax in _AXIS_ORDER:
        axis_row.prop_enum(s, prefix + "priority_axis", ax)
    row = box1.row(align=True)
    row.prop(s, prefix + "priority_angle_from")
    row.prop(s, prefix + "priority_angle_to")
    box1.prop(s, prefix + "priority_flip_back")
    side_row(box1, prefix + "priority_flip_side", 1, a1, getattr(s, prefix + "priority_flip_back"))

    # ── Layer 2 ──
    layout.separator(factor=1.5)
    box2 = layout.box()
    box2.prop(s, prefix + "use_secondary_axis", text=f"Layer 2  ·  Front-Back  ·  axis {a2}")
    if not getattr(s, prefix + "use_secondary_axis"):
        box2.label(text="Off: faces near 45 deg may project chaotically",
                   icon='ERROR')
    col2 = box2.column()
    col2.enabled = getattr(s, prefix + "use_secondary_axis")
    row = col2.row(align=True)
    for ax in _AXIS_ORDER:
        if ax != a1:
            row.prop_enum(s, prefix + "secondary_axis", ax)
    row = col2.row(align=True)
    row.prop(s, prefix + "secondary_angle_from")
    row.prop(s, prefix + "secondary_angle_to")
    col2.prop(s, prefix + "secondary_flip_back")
    side_row(col2, prefix + "secondary_flip_side", 2, a2, getattr(s, prefix + "secondary_flip_back"))

    # ── Layer 3 ──
    layout.separator(factor=1.5)
    box3 = layout.box()
    row3 = box3.row()
    row3.enabled = getattr(s, prefix + "use_secondary_axis")
    row3.prop(s, prefix + "use_remainder_axis",
              text=f"Layer 3  ·  Left-Right  ·  axis {a3}")
    if not getattr(s, prefix + "use_secondary_axis"):
        box3.label(text="Needs Layer 2", icon='INFO')
    elif not getattr(s, prefix + "use_remainder_axis"):
        box3.label(text="Off: nearest-axis rule, may be chaotic near 45 deg",
                   icon='ERROR')
    col3 = box3.column()
    col3.enabled = (getattr(s, prefix + "use_secondary_axis")
                    and getattr(s, prefix + "use_remainder_axis"))
    col3.prop(s, prefix + "remainder_flip_back")
    side_row(col3, prefix + "remainder_flip_side", 3, a3, getattr(s, prefix + "remainder_flip_back"))


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


# Below this width (in UI units, scale removed) the four tab buttons would be
# cut to unreadable stubs, so they are laid out as two rows of two.
_TABS_ONE_ROW_MIN_WIDTH = 330


def _tabs_fit_one_row(context):
    region = getattr(context, "region", None)
    width = getattr(region, "width", None)
    if not width:
        return True
    scale = 1.0
    try:
        scale = context.preferences.system.ui_scale or 1.0
    except Exception:
        pass
    return (width / scale) >= _TABS_ONE_ROW_MIN_WIDTH


class TC_PT_Main(Panel):
    bl_label = "ModwallGN"
    bl_idname = "TC_PT_MAIN"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ModwallGN'
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        # Header: add-on name and version (like the tab bar of other add-ons).
        header = layout.row(align=True)
        header.label(text=f"ModwallGN  v{_addon_version()}", icon='MESH_GRID')

        # Tab bar: one row of buttons filling the width; two rows when narrow.
        if _tabs_fit_one_row(context):
            bar = layout.row(align=True)
            bar.scale_y = 1.2
            bar.prop(wm, "modwall_gn_tab", expand=True)
        else:
            flow = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
            flow.scale_y = 1.2
            for ident, label, _desc in TABS:
                flow.prop_enum(wm, "modwall_gn_tab", ident, text=label)


def _tab_is(context, *tabs):
    return context.window_manager.modwall_gn_tab in tabs


class _TabPlate:
    """Common settings of the plates (sub-panels) shown under the tab bar."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ModwallGN'
    bl_parent_id = "TC_PT_MAIN"


_CUT_TABS = ('TILE_GRID', 'CYLINDER', 'UVW')


class TC_PT_Setup(_TabPlate, Panel):
    bl_label = "Setup"
    bl_idname = "TC_PT_SETUP"

    @classmethod
    def poll(cls, context):
        return _tab_is(context, *_CUT_TABS)

    def draw(self, context):
        _draw_setup(self.layout, context, context.window_manager.modwall_gn_tab)


class TC_PT_TileLayers(_TabPlate, Panel):
    bl_label = "Texture direction & priority layers"
    bl_idname = "TC_PT_TILE_LAYERS"

    @classmethod
    def poll(cls, context):
        return _tab_is(context, 'TILE_GRID')

    def draw(self, context):
        _draw_tile_settings(self.layout, context)


class TC_PT_CylinderTab(_TabPlate, Panel):
    bl_label = "Cylinder settings"
    bl_idname = "TC_PT_CYLINDER_TAB"

    @classmethod
    def poll(cls, context):
        return _tab_is(context, 'CYLINDER')

    def draw(self, context):
        _draw_cylinder_settings(self.layout, context)


class TC_PT_UVWTab(_TabPlate, Panel):
    bl_label = "UVW settings"
    bl_idname = "TC_PT_UVW_TAB"

    @classmethod
    def poll(cls, context):
        return _tab_is(context, 'UVW')

    def draw(self, context):
        _draw_uvw_settings(self.layout, context)


class TC_PT_UVWLayers(_TabPlate, Panel):
    bl_label = "Texture direction & priority layers (Box)"
    bl_idname = "TC_PT_UVW_LAYERS"

    @classmethod
    def poll(cls, context):
        return (_tab_is(context, 'UVW')
                and context.scene.tc_settings.uvw_mapping_type == 'BOX')

    def draw(self, context):
        _draw_uvw_layers(self.layout, context)


class TC_PT_Apply(_TabPlate, Panel):
    bl_label = "Options / Apply"
    bl_idname = "TC_PT_APPLY"

    @classmethod
    def poll(cls, context):
        return _tab_is(context, *_CUT_TABS)

    def draw(self, context):
        _draw_options_apply(self.layout, context, context.window_manager.modwall_gn_tab)


class TC_PT_VertexPaintTab(_TabPlate, Panel):
    bl_label = "Vertex Paint Tools"
    bl_idname = "TC_PT_VERTEX_PAINT_TAB"

    @classmethod
    def poll(cls, context):
        return _tab_is(context, 'VERTEX_PAINT')

    def draw(self, context):
        _draw_vertex_paint(self.layout, context)
