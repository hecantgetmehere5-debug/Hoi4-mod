# Faction Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every playable faction a national focus tree (a war section plus ideology paths), and add the Storting, Swedish Opinion and Denmark trade mechanics and the links between factions described in the spec.

**Architecture:** All script is written by hand under `content/` (`common/national_focus`, `common/decisions`, `common/decisions/categories`, `events`, `common/scripted_effects`, `common/scripted_triggers`, `common/ideas`, `common/on_actions`, `localisation/english`). `make build` copies it into `mod/`. New tags (Reindeer Nation, Great Muslim Oslo Republic, Neutral Coalition mini-states) go into `data/factions.yaml` as `spawn: true` entries with no states, and `tools/history.py` generates their files. A new static linter, `tools/lint_content.py`, parses the Clausewitz script, and `tests/test_content.py` runs it against `content/` so every task is checked by pytest. The game is never launched.

**Tech Stack:** HOI4 1.19.4 script (no DLC), Python 3 + pytest, PyYAML.

**Spec:** `docs/superpowers/specs/2026-11-04-faction-content-design.md`

## Global Constraints

- HOI4 1.19.4 base game, no DLC. Use only base-game focus/decision/effect syntax and vanilla `GFX_goal_*` / `GFX_decision_*` icons.
- All hand-written script lives under `content/`. Nothing in `mod/` is edited by hand. `make build` copies the script.
- Country history changes go into `tools/history.py` / `data/factions.yaml`, never into `content/`.
- Every new id uses the `nwc_` prefix (focus, decision, category, event namespace, idea, flag, variable, temp variable, scripted effect/trigger).
- Localisation is UTF-8 with a BOM in `content/localisation/english/nwc_*_l_english.yml`. Each file starts with `l_english:`.
- State references use `@STATE:key@` / `@VP:key@` tokens. Keys must exist in `data/states.yaml`.
- Every event follows the existing pattern: `is_triggered_only = yes` (unless it is mean-time-to-happen), `immediate = { log = "NWC event <id> fired" }`, `picture = GFX_report_event_generic_read_write`, and localisation keys `<id>.t`, `<id>.d`, `<id>.a`... for each option.
- Placeholder flavour text is allowed. Write it as one short neutral sentence, because the user writes the story later.
- Ideology paths open **during** the civil war. Every tree has a war section and the paths sit alongside it.
- Storting runs on every Government path **except Fascism**.
- Swedish puppet takeover = game over for the Government. Mechanism: `nwc_sweden.4` makes NOR a SWE puppet, sets global flag `nwc_game_over_sweden`, fires news event `nwc_news.20` "Norway Falls Under Swedish Rule", and if NOR is player-controlled the player is moved to SWE's puppet with no way back: the `nwc_game_over_sweden` flag hides every NOR decision category and makes every NOR focus `available = { always = no }` via the scripted trigger `nwc_gov_alive` (defined in Task 4, checked in every NOR focus `available` and every NOR decision category `visible`). The game continues, but the Government's story is over.
- Tests run with `.venv/bin/python -m pytest -q`. All 75 existing tests must stay green.

## Review Focus

1. **Mutually exclusive branches that are only one-sided.** A player can take both branches if `mutually_exclusive` is listed on only one focus. Linter test `test_mutually_exclusive_symmetric` (Task 1).
2. **Event or focus referencing a tag that does not exist** (for example a typo like `NRN`, or a spawn tag missing from `factions.yaml`). The reference should resolve, otherwise the game silently does nothing. Linter test `test_tag_references_exist` (Task 1).
3. **Storting odds outside 0–100** after concessions stack up. Odds must be clamped so the bill can always pass or fail. Test `test_storting_support_clamped` (Task 3).
4. **Swedish Opinion bands overlapping or leaving gaps**, so that no band fires or two bands fire in the same month. Test `test_swedish_bands_partition` (Task 4).
5. **Flags or variables checked but never set** (for example `has_country_flag = nwc_elk_path` when the setter is spelled differently). The branch would become unreachable. Linter test `test_flags_set_somewhere` (Task 1).

---

## File Structure

| Path | Responsibility |
|---|---|
| `tools/pdx.py` | Clausewitz parser: `parse(text) -> list[Node]`, where `Node = (key, op, value)` and `value` is `str` or `list[Node]` |
| `tools/lint_content.py` | `lint(root: Path) -> list[str]` returns error messages. It collects ids and references across `content/`. CLI: `python -m tools.lint_content` |
| `tests/test_content.py` | Runs the linter on `content/` and unit-tests the linter on small fixtures |
| `content/common/scripted_effects/nwc_storting_effects.txt`, `content/common/scripted_triggers/nwc_storting_triggers.txt`, `content/common/decisions/nwc_storting.txt`, `content/events/nwc_storting.txt` | Storting |
| `content/common/scripted_effects/nwc_sweden_effects.txt`, `content/events/nwc_sweden.txt`, `content/common/decisions/nwc_sweden.txt` | Swedish Opinion |
| `content/common/national_focus/nwc_<tag>.txt` (one per faction) | Focus trees |
| `content/events/nwc_<tag>.txt` | Faction events |
| `content/localisation/english/nwc_<topic>_l_english.yml` | One localisation file per task |
| `content/common/decisions/categories/nwc_categories.txt` | All decision categories |
| `content/common/on_actions/nwc_on_actions.txt` | Extended with the monthly pulse |

The lint/test patterns live in Task 1. Later tasks reference it as "the content lint" and pass when `tests/test_content.py` is green.

---

### Task 1: Content parser, linter and test harness

**Files:**
- Create: `tools/pdx.py`, `tools/lint_content.py`, `tests/test_content.py`, `tests/fixtures/lint/` (small good and bad `.txt` / `.yml` samples)
- Modify: `Makefile` (add a `lint` target: `$(PY) -m tools.lint_content`, and add `lint` to the `.PHONY` line: `.PHONY: setup fetch build test install lint`)

**Interfaces:**
- Produces:
  - `pdx.parse(text: str) -> list[tuple[str, str, str | list]]`. It raises `pdx.ParseError(line: int, msg)` on an unbalanced brace or an unterminated string. It handles `#` comments, quoted strings, and the operators `= < > <= >=`.
  - `lint_content.lint(root: Path, factions: Path = DATA/"factions.yaml", vanilla: Path = DATA/"vanilla_tags.txt", states: Path = DATA/"states.yaml") -> list[str]`
  - `lint_content.collect(root) -> Index`. `Index` is a dataclass with these sets: `focuses`, `decisions`, `categories`, `events`, `ideas`, `scripted_effects`, `scripted_triggers`, `country_flags_set`, `country_flags_checked`, `global_flags_set`, `global_flags_checked`, `vars_set`, `vars_checked`, `loc_keys`, `tags_referenced`, plus `mutex: dict[str, set[str]]` and `prereqs: dict[str, set[str]]`.

- [ ] **Step 1: Write failing tests** in `tests/test_content.py`
  - `test_parse_nested`: `parse('a = { b = 1 c = "x y" }') == [("a","=",[("b","=","1"),("c","=","x y")])]`
  - `test_parse_unbalanced_raises`: `parse("a = {")` raises `ParseError`
  - `test_content_lints_clean`: `lint(Path("content")) == []`
  - Fixture-driven, one bad fixture each, each asserting a specific message substring:
    - `test_unlocalised_focus` → `"missing loc: nwc_x_focus"`
    - `test_unlocalised_focus_desc` → `"missing loc: nwc_x_focus_desc"`
    - `test_unknown_prerequisite` → `"unknown focus"`
    - `test_mutually_exclusive_symmetric` → `"mutex not symmetric"`
    - `test_unknown_event_id` → `"unknown event"` (covers `country_event`/`news_event` `id = ` and the `days` chain form)
    - `test_tag_references_exist` → `"unknown tag"`. Tags come from `factions.yaml` plus `vanilla_tags.txt`. Check `TAG = {` scopes, `tag =`, `original_tag =`, `puppet =`, `annex_country = { target = }`, `declare_war_on = { target = }`, and `has_war_with`.
    - `test_flags_set_somewhere` → `"flag never set"`. Check `has_country_flag` only against `set_country_flag`, and `has_global_flag` only against `set_global_flag` (a global flag never satisfies a country-flag check). Do the same for variables: `check_variable` and variables read in `var =`/arithmetic against `set_variable`/`add_to_variable`/`set_variable_to_random`/`set_temp_variable*`/`set_temp_variable_to_random` (variables and temp variables share `vars_set`). Fixture pairs cover a misspelled flag, a global/country mismatch, and an unset variable.
    - `test_unknown_state_token` → `"unknown state key"`
    - `test_loc_bom_and_header` → `"no BOM"` / `"missing l_english"`
    - `test_duplicate_ids` → `"duplicate focus"` (also covers decisions and events)
    - `test_unknown_idea` → `"unknown idea"` (covers `add_ideas`/`remove_ideas`/`swap_ideas`, and ignores vanilla ideas listed in a whitelist set `VANILLA_IDEAS` inside the linter, initially empty)
    - `test_unknown_scripted_effect`: a key ending in `= yes` that matches the `nwc_` prefix and is not defined → `"unknown scripted effect"`
    - `test_focus_tree_has_country_factor`: each `focus_tree` must contain `country = { factor = 0 modifier = { add = 10 tag = X } }` naming a known tag
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_content.py -q`. Expected: FAIL (`ModuleNotFoundError: tools.pdx`).
- [ ] **Step 3:** Implement `tools/pdx.py` with a hand-written tokenizer and a recursive descent parser.
- [ ] **Step 4:** Implement `tools/lint_content.py`. `collect` walks every `.txt` under `root` (parsing each one) and every `.yml` (with key regex `^\s+([\w.]+):\d?\s`). `lint` derives the errors. Localisation is required for: focus `id` and `id_desc`; decision id and `id_desc`; category id; event `.t`/`.d` and each option `name`; idea id. Existing `content/` files must lint clean. Fix real defects found there in this task.
- [ ] **Step 5:** Run `.venv/bin/python -m pytest -q`. Expected: all pass (75 + new).
- [ ] **Step 6:** Commit: `git add tools/pdx.py tools/lint_content.py tests/test_content.py tests/fixtures Makefile && git commit -m "Add content parser and linter with tests"`

---

### Task 2: Spawnable tags infrastructure

**Files:**
- Modify: `data/factions.yaml`, `tools/history.py`, `tests/test_history.py`

**Interfaces:**
- Produces:
  - In `factions.yaml`, a flag `spawn: true`. A spawn tag owns no states, gets a history file with `capital = <its capital key's state>` and no `owner`, a country file, a flag and localisation. Any reused vanilla tag is added to `history.VANILLA_COUNTRY_FILES` with its vanilla file name.
  - Tags:
    - `RDN` Reindeer Nation (new, capital `voss`)
    - `GMO` Great Muslim Oslo Republic (new, capital `oslo`)
    - Neutral Coalition mini-states reusing vanilla tags. Each canton gets a `cantons:` list in `factions.yaml` naming the NCL states (keys in `data/states.yaml`) it receives in Task 13; the first is its capital:
      | Tag | Name | Capital | States |
      |---|---|---|---|
      | `EST` | Hedmarken Canton | `hamar` | `hamar`, `ringsaker` |
      | `LAT` | Gudbrandsdal Canton | `lillehammer` | `lillehammer`, `midt_gudbrandsdal`, `nord_gudbrandsdal` |
      | `LIT` | Valdres Canton | `valdres` | `valdres` |
      | `ICE` | Østerdal Canton | `sor_osterdal` | `sor_osterdal`, `nord_osterdal`, `trysil` |
      | `SCO` | Hadeland Canton | `land` | `land` |
    - Reused vanilla tags: add `"EST": "Estonia", "LAT": "Latvia", "LIT": "Lithuania", "ICE": "Iceland", "SCO": "Scotland"` to `history.VANILLA_COUNTRY_FILES`. `write_countries` overwrites their vanilla country file, and the history writer emits `history/countries/<TAG> - <vanilla name>.txt` with exactly the vanilla file name so the vanilla history (states, leaders, OOB) is replaced, not duplicated. Their vanilla state ownership is irrelevant because vanilla states are already switched off.
    - Because these five are in `VANILLA_COUNTRY_FILES`, the existing `test_new_tags_do_not_clash_with_vanilla` (`(tag in taken) == (tag in VANILLA_COUNTRY_FILES)`) passes for them without changes; RDN and GMO must not be vanilla tags.
  - `FRP` is not removed by the merge with NRM, and no new tag is needed for it.
- [ ] **Step 1: Write failing tests**
  - `test_spawn_tags_have_files_but_no_states`: for each `spawn` tag there is a history file, a country file and a flag, and the tag owns no state.
  - `test_spawn_tags_in_tag_list`: each new spawn tag (RDN, GMO) appears in `common/country_tags`; reused vanilla tags do not get a second entry.
  - `test_reused_tag_history_overwrites_vanilla`: for EST, LAT, LIT, ICE, SCO the generated history file name equals the vanilla file name and contains no `owner`/`set_politics` leftovers from vanilla.
  - `test_canton_states_owned_by_ncl`: every state in a `cantons:` list is owned by NCL in the generated history.
  - The existing `test_new_tags_do_not_clash_with_vanilla` must still pass.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Add the entries and handle `spawn` in `history.country_history` and `write_countries`. Skip spawn tags in ownership and unit generation.
- [ ] **Step 4:** Run `pytest -q`. Expected: all pass.
- [ ] **Step 5:** Commit: `"Add spawnable tags for Reindeer Nation, Oslo Republic and NCL cantons"`

---

### Task 3: Storting mechanic (Government)

**Files:**
- Create: `content/common/scripted_effects/nwc_storting_effects.txt`, `content/common/scripted_triggers/nwc_storting_triggers.txt`, `content/common/decisions/nwc_storting.txt`, `content/common/decisions/categories/nwc_categories.txt`, `content/events/nwc_storting.txt`, `content/localisation/english/nwc_storting_l_english.yml`
- Modify: `content/common/scripted_effects/nwc_scripted_effects.txt` (`nwc_game_start` calls `nwc_storting_init = yes`)
- Test: `tests/test_content.py`

**Interfaces:**
- Produces (all on NOR scope):
  - Variables `nwc_ap_support` and `nwc_h_support` (0–100, the percentage of each bloc voting yes), `nwc_bill_amend` (amendments on the pending bill, 0–2, reset when a bill is proposed).
  - Temp variables (not stored): `nwc_vote_roll`, `nwc_vote_share`, `nwc_bill_ap_base`, `nwc_bill_h_base`.
  - Flags `nwc_bill_<name>_pending`, `nwc_bill_<name>_passed`, `nwc_storting_suspended`.
  - Scripted effects:
    - `nwc_storting_init`: sets both supports to 40.
    - `nwc_storting_clamp`
    - `nwc_storting_vote`: rolls and fires `nwc_storting.2` (passed) or `nwc_storting.3` (failed).
    - `nwc_propose_bill`: expects temp vars `nwc_bill_ap_base`/`nwc_bill_h_base` set by the caller.
  - Scripted trigger `nwc_storting_active = { NOT = { has_country_flag = nwc_storting_suspended } }`.
  - Decision category `nwc_storting_category`, visible when `nwc_storting_active = yes`.
  - Bill pattern, used by Task 4 (Sweden) and Task 5 (Government): one decision `nwc_propose_<bill>` per bill. When the bill passes, the vote event's option calls `nwc_bill_<bill>_effect = yes`.
- Rules (from the spec):
  - Yes share = `(nwc_ap_support + nwc_h_support) / 2`, stored in temp var `nwc_vote_share`.
  - Gate: if `nwc_vote_share <= 70` the bill fails outright (`nwc_storting.3`). A bill can never pass at 70 or below.
  - Luck, only above 70: `set_temp_variable_to_random = { var = nwc_vote_roll min = 0 max = 100 }`. Pass chance = `clamp(60 + (share - 70) * 2, 0, 100)`: 60% just above 70, 80% at 80, 100% at 90+. Pass if `nwc_vote_roll < chance`.
  - Concession decisions:
    - `nwc_concede_to_ap` and `nwc_concede_to_h`: cost 25 PP, +15 to that bloc, −5 to the other.
    - `nwc_amend_bill`: cost 10 PP, +5 to both, increments `nwc_bill_amend`. Limit 2 per bill (`available` checks `nwc_bill_amend < 2`). Each amendment halves the bill's payoff, so a concession (net +5 average, full payoff) and an amendment (+5 average, weaker bill) are a real trade-off.
    - Amendment scaling uses tiered static ideas, not a multiplier: every bill with a modifier defines three ideas `nwc_bill_<name>_full`, `_amended1` (half), `_amended2` (quarter). `nwc_bill_<name>_effect` picks the idea with `if`/`else_if` on `nwc_bill_amend` (0/1/2). Bills whose payoff is a variable change (e.g. Swedish opinion) instead add `10 / 5 / 3` by the same tier check. No dynamic modifier is needed.
  - After every change, the supports are clamped to 0–100.
- [ ] **Step 1: Write failing tests** (static, parsing the built script):
  - `test_storting_files_exist_and_lint`
  - `test_storting_support_clamped`: every `add_to_variable` on `nwc_ap_support`/`nwc_h_support` in `content/` sits in a block that also calls `nwc_storting_clamp = yes`. The test parses the files and walks the blocks.
  - `test_storting_threshold`: `nwc_storting_vote` contains `check_variable = { nwc_vote_share > 70 }` guarding the roll, and the fail event is fired in the `else` branch with no roll.
  - `test_amend_limited`: `nwc_amend_bill`'s `available` checks `nwc_bill_amend < 2`, and every `nwc_bill_*_effect` branches on `nwc_bill_amend`.
  - `test_fascism_suspends_storting`: the Fascism focus (Task 5) sets `nwc_storting_suspended`. Mark this test `xfail(strict=True)` until Task 5 lands, then remove the marker.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Write the script and localisation. Include one test bill, `nwc_bill_emergency_budget`, which gives +10% / +5% / +2.5% factory output for 180 days (ideas `nwc_bill_emergency_budget_full/_amended1/_amended2`), so the mechanic is playable on its own.
- [ ] **Step 4:** Run `pytest -q` and `make build`. Expected: pass, and `mod/common/decisions/nwc_storting.txt` exists.
- [ ] **Step 5:** Commit: `"Add Storting bill, concession and vote mechanic"`

---

### Task 4: Swedish Opinion

**Files:**
- Create: `content/common/scripted_effects/nwc_sweden_effects.txt`, `content/events/nwc_sweden.txt`, `content/common/decisions/nwc_sweden.txt`, `content/common/ideas/nwc_sweden_ideas.txt`, `content/localisation/english/nwc_sweden_l_english.yml`
- Modify: `content/common/on_actions/nwc_on_actions.txt` (add `on_monthly_NOR = { effect = { nwc_sweden_monthly = yes } }` **inside the existing single `on_actions = { ... }` block**, next to `on_startup`; do not add a second top-level `on_actions` block), `nwc_game_start` (call `nwc_sweden_init`)

**Interfaces:**
- Consumes: the Task 3 bill pattern and `nwc_storting_category`.
- Produces:
  - Global variable `nwc_swe_opinion` (0–100, starts at 50).
  - Scripted effects `nwc_swe_opinion_add` (reads temp var `nwc_swe_delta`, then clamps) and `nwc_swe_set_max`.
  - Variable `nwc_swe_low_months` (consecutive months below 20). Global flag `nwc_game_over_sweden`. Scripted trigger `nwc_gov_alive = { NOT = { has_global_flag = nwc_game_over_sweden } }`.
  - Flags `nwc_swe_stance_neutral|aid|intervene|puppet`.
  - Events:
    - `nwc_sweden.1`: aid begins (fires once on entering the aid band). While the stance flag is `aid`, `nwc_sweden_monthly` has SWE `send_equipment = { equipment = infantry_equipment amount = 500 target = NOR }` and `send_equipment = { equipment = support_equipment amount = 50 target = NOR }` each month.
    - `nwc_sweden.2`: Sweden intervenes for NOR. SWE joins NOR's war with `add_to_war = { targeted_alliance = NOR enemy = <each enemy> }` for every country at war with NOR (`every_country = { limit = { has_war_with = NOR } ... }`).
    - `nwc_sweden.3`: Sweden warns.
    - `nwc_sweden.4`: puppet takeover, displeased band only. Effects in order: `SWE = { puppet = NOR }` (NOR keeps its wars; no white peace), `set_global_flag = nwc_game_over_sweden`, `news_event = { id = nwc_news.20 }`. The game-over mechanism is the one in Global Constraints (`nwc_gov_alive` locks the tree and decisions).
    - `nwc_sweden.6`: Sweden opposes the Danish union. Fired once when `nwc_union_denmark` is set (after `nwc_denmark.2`). SWE `declare_war_on = { target = NOR type = annex_everything }` and `declare_war_on = { target = DEN type = topple_government }`. This is not a game over; the player fights Sweden with Denmark as overlord. Does not touch `nwc_game_over_sweden`.
    - `nwc_sweden.5`: Swedish-sponsored person offered. Mean-time-to-happen country event for NOR, `mean_time_to_happen = { days = 180 }`, trigger: opinion ≥ 40, `nwc_gov_alive = yes`, fewer than 3 `nwc_swe_advisor_*` ideas taken. Option A adds the next advisor idea `nwc_swe_advisor_<n>` and +8 opinion; option B refuses (−3 opinion). This is the only opinion source that works under Fascism.
  - Bills `nwc_bill_swe_trade`, `nwc_bill_swe_border` and `nwc_bill_swe_defence`, each worth +10 opinion on pass (scaled by amendments).
  - Ideas `nwc_swe_advisor_1..3`.
- Bands (checked monthly, each band exclusive):
  - **0–19 displeased.** Fire `.3` as a warning the first time. Fire `.4` if the opinion is still below 20 after 2 consecutive months.
  - **20–54 neutral.**
  - **55–79 aid.**
  - **80–100 intervene.** Fires `.2` once.
  - Union with Denmark (flag `nwc_union_denmark`) fires `.6` once regardless of opinion and stops band processing (no `.1`/`.2`/`.4` afterwards). Order: focus `nwc_nor_union_denmark` → `nwc_denmark.2` (DEN puppets NOR; the focus already set `nwc_union_denmark`) → next monthly pulse → `nwc_sweden.6`. Only DEN ever puppets NOR on this path.
  - Union with Sweden calls `nwc_swe_set_max`.
- [ ] **Step 1: Write failing tests**
  - `test_swedish_bands_partition`: parse the `check_variable` bounds in `nwc_sweden_monthly`. Assert they cover 0–100 with no overlap and no gap (boundaries 20, 55, 80).
  - `test_union_denmark_war`: `nwc_sweden_monthly` checks `nwc_union_denmark` before the bands and fires `nwc_sweden.6`; `nwc_sweden.6` declares war on NOR and DEN and contains no `puppet`.
  - `test_puppet_is_game_over`: `nwc_sweden.4` contains `puppet = NOR` in SWE scope, sets `nwc_game_over_sweden` and fires `nwc_news.20`; every NOR focus `available` and every NOR decision category `visible` calls `nwc_gov_alive = yes` (checked once Task 5 lands; xfail strict until then).
  - `test_displeased_needs_two_months`: `.4` is gated on `nwc_swe_low_months >= 2`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Write the script and localisation.
- [ ] **Step 4:** Run `pytest -q`. Expected: pass.
- Fascism: the Storting is suspended, so the three Swedish bills are unavailable. This is intentional: a Fascist Government is cut off from Sweden by design and can raise opinion only through `nwc_sweden.5` advisors. State this in the Fascism focus description.
- [ ] **Step 5:** Commit: `"Add Swedish Opinion mechanic with bands, aid, intervention and puppet ending"`

---

### Task 5: Government (NOR) focus tree and fork events

**Files:**
- Create: `content/common/national_focus/nwc_nor.txt`, `content/events/nwc_gov.txt`, `content/common/ideas/nwc_gov_ideas.txt`, `content/localisation/english/nwc_gov_l_english.yml`
- Modify: `content/events/nwc_siege.txt`. Reuse the existing leader events, do not add new ones:
  - Held branch: `nwc_siege.6` already kills Støre (`kill_country_leader`, `nwc_news.3`). Add to its option `set_country_flag = nwc_oslo_held`, `set_country_flag = nwc_gov_branch_held`, and `country_event = { id = nwc_links.5 days = 365 }` (the JNP white peace timer, Task 16).
  - Taken branch: in both options of `nwc_siege.7` change `country_event = { id = nwc_siege.10 days = 60 random_days = 60 }` to `days = 30` (the spec's ~30 days) and add `set_country_flag = nwc_oslo_taken`. `nwc_siege.10` (Støre resigns, `retire_country_leader`) adds `set_country_flag = nwc_gov_branch_taken`.

**Interfaces:**
- Consumes: Storting (Task 3), Swedish Opinion (Task 4).
- Produces:
  - Tree id `nwc_nor_focus`.
  - Flags `nwc_oslo_held`, `nwc_oslo_taken`, `nwc_gov_branch_held`, `nwc_gov_branch_taken` (set in `nwc_siege.6` / `.7` / `.10`).
  - Scheduled event `nwc_links.5` 365 days after Støre's death (replaces any date variable; no `nwc_stoere_dead_date`).
  - Path flags `nwc_gov_hoyre`, `nwc_gov_fascism`, `nwc_gov_oligarchy`, `nwc_gov_crown`, `nwc_union_denmark`, `nwc_gov_independent_kingdom`, `nwc_union_sweden`, `nwc_gov_ap`, `nwc_gov_ai_technocracy`, `nwc_gov_socialist`, `nwc_elk_path`. Other tasks read these flags.
  - Focus `nwc_nor_rebesiege_oslo`, available on the Høyre/Crown paths. Task 16 wires it.
- Content:
  - **War section** (about 8 focuses, no prerequisites on the fork): army, economy, siege.
  - **Fork:**
    - No new fork events. `nwc_siege.6` (assassination) and `nwc_siege.10` (resignation, now 30 days) set `nwc_gov_branch_held` / `nwc_gov_branch_taken`, which make the two branch roots `available`. `nwc_gov.txt` holds only path events.
  - **Held branch:**
    - `nwc_nor_hoyre` leads to the mutually exclusive pair `nwc_nor_fascism` (sets `nwc_storting_suspended` and `nwc_gov_fascism`) and `nwc_nor_oligarchy`.
    - `nwc_nor_crown` leads to three mutually exclusive focuses: `nwc_nor_union_denmark`, `nwc_nor_independent_kingdom`, `nwc_nor_union_sweden` (the last calls `nwc_swe_set_max`).
    - The Hoyre and Crown roots are mutually exclusive.
  - **Taken branch:**
    - `nwc_nor_ap` leads to the mutually exclusive pair `nwc_nor_ai_technocracy` and `nwc_nor_socialist`.
    - `nwc_nor_elk` is the joke path. It sets `nwc_elk_path` and swaps the leader to an elk character `nwc_nor_elk_pm` with `create_country_leader`.
    - The AP and Elk roots are mutually exclusive.
  - Each final path focus sets the ruling party with `set_politics` and adds one path idea.
  - At least 2 focuses per path propose a Storting bill.
- [ ] **Step 1: Write failing tests**
  - `test_nor_tree_paths`: parse the tree and assert that every path flag above is set by exactly one focus.
  - `test_nor_branches_exclusive`: `nwc_nor_hoyre` is mutually exclusive with `nwc_nor_crown`, and `nwc_nor_ap` with `nwc_nor_elk`.
  - `test_fork_events_scheduled`: `nwc_siege.6` sets `nwc_oslo_held` and `nwc_gov_branch_held` and schedules `nwc_links.5` with `days = 365`; `nwc_siege.7` sets `nwc_oslo_taken` and schedules `nwc_siege.10` with `days = 30` and no `random_days`; `nwc_siege.10` sets `nwc_gov_branch_taken`; no other event in `content/` contains `kill_country_leader` or `retire_country_leader` for NOR.
  - Every NOR focus `available` includes `nwc_gov_alive = yes`; remove the xfail on `test_puppet_is_game_over`.
  - Remove the xfail marker from `test_fascism_suspends_storting`.
  - The content lint stays green.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Write the tree, events, ideas and localisation. Lay out the positions with `relative_position_id`.
- [ ] **Step 4:** Run `pytest -q && make build`. Expected: pass.
- [ ] **Step 5:** Commit: `"Add Government focus tree with Oslo fork and paths"`

---

### Tasks 6–15: Faction trees

Every faction task follows the same steps and shape:

**Files:**
- Create: `content/common/national_focus/nwc_<tag>.txt`
- Create: `content/events/nwc_<tag>.txt` (only if the task needs events)
- Create: `content/localisation/english/nwc_<tag>_l_english.yml`
- Optional: `content/common/ideas/nwc_<tag>_ideas.txt`

**Steps:**
- [ ] **1. Write the failing test** `test_<tag>_tree_paths` in `tests/test_content.py`. It asserts:
  - the tree id is `nwc_<tag>_focus` and its country factor names the right tag(s) (the JNP tree names both `JNP` and `GMO`);
  - each listed path flag is set by exactly one focus;
  - the listed mutually exclusive pairs exist (symmetry is already checked by the lint).
- [ ] **2.** Run the test. Expected: FAIL.
- [ ] **3.** Write a war section of about 6 focuses, plus the paths. Each path root is `available` during the war. Each final path focus sets politics and adds one idea.
- [ ] **4.** Run `pytest -q`. Expected: pass.
- [ ] **5.** Commit `"Add <TAG> focus tree"`.

| Task | Tag | Flags (each set by one focus) | Exclusive structure / extra |
|---|---|---|---|
| 6 | WFR | `nwc_wfr_military_reform` | Military tree only. Events `nwc_wfr.1` "Supply Package from Oslo" and `nwc_wfr.2` "Volunteers from the East" fire from focuses and need NOR to exist. Default ending (spec: merges back after the war; not yet in `content/`, covered here): event `nwc_wfr.3` "Return to the Government" for NOR, fired by `nwc_wfr_monthly` check in `on_monthly_NOR` when NOR is at peace (`has_war = no`), WFR exists and `nwc_wfr_breakaway_done` is not set: `NOR = { annex_country = { target = WFR transfer_troops = yes } }`. Decision `nwc_wfr_reindeer_breakaway` is wired in Task 16. |
| 7 | JNP | `nwc_jnp_fortify` | War tree only, no expansion. Country factor: `modifier = { add = 10 tag = JNP }` and `modifier = { add = 10 tag = GMO }` (GMO reuses this tree). The white peace and the switch to GMO happen in Task 16. |
| 8 | KRF | `nwc_krf_orthodox`, `nwc_krf_abyzov`, `nwc_krf_monastery`, `nwc_krf_protestant`, `nwc_krf_nondenom`, `nwc_krf_luther`, `nwc_krf_catholic`, `nwc_krf_crusade`, `nwc_krf_papacy` | The church is picked in a decision category `nwc_krf_church_category` with 3 decisions (`nwc_krf_choose_orthodox`/`_protestant`/`_catholic`). Each sets its church flag, and the visible triggers make them exclusive. The 6 sub-path focuses form exclusive pairs under their church. Abyzov creates the leader `nwc_krf_abyzov_leader`. |
| 9 | SOC | `nwc_soc_rodt_sv`, `nwc_soc_democratic`, `nwc_soc_micro`, `nwc_soc_hardline`, `nwc_soc_left` | The `rodt_sv` and `micro` roots are exclusive, and so are `hardline` and `left`. The third path is a stub (Task 18). |
| 10 | FRP | `nwc_frp_libertarian`, `nwc_frp_accelerationist` | The two are exclusive. Focus `nwc_frp_offer_union` is under the accelerationist path and is wired in Task 16. |
| 11 | NRM | `nwc_nrm_neonazi`, `nwc_nrm_viking`, `nwc_nrm_ingsoc` | Three-way exclusive. |
| 12 | SAP | `nwc_sap_nationalism`, `nwc_sap_reindeer`, `nwc_sap_portal` | Three-way exclusive. The portal ending is a stub (Task 18). |
| 13 | NCL | `nwc_ncl_decentral`, `nwc_ncl_pagan` | Exclusive. The final decentral focus, for each canton in the Task 2 table: `every_state = { limit = { <state in canton list> } add_core_of = <TAG> }`, then `release_puppet = <TAG>` (which releases the tag's owned cores as NCL's puppet). Test `test_ncl_cantons_cored`: each canton tag gets `add_core_of` on every state in its list before its `release_puppet`. The existing idea `nwc_civilian_boom` stays. |
| 14 | ABI | `nwc_abi_anarcho`, `nwc_abi_ancom`, `nwc_abi_syndicalism`, `nwc_abi_distributist`, `nwc_abi_georgist`, `nwc_abi_egoism` | The anarcho and distributist leans are exclusive, and each pair under them is exclusive. |
| 15 | BRG | `nwc_brg_merchant`, `nwc_brg_coop_abi` | Exclusive. Merchant gives dockyards and convoys. `coop_abi` is wired in Task 16. |

For SAP, add a test `test_sap_portal_is_stub`: the portal end focus sets `nwc_sap_portal_opened` and has no other effect except a `log`.

---

### Task 16: Cross-faction links

**Files:**
- Create: `content/events/nwc_links.txt`, `content/common/decisions/nwc_links.txt`, `content/localisation/english/nwc_links_l_english.yml`
- Modify: the trees from Tasks 5–15, to call the link events

**Interfaces:**
- Consumes: the path flags from Tasks 5–15 and the spawn tags from Task 2.
- Links:
  1. **FrP–NRM union.** `nwc_frp_offer_union` sends `nwc_links.1` to NRM. NRM can accept from any path. If accepted, `FRP = { annex_country = { target = NRM transfer_troops = yes } }` and the flag `nwc_frp_nrm_union` is set. If refused, `nwc_links.2` goes back to FRP.
  2. **Reindeer Nation.** The WFR decision `nwc_wfr_reindeer_breakaway` is available when NOR has `nwc_elk_path`. Effect order: `set_global_flag = nwc_wfr_breakaway_done` (blocks the `nwc_wfr.3` merge); `NOR = { end_puppet = WFR }`; WFR leaves NOR's wars (`WFR = { white_peace = <each enemy> }` via `every_country = { limit = { has_war_with = WFR } }`); `every_state = { limit = { is_owned_by = WFR } RDN = { transfer_state = PREV } }`, so WFR is left with no states and ceases to exist (no `annex_country`); then `RDN = { declare_war_on = { target = NOR type = annex_everything } }`, and `nwc_links.3` news event "The Animal Civil War" fires. If SAP has `nwc_sap_reindeer`, `nwc_links.4` offers SAP an alliance with RDN (`create_faction`/`add_to_faction`).
  3. **JNP white peace.** `nwc_links.5` is a triggered-only NOR event (`is_triggered_only = yes`), scheduled by `nwc_siege.6` with `days = 365` (Task 5). Its `trigger` re-checks that JNP exists and still owns `@STATE:oslo@`; if not, it does nothing. It makes a white peace with `white_peace = JNP`, then `GMO = { annex_country = { target = JNP transfer_troops = yes } }` (GMO, owning no states, takes JNP's states and troops; no separate state transfer). GMO is a city-state; its tree is the JNP tree (factor written in Task 7).
  4. **Re-besiege Oslo.** `nwc_nor_rebesiege_oslo` is available with `nwc_gov_hoyre` or `nwc_gov_crown` and `GMO` existing. It declares war on GMO and calls the existing `nwc_fortress_large`.
  5. **Bergen–ABI.** `nwc_brg_coop_abi` sends `nwc_links.6` to ABI. If ABI accepts, `ABI = { puppet = BRG }`. BRG keeps its ideology, and the flag `nwc_brg_abi_puppet` is set.
- [ ] **Step 1: Write failing tests**
  - `test_links_tags_resolve`: covered by the lint.
  - `test_reindeer_requires_elk`: the decision's `available` checks `NOR = { has_country_flag = nwc_elk_path }`.
  - `test_white_peace_after_year`: `nwc_links.5` is triggered-only and is scheduled only from `nwc_siege.6` with `days = 365`.
  - `test_reindeer_frees_wfr`: the decision calls `end_puppet` and sets `nwc_wfr_breakaway_done` before RDN's `declare_war_on`, and contains no `release`.
  - `test_rebesiege_gated`: the focus is available only on the Høyre or Crown path.
  - `test_union_needs_acceptance`: the annex happens only inside an NRM event option.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Write the script and localisation.
- [ ] **Step 4:** Run `pytest -q && make build`. Expected: pass.
- [ ] **Step 5:** Commit: `"Wire cross-faction links: FrP-NRM union, Reindeer Nation, Oslo Republic, Bergen-ABI"`

---

### Task 17: Denmark trade deals and the union role

**Files:**
- Create: `content/common/decisions/nwc_denmark.txt`, `content/events/nwc_denmark.txt`, `content/localisation/english/nwc_denmark_l_english.yml`

**Interfaces:**
- Consumes: `nwc_union_denmark` (Task 5) and `nwc_brg_abi_puppet` (Task 16, which does not block these deals).
- Content:
  - BRG decision category `nwc_brg_trade_category` with deals `nwc_brg_trade_den_fish`, `_fuel` and `_arms`. Each one sends `nwc_denmark.1` to DEN. The AI accepts if `DEN` exists. The deal gives a 180-day timed idea to BRG and `add_offsite_building` or an equipment grant. Cooldown is 90 days.
  - The `nwc_nor_union_denmark` focus fires `nwc_denmark.2`, which sets up the personal union: DEN makes NOR a puppet with `DEN = { puppet = NOR }`, NOR keeps its ideology. The flag `nwc_union_denmark` is set by the focus itself (Task 5), in the same effect block before `nwc_denmark.2` fires. Sweden reacts on the next monthly pulse with `nwc_sweden.6` (war, Task 4). DEN is the only country that puppets NOR on this path.
- [ ] **Step 1: Write failing tests**
  - `test_den_trade_deals_bergen_only`: each deal decision has `tag = BRG` in `allowed`.
  - `test_union_denmark_puppets`: `nwc_denmark.2` contains `puppet = NOR` within DEN scope.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Write the script.
- [ ] **Step 4:** Run `pytest -q`. Expected: pass.
- [ ] **Step 5:** Commit: `"Add Denmark trade deals with Bergen and Union with Denmark"`

---

### Task 18: Stubs for open items

**Files:**
- Create: `content/common/national_focus/nwc_ana.txt`, `content/localisation/english/nwc_stubs_l_english.yml`
- Modify: `content/common/national_focus/nwc_soc.txt`, `nwc_sap.txt`

**Content:**
- **ANA:** a war section only, plus one focus `nwc_ana_paths_tbd` that sets `nwc_ana_paths_tbd` and logs.
- **SOC:** a third root `nwc_soc_third_path` with `available = { always = no }`, mutually exclusive with both roots.
- **SAP:** the portal end focus fires `nwc_sap.99` "The Portal Opens". Its only option sets `nwc_sap_portal_opened`. This is the hook for the later world.
- Every stub's localisation reads `"(To be written.)"` so it is easy to find.

**Steps:**
- [ ] **Step 1: Write failing test** `test_stubs_marked`. It checks that each stub id exists and that its localisation contains `(To be written.)`.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Write the stubs.
- [ ] **Step 4:** Run `pytest -q && make build`. Expected: pass.
- [ ] **Step 5:** Commit: `"Add stubs for Anarchist Cells, Socialist third path and Sápmi portal"`

---

### Task 19: Playtest checklist

**Files:**
- Modify: `README.md` (add one checklist line per faction path, the Storting vote and each Swedish band)

**Steps:**
- [ ] **Step 1:** Run `make build && .venv/bin/python -m pytest -q && .venv/bin/python -m tools.lint_content`. Expected: all green, and the lint prints nothing.
- [ ] **Step 2:** Commit: `"Add faction content playtest checklist"`
