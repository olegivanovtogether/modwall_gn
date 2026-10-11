"""UV geometry: priority layers, axis choice, flip rules, cell rotation, seams.
Pure functions, no scene objects."""

import bmesh
import math


_AXIS_ORDER = ('X', 'Y', 'Z')


def _resolve_priority_axes(s, prefix=""):
    """(layer1, layer2, layer3) axis names; the three are always distinct.
    `prefix` selects the settings set ("" Tile Grid, "uvw_" UVW Map)."""
    primary = getattr(s, prefix + "priority_axis")
    a1 = primary if primary in _AXIS_ORDER else 'Z'
    a2 = getattr(s, prefix + "secondary_axis")
    if a2 not in _AXIS_ORDER or a2 == a1:
        a2 = next(a for a in _AXIS_ORDER if a != a1)
    a3 = next(a for a in _AXIS_ORDER if a not in (a1, a2))
    return a1, a2, a3


_LAYER_ROLES = {
    1: ("Top-Bottom", "Top", "Bottom"),
    2: ("Front-Back", "Front", "Back"),
    3: ("Left-Right", "Left", "Right"),
}


_DEFAULT_FLIP_SIGN = {'X': '-', 'Y': '+', 'Z': '-'}   # side flipped before


def _flip_side_buttons(layer, axis):
    """[(enum value, text), (enum value, text)] for the Flip side buttons of a
    layer. The words belong to the layer role (1 top/bottom, 2 front/back,
    3 left/right); the sign and letter come from the layer's current axis."""
    _, plus_name, minus_name = _LAYER_ROLES[layer]
    default_is_minus = _DEFAULT_FLIP_SIGN[axis] == '-'
    minus = ('DEFAULT' if default_is_minus else 'OPPOSITE', f"{minus_name} (-{axis})")
    plus = ('OPPOSITE' if default_is_minus else 'DEFAULT', f"{plus_name} (+{axis})")
    return [minus, plus]


def _angle_range_tenths(a_from, a_to):
    """Slider degrees -> inclusive integer range in tenths of a degree.
    Blender stores the sliders as float32 (0.1 -> 0.10000000149), so compare
    in integers; clamp to 0..90 and swap if From > To."""
    lo = max(0, min(900, round(a_from * 10.0)))
    hi = max(0, min(900, round(a_to * 10.0)))
    return (lo, hi) if lo <= hi else (hi, lo)


def _uv_axes_for(major, fn, flip, ax_x, ax_y, ax_z, eps=0.0, opposite=False):
    """U/V projection axes for a face projected along box axis `major`.
    flip=True turns the face over (U mirrored) when its normal looks to the
    flipped side of the axis. Default side (what ordinary wall faces already
    did): X: -X, Y: +Y; Z had no rule, so it is -Z (down-facing).
    opposite=True flips the other side instead (X: +X, Y: -Y, Z: +Z)."""
    if major == 'Y':
        # box XZ plane -> U along ax_x, V along ax_z
        d = fn.dot(ax_y)
        hit = (d < -eps) if opposite else (d > eps)
        return (-ax_x if (flip and hit) else ax_x), ax_z
    if major == 'Z':
        # box XY plane -> U along ax_x, V along ax_y
        d = fn.dot(ax_z)
        hit = (d > eps) if opposite else (d < -eps)
        return (-ax_x if (flip and hit) else ax_x), ax_y
    # box YZ plane -> U along ax_y, V along ax_z
    d = fn.dot(ax_x)
    hit = (d > eps) if opposite else (d < -eps)
    return (-ax_y if (flip and hit) else ax_y), ax_z


def _swap_cell_scale(obj, vertical):
    """Swap width (X) and height (Z) of a controller / gizmo scale when the
    texture direction switches between horizontal and vertical.

    Y follows X when it did before (default controllers have Y == X) and is
    kept as an independent value otherwise. The decision is remembered on the
    object, so swapping back restores the original scale exactly; if the user
    edited Y in between, it is decided again from the current values.
    """
    sx, sy, sz = obj.scale
    last = obj.get("tc_y_last")
    follows = obj.get("tc_y_follows_x")
    if last is None or follows is None or abs(sy - last) > 1e-6:
        follows = abs(sy - sx) < 1e-6
    new_y = sz if follows else sy
    obj.scale = (sz, new_y, sx)
    obj["tc_y_follows_x"] = bool(follows)
    obj["tc_y_last"] = float(new_y)
    obj["tc_vertical"] = bool(vertical)


def _cell_uv_rotate(u, v, rot):
    """Rotate the texture inside a tile cell by rot degrees (0/90/180/270).
    (u, v) are cell coordinates 0..1; returns the sampled texture coords."""
    if rot == 90:
        return v, 1.0 - u
    if rot == 180:
        return 1.0 - u, 1.0 - v
    if rot == 270:
        return 1.0 - v, u
    return u, v


def _priority_layers(s, prefix=""):
    """Settings -> `layers` dict for _apply_tile_uvs / preview (None = legacy).
    `prefix` selects the settings set ("" Tile Grid, "uvw_" UVW Map)."""
    def get(name):
        return getattr(s, prefix + name)

    if not get("use_priority_axis"):
        return None
    return {
        'axes': _resolve_priority_axes(s, prefix),
        'range1': _angle_range_tenths(get("priority_angle_from"), get("priority_angle_to")),
        'range2': _angle_range_tenths(get("secondary_angle_from"), get("secondary_angle_to")),
        'use2': get("use_secondary_axis"),
        'use3': get("use_remainder_axis"),
        'flip1': get("priority_flip_back"),
        'flip2': get("secondary_flip_back"),
        'flip3': get("remainder_flip_back"),
        'opp1': get("priority_flip_side") == 'OPPOSITE',
        'opp2': get("secondary_flip_side") == 'OPPOSITE',
        'opp3': get("remainder_flip_side") == 'OPPOSITE',
    }


def _choose_axis_and_flip(fn, layers, ax_x, ax_y, ax_z):
    """(major, flip, eps, opposite) for a face normal `fn`."""
    axis_vec = {'X': ax_x, 'Y': ax_y, 'Z': ax_z}

    def angle_tenths(fn_unit, axis):
        cos_a = min(1.0, abs(fn_unit.dot(axis_vec[axis])))
        return round(math.degrees(math.acos(cos_a)) * 10.0)

    if layers is not None and fn.length > 1e-6:
        fn_u = fn.normalized()
        a1, a2, a3 = layers['axes']
        lo, hi = layers['range1']
        if lo <= angle_tenths(fn_u, a1) <= hi:
            return a1, layers['flip1'], 1e-4, layers['opp1']
        if layers['use2']:
            lo, hi = layers['range2']
            if lo <= angle_tenths(fn_u, a2) <= hi:
                return a2, layers['flip2'], 1e-4, layers['opp2']
            if layers['use3']:
                return a3, layers['flip3'], 1e-4, layers['opp3']

    # Legacy rule: which box face is this mesh face most parallel to?
    dot_x = abs(fn.dot(ax_x))
    dot_y = abs(fn.dot(ax_y))
    dot_z = abs(fn.dot(ax_z))
    if dot_y >= dot_x and dot_y >= dot_z:
        major = 'Y'
    elif dot_z >= dot_x:
        major = 'Z'
    else:
        major = 'X'
    return major, major != 'Z', 0.0, False   # legacy: X/Y flip, Z never


def _apply_tile_uvs(bm, b_min, b_max, tile_u, tile_v,
                    box_origin, ax_x, ax_y, ax_z,
                    layers=None, rotation=0):
    """rotation: texture direction inside the cell, 0/90/180/270 degrees.

    layers=None: legacy rule (axis with the largest normal component,
    ties Y > Z > X; X/Y faces flip as before, Z never flips).

    layers (dict) enables the priority layers:
      axes     (a1, a2, a3)  distinct axis names
      range1   (lo, hi)      tenths of a degree, inclusive, vs axis a1
      range2   (lo, hi)      same for axis a2
      use2     bool          layer 2 enabled; if False faces outside layer 1
                             use the legacy rule (layer 3 is skipped too)
      use3     bool          layer 3 enabled; if False faces outside layers
                             1 and 2 use the legacy rule
      flip1, flip2, flip3    bool, "Flip Back Faces" per layer
    Angle = angle between the face normal and the axis, sign ignored. Order:
    layer 1, then layer 2, then the remaining axis a3 (layer 3).
    """
    uv_layer = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    tile_u = max(tile_u, 0.001)
    tile_v = max(tile_v, 0.001)

    stats = {'quads': 0, 'triangles': 0, 'ngons': 0}
    bm.normal_update()

    for face in bm.faces:
        n = len(face.verts)
        if n == 3:   stats['triangles'] += 1
        elif n == 4: stats['quads'] += 1
        else:        stats['ngons'] += 1

        fn = face.normal
        major, flip, eps, opp = _choose_axis_and_flip(fn, layers, ax_x, ax_y, ax_z)

        ua, va = _uv_axes_for(major, fn, flip, ax_x, ax_y, ax_z, eps, opp)

        # Face center -> tile cell (keeps all verts of one face in same cell).
        # Projection Box origin is the center of the preview tile, so cell
        # boundaries live at half-tile offsets from the origin.
        c = face.calc_center_median() - box_origin
        cu = math.floor(c.dot(ua) / tile_u + 0.5)
        cv = math.floor(c.dot(va) / tile_v + 0.5)

        for loop in face.loops:
            p  = loop.vert.co - box_origin
            pu = p.dot(ua)
            pv = p.dot(va)
            uf = max(0.0, min(1.0, (pu - (cu - 0.5) * tile_u) / tile_u))
            vf = max(0.0, min(1.0, (pv - (cv - 0.5) * tile_v) / tile_v))
            uf, vf = _cell_uv_rotate(uf, vf, rotation)
            loop[uv_layer].uv = (b_min[0] + uf * (b_max[0] - b_min[0]),
                                 b_min[1] + vf * (b_max[1] - b_min[1]))

    return stats


def _process_seams(bm, uv_layer, angle_deg, dissolve_non_seamed_edges=False):
    corner_rad = math.radians(angle_deg)
    tol = 0.001
    to_dissolve = []

    for edge in bm.edges:
        if len(edge.link_faces) != 2:
            edge.seam = True
            continue
        if edge.calc_face_angle(0.0) > corner_rad:
            edge.seam = True
            continue

        f0, f1 = edge.link_faces
        f0_uv = {l.vert: l[uv_layer].uv for l in f0.loops}
        f1_uv = {l.vert: l[uv_layer].uv for l in f1.loops}

        uv_differs = False
        for v in edge.verts:
            if v in f0_uv and v in f1_uv:
                du = abs(f0_uv[v][0] - f1_uv[v][0])
                dv = abs(f0_uv[v][1] - f1_uv[v][1])
                if du > tol or dv > tol:
                    uv_differs = True
                    break

        if uv_differs:
            edge.seam = True
        else:
            edge.seam = False
            if dissolve_non_seamed_edges:
                to_dissolve.append(edge)

    if dissolve_non_seamed_edges and to_dissolve:
        bmesh.ops.dissolve_edges(bm, edges=to_dissolve,
                                 use_verts=True, use_face_split=False)
