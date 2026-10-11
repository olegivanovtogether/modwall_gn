bl_info = {
    "name": "ModwallGN (Simple Tile Cutter)",
    "author": "Oleh Strykitchenko",
    "version": (0, 7, 1),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > ModwallGN",
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
    ops_tile_grid.TC_OT_SelectController,
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
    panels.TC_PT_TileSetup,
    panels.TC_PT_TileLayers,
    panels.TC_PT_TileApply,
    panels.TC_PT_CylinderTab,
    panels.TC_PT_UVWTab,
    panels.TC_PT_VertexPaintTab,
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


def _is_ours(obj):
    """True for objects defined in this package (any copy of it, so classes
    and handlers left by an older load of the same package are found too)."""
    module = getattr(obj, "__module__", "") or ""
    return module == __package__ or module.startswith(__package__ + ".")


def _all_subclasses(base):
    """All direct and indirect subclasses (type.__subclasses__ is shallow)."""
    seen, stack = [], list(base.__subclasses__())
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.append(cls)
        stack.extend(cls.__subclasses__())
    return seen


def _remove_load_handlers():
    for h in list(bpy.app.handlers.load_post):
        if getattr(h, "__name__", "") == "_tc_load_post" and _is_ours(h):
            bpy.app.handlers.load_post.remove(h)


def _delete_scene_settings():
    if not hasattr(bpy.types.Scene, "tc_settings"):
        return
    prop = bpy.types.Scene.bl_rna.properties.get("tc_settings")
    fixed = getattr(prop, "fixed_type", None)
    # Another add-on could own a property with this name; only ours is a
    # pointer to the TC_Settings group.
    if fixed is None or getattr(fixed, "identifier", "") != "TC_Settings":
        return
    del bpy.types.Scene.tc_settings


def _unregister_registered_classes():
    """Unregister every class of this add-on that is currently registered.

    Blender does not expose registered classes through bpy.types.<name>, so
    they are found by scanning the subclasses of the Blender base types and
    keeping only classes defined in this package. That also catches classes
    left by an older copy of the module (reload without unregister).
    Returns a list of error strings for classes that could not be removed.
    """
    found = list(classes)
    for base in (bpy.types.PropertyGroup, bpy.types.Operator, bpy.types.Panel):
        for sub in _all_subclasses(base):
            if _is_ours(sub) and sub not in found:
                found.append(sub)
    errors = []
    for cls in reversed(found):
        if not getattr(cls, "is_registered", False):
            continue   # nothing to do
        try:
            bpy.utils.unregister_class(cls)
        except Exception as exc:
            errors.append(f"{cls.__name__}: {exc}")
    return errors


def _unregister_all():
    """Safe to call at any time and any number of times. Every step runs even
    if an earlier one failed; returns the list of problems."""
    errors = []
    for step in (_remove_load_handlers,
                 panels.unregister_tab_property,
                 _delete_scene_settings,
                 _unregister_registered_classes):
        try:
            result = step()
            if result:
                errors.extend(result)
        except Exception as exc:
            errors.append(f"{step.__name__}: {exc}")
    return errors


def register():
    # Start from a clean state so register() can be called repeatedly and
    # after a reload without an unregister() in between.
    leftovers = _unregister_all()
    if leftovers:
        raise RuntimeError(
            "modwall_gn: could not clear an earlier registration: "
            + "; ".join(leftovers))
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
        bpy.types.Scene.tc_settings = PointerProperty(type=props.TC_Settings)
        panels.register_tab_property()
        bpy.app.handlers.load_post.append(_tc_load_post)
    except Exception as exc:
        # do not leave a half registered add-on behind
        problems = _unregister_all()
        if problems:
            raise RuntimeError(
                f"{exc} (rollback also failed: {'; '.join(problems)})") from exc
        raise
    try:
        _sync_axis_memory()
    except Exception:
        pass   # bpy.data is restricted while the add-on is being enabled


def unregister():
    for problem in _unregister_all():
        print(f"modwall_gn: unregister problem: {problem}")


if __name__ == "__main__":
    register()
