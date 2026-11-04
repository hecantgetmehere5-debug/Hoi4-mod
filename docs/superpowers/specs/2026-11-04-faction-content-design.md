# Faction Content — Design

Planned country by country with the user; built together once every faction is planned.
Builds on the opening (Oslo siege, three outbreak paths) already in content/.

## Government (NOR — Ap + Høyre)

The Oslo siege outcome is the big fork:

- **Oslo holds → Jonas Gahr Støre assassinated.** Choose:
  - **Høyre** → *Fascism* or *Oligarchy* (Norway owned by a few rich families and companies after selling off what the state has left).
  - **The Crown (monarchy)** → *Union with Denmark*, *Independent Kingdom*, or *Union with Sweden*.
- **Oslo taken → Støre resigns (later).** Choose:
  - **Arbeiderpartiet** → *Social-democratic AI technocracy* or *Socialist*.
  - **The Elk** → the new Prime Minister who replaces Støre is secretly an elk (deliberately silly joke path).

Claude's guesses (not yet confirmed): shared focuses before the fork (army, economy, siege); the branch unlocks by event after the assassination/resignation.

## Western Forces (WFR — Government puppet in the west)

- Mainly a **military tree**, plus events showing dependence on the Government, e.g. "Supply Package from Oslo", "Volunteers from the East".
- Default ending: merges back into the Government after the war (decided earlier).
- **Easter egg:** if the Government takes the Elk path, the Western Forces can break away as the **Reindeer Nation** and fight an animal civil war against the Elk government.

## Jihadist Nationalist Party (JNP — holds Oslo)

- If Oslo falls: annexed (already built).
- If Oslo **holds for a long time**: white peace with the Government; JNP becomes the **Great Muslim Oslo Republic**, a city-state that stays small (no expansion path).
- The Government's **Høyre** and **Monarchy** paths get a way to re-besiege Oslo later.
- Claude's guess for "a long time": Oslo still held about a year after the Støre assassination.

## KrF (Christian Democrats — Agder/Telemark)

An **election** decides the church:

- **Orthodox**
  - *Andrij Abyzov path* — inside joke: a fictional Ukrainian immigrant to Norway, Orthodox but schismatic from the Moscow Patriarchate, who loves AI and wants to build an **AI Christianity**.
  - *Monastery path* — (Claude's guess) inward-looking monastic theocracy.
- **Protestant**
  - *Non-denominational*
  - *Martin Luther path* — ultra-Protestant, very anti-Catholic and anti-Orthodox.
- **Catholic**
  - *Crusade path*
  - *Papacy path*

## Socialists (SOC — Rødt + SV)

Choose who to side with:

- **Rødt/SV** → *Democratic socialism*.
- **The micro parties** (NKP — old pro-Soviet Marxist-Leninists; Tjen Folket — Maoist, anti-election street militants; Kommunistisk Plattform — hardline Marxist-Leninists who left when AKP became Rødt) → *Hardline communism* or *Left communism*.
- **Third path:** to be decided later (not needed now).

## FrP (right-wing libertarians — Trøndelag/southern Nordland)

- *Ultra-libertarian* — free private market, tiny state, maximum personal freedom.
- *Ultra-nationalist accelerationist* — FrP instigates a union with the NRM (Nordic Resistance Movement); it only happens if the NRM accepts, and the two become one country.

## NRM (Nordic Resistance Movement — Møre/Sunnfjord coast)

- *Neo-Nazi* path.
- *Viking* path.
- *Ingsoc* path (Orwell's 1984-style totalitarian state).
- Can also accept FrP's union offer (see FrP).

## Sápmi (SAP — Sámi Parliament, the north)

- *Sámi nationalism*.
- *Sentient reindeer* path. (Claude's note: could tie in with the Western Forces' Reindeer Nation easter egg.)
- *Portal* path — a portal to another world opens; the other world is planned later.

## Neutral Coalition (NCL — Sp + MDG, Innlandet)

- *Extreme decentralisation* — the coalition splits into many small states, all puppets under a tiny central government state.
- *Paganism*.

## Askøy–Bømlo Insurgency (ABI — anarcho-distributists around Bergen)

- **Lean anarcho** → *Anarcho-communism* or *Syndicalism*.
- **Lean distributist** → *Georgist mutualism* or *Egoism*.

## Free City of Bergen (BRG — merchant city-state)

- *Merchant city* — go all in on trade and build the biggest merchant navy around.
- *Cooperate with Askøy–Bømlo* — becomes ABI's puppet but keeps its own ideology.

## Anarchist Cells (ANA — guerrillas)

- Paths to be decided later.

## Sweden (SWE — the neighbour)

- Ordinary 2030 Sweden; no collapse like Norway had.
- **Swedish Opinion mechanic:** the Government must keep Sweden pleased.
  - Very pleased → Sweden intervenes **for** the Government.
  - Pleased (not enough to intervene) → Sweden stays out but sends **aid**.
  - Middling → Sweden stays neutral.
  - Displeased → Sweden intervenes and makes Norway its **puppet**.
  - If the Government goes **Monarchy → Union with Denmark**, Sweden intervenes regardless.
  - Opinion rises by enacting **Swedish-sponsored laws** and appointing **Swedish-sponsored people** to the government.
- **Storting mechanic (Government):** a parliament system — details to plan (ties into passing the Swedish laws).
  - Core of it: balance the **social-democratic** and **conservative** blocs in the Storting.
  - Seats are **permanently 50% Ap / 50% Høyre**, but members do not vote as a bloc (not every Høyre politician agrees).
  - A law needs **more than 70% of the votes** to pass, so the player must win over both sides.
  - Flow: **propose a bill** → offer **concessions** and **amend the law** to win each side over → vote (>70% passes).

## Denmark (DEN)

- Minimal content: **trade deals with Bergen** (plus its role in the Union-with-Denmark path).

## Finland (FIN)

- No content.

## Russia (SOV)

- No content.

## Still open (user will add later)

- General story and per-path story/flavour text for every faction.
- Anarchist Cells paths; Socialists' third path; Sápmi portal world.
- Build what is decided now; leave clean hooks for these.

## Decisions from the builder check

**User's answers**
- Ideology paths open **during** the civil war (each tree: war section + paths alongside).
- Storting votes have **luck**: support numbers set the odds, a bill can still fail.
- Swedish puppet takeover = **game over** for the Government (the mod centres on the civil war).
- The Storting continues on every path **except Fascism** (no Storting there); other paths at builder's discretion.
- KrF church: the player **picks it in a decision**.
- "Oslo holds" means JNP keeps holding Oslo through the siege → Støre assassinated; "Oslo taken" means the Government retakes it → Støre resigns.

**Claude's calls (check these)**
- Concessions cost political power and/or lower the other bloc's support; amendments weaken the law's effect.
- Swedish opinion is a 0–100 variable checked monthly; Sweden can escalate (neutral → aid → intervene, or → puppet).
- "Intervene for the Government" = Sweden joins the Government's wars against all its enemies.
- Swedish-sponsored people = vanilla advisors/ideas, offered by events.
- Støre resigns by event ~30 days after Oslo is taken.
- FrP offers the union by focus; NRM can accept from any path; the FrP tag survives the merge.
- Reindeer Nation: WFR decision once the Government is on the Elk path; new tag; Sápmi's sentient reindeer can ally with it.
- Høyre/Monarchy re-besiege Oslo by focus, breaking the JNP white peace.
- Bergen–ABI puppet needs ABI to accept by event; Denmark trade deals still allowed.
- Union with Denmark = personal union with Danish control; Union with Sweden sets Swedish opinion to max.
- Neutral Coalition mini-states and the Great Muslim Oslo Republic reuse spare vanilla tags.
- Sápmi portal path is in the tree with a stub ending.
