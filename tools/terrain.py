"""Province terrain, coastal flags and the art bitmaps (terrain, rivers, trees, normals, colormaps).

Index values follow vanilla common/terrain/00_terrain.txt and the vanilla
rivers.bmp palette, so the mod keeps the vanilla terrain definitions.
"""
import json
import math
import struct
from functools import cache

import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import shape

from tools import geo, provinces, raster
from tools.geo import HEIGHT, SRC, WIDTH

# terrain.bmp indices (vanilla 00_terrain.txt)
T_PLAINS, T_FOREST, T_MARSH, T_MOUNTAIN, T_URBAN, T_LAKES, T_OCEAN, T_SNOW, T_HILLS = 0, 1, 9, 6, 13, 14, 15, 16, 17

TERRAIN_INDEX = {"plains": T_PLAINS, "forest": T_FOREST, "hills": T_HILLS, "mountain": T_MOUNTAIN,
                 "marsh": T_MARSH, "urban": T_URBAN, "lakes": T_LAKES, "ocean": T_OCEAN}

# rivers.bmp palette indices (vanilla)
R_SOURCE, R_FLOW_IN, R_FLOW_OUT = 0, 1, 2
R_WIDTHS = range(3, 12)
R_WATER, R_LAND = 254, 255
RIVER_PALETTE = [(0, 255, 0), (255, 0, 0), (255, 252, 0), (0, 225, 255), (0, 200, 255), (0, 150, 255),
                 (0, 100, 255), (0, 0, 255), (0, 0, 225), (0, 0, 200), (0, 0, 150), (0, 0, 100)]

# trees.bmp: vanilla scales trees.bmp to 1650/5632 of the map; indices in TREE_INDICES count as trees.
TREES_SCALE = 1650 / 5632
TREE_CONIFER = 3
TREE_INDICES = (3, 4, 7, 10)

# Graphical colour for terrain.bmp palette (editor display only) and colormap.
TERRAIN_RGB = {T_PLAINS: (134, 151, 89), T_FOREST: (52, 83, 45), T_MARSH: (98, 110, 70), T_MOUNTAIN: (128, 120, 108),
               T_URBAN: (120, 120, 120), T_LAKES: (58, 91, 255), T_OCEAN: (40, 83, 176), T_SNOW: (235, 238, 240),
               T_HILLS: (118, 128, 82)}


def treeline_m(lat: np.ndarray) -> np.ndarray:
    """Approximate Norwegian tree line, falling from ~1100 m at 60°N to ~400 m at 70°N."""
    return 1100 - 70 * (np.asarray(lat) - 60)


@cache
def _lat_grid() -> np.ndarray:
    ys = (np.arange(HEIGHT) + 0.5)
    lon, lat = geo.px_to_lonlat(np.full(HEIGHT, WIDTH / 2), ys)
    return np.asarray(lat, np.float32)


def classify_land(mean_h, relief, lat, lon, coastal, urban) -> str:
    if urban:
        return "urban"
    tl = float(treeline_m(lat))
    if mean_h > tl + 150 or relief > 300:
        return "mountain"
    if mean_h > tl - 100 or relief > 150:
        return "hills"
    if lat > 68.8 and lon > 21 and relief < 60 and not coastal:
        return "marsh"
    if mean_h < 220 and relief < 45:
        return "plains"
    if coastal and lon < 7.5 and relief < 90:
        return "plains"
    return "forest"


def _neighbour_pairs(ids: np.ndarray) -> np.ndarray:
    """Unique (a, b) pairs of 4-adjacent different province IDs, a < b."""
    pairs = []
    for a, b in ((ids[:-1], ids[1:]), (ids[:, :-1], ids[:, 1:])):
        m = a != b
        pairs.append(np.stack([a[m], b[m]], 1))
    p = np.concatenate(pairs)
    p.sort(1)
    return np.unique(p, axis=0)


@cache
def adjacency() -> dict[int, set[int]]:
    out: dict[int, set[int]] = {}
    for a, b in _neighbour_pairs(provinces.provinces().ids).tolist():
        out.setdefault(a, set()).add(b)
        out.setdefault(b, set()).add(a)
    return out


@cache
def urban_states() -> set[str]:
    dens = provinces._state_density()
    return {k for k, d in dens.items() if d >= provinces.CITY_DENSITY}


@cache
def annotate() -> provinces.ProvinceMap:
    """Set terrain and coastal on every province (in place) and return the map."""
    pm = provinces.provinces()
    ids = pm.ids
    elev = raster.elevation_m()
    n = max(pm.info) + 1
    idx = np.arange(n)
    mean_h = ndimage.mean(elev, ids, idx)
    relief = ndimage.standard_deviation(elev, ids, idx)
    adj = adjacency()
    urban = urban_states()
    for p in pm.info.values():
        if p.kind == "sea":
            p.terrain, p.coastal = "ocean", False
            continue
        if p.kind == "lake":
            p.terrain, p.coastal = "lakes", False
            continue
        p.coastal = any(pm.info[q].kind == "sea" for q in adj.get(p.id, ()))
        lon, lat = geo.px_to_lonlat(*p.centroid)
        p.terrain = classify_land(float(mean_h[p.id]), float(relief[p.id]), lat, lon, p.coastal,
                                  p.region in urban)
    # Sea provinces touching land are coastal waters (HOI4 marks them coastal too).
    for p in pm.info.values():
        if p.kind == "sea":
            p.coastal = any(pm.info[q].kind == "land" for q in adj.get(p.id, ()))
    return pm


@cache
def terrain_bitmap() -> np.ndarray:
    pm = annotate()
    lut = np.zeros(max(pm.info) + 1, np.uint8)
    for p in pm.info.values():
        lut[p.id] = TERRAIN_INDEX[p.terrain]
    prov = lut[pm.ids]
    elev = ndimage.uniform_filter(raster.elevation_m(), 5)
    tl = treeline_m(_lat_grid())[:, None]
    land = raster.land_mask()
    # Graphical terrain follows elevation pixel by pixel; urban, marsh and water follow the province.
    t = np.where(prov == T_PLAINS, T_PLAINS, T_FOREST).astype(np.uint8)
    t[elev > tl - 150] = T_HILLS
    t[elev > tl + 150] = T_MOUNTAIN
    t[elev > tl + 700] = T_SNOW
    keep = np.isin(prov, (T_URBAN, T_MARSH)) | ~land
    t[keep] = prov[keep]
    return t


def _palette(colours: dict[int, tuple]) -> list[int]:
    pal = [0] * 768
    for i, c in colours.items():
        pal[3 * i:3 * i + 3] = c
    return pal


def write_terrain_bmp(path) -> None:
    im = Image.fromarray(terrain_bitmap(), "P")
    im.putpalette(_palette(TERRAIN_RGB))
    im.save(path)


# --- rivers ------------------------------------------------------------------

def _line_4(x0, y0, x1, y1):
    """4-connected pixel line: a Bresenham line with a corner pixel added at every diagonal step."""
    pts = [(x0, y0)]
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    err = dx + dy
    x, y = x0, y0
    while (x, y) != (x1, y1):
        e2 = 2 * err
        moved_x = False
        if e2 >= dy:
            err += dy
            x += sx
            moved_x = True
        if e2 <= dx:
            err += dx
            if moved_x:
                pts.append((x, y))
            y += sy
        pts.append((x, y))
    return pts


def _river_lines():
    from shapely.geometry import box
    bounds = box(*geo.map_bounds_lonlat())
    feats = []
    for name in ("ne_10m_rivers_lake_centerlines.geojson", "ne_10m_rivers_europe.geojson"):
        with open(SRC / name, encoding="utf-8") as f:
            for ft in json.load(f)["features"]:
                if ft["properties"].get("featurecla", "").startswith("Lake"):
                    continue
                g = shape(ft["geometry"])
                if not g.intersects(bounds):
                    continue
                g = g.intersection(bounds)
                if g.is_empty or g.geom_type not in ("LineString", "MultiLineString"):
                    continue
                rank = ft["properties"].get("scalerank") or 10
                parts = [g] if g.geom_type == "LineString" else list(g.geoms)
                for part in parts:
                    feats.append((rank, part))
    feats.sort(key=lambda t: t[0])
    return feats


def _width_for(rank) -> int:
    return int(np.clip(12 - rank, 3, 8))


@cache
def river_bitmap() -> np.ndarray:
    land = raster.land_mask()
    playable = raster.state_raster() <= len(geo.load_states())
    elev = raster.elevation_m()
    out = np.full(land.shape, R_LAND, np.uint8)
    out[~land] = R_WATER
    river = np.zeros(land.shape, bool)
    for rank, line in _river_lines():
        coords = np.asarray(line.coords)
        xs, ys = geo.lonlat_to_px(coords[:, 0], coords[:, 1])
        px = []
        for i in range(len(xs) - 1):
            seg = _line_4(int(xs[i]), int(ys[i]), int(xs[i + 1]), int(ys[i + 1]))
            px.extend(seg if not px else seg[1:])
        # Keep only on-map land pixels in the playable area; take the longest run.
        runs, cur = [], []
        for x, y in px:
            if 1 <= x < WIDTH - 1 and 1 <= y < HEIGHT - 1 and land[y, x] and playable[y, x]:
                cur.append((x, y))
            else:
                if cur:
                    runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        for run in runs:
            if len(run) < 12:
                continue
            # Flow downhill: start at the higher end.
            if elev[run[0][1], run[0][0]] < elev[run[-1][1], run[-1][0]]:
                run = run[::-1]
            _draw_river(out, river, land, run, _width_for(rank))
    return out


def _touches(mask, x, y):
    return mask[y - 1, x] or mask[y + 1, x] or mask[y, x - 1] or mask[y, x + 1]


def _forms_block(river, drawn, x, y) -> bool:
    """Would (x, y) complete a 2x2 square of river pixels?"""
    own = set(drawn[-2:])

    def on(px, py):
        return river[py, px] or (px, py) in own

    for dx in (-1, 0):
        for dy in (-1, 0):
            sq = [(x + dx + i, y + dy + j) for i in (0, 1) for j in (0, 1)]
            if all((px, py) == (x, y) or on(px, py) for px, py in sq):
                return True
    return False


def _draw_river(out, river, land, run, width):
    """Draw one river from source to mouth; stop with a flow-in pixel where it meets an earlier river."""
    drawn, joined = [], False
    index: dict[tuple[int, int], int] = {}
    for x, y in run:
        if river[y, x]:
            break
        touching = _touches(river, x, y)
        if not drawn and touching:
            continue  # don't start a source right next to another river
        if (x, y) in index:
            del drawn[index[(x, y)] + 1:]
            index = {p: i for i, p in enumerate(drawn)}
            continue
        # Shortcut loops: if this pixel touches an earlier pixel of the same river, cut back to it.
        earlier = [index[q] for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)) if q in index]
        if earlier and min(earlier) < len(drawn) - 1:
            del drawn[min(earlier) + 1:]
            index = {p: i for i, p in enumerate(drawn)}
        if touching and _forms_block(river, drawn, x, y):
            break
        drawn.append((x, y))
        index[(x, y)] = len(drawn) - 1
        if touching:
            joined = True
            break
    if len(drawn) < 8:
        return
    for x, y in drawn:
        out[y, x] = width
        river[y, x] = True
    out[drawn[0][1], drawn[0][0]] = R_SOURCE
    if joined:
        out[drawn[-1][1], drawn[-1][0]] = R_FLOW_IN


def write_rivers_bmp(path) -> None:
    im = Image.fromarray(river_bitmap(), "P")
    pal = [255] * 768
    for i, c in enumerate(RIVER_PALETTE):
        pal[3 * i:3 * i + 3] = c
    pal[3 * R_WATER:3 * R_WATER + 3] = (122, 122, 122)
    im.putpalette(pal)
    im.save(path)


# --- trees, normals, colormaps ----------------------------------------------

def trees_size() -> tuple[int, int]:
    return round(WIDTH * TREES_SCALE), round(HEIGHT * TREES_SCALE)


@cache
def tree_bitmap() -> np.ndarray:
    w, h = trees_size()
    forest = (terrain_bitmap() == T_FOREST).astype(np.float32)
    small = np.asarray(Image.fromarray(forest * 255).convert("L").resize((w, h), Image.BILINEAR)) > 100
    # Thin the canopy into scattered clumps so trees don't render as a solid carpet.
    rng = np.random.default_rng(2030)
    keep = rng.random(small.shape) < 0.55
    return np.where(small & keep, TREE_CONIFER, 0).astype(np.uint8)


def write_trees_bmp(path) -> None:
    im = Image.fromarray(tree_bitmap(), "P")
    pal = [0] * 768
    for i in TREE_INDICES:
        pal[3 * i:3 * i + 3] = (30, 90, 40)
    im.putpalette(pal)
    im.save(path)


def normal_map() -> np.ndarray:
    hm = raster.heightmap().astype(np.float32)
    small = np.asarray(Image.fromarray(hm).resize((WIDTH // 2, HEIGHT // 2), Image.BILINEAR), np.float32)
    gy, gx = np.gradient(small)
    strength = 2.0
    nx, nz = -gx * strength, -gy * strength
    ny = np.ones_like(nx)
    length = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    rgb = np.stack([nx / length, ny / length, nz / length], -1) * 127.5 + 127.5
    return np.clip(rgb, 0, 255).astype(np.uint8)


def write_normal_map(path) -> None:
    Image.fromarray(normal_map(), "RGB").save(path)


def _write_dds_rgba(path, rgba: np.ndarray) -> None:
    """Uncompressed 32-bit A8R8G8B8 DDS, no mipmaps."""
    h, w, _ = rgba.shape
    flags = 0x1 | 0x2 | 0x4 | 0x8 | 0x1000  # caps, height, width, pitch, pixelformat
    header = b"DDS " + struct.pack("<7I", 124, flags, h, w, w * 4, 0, 0) + b"\0" * 44
    header += struct.pack("<2I4s5I", 32, 0x41, b"\0\0\0\0", 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    header += struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    assert len(header) == 128
    with open(path, "wb") as f:
        f.write(header)
        f.write(np.ascontiguousarray(rgba[..., [2, 1, 0, 3]]).tobytes())


def colormap() -> np.ndarray:
    """Half-size RGBA land colormap; alpha marks city lights in urban provinces."""
    t = terrain_bitmap()
    lut = np.zeros((256, 3), np.uint8)
    for i, c in TERRAIN_RGB.items():
        lut[i] = c
    rgb = lut[t].astype(np.float32)
    hm = raster.heightmap().astype(np.float32)
    shade = 0.85 + 0.3 * ((hm - 95).clip(0) / 160)
    rgb *= shade[..., None]
    alpha = np.where(t == T_URBAN, 255, 0).astype(np.float32)
    img = np.dstack([rgb.clip(0, 255), alpha]).astype(np.uint8)
    return np.asarray(Image.fromarray(img, "RGBA").resize((WIDTH // 2, HEIGHT // 2), Image.BILINEAR))


def water_colormap() -> np.ndarray:
    hm = raster.heightmap().astype(np.float32)
    depth = ((raster.SEA_LEVEL - hm).clip(0, 31) / 31)[..., None]
    shallow, deep = np.array([60, 120, 150], np.float32), np.array([12, 40, 70], np.float32)
    rgb = shallow * (1 - depth) + deep * depth
    img = np.dstack([rgb, np.full(hm.shape, 255, np.float32)]).astype(np.uint8)
    return np.asarray(Image.fromarray(img, "RGBA").resize((WIDTH // 2, HEIGHT // 2), Image.BILINEAR))


def write_colormaps(terrain_dir) -> None:
    terrain_dir.mkdir(parents=True, exist_ok=True)
    _write_dds_rgba(terrain_dir / "colormap_rgb_cityemissivemask_a.dds", colormap())
    water = water_colormap()
    for i in range(3):  # vanilla ships three sizes: _0 full, _1 half, _2 quarter
        h, w = water.shape[0] >> i, water.shape[1] >> i
        _write_dds_rgba(terrain_dir / f"colormap_water_{i}.dds",
                        np.asarray(Image.fromarray(water, "RGBA").resize((w, h), Image.BILINEAR)))
