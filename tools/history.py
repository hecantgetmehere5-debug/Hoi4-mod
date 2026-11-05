"""Write states, countries, tags, bookmark, localisation, flags and the mod descriptor."""
from pathlib import Path

import numpy as np
from PIL import Image

from tools import geo, ideologies, mapfiles, raster, terrain

START_DATE = "2030.1.1.12"
END_DATE = "2080.1.1.1"
MOD_NAME = "Norwegian Civil War 2030"
# Tags this mod shares with vanilla, and vanilla's country file for each (common/country_tags/00_countries.txt).
VANILLA_COUNTRY_FILES = {"NOR": "Norway", "SWE": "Sweden", "FIN": "Finland", "SOV": "Soviet Union", "DEN": "Denmark",
                         "EST": "Estonia", "LAT": "Latvia", "LIT": "Lithuania", "ICE": "Iceland", "SCO": "Scotland"}
SUPPORTED_VERSION = "1.19.*"
STARTING_TECH = ("infantry_weapons", "infantry_weapons1", "tech_support", "tech_engineers", "tech_recon",
                 "gw_artillery", "interwar_antiair")
DIVISION_TEMPLATE = """division_template = {
\tname = "Infantry Division"
\tregiments = {
\t\tinfantry = { x = 0 y = 0 }
\t\tinfantry = { x = 0 y = 1 }
\t\tinfantry = { x = 1 y = 0 }
\t\tinfantry = { x = 1 y = 1 }
\t}
}
"""

# Vanilla world content that points at states and countries this map removes.
# Only history, tags, bookmarks and map regions are replaced: the game needs vanilla's
# default focus tree, on_actions, decisions and characters to start, even if they log errors.
REPLACE_PATHS = (
    "history/states", "history/countries", "history/units",
    "common/bookmarks", "map/strategicregions", "map/supplyareas",
    # Vanilla AI data names strategic regions and states by number; on this map those ids are
    # invalid, and the AI reads them on the first day of a game.
    "common/ai_areas", "common/ai_strategy", "common/ai_strategy_plans",
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


# Shared building slots per state category (vanilla common/state_category).
BUILDING_SLOTS = {"pastoral": 1, "rural": 2, "town": 4, "large_town": 5, "city": 6, "large_city": 8,
                  "metropolis": 10, "wasteland": 0}


def factories(pop: int, category: str) -> tuple[int, int]:
    """(industrial_complex, arms_factory) for a 2030 service economy without oil money.

    Never more than the state category's building slots: the game crashes when a game starts
    with a state over its limit ("Oslo has too many buildings").
    """
    slots = BUILDING_SLOTS[category]
    mil = min(int(pop >= 150_000), slots)
    civ = min(int(pop // 70_000), slots - mil)
    return civ, mil


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
    lakes = mapfiles.state_lakes()
    vps = mapfiles.victory_points()
    pops = _state_pop()
    area = _state_area()
    info = terrain.annotate().info
    out = {}
    for s in geo.load_states():
        owner = geo.state_owner(s)
        pop = pops[s.key]
        civ, mil = factories(pop, state_category(pop, False))
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
                                                       lines, sorted(set(sp[s.key] + lakes.get(s.key, []))), impassable=False)
    for key, owner, _ in raster.wasteland():
        lines = [f"\t\towner = {owner}", f"\t\tadd_core_of = {owner}"]
        out[f"{sid[key]}-{key}.txt"] = _state_text(sid[key], 1000, "wasteland", lines, sorted(set(sp[key] + lakes.get(key, []))),
                                                  impassable=True)
    return out


def load_armies() -> dict[str, dict]:
    return geo._yaml("armies.yaml")


def division_locations(tag: str) -> list[int]:
    """Land provinces for the tag's starting divisions: VP provinces first, spread over its states."""
    army = load_armies().get(tag, {})
    sp = mapfiles.state_provinces()
    vps = mapfiles.victory_points()
    states = [s.key for s in geo.load_states() if geo.state_owner(s) == tag and not mapfiles.is_wasteland(s.key)]
    if not states:
        return []
    capital = geo.load_factions()[tag].capital
    states.sort(key=lambda k: k != capital)
    # Per state: VP province first, then the rest in order.
    queues = {k: [vps[k]] + [p for p in sp[k] if p != vps[k]] for k in states}
    if "per_state" in army:
        return [queues[k][i % len(queues[k])] for k in states for i in range(army["per_state"])]
    n = army.get("divisions", 0)
    out = []
    for i in range(n):
        k = states[i % len(states)]
        q = queues[k]
        out.append(q[(i // len(states)) % len(q)])
    return out


def units_text(tag: str) -> str:
    factor = load_armies().get(tag, {}).get("equipment", 1.0)
    divs = [f"\tdivision = {{\n\t\tdivision_name = {{ is_name_ordered = yes name_order = {i} }}\n"
            f"\t\tlocation = {p}\n\t\tdivision_template = \"Infantry Division\"\n"
            f"\t\tstart_experience_factor = 0.2\n\t\tstart_equipment_factor = {factor}\n\t}}"
            for i, p in enumerate(division_locations(tag), 1)]
    body = "units = {\n" + "\n".join(divs) + "\n}\n" if divs else ""
    return DIVISION_TEMPLATE + body


def _state_text(sid, manpower, category, history, provs, impassable) -> str:
    extra = "\timpassable = yes\n" if impassable else ""
    return (f"state = {{\n\tid = {sid}\n\tname = \"NWC_STATE_{sid}\"\n\tmanpower = {manpower}\n"
            f"\tstate_category = {category}\n{extra}\thistory = {{\n" + "\n".join(history) +
            f"\n\t}}\n\tprovinces = {{\n\t\t{' '.join(map(str, provs))}\n\t}}\n\tlocal_supplies = 0.0\n}}\n")


# Groups whose countries hold elections.
ELECTORAL = ("democratic", "conservative", "democratic_socialism")


def country_history(f: geo.Faction, puppets: list[str]) -> str:
    sid = mapfiles.state_ids()
    if f.spawn:
        # Released mid-game by an event, which sets its government; it starts with no land or army.
        return f"capital = {sid[f.capital]}\n" + "set_technology = {\n" + "".join(f"\t{t} = 1\n" for t in STARTING_TECH) + "}\n"
    pops = ideologies.popularities(f)
    lines = [f"capital = {sid[f.capital]}", "set_research_slots = 3",
             "set_stability = 0.4", "set_war_support = 0.6",
             "set_politics = {", f"\truling_party = {f.ideology}", '\tlast_election = "2029.9.9"',
             "\telection_frequency = 48", f"\telections_allowed = {'yes' if f.ideology in ELECTORAL else 'no'}",
             "}", "set_popularities = {"]
    lines += [f"\t{k} = {v}" for k, v in pops.items()] + ["}"]
    if f.leader:
        lines.append(f"recruit_character = {ideologies.leader_id(f.tag)}")
    for p in puppets:
        lines.append(f"set_autonomy = {{ target = {p} autonomous_state = autonomy_puppet }}")
    # Every vanilla country starts with laws, base technologies, convoys and an order of battle.
    lines += [f'oob = "{f.tag}_2030"', "set_convoys = 10",
              "add_ideas = {", "\tvolunteer_only", "\tcivilian_economy", "\texport_focus"]
    if idea := load_armies().get(f.tag, {}).get("economy_idea"):
        lines.append(f"\t{idea}")
    lines += ["}",
              "set_technology = {"] + [f"\t{t} = 1" for t in STARTING_TECH] + ["}"]
    return "\n".join(lines) + "\n"


ASCII = str.maketrans({"å": "a", "Å": "A", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "á": "a", "ä": "a",
                       "ö": "o"})


def _file_name(f: geo.Faction) -> str:
    return "".join(c for c in f.name.translate(ASCII) if c.isascii() and (c.isalnum() or c in " -")).strip()


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
        if tag in VANILLA_COUNTRY_FILES:
            # Reused vanilla tag: keep vanilla's tag entry and override its country file.
            country_file = VANILLA_COUNTRY_FILES[tag]
        else:
            country_file = name
            tag_lines.append(f'{tag} = "countries/{name}.txt"')
        r, g, b = f.colour
        (countries / f"{country_file}.txt").write_text(
            f"graphical_culture = western_european_gfx\ngraphical_culture_2d = western_european_2d\n"
            f"color = rgb {{ {r} {g} {b} }}\n", encoding="utf-8")
        puppets = [t for t, o in factions.items() if o.puppet_of == tag]
        # A reused spawn tag takes vanilla's exact history file name, so it replaces vanilla's file.
        hist_name = VANILLA_COUNTRY_FILES[tag] if f.spawn and tag in VANILLA_COUNTRY_FILES else name
        (hist / f"{tag} - {hist_name}.txt").write_text(country_history(f, puppets), encoding="utf-8")
        if not f.spawn:
            (units / f"{tag}_2030.txt").write_text(units_text(tag), encoding="utf-8")
    # Vanilla countries this map leaves out still need a history file; they start with no states.
    # Vanilla gives even countries that start without land a capital; a game won't start without one.
    absent_capital = mapfiles.state_ids()[factions["FIN"].capital]
    lines = (geo.DATA / "vanilla_tags.txt").read_text().splitlines()
    for tag in (l.strip() for l in lines if l.strip() and not l.startswith("#")):
        if tag not in factions:
            (hist / f"{tag} - absent.txt").write_text(
                f"# Not on this map.\ncapital = {absent_capital}\n", encoding="utf-8")
    # Added next to vanilla's tags, so vanilla scripts that name GER, ENG and so on still find them.
    (tags / "nwc_countries.txt").write_text("\n".join(tag_lines) + "\n", encoding="utf-8")


def write_states(mod: Path) -> None:
    d = mod / "history" / "states"
    d.mkdir(parents=True, exist_ok=True)
    for name, text in state_files().items():
        (d / name).write_text(text, encoding="utf-8")


def write_ai_areas(mod: Path) -> None:
    """Every AI area vanilla scripts name, each holding only valid strategic regions of this map."""
    names = [l.strip() for l in (geo.DATA / "vanilla_ai_areas.txt").read_text().splitlines()
             if l.strip() and not l.startswith("#")]
    land = sorted(r.id for r in mapfiles.strategic_regions() if r.weather == "land")
    ids = " ".join(map(str, land))
    d = mod / "common" / "ai_areas"
    d.mkdir(parents=True, exist_ok=True)
    body = "".join(f"\t{n} = {{\n\t\tstrategic_regions = {{ {ids} }}\n\t}}\n" for n in names)
    (d / "nwc_ai_areas.txt").write_text(f"areas = {{\n{body}}}\n", encoding="utf-8")


def write_tutorial(mod: Path) -> None:
    """Map-independent tutorial; vanilla's points the camera at state 550, which crashes game start here."""
    d = mod / "tutorial"
    d.mkdir(parents=True, exist_ok=True)
    (d / "tutorial.txt").write_text((geo.DATA / "tutorial.txt").read_text(encoding="utf-8"), encoding="utf-8")


def write_names(mod: Path) -> None:
    """Name lists for the new tags: without one the game can't name generated leaders and scientists."""
    text = (geo.DATA / "names_norway.txt").read_text(encoding="utf-8")
    block = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
    new_tags = [t for t in geo.load_factions() if t not in VANILLA_COUNTRY_FILES]
    d = mod / "common" / "names"
    d.mkdir(parents=True, exist_ok=True)
    (d / "nwc_names.txt").write_text("".join(f"{t} = {block}\n\n" for t in new_tags), encoding="utf-8")


def write_bookmark_and_defines(mod: Path) -> None:
    factions = geo.load_factions()
    d = mod / "common" / "bookmarks"
    d.mkdir(parents=True, exist_ok=True)
    playable = [t for t, f in factions.items() if not f.background and not f.spawn and t != "SWE"]
    countries = "\n".join(f"\t\t{t} = {{ }}" for t in playable)
    (d / "nwc_2030.txt").write_text(
        "bookmarks = {\n\tbookmark = {\n\t\tname = \"NWC_BOOKMARK\"\n\t\tdesc = \"NWC_BOOKMARK_DESC\"\n"
        f"\t\tdate = {START_DATE}\n\t\tpicture = \"GFX_select_date_1936\"\n\t\tdefault_country = \"NOR\"\n"
        f"\t\tdefault = yes\n{countries}\n\t\teffect = {{\n\t\t\trandomize_weather = 22345\n\t\t}}\n\t}}\n}}\n",
        encoding="utf-8")
    dd = mod / "common" / "defines"
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "00_nwc_defines.lua").write_text(
        f'NDefines.NGame.START_DATE = "{START_DATE}"\nNDefines.NGame.END_DATE = "{END_DATE}"\n'
        '-- Country the game plays as when launched with -hands_off (used by tools/launch_check.sh).\n'
        'NDefines.NGame.HANDS_OFF_START_TAG = "NOR"\n', encoding="utf-8")


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
            rows.append(f' NWC_STATE_{i}:0 "{q(names[key].name)}"')
            rows.append(f' VICTORY_POINTS_{vps[key]}:0 "{q(names[key].vp)}"')
        else:
            label = {"waste_fin": "Finland", "waste_sov": "Kola", "waste_den": "Jutland"}.get(key, "Sverige")
            rows.append(f' NWC_STATE_{i}:0 "{label}"')
    for r in mapfiles.strategic_regions():
        rows.append(f' NWC_STRATEGICREGION_{r.id}:0 "{q(r.name)}"')
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
            # A real flag image in data/flags/<TAG>.png overrides the generated placeholder.
            # A hand-tuned data/flags/<TAG>_<w>.png small version wins over downscaling the master.
            flags = Path(__file__).resolve().parents[1] / "data" / "flags"
            sized = flags / f"{tag}_{size[0]}.png"
            src = sized if sized.exists() else flags / f"{tag}.png"
            img = Image.open(src).convert("RGBA").resize(size, Image.LANCZOS) if src.exists() else flag(f.colour, size)
            img.save(d / f"{tag}.tga")


def descriptor(path: str | None = None) -> str:
    lines = ['version="0.1.0"', f'name="{MOD_NAME}"', f'supported_version="{SUPPORTED_VERSION}"',
             'tags={\n\t"Map"\n\t"Alternative History"\n}']
    lines += [f'replace_path="{p}"' for p in REPLACE_PATHS]
    if path:
        lines.append(f'path="{path}"')
    return "\n".join(lines) + "\n"


def write_all(mod: Path) -> None:
    write_states(mod)
    write_countries(mod)
    write_names(mod)
    write_tutorial(mod)
    write_ai_areas(mod)
    write_bookmark_and_defines(mod)
    write_localisation(mod)
    write_flags(mod)
    ideologies.write_all(mod)
    (mod / "descriptor.mod").write_text(descriptor(), encoding="utf-8")
