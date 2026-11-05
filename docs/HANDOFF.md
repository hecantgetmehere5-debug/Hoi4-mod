# Handoff: state of the project

Read this first if you are an AI or developer picking up work on **Norwegian Civil War 2030**. It covers what exists, where it lives, what is planned, and the rules the owner works by. Last updated 2026-11-05.

## What the mod is

A Hearts of Iron IV total conversion for 1.19.4, base game only, no DLC, played on macOS. Norway in 2030 has collapsed into a civil war between factions. The map is an upscaled Norway plus a thin strip of Sweden.

## Owner's working rules

These are not negotiable.

- **The owner playtests every build themselves.** Never launch HOI4 automatically; `tools/launch_check.sh` exists but must not be used without being asked.
- **After every change:**
  1. Run `make build`.
  2. Run `.venv/bin/python -m tools.build install`, which symlinks `mod/` into `~/Documents/Paradox Interactive/Hearts of Iron IV/mod/norway_civil_war`.
  3. Commit.
  4. **Push to origin.**
- **Check the branch before building.** GitHub Desktop has switched the checkout to an old branch before, and the game then silently loaded old code.
- **Dangling references usually crash HOI4.** In practice, a reference to anything that doesn't exist (a state, tag, ideology, event, idea, GFX or id) crashed the game rather than just logging an error. Before removing or replacing anything, find every reference to it.
- **Workflows and agents may be used for anything, including coding, without asking.**
  - Give each independent item its own agent.
  - Mid-work, run only the relevant tests.
  - Run the full suite once at the end. It takes about 5–10 minutes because the map tests regenerate the map.

## Repo layout

| Path | What it is |
|---|---|
| `tools/*.py` | The Python generator. `make build` = `.venv/bin/python -m tools.build all`, which writes `mod/`. |
| `data/*.yaml` | The data driving the generator. Key files: `factions.yaml` (tags, names, ideology, leaders, portraits, parties) and `ideologies.yaml` (the 22 ideologies). |
| `content/` | Hand-written game script (events, scripted effects, on_actions, ideas, dynamic modifiers, decisions, localisation, gfx). `copy_content` copies it into `mod/` and expands the `@STATE:key@` and `@VP:key@` tokens. |
| `data/flags/<TAG>.png` | Real flag masters. They override the generated placeholder flag, and `<TAG>_<width>.png` overrides a single size. Concepts and the scripts that draw them are in `data/flags/concepts/`; credits are in `data/flags/CREDITS.md`. |
| `content/gfx/leaders/nwc/*.png` | Leader portraits at 156x210. Credits are in `data/portraits/CREDITS.md`. |
| `tests/` | The pytest suite: `.venv/bin/python -m pytest -q`. |
| `docs/superpowers/specs/2026-11-04-faction-content-design.md` | **The design source of truth.** It covers every faction's paths, mechanics, ideologies, leader titles and flags. |
| `docs/superpowers/plans/2026-11-04-faction-content.md` | The 19-task build plan for the faction content. |

## What is built and working

- **The map.** Includes fixes for every game-start crash found so far: the tutorial override, building slots, unit stacks, AI areas, name lists, continents, and the one-pixel port offset.
- **The opening.** This is the Oslo siege.
  - JNP holds Oslo as Fortress Oslo: a dynamic modifier, level-10 bunkers and 15 divisions.
  - Siege events `nwc_siege.1`–`.4` fire every two weeks. Each event weakens the fortress, and the tooltips show by how much.
  - After the last event the Government has two months to take Oslo.
  - The outcome decides the story:
    - If Oslo holds, Støre is assassinated.
    - If the Government takes it, Støre resigns.
  - Then `nwc_outbreak` starts the general war.
- **The Western Forces (WFR)** are independent, not a puppet. They declare war on JNP themselves, and ABI and the NRM fight them directly.
- **The Norwegian Black Army (ANA, formerly the Anarchist Cells)** is a lasting insurgency; its spirit is "Legacy of Makhno". They surrender only when every pocket is occupied, and spawn new cells every month, even behind enemy lines.
- **Starting armies:** `data/armies.yaml`.
- **The Storting mechanic** (plan Task 3) and **Swedish opinion** (plan Task 4) exist in `content/`.
- **22 custom ideologies**, replacing the vanilla four, Kaiserredux-style.
  - They are generated from `data/ideologies.yaml` by `tools/ideologies.py`.
  - The vanilla ids are reused: democratic = Social Democracy, communism = Marxist-Leninism, fascism = Fascism, neutrality = Autocracy.
  - The vanilla sub-types are kept but hidden, so nothing dangles.
- **Leaders and portraits.**
  - Factions based on real parties are led by their real current leaders, with Wikimedia Commons portraits.
  - User-supplied portraits are used for ABI, ANA and the NRM.
- **Flags.**
  - Real flags: NOR, SWE, DEN, FIN, SOV (Russia) and SAP (Sámi).
  - Designed flags: WFR, FRP, JNP and GMO, NCL and the cantons, ABI, NRM, BRG, and RDN.

## Spawn tags

These exist in the files but have no land at game start.

- **GMO:** the Great Muslim Oslo Republic, JNP's long-siege outcome.
- **RDN:** the **Western Military Council**, the anti-fascist WFR breakaway if the Government goes Fascist. It was formerly the Reindeer Nation, which the owner cut.
- **EST, LAT, LIT, ICE, SCO:** the Neutral Coalition's decentralisation cantons. These are vanilla tags reused.

## Not done yet (in rough order)

1. **Flags for KrF and the Socialists.** Both are undecided; ask the owner.
2. **Plan Tasks 5–19:** the Government tree, every faction's focus tree, the cross-faction links, Denmark's trade deals and the stubs. The owner wants the focus trees near the end, and has other things to add first, so ask what's next.
3. **Wiring the RDN breakaway** to the Fascism path (plan Task 16), and **the spawn events** that give spawn tags their governments.
4. **Story and flavour text.** The owner writes it later; placeholders are one short neutral sentence.
5. **Open design items:**
   - the Anarchist Cells' paths
   - the Socialists' third path
   - the world beyond Sápmi's portal

## Known caveats

- None of the ideology, portrait or flag work has been confirmed in-game yet; it is awaiting the owner's playtest.
- Base-game focus trees and events for SWE, DEN, FIN and SOV may switch those countries to the reused vanilla ideology ids, which gives the wrong flavour but doesn't crash.
- The pre-existing test `test_amend_limited` and the map tests have been flaky or failing at times. Check `pytest -q` output before assuming you broke something.
