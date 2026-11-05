# Norwegian Civil War 2030

A Hearts of Iron IV total conversion: Norway in 2030, after the oil fund and
the oil industry collapsed and the country broke apart. The map is Norway,
scaled up, plus a strip of Sweden.

The map, the opening siege, ideologies, leaders and flags are built; focus trees
come later. **Start with `docs/HANDOFF.md`** for the current state and plans.

## Build and install

```bash
make setup     # once: Python environment
make build     # downloads source data (first time) and regenerates mod/
make install   # links mod/ into ~/Documents/Paradox Interactive/Hearts of Iron IV/mod
make test
```

Then enable **Norwegian Civil War 2030** in the HOI4 launcher's playset.

`mod/` is generated and not committed. Everything in it comes from:

| File | What it decides |
|---|---|
| `data/ownership.yaml` | which faction owns each municipality on 1 January 2030 |
| `data/states.yaml` | how municipalities group into states, state names, victory point towns |
| `data/factions.yaml` | country tags, names, colours, capitals, Western Forces as a puppet |
| `data/sweden_strip.yaml` | which Swedish municipalities are on the map |
| `data/strategic_regions.yaml` | land strategic regions |
| `data/registry/*.json` | permanent state and province IDs; never edit by hand |

To move a front line, change `ownership.yaml` (and `states.yaml` if a state
would get two owners), then `make build`. State and province IDs stay the same.

## Playtest checklist

1. The game loads to the main menu with the mod enabled.
2. The 2030 bookmark shows the factions; pick any of them.
3. The map looks like Norway: fjords, mountains, lakes (Mjøsa), rivers.
4. Every faction sits where the approved map puts it (`reference/faction_map.png`):
   Oslo is the Jihadist Nationalist Party, Bergen is its own city, the
   anarchist pockets are scattered single states.
5. Sweden is neutral and owns the strip; Finland, Russia and Denmark are grey
   impassable land at the edge.
6. Units can walk between neighbouring states and onto bridged islands
   (Askøy, Lofoten, Senja).
7. After quitting, run
   `python tools/check_log.py ~/Documents/Paradox\ Interactive/Hearts\ of\ Iron\ IV/logs/error.log`
   and send me whatever it prints.
