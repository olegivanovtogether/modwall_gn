"""Materials used by the preview objects."""

import bpy


def _make_material_transparent(mat, alpha=0.55):
    mat.diffuse_color = (mat.diffuse_color[0], mat.diffuse_color[1],
                         mat.diffuse_color[2], alpha)
    mat.blend_method = 'BLEND'
    if hasattr(mat, "use_backface_culling"):
        mat.use_backface_culling = True
    if hasattr(mat, "show_transparent_back"):
        mat.show_transparent_back = True
    if hasattr(mat, "use_screen_refraction"):
        mat.use_screen_refraction = True

    if mat.use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            if "Alpha" in bsdf.inputs:
                bsdf.inputs["Alpha"].default_value = alpha
            if "Base Color" in bsdf.inputs and not bsdf.inputs["Base Color"].is_linked:
                color = bsdf.inputs["Base Color"].default_value
                bsdf.inputs["Base Color"].default_value = (
                    color[0], color[1], color[2], alpha,
                )


def _preview_material(ref_tile):
    src_mat = None
    if ref_tile is not None and ref_tile.data.materials:
        src_mat = ref_tile.data.materials[0]

    if src_mat is not None:
        mat_name = f"TC_Preview_{src_mat.name}"
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = src_mat.copy()
            mat.name = mat_name
        _make_material_transparent(mat)
        return mat

    mat = bpy.data.materials.get("TC_Tile_Preview_Material")
    if mat is None:
        mat = bpy.data.materials.new("TC_Tile_Preview_Material")
        mat.diffuse_color = (0.2, 0.65, 1.0, 0.55)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            bsdf.inputs["Base Color"].default_value = (0.2, 0.65, 1.0, 0.55)
            bsdf.inputs["Alpha"].default_value = 0.55
    _make_material_transparent(mat)
    return mat


def _wire_material():
    mat = bpy.data.materials.get("TC_Tile_Preview_Wire_Material")
    if mat is None:
        mat = bpy.data.materials.new("TC_Tile_Preview_Wire_Material")
        mat.diffuse_color = (0.0, 1.0, 0.1, 1.0)
    return mat
