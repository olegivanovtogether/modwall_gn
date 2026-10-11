bl_info = {
    "name": "Simple Tile Cutter",
    "author": "Oleh Strykitchenko",
    "version": (0, 6, 14),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Tile Cutter",
    "description": "Alpha tool for a focused mobile-game asset workflow: cut meshes into tile-sized sections and project UVs from a reference tile",
    "category": "Mesh",
}

import bpy
from bpy.app.handlers import persistent
from bpy.props import PointerProperty

# Modules in dependency order (a module only imports the ones above it).
from . import (
    bmesh_baker,
    uv_geom,
    preview_mat,
    vertex_paint,
    tile_grid,
    cylinder,
    uvw,
    callbacks,
    props,
    ops_tile_grid,
    ops_cylinder,
    ops_uvw,
    ops_vertex_paint,
    panels,
)

_MODULES = (
    bmesh_baker, uv_geom, preview_mat, vertex_paint, tile_grid, cylinder, uvw,
    callbacks, props, ops_tile_grid, ops_cylinder, ops_uvw, ops_vertex_paint,
    panels,
)

if "_modules_loaded" in globals():
    # F3 > Reload Scripts: reload every module in dependency order so that no
    # stale copy of a function stays bound in a dependent module.
    import importlib
    for _module in _MODULES:
        importlib.reload(_module)
_modules_loaded = True


classes = (
    props.TC_Settings,
    ops_tile_grid.TC_OT_Apply,
    ops_tile_grid.TC_OT_ResetProjBox,
    ops_tile_grid.TC_OT_RotateTexture,
    ops_cylinder.TC_OT_SelectCylinderControl,
    ops_cylinder.TC_OT_ApplyCylinder,
    ops_uvw.TC_OT_SelectUVWGizmo,
    ops_uvw.TC_OT_ApplyUVWMap,
    ops_vertex_paint.TC_OT_SetVertexPaintColor,
    ops_vertex_paint.TC_OT_SyncVertexPaintBrush,
    ops_vertex_paint.TC_OT_EnterVertexPaintMode,
    ops_vertex_paint.TC_OT_ExitVertexPaintMode,
    ops_vertex_paint.TC_OT_FillVertexPaintColor,
    panels.TC_PT_Main,
    panels.TC_PT_TileGrid,
    panels.TC_PT_TileGridApply,
    panels.TC_PT_CylinderProjection,
    panels.TC_PT_UVWMapProjection,
    panels.TC_PT_VertexPaintTools,
)


def _sync_axis_memory():
    """Make `priority_axis_prev` match the current layer 1 axis in every scene
    (it is not stored in older files, so it could be stale after loading)."""
    for scene in bpy.data.scenes:
        st = getattr(scene, "tc_settings", None)
        if st is not None:
            st.priority_axis_prev = st.priority_axis


@persistent
def _tc_load_post(_dummy=None):
    _sync_axis_memory()


def register():
    if hasattr(bpy.types.Scene, "tc_settings"):
        del bpy.types.Scene.tc_settings
    for cls in classes:
        existing = getattr(bpy.types, cls.__name__, None)
        if existing is not None:
            try:
                bpy.utils.unregister_class(existing)
            except Exception:
                pass
        bpy.utils.register_class(cls)
    bpy.types.Scene.tc_settings = PointerProperty(type=props.TC_Settings)
    if _tc_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_tc_load_post)
    try:
        _sync_axis_memory()
    except Exception:
        pass


def unregister():
    if _tc_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_tc_load_post)
    if hasattr(bpy.types.Scene, "tc_settings"):
        del bpy.types.Scene.tc_settings
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


if __name__ == "__main__":
    register()
