"""Write states, countries, tags, bookmark, localisation, flags and the mod descriptor."""
from pathlib import Path

import numpy as np
from PIL import Image

from tools import geo, mapfiles, raster, terrain

START_DATE = "2030.1.1.12"
END_DATE = "2080.1.1.1"
MOD_NAME = "Norwegian Civil War 2030"

REPLACE_PATHS = (
    "history/states", "history/countries", "history/units", "history/general",
    "common/country_tags", "common/bookmarks", "map/strategicregions", "map/supplyareas",
)

CATEGORIES = ((5_000, "pastoral"), (15_000, "rural"), (40_000, "town"), (90_000, "large_town"),
              (200_000, "city"), (450_000, "large_city"), (10 ** 9, "metropolis"))


def state_category(pop: int, wasteland: bool) -> str:
    if wasteland:
        return "wasteland"
    return next(name for limit, name in CATEGORIES if pop < limit)


def vp_value(pop: int) -> int:
    return int(np.clip(round(pop / 15_000), 1, 50))


def infrastructure(pop: int, km2: float) -> int:
    density = pop / max(km2, 1)
    return 4 if density > 250 else 3 if density > 30 else 2 if density > 5 else 1


def factories(pop: int) -> tuple[int, int]:
    """(industrial_complex, arms_factory) for a 2030 service economy without oil money."""
    civ = int(pop // 70_000)
    return civ, int(pop >= 150_000)


def _state_pop() -> dict[str, int]:
    pop = geo.load_population()
    return {s.key: sum(pop[k] for k in s.kommuner) for s in geo.load_states()}


def _state_area() -> dict[str, float]:
    counts = np.bincount(raster.state_raster().ravel(), minlength=len(raster.all_state_keys()) + 1)
    km2 = (geo.PIXEL_M / 1000) ** 2
    return {k: counts[i + 1] * km2 for i, k in enumerate(raster.all_state_keys())}


def state_files() -> dict[str, str]:
    """file name -> contents for every history/states file."""
    sid = mapfiles.state_ids()
    sp = mapfiles.state_provinces()
    vps = mapfiles.victory_points()
    pops = _state_pop()
    area = _state_area()
    info = terrain.annotate().info
    out = {}
    for s in geo.load_states():
        owner = geo.state_owner(s)
        pop = pops[s.key]
        civ, mil = factories(pop)
        cores = [owner] + (["NOR"] if owner not in ("NOR", "SWE") else [])
        naval = [p for p in sp[s.key] if info[p].coastal][:1]
        lines = [f"\t\towner = {owner}"] + [f"\t\tadd_core_of = {c}" for c in cores]
        lines.append(f"\t\tvictory_points = {{ {vps[s.key]} {vp_value(pop)} }}")
        lines.append("\t\tbuildings = {")
        lines.append(f"\t\t\tinfrastructure = {infrastructure(pop, area[s.key])}")
        if civ:
            lines.append(f"\t\t\tindustrial_complex = {civ}")
        if mil:
            lines.append(f"\t\t\tarms_factory = {mil}")
        if s.key == geo.load_factions()[owner].capital:
            lines.append("\t\t\tair_base = 2")
        for p in naval:
            lines.append(f"\t\t\t{p} = {{ naval_base = {2 if pop >= 50_000 else 1} }}")
        lines.append("\t\t}")
        out[f"{sid[s.key]}-{s.key}.txt"] = _state_text(sid[s.key], pop, state_category(pop, False),
                                                       lines, sp[s.key], impassable=False)
    for key, owner, _ in raster.wasteland():
        lines = [f"\t\towner = {owner}", f"\t\tadd_core_of = {owner}"]
        out[f"{sid[key]}-{key}.txt"] = _state_text(sid[key], 1000, "wasteland", lines, sp[key], impassable=True)
    return out


def _state_text(sid, manpower, category, history, provs, impassable) -> str:
    extra = "\timpassable = yes\n" if impassable else ""
    return (f"state = {{\n\tid = {sid}\n\tname = \"STATE_{sid}\"\n\tmanpower = {manpower}\n"
            f"\tstate_category = {category}\n{extra}\thistory = {{\n" + "\n".join(history) +
            f"\n\t}}\n\tprovinces = {{\n\t\t{' '.join(map(str, provs))}\n\t}}\n\tlocal_supplies = 0.0\n}}\n")


IDEOLOGY_SPLITS = {
    "democratic": {"democratic": 60, "neutrality": 20, "communism": 10, "fascism": 10},
    "communism": {"communism": 60, "democratic": 20, "neutrality": 15, "fascism": 5},
    "fascism": {"fascism": 65, "neutrality": 20, "democratic": 10, "communism": 5},
    "neutrality": {"neutrality": 60, "democratic": 20, "communism": 10, "fascism": 10},
}


def country_history(f: geo.Faction, puppets: list[str]) -> str:
    sid = mapfiles.state_ids()
    pops = IDEOLOGY_SPLITS[f.ideology]
    lines = [f"capital = {sid[f.capital]}", "set_research_slots = 3",
             "set_stability = 0.4", "set_war_support = 0.6",
             "set_politics = {", f"\truling_party = {f.ideology}", '\tlast_election = "2029.9.9"',
             "\telection_frequency = 48", f"\telections_allowed = {'yes' if f.ideology == 'democratic' else 'no'}",
             "}", "set_popularities = {"]
    lines += [f"\t{k} = {v}" for k, v in pops.items()] + ["}"]
    for p in puppets:
        lines.append(f"set_autonomy = {{ target = {p} autonomous_state = autonomy_puppet }}")
    return "\n".join(lines) + "\n"


def _file_name(f: geo.Faction) -> str:
    return "".join(c if c.isalnum() or c in " -" else "" for c in f.name).strip()


def write_countries(mod: Path) -> None:
    factions = geo.load_factions()
    tags = mod / "common" / "country_tags"
    countries = mod / "common" / "countries"
    hist = mod / "history" / "countries"
    units = mod / "history" / "units"
    for d in (tags, countries, hist, units):
        d.mkdir(parents=True, exist_ok=True)
    tag_lines = []
    for tag, f in factions.items():
        name = _file_name(f)
        tag_lines.append(f'{tag} = "countries/{name}.txt"')
        r, g, b = f.colour
        (countries / f"{name}.txt").write_text(
            f"graphical_culture = western_european_gfx\ngraphical_culture_2d = western_european_2d\n"
            f"color = rgb {{ {r} {g} {b} }}\n", encoding="utf-8")
        puppets = [t for t, o in factions.items() if o.puppet_of == tag]
        (hist / f"{tag} - {name}.txt").write_text(country_history(f, puppets), encoding="utf-8")
        (units / f"{tag}_2030.txt").write_text("# Order of battle comes with the military project.\n",
                                               encoding="utf-8")
    (tags / "00_countries.txt").write_text("\n".join(tag_lines) + "\n", encoding="utf-8")


def write_states(mod: Path) -> None:
    d = mod / "history" / "states"
    d.mkdir(parents=True, exist_ok=True)
    for name, text in state_files().items():
        (d / name).write_text(text, encoding="utf-8")


def write_bookmark_and_defines(mod: Path) -> None:
    factions = geo.load_factions()
    d = mod / "common" / "bookmarks"
    d.mkdir(parents=True, exist_ok=True)
    playable = [t for t, f in factions.items() if not f.background and t != "SWE"]
    countries = "\n".join(f"\t\t{t} = {{ }}" for t in playable)
    (d / "nwc_2030.txt").write_text(
        "bookmarks = {\n\tbookmark = {\n\t\tname = \"NWC_BOOKMARK\"\n\t\tdesc = \"NWC_BOOKMARK_DESC\"\n"
        f"\t\tdate = {START_DATE}\n\t\tpicture = \"GFX_select_date_1936\"\n\t\tdefault_country = \"NOR\"\n"
        f"\t\tdefault = yes\n{countries}\n\t\teffect = {{\n\t\t\trandomize_weather = 22345\n\t\t}}\n\t}}\n}}\n",
        encoding="utf-8")
    dd = mod / "common" / "defines"
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "00_nwc_defines.lua").write_text(
        f'NDefines.NGame.START_DATE = "{START_DATE}"\nNDefines.NGame.END_DATE = "{END_DATE}"\n', encoding="utf-8")


def localisation() -> str:
    factions = geo.load_factions()
    sid = mapfiles.state_ids()
    vps = mapfiles.victory_points()
    names = {s.key: s for s in geo.load_states()}
    rows = ["l_english:"]

    def q(s):
        return s.replace('"', "'")

    for tag, f in factions.items():
        rows += [f' {tag}:0 "{q(f.name)}"', f' {tag}_DEF:0 "{q(f.name)}"', f' {tag}_ADJ:0 "{q(f.adjective)}"']
    for key, i in sorted(sid.items(), key=lambda kv: kv[1]):
        if key in names:
            rows.append(f' STATE_{i}:0 "{q(names[key].name)}"')
            rows.append(f' VICTORY_POINTS_{vps[key]}:0 "{q(names[key].vp)}"')
        else:
            label = {"waste_fin": "Finland", "waste_sov": "Kola", "waste_den": "Jutland"}.get(key, "Sverige")
            rows.append(f' STATE_{i}:0 "{label}"')
    for r in mapfiles.strategic_regions():
        rows.append(f' STRATEGICREGION_{r.id}:0 "{q(r.name)}"')
    rows += [' NWC_BOOKMARK:0 "The Norwegian Civil War"',
             ' NWC_BOOKMARK_DESC:0 "2030. The oil fund is gone, the parties have turned on each other, '
             'and Norway has broken apart."']
    return "\n".join(rows) + "\n"


def write_localisation(mod: Path) -> None:
    d = mod / "localisation" / "english"
    d.mkdir(parents=True, exist_ok=True)
    (d / "nwc_map_l_english.yml").write_bytes(b"\xef\xbb\xbf" + localisation().encode("utf-8"))


def flag(colour, size) -> Image.Image:
    """Placeholder flag: faction colour with a darker Nordic cross."""
    w, h = size
    img = Image.new("RGBA", size, (*colour, 255))
    a = np.asarray(img).copy()
    dark = (np.array(colour) * 0.55).astype(np.uint8)
    t = max(1, h // 6)
    cx = int(w * 0.36)
    a[h // 2 - t // 2: h // 2 - t // 2 + t, :, :3] = dark
    a[:, cx - t // 2: cx - t // 2 + t, :3] = dark
    return Image.fromarray(a, "RGBA")


def write_flags(mod: Path) -> None:
    for sub, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
        d = mod / "gfx" / "flags" / sub
        d.mkdir(parents=True, exist_ok=True)
        for tag, f in geo.load_factions().items():
            flag(f.colour, size).save(d / f"{tag}.tga")


def descriptor(path: str | None = None) -> str:
    lines = ['version="0.1.0"', f'name="{MOD_NAME}"', 'supported_version="1.*"',
             'tags={\n\t"Map"\n\t"Alternative History"\n}']
    lines += [f'replace_path="{p}"' for p in REPLACE_PATHS]
    if path:
        lines.append(f'path="{path}"')
    return "\n".join(lines) + "\n"


def write_all(mod: Path) -> None:
    write_states(mod)
    write_countries(mod)
    write_bookmark_and_defines(mod)
    write_localisation(mod)
    write_flags(mod)
    (mod / "descriptor.mod").write_text(descriptor(), encoding="utf-8")
