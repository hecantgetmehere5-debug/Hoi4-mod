"""Cut the map into provinces with IDs that stay stable across re-runs.

Every province grows from a seed pixel. Seeds are kept in
data/registry/provinces.json; a re-run keeps every seed that still lies in its
region, samples new seeds only where needed, and reuses retired IDs so the IDs
stay a gapless 1..N sequence (HOI4 requires that).
"""
import json
import zlib
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from tools import geo, raster
from tools.geo import DATA

REGISTRY = DATA / "registry" / "provinces.json"
SEA = "sea"
MIN_PROVINCE_PX = 30
MAX_BOX_PX = 120  # vanilla's widest province is 280 px; the game rejects provinces with too large a box

# Seed spacing in pixels (400 m each).
SPACING_CITY = 16
SPACING_COASTAL = 38
SPACING_INLAND = 52
SPACING_SWEDEN = 64
SPACING_WASTELAND = 90
SPACING_SEA_NEAR = 50
SPACING_SEA_FAR = 90
SEA_NEAR_PX = 40
CITY_DENSITY = 250  # people per km² for city spacing


@dataclass
class Province:
    id: int
    rgb: tuple[int, int, int]
    kind: str  # "land" | "sea" | "lake"
    region: str  # state key, "sea" or "lake"
    seed: tuple[int, int]
    size: int = 0
    centroid: tuple[float, float] = (0.0, 0.0)
    coastal: bool = False
    terrain: str = "unknown"

    @property
    def state_key(self):
        return self.region if self.kind == "land" else None


@dataclass
class ProvinceMap:
    ids: np.ndarray  # uint32 province id per pixel
    info: dict[int, Province] = field(default_factory=dict)


def _rng(key: str) -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(key.encode()))


def _spacing(key: str, owner: str, coastal: bool, density: float, wasteland: bool) -> int:
    if wasteland:
        return SPACING_WASTELAND
    if density >= CITY_DENSITY:
        return SPACING_CITY
    if owner == "SWE":
        return SPACING_SWEDEN
    return SPACING_COASTAL if coastal else SPACING_INLAND


def _sample(mask: np.ndarray, spacing, key: str, fixed: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Deterministic dart throwing. spacing is an int or a per-pixel array."""
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return list(fixed)
    step = max(2, int(np.min(spacing) if not np.isscalar(spacing) else spacing) // 3)
    pick = (ys % step == 0) & (xs % step == 0)
    cy, cx = ys[pick], xs[pick]
    order = _rng(key).permutation(len(cy))
    cell = int(np.max(spacing)) if not np.isscalar(spacing) else spacing
    grid: dict[tuple[int, int], list[tuple[int, int]]] = {}
    accepted = []

    def add(y, x):
        accepted.append((y, x))
        grid.setdefault((y // cell, x // cell), []).append((y, x))

    for y, x in fixed:
        add(y, x)
    for i in order:
        y, x = int(cy[i]), int(cx[i])
        r = spacing if np.isscalar(spacing) else int(spacing[y, x])
        gy, gx = y // cell, x // cell
        ok = True
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for py, px in grid.get((gy + dy, gx + dx), ()):
                    if (py - y) ** 2 + (px - x) ** 2 < r * r:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            add(y, x)
    return accepted


def _ensure_component_seeds(mask, seeds, key):
    """Every connected piece of a region gets at least one seed."""
    labels, n = ndimage.label(mask)
    have = {labels[y, x] for y, x in seeds}
    out = list(seeds)
    for lab in range(1, n + 1):
        if lab not in have:
            ys, xs = np.nonzero(labels == lab)
            mid = len(ys) // 2
            out.append((int(ys[mid]), int(xs[mid])))
    return out


def _voronoi(code: np.ndarray, seeds) -> np.ndarray:
    lab = np.zeros(code.shape, np.uint32)
    by_code: dict[int, list[int]] = {}
    for i, (_, _, _, c) in enumerate(seeds):
        by_code.setdefault(c, []).append(i)
    flat = code.ravel()
    order = np.argsort(flat, kind="stable")
    sorted_codes = flat[order]
    for c, idx in by_code.items():
        lo, hi = np.searchsorted(sorted_codes, [c, c + 1])
        pix = order[lo:hi]
        pts = np.array([seeds[i][2] for i in idx])
        if len(idx) == 1:
            lab.ravel()[pix] = idx[0] + 1
            continue
        _, nearest = cKDTree(pts).query(np.column_stack(np.unravel_index(pix, code.shape)))
        lab.ravel()[pix] = np.array(idx)[nearest] + 1
    # Keep only the piece of each province that holds its seed; regrow the rest.
    seed_piece = {}
    for i, (_, _, (y, x), _) in enumerate(seeds):
        seed_piece[i + 1] = y, x
    out = np.zeros_like(lab)
    objs = ndimage.find_objects(lab)
    for l, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        sub = lab[sl] == l
        comp, n = ndimage.label(sub)
        y, x = seed_piece[l]
        cid = comp[y - sl[0].start, x - sl[1].start]
        out[sl][comp == cid] = l
    return _grow_into(code, out)


def _grow_into(region, lab):
    todo = (region > 0) & (lab == 0)
    while todo.any():
        best = np.zeros_like(lab)
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            nl = np.roll(lab, shift, axis)
            nr = np.roll(region, shift, axis)
            ok = todo & (nr == region) & (nl > 0)
            edge = [slice(None), slice(None)]
            edge[axis] = 0 if shift == 1 else -1
            ok[tuple(edge)] = False
            best = np.where(ok & (nl > best), nl, best)
        grew = best > 0
        if not grew.any():
            break
        lab[grew] = best[grew]
        todo &= ~grew
    return lab


def _regions():
    """region code per pixel, and code -> (key, kind, owner, wasteland)."""
    states = raster.state_raster().astype(np.int32)
    lakes = raster.lake_mask()
    keys = raster.all_state_keys()
    n_play = len(geo.load_states())
    code = states.copy()
    meta = {}
    owners = {s.key: geo.state_owner(s) for s in geo.load_states()}
    waste_owner = {k: o for k, o, _ in raster.wasteland()}
    for i, k in enumerate(keys):
        meta[i + 1] = (k, "land", owners.get(k) or waste_owner[k], i >= n_play)
    sea_code = len(keys) + 1
    sea = (states == 0) & ~lakes
    # Water cut off from the open ocean (inner fjord basins) is a lake in HOI4, not sea.
    sea_lab, _ = ndimage.label(sea)
    ocean = {int(np.bincount(sea_lab[sea_lab > 0]).argmax())}
    # Water that leaves the map (the Baltic past the bottom edge) is open sea too.
    ocean |= set(np.unique(np.concatenate([sea_lab[0], sea_lab[-1], sea_lab[:, 0], sea_lab[:, -1]])).tolist())
    enclosed = sea & ~np.isin(sea_lab, sorted(ocean - {0}))
    lakes = lakes | enclosed
    code[sea & ~enclosed] = sea_code
    meta[sea_code] = (SEA, "sea", None, False)
    lake_lab, n_lakes = ndimage.label(lakes)
    for j in range(1, n_lakes + 1):
        c = sea_code + j
        code[lake_lab == j] = c
        meta[c] = (f"lake", "lake", None, False)
    return code, meta


def _state_density() -> dict[str, float]:
    pop = geo.load_population()
    states = raster.state_raster()
    counts = np.bincount(states.ravel(), minlength=len(raster.all_state_keys()) + 1)
    out = {}
    for i, s in enumerate(geo.load_states()):
        km2 = counts[i + 1] * (geo.PIXEL_M / 1000) ** 2
        out[s.key] = sum(pop[k] for k in s.kommuner) / max(km2, 1)
    return out


def load_registry() -> list[dict]:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text())["provinces"]
    return []


def save_registry(provs: list[Province], path: Path = REGISTRY) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"id": p.id, "region": p.region, "kind": p.kind, "seed": list(p.seed), "rgb": list(p.rgb)}
            for p in sorted(provs, key=lambda p: p.id)]
    path.write_text(json.dumps({"provinces": rows}, ensure_ascii=False, indent=0))


def _colour_for(pid: int, used: set) -> tuple[int, int, int]:
    h = zlib.crc32(f"province-{pid}".encode())
    while True:
        rgb = ((h >> 16) & 255, (h >> 8) & 255, h & 255)
        if rgb != (0, 0, 0) and rgb not in used:
            return rgb
        h = zlib.crc32(h.to_bytes(4, "little"))


def build_provinces(registry: list[dict] | None = None) -> ProvinceMap:
    code, meta = _regions()
    registry = load_registry() if registry is None else registry
    land = code <= len(raster.all_state_keys())
    sea = code == len(raster.all_state_keys()) + 1
    dist_land = ndimage.distance_transform_edt(~land)
    coast = ndimage.binary_dilation(land) & ~land
    near_coast = ndimage.binary_dilation(coast, iterations=1)
    density = _state_density()

    old_by_region: dict[str, list[dict]] = {}
    for row in registry:
        old_by_region.setdefault(row["region"], []).append(row)

    seeds: list[tuple[str, str, tuple[int, int], int]] = []  # (region, kind, seed, code)
    # Land states and wasteland.
    for c, (key, kind, owner, waste) in meta.items():
        if kind != "land":
            continue
        mask = code == c
        old = [tuple(r["seed"]) for r in old_by_region.get(key, []) if mask[r["seed"][0], r["seed"][1]]]
        is_coastal = bool((mask & near_coast).any())
        sp = _spacing(key, owner, is_coastal, density.get(key, 0), waste)
        pts = _ensure_component_seeds(mask, _sample(mask, sp, key, old), key)
        seeds += [(key, "land", p, c) for p in pts]
    # Sea: smaller provinces near the coast.
    sea_c = len(raster.all_state_keys()) + 1
    sp = np.where(dist_land < SEA_NEAR_PX, SPACING_SEA_NEAR, SPACING_SEA_FAR)
    old = [tuple(r["seed"]) for r in old_by_region.get(SEA, []) if sea[r["seed"][0], r["seed"][1]]]
    pts = _ensure_component_seeds(sea, _sample(sea, sp, SEA, old), SEA)
    seeds += [(SEA, "sea", p, sea_c) for p in pts]
    # Lakes: one province per lake, seeded where the old seed was if still a lake.
    old_lakes = [tuple(r["seed"]) for r in old_by_region.get("lake", [])]
    for c, (key, kind, _, _) in meta.items():
        if kind != "lake":
            continue
        mask = code == c
        keep = [s for s in old_lakes if mask[s]]
        if keep:
            seeds.append(("lake", "lake", keep[0], c))
        else:
            ys, xs = np.nonzero(mask)
            seeds.append(("lake", "lake", (int(ys[len(ys) // 2]), int(xs[len(xs) // 2])), c))

    # Nearest seed of the same region, then repair any piece cut off from its seed.
    tmp = _voronoi(code, seeds)
    tmp = _merge_small(tmp, code)
    for _ in range(6):
        extra = _split_seeds(tmp, seeds)
        if not extra:
            break
        seeds = seeds + extra
        tmp = _merge_small(_voronoi(code, seeds), code)
    tmp = _remove_x_crossings(tmp, code)
    alive = np.unique(tmp)
    alive = alive[alive > 0]
    seeds = [seeds[i - 1] for i in alive]
    remap = np.zeros(int(tmp.max()) + 1, np.uint32)
    remap[alive] = np.arange(1, len(alive) + 1)
    tmp = remap[tmp]

    ids_for = _assign_ids(seeds, registry)
    lut = np.zeros(len(seeds) + 1, np.uint32)
    lut[1:] = ids_for
    ids = lut[tmp]

    old_rgb = {r["id"]: tuple(r["rgb"]) for r in registry}
    old_key = {(r["region"], tuple(r["seed"])): r["id"] for r in registry}
    used = set()
    info = {}
    sizes = np.bincount(ids.ravel(), minlength=len(seeds) + 1)
    cy = ndimage.mean(np.indices(ids.shape)[0], ids, index=np.arange(len(seeds) + 1))
    cx = ndimage.mean(np.indices(ids.shape)[1], ids, index=np.arange(len(seeds) + 1))
    for (region, kind, seed, _), pid in zip(seeds, ids_for):
        pid = int(pid)
        same = old_key.get((region, seed)) == pid
        rgb = old_rgb[pid] if same and old_rgb.get(pid) not in used else None
        if rgb is None:
            rgb = old_rgb.get(pid) if pid in old_rgb and old_rgb[pid] not in used else _colour_for(pid, used)
        used.add(rgb)
        info[pid] = Province(pid, rgb, kind, region, seed, int(sizes[pid]), (float(cx[pid]), float(cy[pid])))
    return ProvinceMap(ids, info)


def _split_seeds(lab: np.ndarray, seeds) -> list:
    """An extra seed, far from the existing one, for every province whose box is wider than MAX_BOX_PX."""
    extra = []
    for l, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        if max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) <= MAX_BOX_PX:
            continue
        region, kind, (sy, sx), c = seeds[l - 1]
        ys, xs = np.nonzero(lab[sl] == l)
        ys, xs = ys + sl[0].start, xs + sl[1].start
        i = int(np.argmax((ys - sy) ** 2 + (xs - sx) ** 2))
        extra.append((region, kind, (int(ys[i]), int(xs[i])), c))
    return extra


def _x_crossings(lab: np.ndarray) -> np.ndarray:
    """(y, x) of every 2x2 block where four different provinces meet; x wraps across the map edge."""
    wrapped = np.concatenate([lab, lab[:, :1]], axis=1)
    tl, tr, bl, br = wrapped[:-1, :-1], wrapped[:-1, 1:], wrapped[1:, :-1], wrapped[1:, 1:]
    four = (tl != tr) & (tl != bl) & (tl != br) & (tr != bl) & (tr != br) & (bl != br)
    return np.argwhere(four)


def _remove_x_crossings(lab: np.ndarray, code: np.ndarray) -> np.ndarray:
    """HOI4 rejects points where four provinces meet ("Map invalid X crossing").

    Give one pixel of each such 2x2 block to a neighbour in the same region.
    """
    w = lab.shape[1]
    lab = lab.copy()
    for _ in range(4):
        spots = _x_crossings(lab)
        if not len(spots):
            break
        for y, x in spots:
            cells = [(y, x), (y, (x + 1) % w), (y + 1, x), (y + 1, (x + 1) % w)]
            done = False
            for cy, cx in cells:
                for ny, nx in cells:
                    if (ny, nx) != (cy, cx) and (ny == cy or nx == cx) and code[ny, nx] == code[cy, cx] \
                            and lab[ny, nx] != lab[cy, cx]:
                        lab[cy, cx] = lab[ny, nx]
                        done = True
                        break
                if done:
                    break
    return lab


def _merge_small(lab: np.ndarray, code: np.ndarray) -> np.ndarray:
    """Merge provinces under MIN_PROVINCE_PX into a touching province of the same region."""
    for _ in range(4):
        sizes = np.bincount(lab.ravel())
        small = set(np.nonzero((sizes > 0) & (sizes < MIN_PROVINCE_PX))[0]) - {0}
        if not small:
            break
        target = {}
        for axis in (0, 1):
            a = lab.take(range(0, lab.shape[axis] - 1), axis)
            b = lab.take(range(1, lab.shape[axis]), axis)
            ca = code.take(range(0, lab.shape[axis] - 1), axis)
            cb = code.take(range(1, lab.shape[axis]), axis)
            m = (a != b) & (ca == cb)
            for x, y in ((a[m], b[m]), (b[m], a[m])):
                for s_, t_ in zip(x.tolist(), y.tolist()):
                    if s_ in small and t_ not in small and s_ not in target:
                        target[s_] = t_
        if not target:
            break
        lut = np.arange(len(sizes), dtype=lab.dtype)
        for s_, t_ in target.items():
            lut[s_] = t_
        lab = lut[lab]
    return lab


def _assign_ids(seeds, registry) -> list[int]:
    """Keep registry IDs for surviving seeds, fill retired IDs first, then append."""
    old = {(r["region"], tuple(r["seed"])): r["id"] for r in registry}
    out = [old.get((region, seed)) for region, _, seed, _ in seeds]
    taken = {i for i in out if i is not None}
    max_old = max((r["id"] for r in registry), default=0)
    free = sorted(set(range(1, max_old + 1)) - taken)
    nxt = max(max_old, len(seeds) and 0) + 1
    for i, v in enumerate(out):
        if v is None:
            if free:
                out[i] = free.pop(0)
            else:
                out[i] = nxt
                nxt += 1
    if free:
        # Fewer provinces than before: move the highest IDs into the gaps so IDs stay 1..N.
        order = sorted(range(len(out)), key=lambda i: -out[i])
        for i in order:
            if not free or out[i] < free[0]:
                break
            out[i] = free.pop(0)
    return out


@cache
def provinces() -> ProvinceMap:
    return build_provinces()
