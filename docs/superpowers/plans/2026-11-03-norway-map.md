# Norway Civil War Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python pipeline in this repo that regenerates a loadable HOI4 total-conversion map of Norway plus a thin Swedish strip, with the approved faction ownership on 1 January 2030.

**Architecture:** Source geodata (municipality borders, elevation, rivers/lakes) → hand-edited YAML data (who owns what, how municipalities group into states) → a raster stage that draws everything in one fixed projection → writers that emit every HOI4 file under `mod/`. A persistent JSON registry keeps state and province IDs stable across re-runs. `make build` regenerates all of `mod/` from scratch; `make install` links it into the game's mod folder.

**Tech Stack:** Python 3.12, numpy, shapely 2, pyproj, rasterio (rasterize), Pillow, scipy (Voronoi/nearest via KD-tree), PyYAML, pytest. Pinned in `requirements.txt`.

**Spec:** `docs/superpowers/specs/2026-11-03-norway-map-design.md`

## Global Constraints

- Target: current HOI4 version, base game, **no DLC**.
- Map: only Norway and the Swedish strip are land; everything else is sea or impassable wasteland. No Svalbard.
- Every faction border falls on a state border; no state has more than one owner.
- Big cities are their own states: Oslo, Bergen, Trondheim, Stavanger, Kristiansand, Tromsø, Drammen, Fredrikstad+Sarpsborg, Bodø (more allowed).
- Starting ownership = `make_map.py` `COUNTY` + `OVERRIDES` tables (the approved map), migrated to `data/ownership.yaml` in Task 2.
- Chaos anarchists = **one** country owning all pockets. Western Forces = **puppet of the Government** at start.
- Sweden (`SWE`) neutral, owns the whole strip: Kiruna, Östersund, Karlstad, Strömstad/Arvika area, nothing much beyond.
- State and province IDs are never renumbered by a re-run (registry files are committed).
- All vanilla world content replaced or emptied via `replace_path`.
- Source municipality data: `Kommuner-M.geojson`, github.com/robhop/fylker-og-kommuner (2024 structure).
- Every generated file is reproducible from `make build`; nothing in `mod/map` is hand-edited.

## Review Focus

1. **Re-run after a data edit** (move one municipality to another state) → every other state/province keeps its ID and colour. Test in Task 4.
2. **Tiny islands and skerries** that rasterize to a few pixels → merged into the nearest same-state land province, never left as orphan specks or zero-pixel provinces. Test in Task 4.
3. **Narrow fjords** that rasterize as 1-pixel water or cut land provinces in two → every province's pixels form one connected blob. Test in Task 4.
4. **Coastal flag and ports**: a land province touching only a lake must not be marked coastal. Test in Task 5.
5. **Game load**: the game starts with the mod and `error.log` has no map/state/province errors. Manual check in Task 8, with a log-scanning script.

---

## File Structure

```
requirements.txt, Makefile, descriptor.mod (template), README.md
data/
  sources.yaml          # URLs + sha256 of every download
  ownership.yaml        # kommune code -> faction tag (from make_map.py)
  sweden_strip.yaml     # Swedish municipality codes in the strip
  states.yaml           # state key -> name, kommune codes, category, VP city
  factions.yaml         # tag -> name, colour, ideology placeholder, capital state
  registry/states.json, registry/provinces.json   # stable IDs (committed)
build/                  # downloads + intermediates (git-ignored)
tools/
  fetch.py      # download + checksum
  geo.py        # load + project + merge geometries
  raster.py     # land mask, state raster, heightmap
  provinces.py  # seed points, province raster, registry
  terrain.py    # terrain.bmp, rivers.bmp, trees.bmp, normal map, colormaps
  mapfiles.py   # definition.csv, default.map, positions, strategic regions, railways, supply
  history.py    # states, countries, tags, bookmark, localisation, flags
  build.py      # orchestrates; CLI
  check_log.py  # scans game error.log
tests/  (one test file per tools module)
mod/    # generated output (committed, so the playtester can pull and play)
```

Map projection and size (fixed for all tasks): **EPSG:25833 (UTM 33N), 400 m/pixel, 3072 × 4096 px**, origin top-left at easting −100 000, northing 7 980 000. Defined once as constants in `tools/geo.py`.

---

### Task 1: Project setup and source data

**Files:** Create `requirements.txt`, `Makefile`, `.gitignore`, `data/sources.yaml`, `tools/fetch.py`, `tests/test_fetch.py`. Move `make_map.py` and `faction_map.png` to `reference/`.

**Interfaces:** Produces `fetch_all(dest: Path) -> dict[str, Path]` with keys `kommuner`, `sweden_kommuner`, `countries`, `rivers`, `lakes`, `dem_tiles`.

Sources: kommuner (above); Swedish municipalities (github.com/okfse/sweden-geojson `swedish_municipalities.geojson`); Natural Earth 10m rivers + lakes; elevation from AWS Terrarium tiles (`s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`, zoom 8) covering the map extent.

- [ ] Write `test_fetch_verifies_checksum`: a fake file with the wrong sha256 raises `ChecksumError`; correct one returns its path.
- [ ] Run `pytest tests/test_fetch.py`, expect FAIL.
- [ ] Implement `fetch_all` (skip download if cached file matches checksum; DEM tiles verified by count, not sha).
- [ ] Run tests, expect PASS; run `make fetch`, expect all files in `build/src/`.
- [ ] Commit.

### Task 2: Ownership and state data

**Files:** Create `data/ownership.yaml`, `data/sweden_strip.yaml`, `data/factions.yaml`, `data/states.yaml`, `tools/geo.py` (loaders only here), `tests/test_data.py`.

**Interfaces:** Produces `load_ownership() -> dict[str, str]` (kommune code → tag), `load_states() -> list[State]` where `State(key: str, name: str, kommuner: list[str], category: str, vp_name: str)`, `load_factions() -> dict[str, Faction]`.

Tags (Claude's call): `NOR` Government, `WFR` Western Forces, `JNP` Jihadist Nationalist Party, `KRF` KrF, `SOC` Socialists, `FRP` FrP, `NRM` Nordic Resistance Movement, `SAM` Sametinget, `SPM` Neutral Coalition, `ABI` Askøy–Bømlo, `BRG` Bergen, `ANA` chaos anarchists, `SWE` Sweden. Colours from `reference/make_map.py`.

States: about 70–90, built from traditional districts inside each faction area; every anarchist pocket is its own state; city states listed in Global Constraints. Swedish strip: about 6 states.

- [ ] Write tests: `test_every_kommune_owned_once` (all 357 codes in the geojson appear in ownership.yaml exactly once); `test_ownership_matches_approved_map` (for all 357, result equals `reference/make_map.py` logic); `test_each_state_single_owner`; `test_every_kommune_in_exactly_one_state`; `test_city_states_exist` (Oslo `0301`, Bergen `4601`, Trondheim `5001`, Stavanger `1103`, Kristiansand `4204`, Tromsø `5501`, Drammen `3301`, Bodø `1804` each alone in a state; Fredrikstad `3107` + Sarpsborg `3105` together alone); `test_state_count_between(70, 110)`; `test_sweden_strip_has` Kiruna, Östersund, Karlstad, Strömstad, Arvika.
- [ ] Run, expect FAIL.
- [ ] Write the YAML files and loaders.
- [ ] Run, expect PASS. Render a check image (`python -m tools.build preview-states`) with state borders over faction colours; eyeball against `reference/faction_map.png`.
- [ ] Commit.

### Task 3: Projection, land mask and heightmap

**Files:** Create `tools/raster.py`, `tests/test_raster.py`; extend `tools/geo.py` with constants and `project(geom)`.

**Interfaces:** Produces `state_raster() -> np.ndarray[uint16]` (0 = not land, else state index+1), `land_mask() -> np.ndarray[bool]`, `lake_mask() -> np.ndarray[bool]`, `heightmap() -> np.ndarray[uint8]`.

Heightmap: sea and wasteland edge at value 0–94, **sea level 95**, land 96–255 scaled from 0–2 469 m (Galdhøpiggen) with a sqrt curve so lowlands stay readable. Lakes at their surface height.

- [ ] Write tests: shapes are (4096, 3072); `test_oslo_pixel_is_land` and `test_north_sea_pixel_is_sea` at fixed lat/lon; `test_all_land_heights_above_95`; `test_every_state_has_pixels` (≥ 40 px each).
- [ ] Run, expect FAIL. Implement (rasterio.features.rasterize, all_touched=False; Terrarium decode `h = R*256 + G + B/256 − 32768`, reproject with bilinear). Run, expect PASS.
- [ ] Commit.

### Task 4: Provinces and ID registry

**Files:** Create `tools/provinces.py`, `tests/test_provinces.py`, `data/registry/*.json`.

**Interfaces:** Consumes `state_raster`, `land_mask`, `lake_mask`. Produces `build_provinces() -> ProvinceMap` with `.ids: np.ndarray[uint32]` (province ID per pixel), `.info: dict[int, Province]`, `Province(id, rgb, kind: "land"|"sea"|"lake", state_key|None, coastal: bool, terrain: str, centroid: (x, y))`.

Density: land seeds by Poisson-disk sampling inside each state with spacing 14 px in city states, 22 px in coastal states, 34 px inland, 48 px in the Swedish strip; sea provinces on a 60 px grid clipped to sea, with fjords joining the nearest sea province. Each pixel takes the nearest seed **of its own state** (KD-tree per state), so provinces never cross states.

Registry: a province is keyed by `(state_key, seed x, seed y)`. On re-run, existing seeds are kept for states whose kommune list didn't change; changed states keep the IDs of seeds still inside them; new seeds get `max_id + 1`. Colours are derived from the ID and stored in the registry.

Cleanup: connected components smaller than 8 px are merged into the touching province of the same state (or the nearest one, for islands); a province split into pieces keeps its largest piece and the rest merge as above.

- [ ] Write tests: `test_province_never_crosses_state`; `test_all_provinces_connected` (one 4-connected component each); `test_min_province_size_8px`; `test_colours_unique`; `test_rerun_ids_stable` (build, move one kommune between two states in a temp copy of states.yaml, rebuild; all provinces outside those two states keep id+colour); `test_land_province_count_between(700, 1500)`.
- [ ] Run, expect FAIL. Implement. Run, expect PASS.
- [ ] Commit including `data/registry/`.

### Task 5: Terrain, rivers, trees and art files

**Files:** Create `tools/terrain.py`, `tests/test_terrain.py`.

**Interfaces:** Consumes the rasters and `ProvinceMap`. Produces writers `write_terrain_bmp`, `write_rivers_bmp`, `write_trees_bmp`, `write_normal_map`, `write_colormaps` into `mod/map/`, and sets `Province.terrain` and `Province.coastal`.

Rules (Claude's call): province terrain = `urban` for city-state provinces, `mountain` if mean height > 900 m or slope high, `hills` > 400 m, `forest` for forested lowland south of the treeline, `marsh` for low flat Finnmark plateau, else `plains`; sea `ocean`, lakes `lakes`. Palettes copied from the vanilla 8-bit files at build time (read the game install, path set in `Makefile`). Rivers from Natural Earth, width classes by `scalerank`, each river has one source pixel (green) and flows to sea; one pixel wide, never diagonal-only. `trees.bmp` size = vanilla ratio applied to our size. Normal map from heightmap at half size. Colormap and water colormap DDS generated from terrain colours (Pillow → DDS via `texconv`-free path: write uncompressed DDS header ourselves).

- [ ] Write tests: `test_lake_only_province_not_coastal`; `test_sea_touching_province_is_coastal`; `test_rivers_have_single_pixel_width`; `test_rivers_only_on_land`; `test_bmp_formats` (terrain/rivers/trees are 8-bit indexed with vanilla palette; heightmap 8-bit grey; provinces 24-bit; sizes multiples of 256).
- [ ] Run, expect FAIL. Implement. Run, expect PASS.
- [ ] Commit.

### Task 6: Map definition files

**Files:** Create `tools/mapfiles.py`, `tests/test_mapfiles.py`.

**Interfaces:** Consumes `ProvinceMap`, states. Produces in `mod/map/`: `provinces.bmp`, `definition.csv` (row 0 `0;0;0;0;land;false;unknown;0`), `default.map`, `continent.txt` (one continent `europe`), `adjacencies.csv` (header + `-1` terminator; plus a strait for Askøy/Bømlo bridges where island provinces have no land link), `adjacency_rules.txt`, `buildings.txt`, `unitstacks.txt`, `weatherpositions.txt`, `airports.txt`, `rocketsites.txt`, `cities.txt`, `ambient_object.txt` (empty), `strategicregions/*.txt` (land regions ≈ one per traditional landsdel, ~10; one per sea zone), `railways.txt` (minimum spanning tree over state capitals along adjacent provinces, level 1–3 by population), `supply_nodes.txt` (each state capital province).

Positions are generated from province centroids; the playtester can fix odd ones later with the in-game nudger.

- [ ] Write tests: `test_definition_matches_bitmap` (every bitmap colour in the CSV and vice versa); `test_every_province_in_one_strategic_region`; `test_railways_connect_only_adjacent_provinces`; `test_supply_node_in_every_state_capital`; `test_unitstacks_cover_every_land_province`.
- [ ] Run, expect FAIL. Implement. Run, expect PASS.
- [ ] Commit.

### Task 7: History, countries and vanilla replacement

**Files:** Create `tools/history.py`, `tests/test_history.py`, `descriptor.mod` template.

**Interfaces:** Consumes states, factions, `ProvinceMap`. Produces under `mod/`: `history/states/<id>-<key>.txt` (owner, controller, add_core_of for the owner **and** `NOR`, manpower from population, state category from population, VP on the city province), `history/countries/<TAG> - <Name>.txt` (capital, 2030 politics placeholder, `WFR` as puppet of `NOR` via `set_autonomy`/`puppet` in NOR's file), `common/country_tags/00_countries.txt`, `common/countries/<Name>.txt` (colour, graphical culture), `common/bookmarks/2030.txt` (date `2030.1.1.12`), `localisation/english/nwc_*_l_english.yml` (UTF-8 with BOM: state, VP and country names), placeholder flags `gfx/flags/<TAG>.tga` (+ medium/small) as solid faction colour, and `descriptor.mod` with `replace_path` for `history/states`, `history/countries`, `history/units`, `common/country_tags`, `common/bookmarks`, `common/national_focus`, `events`, `common/decisions`, `common/ai_strategy`, `common/ai_areas`, `map/strategicregions`, `map/supplyareas`; each tag gets an empty `history/units/<TAG>_2030.txt`.

- [ ] Write tests: `test_every_state_file_has_owner_from_ownership`; `test_state_ids_match_registry`; `test_wfr_is_puppet_of_nor`; `test_ana_owns_every_pocket_state`; `test_localisation_has_bom`; `test_every_tag_has_flag_files`.
- [ ] Run, expect FAIL. Implement. Run, expect PASS.
- [ ] Commit.

### Task 8: Build, install and playtest

**Files:** Create `tools/build.py`, `tools/check_log.py`, `tests/test_build.py`, `README.md`.

**Interfaces:** `make build` → `python -m tools.build all`; `make install` symlinks `mod/` to `~/Documents/Paradox Interactive/Hearts of Iron IV/mod/norway_civil_war` and writes `norway_civil_war.mod` there. `check_log.py <error.log>` prints only map/state/province/country errors and exits 1 if any.

- [ ] Write `test_build_twice_is_identical` (two full builds produce byte-identical `mod/`) and `test_check_log_flags_province_errors` (sample log lines → exit 1; a log with only unrelated vanilla noise → exit 0).
- [ ] Run, expect FAIL. Implement. Run, expect PASS.
- [ ] `make build install`. With HOI4 installed, launch with the mod, start the 2030 bookmark as Norway, wait for the map to load, quit; run `python tools/check_log.py ~/Documents/Paradox\ Interactive/Hearts\ of\ Iron\ IV/logs/error.log`. Expect exit 0. Fix and repeat until clean.
- [ ] Write README playtest checklist for the playtester: map looks like Norway; every faction where the approved map puts it; anarchist pockets visible; Sweden neutral; Oslo is JNP; Bergen is its own city; units can move across the map and by sea.
- [ ] Commit; render `reference/ingame_vs_approved.png` (screenshot next to faction map) after the playtester's first run.
