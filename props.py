"""TC_Settings: every addon property (scene.tc_settings)."""

import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    FloatProperty,
    FloatVectorProperty,
    BoolProperty,
    PointerProperty,
    IntProperty,
    EnumProperty,
    StringProperty,
)
from .tile_grid import _on_texture_rotation, _refresh_tile_preview, _sync_proj_box
from .cylinder import _sync_cylinder_preview
from .uvw import _sync_uvw_gizmo
from .callbacks import _poll_mesh, _sync_priority_axes, _sync_seam_options, _sync_vertex_paint_settings


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
        default=1.0, min=0.001, max=100.0,
        unit='LENGTH',
        update=_sync_proj_box,
    )
    tile_size_y: FloatProperty(
        name="Tile Size Y",
        default=1.0, min=0.001, max=100.0,
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
    tile_preview_wire: PointerProperty(
        name="Tile Preview Wire",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    duplicate_before_apply: BoolProperty(
        name="Duplicate Before Apply",
        description="Work on a copy; original mesh is left untouched",
        default=True,
    )
    texture_rotation: EnumProperty(
        name="Texture direction",
        description="How the texture is read: rotate the whole tile layout in 90 degree steps (use Vertical when the texture image is stored turned on its side)",
        items=[
            ('0',   "0° · Horizontal", "Texture is read as stored"),
            ('90',  "90° · Vertical", "Texture turned by 90 degrees; cell width and height are swapped"),
            ('180', "180° · Horizontal, upside down", "Texture turned by 180 degrees"),
            ('270', "270° · Vertical, upside down", "Texture turned by 270 degrees; cell width and height are swapped"),
        ],
        default='0',
        update=_on_texture_rotation,
    )
    use_priority_axis: BoolProperty(
        name="Priority Axis",
        description="Faces whose normal is within the angle range of a priority axis always project along that axis (avoids chaos near 45 degrees)",
        default=True,
        update=_refresh_tile_preview,
    )
    priority_axis: EnumProperty(
        name="Axis",
        description="Layer 1: Projection Box axis that wins inside the angle range",
        items=[
            ('X', "X", "Projection Box X axis"),
            ('Y', "Y", "Projection Box Y axis"),
            ('Z', "Z", "Projection Box Z axis (ceiling / floor)"),
        ],
        default='Z',
        update=_sync_priority_axes,
    )
    priority_axis_prev: StringProperty(
        name="Previous layer 1 axis",
        description="Internal: remembers the layer 1 axis before the last change",
        default='Z',
        options={'HIDDEN'},
    )
    priority_angle_from: FloatProperty(
        name="From",
        description="Minimum angle between the face normal and the layer 1 axis (degrees)",
        default=0.0, min=0.0, max=90.0,
    )
    priority_angle_to: FloatProperty(
        name="To",
        description="Maximum angle between the face normal and the layer 1 axis (degrees); the boundary itself is included",
        default=50.0, min=0.0, max=90.0,
    )
    priority_flip_back: BoolProperty(
        name="Flip Back Faces",
        description="Turn over (mirror U of) the faces of this layer that look away from the axis, like gluing the paper on the other side. Off = straight-through projection",
        default=False,
        update=_refresh_tile_preview,
    )
    priority_flip_side: EnumProperty(
        name="Flip side",
        description="Which side of this layer's axis Flip Back Faces turns over",
        items=[
            ('DEFAULT',  "Default side",  "The side that was flipped before: X: -X, Y: +Y, Z: bottom"),
            ('OPPOSITE', "Opposite side", "The other side of the axis: X: +X, Y: -Y, Z: top"),
        ],
        default='DEFAULT',
        update=_refresh_tile_preview,
    )
    use_secondary_axis: BoolProperty(
        name="Layer 2",
        description="Second priority layer: among faces not caught by layer 1, faces within the angle range of the second axis project along it",
        default=True,
        update=_refresh_tile_preview,
    )
    secondary_axis: EnumProperty(
        name="Axis",
        description="Layer 2: one of the two axes left after layer 1",
        items=[
            ('X', "X", "Projection Box X axis"),
            ('Y', "Y", "Projection Box Y axis"),
            ('Z', "Z", "Projection Box Z axis"),
        ],
        default='X',
        update=_refresh_tile_preview,
    )
    secondary_angle_from: FloatProperty(
        name="From",
        description="Minimum angle between the face normal and the layer 2 axis (degrees)",
        default=0.0, min=0.0, max=90.0,
    )
    secondary_angle_to: FloatProperty(
        name="To",
        description="Maximum angle between the face normal and the layer 2 axis (degrees); the boundary itself is included",
        default=50.0, min=0.0, max=90.0,
    )
    secondary_flip_back: BoolProperty(
        name="Flip Back Faces",
        description="Turn over (mirror U of) the faces of this layer that look away from the axis, like gluing the paper on the other side. Off = straight-through projection",
        default=True,
        update=_refresh_tile_preview,
    )
    secondary_flip_side: EnumProperty(
        name="Flip side",
        description="Which side of this layer's axis Flip Back Faces turns over",
        items=[
            ('DEFAULT',  "Default side",  "The side that was flipped before: X: -X, Y: +Y, Z: bottom"),
            ('OPPOSITE', "Opposite side", "The other side of the axis: X: +X, Y: -Y, Z: top"),
        ],
        default='DEFAULT',
        update=_refresh_tile_preview,
    )
    use_remainder_axis: BoolProperty(
        name="Layer 3",
        description="Third priority layer: faces not caught by layers 1 and 2 project along the remaining axis. Off = nearest-axis rule (may be chaotic near 45 degrees)",
        default=True,
        update=_refresh_tile_preview,
    )
    remainder_flip_back: BoolProperty(
        name="Flip Back Faces",
        description="Turn over (mirror U of) the remaining faces that look away from the remaining axis, like gluing the paper on the other side. Off = straight-through projection",
        default=True,
        update=_refresh_tile_preview,
    )
    remainder_flip_side: EnumProperty(
        name="Flip side",
        description="Which side of this layer's axis Flip Back Faces turns over",
        items=[
            ('DEFAULT',  "Default side",  "The side that was flipped before: X: -X, Y: +Y, Z: bottom"),
            ('OPPOSITE', "Opposite side", "The other side of the axis: X: +X, Y: -Y, Z: top"),
        ],
        default='DEFAULT',
        update=_refresh_tile_preview,
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

    # ── Cylinder Projection ───────────────────────────────────────────────────
    cylinder_target: PointerProperty(
        name="Target Mesh",
        type=bpy.types.Object,
        poll=_poll_mesh,
        update=_sync_cylinder_preview,
    )
    cylinder_reference_tile: PointerProperty(
        name="Reference Tile",
        type=bpy.types.Object,
        poll=_poll_mesh,
        update=_sync_cylinder_preview,
    )
    cylinder_axis: EnumProperty(
        name="Cylinder Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='Z',
        update=_sync_cylinder_preview,
    )
    cylinder_tiles_around: IntProperty(
        name="Tiles Around",
        description="How many tiles repeat around the full circumference",
        default=1, min=1, max=64,
        update=_sync_cylinder_preview,
    )
    cylinder_stretch_around: BoolProperty(
        name="Stretch Around",
        description="Use the older wrap behavior: do not add angular cuts around the cylinder",
        default=False,
    )
    cylinder_tile_height_source: EnumProperty(
        name="Tile Height Source",
        description="Choose how cylinder tile height is measured",
        items=[
            ('AUTO', "Auto from Tile", "Use the smallest non-zero dimension of the flat reference tile"),
            ('MANUAL', "Manual", "Use the manual Tile Height field"),
            ('X', "Reference X", "Use reference tile X dimension"),
            ('Y', "Reference Y", "Use reference tile Y dimension"),
            ('Z', "Reference Z", "Use reference tile Z dimension"),
        ],
        default='X',
        update=_sync_cylinder_preview,
    )
    cylinder_cut_height_bands: BoolProperty(
        name="Cut Height Bands",
        description="Cut side faces into tile-height bands before assigning cylinder UVs",
        default=True,
    )
    cylinder_tile_height: FloatProperty(
        name="Tile Height",
        description="Manual tile height along the cylinder axis",
        default=1.0, min=0.001, max=100.0,
        unit='LENGTH',
        update=_sync_cylinder_preview,
    )
    cylinder_project_caps: BoolProperty(
        name="Project Caps",
        description="Apply planar UV to cap faces (faces whose normal is mostly along the axis)",
        default=True,
        update=_sync_cylinder_preview,
    )
    cylinder_duplicate_before_apply: BoolProperty(
        name="Duplicate Before Apply",
        description="Work on a copy; original mesh is left untouched",
        default=True,
    )
    cylinder_preview: PointerProperty(
        name="Cylinder Preview",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    cylinder_preview_wire: PointerProperty(
        name="Cylinder Preview Wire",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    cylinder_control: PointerProperty(
        name="Cylinder Control",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'EMPTY',
    )

    # ── UVW Map Projection ────────────────────────────────────────────────────
    uvw_target: PointerProperty(
        name="Target Mesh",
        type=bpy.types.Object,
        poll=_poll_mesh,
        update=_sync_uvw_gizmo,
    )
    uvw_reference_tile: PointerProperty(
        name="Reference Tile",
        type=bpy.types.Object,
        poll=_poll_mesh,
        update=_sync_uvw_gizmo,
    )
    uvw_mapping_type: EnumProperty(
        name="Mapping Type",
        items=[
            ('BOX',      "Box",      "Box (cubic) projection from gizmo local axes"),
            ('PLANAR',   "Planar",   "Planar projection from gizmo local XY plane"),
            ('CYLINDER', "Cylinder", "Cylindrical projection around gizmo local Z"),
        ],
        default='BOX',
        update=_sync_uvw_gizmo,
    )
    uvw_cylinder_tiles_around: IntProperty(
        name="Tiles Around",
        description="How many reference tiles repeat around the full UVW cylinder",
        default=1, min=1, max=64,
        update=_sync_uvw_gizmo,
    )
    uvw_duplicate_before_apply: BoolProperty(
        name="Duplicate Before Apply",
        description="Work on a copy; original mesh is left untouched",
        default=True,
    )
    uvw_copy_material: BoolProperty(
        name="Copy Material From Reference",
        description="Replace target materials with the reference tile materials after Apply",
        default=True,
    )
    uvw_flip_u: BoolProperty(
        name="U Flip",
        description="Mirror UV along U axis",
        default=False,
    )
    uvw_flip_v: BoolProperty(
        name="V Flip",
        description="Mirror UV along V axis",
        default=False,
    )
    uvw_gizmo: PointerProperty(
        name="UVW Gizmo",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'EMPTY',
    )
    uvw_gizmo_preview: PointerProperty(
        name="UVW Gizmo Preview",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    uvw_gizmo_preview_wire: PointerProperty(
        name="UVW Gizmo Preview Wire",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    # Vertex Paint Tools
    vp_custom_color: FloatVectorProperty(
        name="Custom",
        description="Custom vertex paint color",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0, 1.0),
    )
    vp_alpha: FloatProperty(
        name="Alpha",
        description="Alpha value used for vertex color fill and alpha-aware painting",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        update=_sync_vertex_paint_settings,
    )
    vp_brush_size: IntProperty(
        name="Radius",
        description="Outer brush radius in screen pixels",
        default=35,
        min=1,
        max=5000,
        update=_sync_vertex_paint_settings,
    )
    vp_brush_hardness: FloatProperty(
        name="Inner",
        description="Inner hard area of the brush falloff",
        default=0.75,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        update=_sync_vertex_paint_settings,
    )
    vp_brush_strength: FloatProperty(
        name="Strength",
        description="Vertex paint brush strength",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        update=_sync_vertex_paint_settings,
    )
