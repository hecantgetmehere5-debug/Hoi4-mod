"""Write every file under mod/map: bitmaps, definitions, positions, regions, railways."""
import json
import math
import zlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np
import yaml
from PIL import Image
from scipy import ndimage
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra, minimum_spanning_tree
from scipy.spatial import cKDTree
from shapely.geometry import shape

from tools import geo, provinces, raster, terrain
from tools.geo import DATA, HEIGHT, SRC

STATE_REGISTRY = DATA / "registry" / "states.json"
SEA_REGION_SIZE = 50  # sea provinces per sea strategic region (roughly)

# Building position names and counts follow vanilla map/buildings.txt.
STATE_BUILDINGS = {  # building -> models per state
    "arms_factory": 6, "industrial_complex": 6, "air_base": 1, "anti_air_building": 3,
    "synthetic_refinery": 1, "fuel_silo": 1, "radar_station": 1, "rocket_site_spawn": 1,
    "nuclear_reactor_spawn": 1, "stronghold_network": 1, "special_project_facility_spawn": 3,
}
COASTAL_STATE_BUILDINGS = {"dockyard": 6}
PROVINCE_BUILDINGS = ("bunker", "supply_node")
COASTAL_PROVINCE_BUILDINGS = ("coastal_bunker", "naval_base_spawn", "floating_harbor",
                              "naval_headquarters", "naval_supply_hub")
SEA_LINKED_BUILDINGS = ("naval_base_spawn", "floating_harbor")
VANILLA_CONTINENTS = ("europe", "north_america", "south_america", "australia", "africa", "asia", "middle_east")
UNIT_STACK_TYPES = 39  # vanilla map/unitstacks.txt uses types 0-38


# --- state ids ---------------------------------------------------------------

def _load_state_registry() -> dict[str, int]:
    if STATE_REGISTRY.exists():
        return json.loads(STATE_REGISTRY.read_text())
    return {}


@cache
def state_ids() -> dict[str, int]:
    """Stable, gapless state IDs: existing keys keep their ID, retired IDs are reused first."""
    keys = raster.all_state_keys()
    old = _load_state_registry()
    out = {k: old[k] for k in keys if k in old}
    free = sorted(set(range(1, max(old.values(), default=0) + 1)) - set(out.values()))
    nxt = max(old.values(), default=0) + 1
    for k in keys:
        if k not in out:
            if free:
                out[k] = free.pop(0)
            else:
                out[k] = nxt
                nxt += 1
    if free:  # fewer states than before: move the highest IDs down into the gaps
        for k in sorted(out, key=lambda k: -out[k]):
            if not free or out[k] < free[0]:
                break
            out[k] = free.pop(0)
    return out


def save_state_registry(path: Path = STATE_REGISTRY) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ids = state_ids()
    path.write_text(json.dumps(dict(sorted(ids.items(), key=lambda kv: kv[1])), ensure_ascii=False, indent=1))


@cache
def state_provinces() -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for p in terrain.annotate().info.values():
        if p.kind == "land":
            out.setdefault(p.region, []).append(p.id)
    return {k: sorted(v) for k, v in out.items()}


@cache
def state_lakes() -> dict[str, list[int]]:
    """Lakes join the state most of their land neighbours belong to, as in vanilla."""
    info = terrain.annotate().info
    adj = terrain.adjacency()
    out: dict[str, list[int]] = {}
    for p in info.values():
        if p.kind != "lake":
            continue
        near = [info[q].region for q in adj.get(p.id, ()) if info[q].kind == "land"]
        if near:
            out.setdefault(max(sorted(set(near)), key=near.count), []).append(p.id)
    return {k: sorted(v) for k, v in out.items()}


def is_wasteland(key: str) -> bool:
    return key.startswith("waste_")


# --- pixel helpers -------------------------------------------------------------

@cache
def _slices():
    return ndimage.find_objects(provinces.provinces().ids)


def province_pixels(pid: int) -> tuple[np.ndarray, np.ndarray]:
    sl = _slices()[pid - 1]
    ys, xs = np.nonzero(provinces.provinces().ids[sl] == pid)
    return ys + sl[0].start, xs + sl[1].start


def world(x: float, y: float) -> tuple[float, float, float]:
    """Pixel position -> HOI4 world coordinates (x, height, z). Vanilla maps z to pixel row HEIGHT - 1 - z."""
    h = raster.heightmap()[int(min(max(y, 0), HEIGHT - 1)), int(x)] / 10
    return float(x), float(h), float(HEIGHT - 1 - y)


def _fmt(x, h, z):
    return f"{x:.2f};{h:.2f};{z:.2f}"


def interior_point(pid: int, key: str) -> tuple[int, int]:
    """A deterministic pixel of the province, preferring pixels far from its edge."""
    ys, xs = province_pixels(pid)
    sl = _slices()[pid - 1]
    sub = provinces.provinces().ids[sl] == pid
    if provinces.provinces().info[pid].kind == "land":
        # The game ignores building positions that are not over land, so stay above sea level.
        dry = sub & (raster.heightmap()[sl] > raster.SEA_LEVEL)
        sub = dry if dry.any() else sub
    d = ndimage.distance_transform_edt(np.pad(sub, 1))[1:-1, 1:-1]
    best = np.argwhere(sub & (d >= max(1.0, d.max() * 0.5)))
    rng = np.random.default_rng(zlib.crc32(key.encode()))
    y, x = best[rng.integers(len(best))]
    return int(x + sl[1].start), int(y + sl[0].start)


# --- victory points ----------------------------------------------------------

@cache
def _places() -> dict[str, tuple[float, float]]:
    with open(SRC / "ne_10m_populated_places_simple.geojson", encoding="utf-8") as f:
        feats = json.load(f)["features"]
    out = {}
    for ft in feats:
        pr = ft["properties"]
        if pr["adm0name"] in ("Norway", "Sweden"):
            lon, lat = ft["geometry"]["coordinates"]
            out[pr["name"]] = (lon, lat)
    return out


@cache
def victory_points() -> dict[str, int]:
    """state key -> province holding the state's victory point (also its capital)."""
    pm = provinces.provinces()
    sp = state_provinces()
    places = _places()
    geoms = raster.kommune_geoms()
    out = {}
    for s in geo.load_states():
        provs = sp[s.key]
        if s.vp in places:
            x, y = geo.lonlat_to_px(*places[s.vp])
        else:
            pt = geoms[s.kommuner[0]].representative_point()
            x, y = (pt.x - geo.ORIGIN_E) / geo.PIXEL_M, (geo.ORIGIN_N - pt.y) / geo.PIXEL_M
        xi, yi = int(np.clip(x, 0, geo.WIDTH - 1)), int(np.clip(y, 0, HEIGHT - 1))
        pid = int(pm.ids[yi, xi])
        if pid not in provs:
            pid = min(provs, key=lambda q: (pm.info[q].centroid[0] - x) ** 2 + (pm.info[q].centroid[1] - y) ** 2)
        out[s.key] = pid
    for key, _, _ in raster.wasteland():
        provs = sp[key]
        out[key] = max(provs, key=lambda q: pm.info[q].size)
    return out


# --- strategic regions ----------------------------------------------------------

@dataclass
class Region:
    id: int
    name: str
    weather: str
    provinces: list[int]


def _kmeans(points: np.ndarray, k: int, iters: int = 30) -> np.ndarray:
    centres = [points[0]]
    for _ in range(1, k):
        d = np.min([((points - c) ** 2).sum(1) for c in centres], axis=0)
        centres.append(points[int(np.argmax(d))])
    centres = np.array(centres, float)
    for _ in range(iters):
        lab = np.argmin(((points[:, None] - centres[None]) ** 2).sum(-1), 1)
        for j in range(k):
            if (lab == j).any():
                centres[j] = points[lab == j].mean(0)
    return lab


def _contiguous(members: list[int], lab: np.ndarray, adj) -> np.ndarray:
    """Give every detached piece of a cluster to the neighbouring cluster it touches most."""
    lab = lab.copy()
    index = {p: i for i, p in enumerate(members)}
    for _ in range(10):
        moved = False
        for j in sorted(set(lab.tolist())):
            nodes = [members[i] for i in np.nonzero(lab == j)[0]]
            node_set = set(nodes)
            pieces = _components(nodes, [(a, b) for a in nodes for b in adj.get(a, ()) if b in node_set])
            pieces.sort(key=len, reverse=True)
            for piece in pieces[1:]:
                near = [int(lab[index[q]]) for a in piece for q in adj.get(a, ()) if q in index and lab[index[q]] != j]
                if near:
                    target = max(sorted(set(near)), key=near.count)
                    for a in piece:
                        lab[index[a]] = target
                    moved = True
        if not moved:
            break
    return lab


@cache
def strategic_regions() -> list[Region]:
    pm = terrain.annotate()
    cfg = yaml.safe_load(open(DATA / "strategic_regions.yaml", encoding="utf-8"))
    sp = state_provinces()
    regions: list[Region] = []
    region_of: dict[int, int] = {}
    for rid, r in cfg.items():
        provs = [p for s in r["states"] for p in sp[s]]
        regions.append(Region(int(rid), r["name"], r["weather"], provs))
        for p in provs:
            region_of[p] = int(rid)
    nid = max(int(k) for k in cfg) + 1
    names = {"waste_fin": "Finland", "waste_sov": "Kola", "waste_den": "Jutland"}
    for key, _, _ in raster.wasteland():
        regions.append(Region(nid, names.get(key, "Sverige"), "land", sp[key]))
        for p in sp[key]:
            region_of[p] = nid
        nid += 1
    # Lakes go to the region of the state they belong to (a state must sit in one region),
    # or, for lakes in no state, to the region most of their land neighbours belong to.
    adj = terrain.adjacency()
    by_id = {r.id: r for r in regions}
    lake_state = {lake: key for key, lakes in state_lakes().items() for lake in lakes}
    for p in pm.info.values():
        if p.kind == "lake":
            if p.id in lake_state:
                rid = region_of[sp[lake_state[p.id]][0]]
            else:
                near = [region_of[q] for q in adj.get(p.id, ()) if q in region_of]
                rid = max(sorted(set(near)), key=near.count) if near else regions[0].id
            by_id[rid].provinces.append(p.id)
    # Sea regions from clustering sea province centroids.
    sea = sorted(p.id for p in pm.info.values() if p.kind == "sea")
    pts = np.array([pm.info[p].centroid for p in sea])
    k = max(1, math.ceil(len(sea) / SEA_REGION_SIZE))
    lab = _contiguous(sea, _kmeans(pts, k), adj)
    n_sea = 0
    for j in range(k):
        members = [sea[i] for i in np.nonzero(lab == j)[0]]
        member_set = set(members)
        # A cluster spanning two separate seas (North Sea and Baltic) becomes one region per piece.
        for piece in _components(members, [(a, b) for a in members for b in adj.get(a, ()) if b in member_set]):
            n_sea += 1
            regions.append(Region(nid, f"Sea {n_sea}", "sea", sorted(piece)))
            nid += 1
    return regions


def _weather(kind: str) -> str:
    text = (DATA / "weather" / f"{kind}.txt").read_text(encoding="utf-8")
    return "\n".join(l for l in text.splitlines() if not l.startswith("#"))


def write_strategic_regions(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for r in strategic_regions():
        ids = " ".join(map(str, sorted(r.provinces)))
        text = (f"strategic_region={{\n\tid={r.id}\n\tname=\"NWC_STRATEGICREGION_{r.id}\"\n"
                f"\tprovinces={{\n\t\t{ids} \n\t}}\n{_weather(r.weather)}\n}}\n")
        (folder / f"{r.id}-{r.name.replace(' ', '_')}.txt").write_text(text, encoding="utf-8")


# --- railways and supply -----------------------------------------------------------

@cache
def _land_graph():
    pm = terrain.annotate()
    land = sorted(p.id for p in pm.info.values() if p.kind == "land" and not is_wasteland(p.region))
    index = {p: i for i, p in enumerate(land)}
    rows, cols, w = [], [], []
    for a, ns in terrain.adjacency().items():
        if a not in index:
            continue
        for b in ns:
            if b in index:
                (ax, ay), (bx, by) = pm.info[a].centroid, pm.info[b].centroid
                rows.append(index[a])
                cols.append(index[b])
                w.append(math.hypot(ax - bx, ay - by) + 1)
    g = csr_matrix((w, (rows, cols)), shape=(len(land), len(land)))
    return land, index, g


def _state_pop() -> dict[str, int]:
    pop = geo.load_population()
    return {s.key: sum(pop[k] for k in s.kommuner) for s in geo.load_states()}


MAX_STRAIT_PX = 150  # 60 km: longest bridge, tunnel or ferry link we create


def _components(nodes, edges):
    parent = {n: n for n in nodes}

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for a, b in edges:
        parent[find(a)] = find(b)
    comps: dict[int, list[int]] = {}
    for n in nodes:
        comps.setdefault(find(n), []).append(n)
    return list(comps.values())


@cache
def _sea_index():
    pm = provinces.provinces()
    seas = [p.id for p in pm.info.values() if p.kind == "sea"]
    _, idx = ndimage.distance_transform_edt(~np.isin(pm.ids, seas), return_indices=True)
    return idx


def _nearest_sea(y: int, x: int) -> int:
    iy, ix = _sea_index()
    return int(provinces.provinces().ids[iy[y, x], ix[y, x]])


def _through_sea(a: int, b: int, y: int, x: int) -> int:
    """Water province a crossing passes through; it must touch both ends, as in vanilla."""
    info = terrain.annotate().info
    adj = terrain.adjacency()
    shared = adj.get(a, set()) & adj.get(b, set())
    both = sorted(q for q in shared if info[q].kind == "sea")
    if both:
        mid = _nearest_sea(y, x)
        return mid if mid in both else both[0]
    return -1  # no shared sea (e.g. across a lake): plain land link, as vanilla never crosses through lakes


@cache
def straits() -> list[tuple[int, int, int]]:
    """(from, to, through_sea) crossings that tie every island of the playable map to the mainland.

    Borůvka-style: each round, every land component links to its nearest other
    component (measured between shore pixels), until one component remains.
    """
    pm = terrain.annotate()
    adj = terrain.adjacency()
    ids = provinces.provinces().ids
    land = [p.id for p in pm.info.values() if p.kind == "land" and not is_wasteland(p.region)]
    land_set = set(land)
    edges = [(a, b) for a in land for b in adj.get(a, ()) if b in land_set and a < b]
    # Shore pixels of playable land.
    is_land = np.isin(ids, land)
    sea_near = ~is_land & ~np.isin(ids, [p.id for p in pm.info.values() if p.kind == "land"])
    shore = is_land & ndimage.binary_dilation(sea_near)
    ys, xs = np.nonzero(shore)
    prov = ids[ys, xs]
    tree = cKDTree(np.column_stack([ys, xs]))
    out = []
    while True:
        comps = _components(land, edges)
        if len(comps) == 1:
            break
        comp_of = {p: i for i, c in enumerate(comps) for p in c}
        comp = np.array([comp_of[p] for p in prov])
        best: dict[int, tuple] = {}
        for k in (16, 64, 256, 1024):
            todo = [c for c in range(len(comps)) if c not in best]
            if not todo:
                break
            sel = np.nonzero(np.isin(comp, todo))[0]
            d, nn = tree.query(np.column_stack([ys[sel], xs[sel]]), k=min(k, len(ys)))
            for row, i in enumerate(sel):
                other = comp[nn[row]] != comp[i]
                if not other.any():
                    continue
                j = int(np.argmax(other))
                cand = (float(d[row, j]), int(i), int(nn[row, j]))
                c = int(comp[i])
                if c not in best or cand < best[c]:
                    best[c] = cand
        added = set()
        for c, (d, i, j) in sorted(best.items(), key=lambda kv: kv[1]):
            a, b = int(prov[i]), int(prov[j])
            key = tuple(sorted((comp[i], comp[j])))
            if key in added:
                continue
            if d > MAX_STRAIT_PX:
                raise ValueError(f"island province {a} is {d:.0f} px from any other land")
            added.add(key)
            my, mx = (ys[i] + ys[j]) // 2, (xs[i] + xs[j]) // 2
            out.append((min(a, b), max(a, b), _through_sea(a, b, my, mx)))
            edges.append((a, b))
    return sorted(set(out))


@cache
def railways() -> list[tuple[int, int, int]]:
    """(level, province_a, province_b) for every railway segment between adjacent provinces."""
    land, index, g = _land_graph()
    vps = victory_points()
    states = [s.key for s in geo.load_states()]
    caps = [index[vps[k]] for k in states]
    dist, pred = dijkstra(g, indices=caps, return_predecessors=True)
    sub = dist[:, caps].copy()
    sub[~np.isfinite(sub)] = 0  # different islands: no railway between them
    mst = minimum_spanning_tree(csr_matrix(sub)).tocoo()
    pop = _state_pop()
    edges: dict[tuple[int, int], int] = {}
    for i, j in zip(mst.row, mst.col):
        pa, pb = pop[states[i]], pop[states[j]]
        level = 3 if min(pa, pb) >= 100_000 else 2 if max(pa, pb) >= 50_000 else 1
        node = caps[j]
        while node != caps[i] and node >= 0:
            prev = pred[i, node]
            if prev < 0:
                break
            a, b = sorted((land[prev], land[node]))
            edges[(a, b)] = max(edges.get((a, b), 0), level)
            node = prev
    return sorted((lvl, a, b) for (a, b), lvl in edges.items())


def write_railways(path: Path) -> None:
    path.write_text("".join(f"{lvl} 2 {a} {b}\n" for lvl, a, b in railways()), encoding="utf-8")


def write_supply_nodes(path: Path) -> None:
    vps = victory_points()
    lines = [f"1 {vps[s.key]}\n" for s in geo.load_states()]
    path.write_text("".join(lines), encoding="utf-8")


# --- definitions and simple map files ------------------------------------------------

def write_provinces_bmp(path: Path) -> None:
    pm = provinces.provinces()
    lut = np.zeros((max(pm.info) + 1, 3), np.uint8)
    for p in pm.info.values():
        lut[p.id] = p.rgb
    Image.fromarray(lut[pm.ids], "RGB").save(path)


def write_definition(path: Path) -> None:
    pm = terrain.annotate()
    lines = ["0;0;0;0;land;false;unknown;0"]
    for pid in sorted(pm.info):
        p = pm.info[pid]
        kind = {"land": "land", "sea": "sea", "lake": "lake"}[p.kind]
        continent = 1 if p.kind == "land" else 0
        coastal = "true" if p.coastal else "false"
        r, g, b = p.rgb
        lines.append(f"{pid};{r};{g};{b};{kind};{coastal};{p.terrain};{continent}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


DEFAULT_MAP = """definitions = "definition.csv"
provinces = "provinces.bmp"
positions = "positions.txt"
terrain = "terrain.bmp"
rivers = "rivers.bmp"
heightmap = "heightmap.bmp"
tree_definition = "trees.bmp"
continent = "continent.txt"
adjacency_rules = "adjacency_rules.txt"
adjacencies = "adjacencies.csv"
ambient_object = "ambient_object.txt"
seasons = "seasons.txt"

# Define which indices in trees.bmp palette which should count as trees for automatic terrain assignment
tree = { 3 4 7 10 }
"""


def write_simple_files(folder: Path) -> None:
    (folder / "default.map").write_text(DEFAULT_MAP, encoding="utf-8")
    # All vanilla continents, even unused ones: vanilla portraits and decisions name them, and an
    # unknown continent breaks parsing of whole portrait files (no leader portraits -> crash).
    names = "\n".join(f"\t{c}" for c in VANILLA_CONTINENTS)
    (folder / "continent.txt").write_text(f"continents = {{\n{names}\n}}\n", encoding="utf-8")
    rows = ["From;To;Type;Through;start_x;start_y;stop_x;stop_y;adjacency_rule_name;Comment"]
    rows += [f"{a};{b};sea;{t};-1;-1;-1;-1;;bridge, tunnel or ferry" if t > 0 else
             f"{a};{b};;-1;-1;-1;-1;-1;;bridge, tunnel or ferry" for a, b, t in straits()]
    rows.append("-1;-1;;-1;-1;-1;-1;-1;-1;")
    (folder / "adjacencies.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (folder / "adjacency_rules.txt").write_text("# No special adjacency rules on this map.\n", encoding="utf-8")
    (folder / "ambient_object.txt").write_text("# No ambient objects on this map.\n", encoding="utf-8")


# --- positions ----------------------------------------------------------------------

def _sea_neighbour(pid: int) -> int:
    pm = terrain.annotate()
    seas = sorted(q for q in terrain.adjacency().get(pid, ()) if pm.info[q].kind == "sea")
    return seas[0] if seas else 0


def _shore_point(pid: int, sea_pid: int) -> tuple[int, int]:
    ids = provinces.provinces().ids
    ys, xs = province_pixels(pid)
    for y, x in zip(ys.tolist(), xs.tolist()):
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, (x + dx) % ids.shape[1]  # the map wraps horizontally
            if 0 <= yy < ids.shape[0] and ids[yy, xx] == sea_pid:
                return x, y
    return interior_point(pid, f"shore{pid}")


def write_buildings(path: Path) -> None:
    pm = terrain.annotate()
    sid = state_ids()
    vps = victory_points()
    lines = []
    for key, provs in state_provinces().items():
        coastal = any(pm.info[p].coastal for p in provs)
        wanted = dict(STATE_BUILDINGS)
        if coastal:
            wanted.update(COASTAL_STATE_BUILDINGS)
        if is_wasteland(key):
            # Impassable: the game still wants an air base and rocket site position per state,
            # plus the port positions every coastal province needs.
            wanted = {"air_base": 1, "rocket_site_spawn": 1}
        for b, n in wanted.items():
            for i in range(n):
                pid = provs[(i + provs.index(vps[key])) % len(provs)]
                x, y = interior_point(pid, f"{key}-{b}-{i}")
                lines.append(f"{sid[key]};{b};{_fmt(*world(x, y))};0.00;0")
        for pid in provs:
            for b in (() if is_wasteland(key) else PROVINCE_BUILDINGS):
                x, y = interior_point(pid, f"{pid}-{b}")
                lines.append(f"{sid[key]};{b};{_fmt(*world(x, y))};0.00;0")
            if pm.info[pid].coastal:
                sea = _sea_neighbour(pid)
                x, y = _shore_point(pid, sea)
                for b in COASTAL_PROVINCE_BUILDINGS:
                    last = sea if b in SEA_LINKED_BUILDINGS else 0
                    lines.append(f"{sid[key]};{b};{_fmt(*world(x, y))};0.00;{last}")
    # No trailing newline: the game reads an empty last line as a building with the wrong field count.
    path.write_text("\n".join(lines), encoding="utf-8")


def write_unitstacks(path: Path) -> None:
    pm = provinces.provinces()
    lines = []
    for pid in sorted(pm.info):
        x, y = pm.info[pid].seed[1], pm.info[pid].seed[0]
        if pm.info[pid].kind == "land":
            x, y = interior_point(pid, f"stack{pid}")
        # Vanilla gives provinces up to 39 stack positions (0-38: standing, moving, attacking, ports,
        # victory point and so on). The game expects them once a game starts, so write them all.
        for t in range(UNIT_STACK_TYPES):
            lines.append(f"{pid};{t};{_fmt(*world(x, y))};0.00;0.00")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_weatherpositions(path: Path) -> None:
    pm = provinces.provinces()
    lines = []
    for r in strategic_regions():
        pid = max(r.provinces, key=lambda p: pm.info[p].size)
        cx, cy = pm.info[pid].centroid
        lines.append(f"{r.id};{_fmt(*world(cx, cy))};small")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_airports_and_rocketsites(folder: Path) -> None:
    sid = state_ids()
    vps = victory_points()
    text = "".join(f"{sid[k]}={{ {vps[k]} }}\n" for k in sorted(vps, key=lambda k: sid[k]))
    (folder / "airports.txt").write_text(text, encoding="utf-8")
    (folder / "rocketsites.txt").write_text(text, encoding="utf-8")


CITY_GROUP_WESTERN = 15  # vanilla map/cities.txt: color_index of the western city group


def write_cities_bmp(path: Path) -> None:
    """City mesh style map (vanilla cities.txt reads map/cities.bmp): western style everywhere."""
    im = Image.fromarray(np.full((HEIGHT, geo.WIDTH), CITY_GROUP_WESTERN, np.uint8), "P")
    pal = [0] * 768
    pal[3 * CITY_GROUP_WESTERN:3 * CITY_GROUP_WESTERN + 3] = (255, 255, 255)
    im.putpalette(pal)
    im.save(path)


def write_supply_area(folder: Path) -> None:
    """Vanilla still ships one legacy supply area; keep one so the folder is never empty."""
    folder.mkdir(parents=True, exist_ok=True)
    ids = " ".join(str(i) for i in sorted(state_ids().values()))
    (folder / "1-SupplyArea.txt").write_text(
        f'supply_area={{\n\tid=1\n\tname="SUPPLYAREA_1"\n\tvalue=12\n\tstates={{\n\t\t{ids}\n\t}}\n}}\n',
        encoding="utf-8")


def write_all(map_dir: Path) -> None:
    map_dir.mkdir(parents=True, exist_ok=True)
    write_provinces_bmp(map_dir / "provinces.bmp")
    write_definition(map_dir / "definition.csv")
    raster.write_heightmap(map_dir / "heightmap.bmp")
    terrain.write_terrain_bmp(map_dir / "terrain.bmp")
    terrain.write_rivers_bmp(map_dir / "rivers.bmp")
    terrain.write_trees_bmp(map_dir / "trees.bmp")
    terrain.write_normal_map(map_dir / "world_normal.bmp")
    terrain.write_colormaps(map_dir / "terrain")
    write_simple_files(map_dir)
    write_cities_bmp(map_dir / "cities.bmp")
    write_strategic_regions(map_dir / "strategicregions")
    write_supply_area(map_dir / "supplyareas")
    write_railways(map_dir / "railways.txt")
    write_supply_nodes(map_dir / "supply_nodes.txt")
    write_buildings(map_dir / "buildings.txt")
    write_unitstacks(map_dir / "unitstacks.txt")
    write_weatherpositions(map_dir / "weatherpositions.txt")
    write_airports_and_rocketsites(map_dir)
