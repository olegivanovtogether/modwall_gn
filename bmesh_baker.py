import bpy
import bmesh
import math
from mathutils import Vector

def get_tile_bounds(tile_obj):
    """Extracts UV min/max bounds from a tile object's active UV layer."""
    if not tile_obj or tile_obj.type != 'MESH' or not tile_obj.data.uv_layers:
        return (0.0, 0.0), (1.0, 1.0)
        
    uv_layer = tile_obj.data.uv_layers.active.data
    min_u, min_v = 1.0, 1.0
    max_u, max_v = 0.0, 0.0
    
    for loop_uv in uv_layer:
        u, v = loop_uv.uv
        min_u = min(min_u, u)
        min_v = min(min_v, v)
        max_u = max(max_u, u)
        max_v = max(max_v, v)
        
    return (min_u, min_v), (max_u, max_v)

def slice_mesh_with_grid(bm, tile_size, offset=(0.0, 0.0),
                         origin=None, axes=None, center_origin=False):
    """
    Bisects the BMesh along a tile grid.

    By default this uses the local X/Y/Z axes. When origin and axes are passed,
    cut planes are aligned to the Projection Box, so rotated grids cut and UV
    project from the same coordinate system.

    offset=(offset_x, offset_z) is kept for older callers and shifts the
    default X/Z cut planes.
    Returns a set of BMEdge objects created by the bisect operations.
    """
    if origin is None:
        origin = Vector((offset[0], 0.0, offset[1]))
    else:
        origin = Vector(origin)

    if axes is None:
        axes = (
            Vector((1.0, 0.0, 0.0)),
            Vector((0.0, 1.0, 0.0)),
            Vector((0.0, 0.0, 1.0)),
        )
    else:
        axes = tuple(Vector(axis).normalized() for axis in axes)

    cut_edges = set()

    def bisect_axis(axis, step):
        if step <= 0.001: return

        values = [(v.co - origin).dot(axis) for v in bm.verts]
        if not values:
            return

        if center_origin:
            start_mult = math.floor(min(values) / step - 0.5)
            end_mult   = math.ceil(max(values) / step - 0.5)
        else:
            start_mult = math.floor(min(values) / step)
            end_mult   = math.ceil(max(values) / step)

        for mult in range(start_mult, end_mult + 1):
            dist = (mult + 0.5) * step if center_origin else mult * step
            plane_co = origin + axis * dist
            plane_no = axis

            result = bmesh.ops.bisect_plane(
                bm,
                geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                plane_co=plane_co,
                plane_no=plane_no,
                clear_inner=False,
                clear_outer=False
            )
            for elem in result['geom_cut']:
                if isinstance(elem, bmesh.types.BMEdge):
                    cut_edges.add(elem)

    ax_x, ax_y, ax_z = axes
    bisect_axis(ax_x, tile_size[0])  # tile width
    bisect_axis(ax_z, tile_size[1])  # tile height
    bisect_axis(ax_y, tile_size[0])  # side/reveal depth rhythm

    return cut_edges

def _classify_face_by_normal(face):
    """Fallback face type from normal when FaceType attribute is missing or invalid."""
    ny = face.normal.y
    if ny < -0.99:
        return 0  # Front
    elif ny > 0.99:
        return 1  # Back
    else:
        return 2  # Side (Reveal can't be inferred from normal alone)

def apply_uvs_to_faces(bm, settings, uv_layer):
    """
    Reads 'FaceType', applies UVs from the corresponding atlas region, 
    and collects stats.
    """
    face_type_layer = bm.faces.layers.int.get("FaceType")
    
    stats = {
        'front': 0, 'back': 0, 'side': 0, 'reveal': 0, 'missing_type': 0,
        'warnings': [], 'faces_without_uv': 0, 'faces_larger_than_tile': 0
    }
    
    if not face_type_layer:
        stats['warnings'].append("FaceType attribute not found! Did GN apply correctly?")
        
    main_b = get_tile_bounds(settings.main_tile)
    back_b = get_tile_bounds(settings.back_tile if settings.back_tile else settings.main_tile)
    side_b = get_tile_bounds(settings.side_tile if settings.side_tile else settings.main_tile)
    reveal_b = get_tile_bounds(settings.reveal_tile if settings.reveal_tile else (settings.side_tile if settings.side_tile else settings.main_tile))
    
    bounds_map = {0: main_b, 1: back_b, 2: side_b, 3: reveal_b}
    
    tile_size_x = max(settings.tile_size[0], 0.001)
    tile_size_y = max(settings.tile_size[1], 0.001)

    for face in bm.faces:
        if face_type_layer:
            ftype = face[face_type_layer]
            if ftype not in (0, 1, 2, 3):
                ftype = _classify_face_by_normal(face)
                stats['missing_type'] += 1
        else:
            ftype = _classify_face_by_normal(face)
            stats['missing_type'] += 1
            
        if ftype == 0: stats['front'] += 1
        elif ftype == 1: stats['back'] += 1
        elif ftype == 2: stats['side'] += 1
        elif ftype == 3: stats['reveal'] += 1
        else: stats['missing_type'] += 1

        # Check if face exceeds tile_size (validation)
        min_v = Vector((float('inf'), float('inf'), float('inf')))
        max_v = Vector((float('-inf'), float('-inf'), float('-inf')))
        for v in face.verts:
            for i in range(3):
                min_v[i] = min(min_v[i], v.co[i])
                max_v[i] = max(max_v[i], v.co[i])
                
        if (max_v.x - min_v.x > tile_size_x + 0.001) or \
           (max_v.y - min_v.y > tile_size_x + 0.001) or \
           (max_v.z - min_v.z > tile_size_y + 0.001):
            stats['faces_larger_than_tile'] += 1
            stats['warnings'].append(f"Face {face.index} exceeds tile_size! Size: ({max_v.x-min_v.x:.2f}, {max_v.y-min_v.y:.2f}, {max_v.z-min_v.z:.2f})")

        b_min, b_max = bounds_map.get(ftype, main_b)
        
        has_uv = False
        for loop in face.loops:
            co = loop.vert.co
            u_coord, v_coord = 0.0, 0.0
            
            nx, ny, nz = abs(face.normal.x), abs(face.normal.y), abs(face.normal.z)
            
            if ftype == 0: # Front
                u_coord, v_coord = co.x, co.z
            elif ftype == 1: # Back
                u_coord, v_coord = -co.x, co.z
            else: # Side/Reveal
                if nz >= nx and nz >= ny:
                    u_coord, v_coord = co.x, co.y
                elif nx >= ny and nx >= nz:
                    u_coord, v_coord = co.y if face.normal.x > 0 else -co.y, co.z
                else:
                    u_coord, v_coord = co.x if face.normal.y > 0 else -co.x, co.z
                    
            u_frac = (u_coord % tile_size_x) / tile_size_x
            v_frac = (v_coord % tile_size_y) / tile_size_y
            
            if u_frac < 0.001 and abs(u_coord) > 0.001: u_frac = 1.0
            if v_frac < 0.001 and abs(v_coord) > 0.001: v_frac = 1.0
            
            final_u = b_min[0] + u_frac * (b_max[0] - b_min[0])
            final_v = b_min[1] + v_frac * (b_max[1] - b_min[1])
            
            loop[uv_layer].uv = (final_u, final_v)
            has_uv = True
            
        if not has_uv:
            stats['faces_without_uv'] += 1
            
    return stats

def slice_and_uv_wall(obj, settings):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    
    faces_before = len(bm.faces)
    
    slice_mesh_with_grid(bm, settings.tile_size)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    
    # Convert 'UVMap' GN attribute to real UV layer or create it
    uv_layer = bm.loops.layers.uv.get("UVMap")
    if not uv_layer:
        uv_layer = bm.loops.layers.uv.new("UVMap")
        
    stats = apply_uvs_to_faces(bm, settings, uv_layer)
    
    stats['faces_before'] = faces_before
    stats['faces_after'] = len(bm.faces)
    stats['has_uvmap'] = True
    
    # Check topology
    stats['triangles'] = sum(1 for f in bm.faces if len(f.verts) == 3)
    stats['ngons'] = sum(1 for f in bm.faces if len(f.verts) > 4)
    
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    
    return stats
