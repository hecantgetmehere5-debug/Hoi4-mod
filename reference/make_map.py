"""Render the 2030 Norwegian Civil War starting map from municipality borders.
Usage: python make_map.py <kommuner.geojson> <countries.geojson> <out.png>
"""
import json, math, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly, Patch
from shapely.geometry import shape
from shapely.ops import unary_union

FACTIONS = {
    "GOV":  ("Government (Ap + H)",              "#1f3fd6"),
    "WGOV": ("Western Forces (Government)",      "#4a63c9"),
    "MUS":  ("Jihadist Nationalist Party",       "#2b2b2b"),
    "KRF":  ("KrF (Christian Democracy)",        "#f08c00"),
    "SOC":  ("Socialists (Rødt + SV)",           "#d61f1f"),
    "FRP":  ("FrP (Libertarian)",                "#2f9bf0"),
    "NRM":  ("Nordic Resistance Movement",       "#7a4a12"),
    "SAMI": ("Sametinget",                       "#9466d6"),
    "CEN":  ("Neutral Coalition (Sp + MDG)",     "#2e7d1f"),
    "AB":   ("Askøy–Bømlo Insurgency",           "#8b0f1a"),
    "BRG":  ("Free City of Bergen",              "#d4b20a"),
    "ANA":  ("Anarchist pockets (chaos)",        "#140808"),
}

# County defaults (first two digits of kommunenummer)
COUNTY = {"03": "MUS", "11": "SOC", "15": "NRM", "18": "SAMI", "31": "GOV",
          "32": "GOV", "33": "CEN", "34": "CEN", "39": "GOV", "40": "KRF",
          "42": "KRF", "46": "WGOV", "50": "FRP", "55": "SAMI", "56": "SAMI"}

OVERRIDES = {
    # Finnmark
    "5610": "SOC", "5612": "SOC", "5605": "ANA",
    # Southern Nordland -> FrP
    **{k: "FRP" for k in "1811 1812 1813 1815 1816 1818 1820 1822 1824 1826 1827".split()},
    "1825": "ANA",
    # Trøndelag pockets
    "5029": "ANA", "5034": "ANA", "5022": "ANA",
    # Inner Møre -> FrP / Western Forces
    "1566": "FRP", "1563": "FRP", "1576": "FRP", "1560": "FRP",
    "1525": "WGOV", "1539": "WGOV",
    # Vestland coast -> NRM
    **{k: "NRM" for k in "4602 4648 4649 4650 4647 4645 4646 4636 4637".split()},
    "4635": "ANA",
    # Askøy–Bømlo coast and islands
    **{k: "AB" for k in "4627 4626 4633 4632 4631 4625 4624 4616 4615 4614 4613 4612 4630 4623 4628 4629 4634 4617".split()},
    "4601": "BRG",
    # Sunnhordland / Hardanger -> socialists
    **{k: "SOC" for k in "4611 4618".split()},
    # Rogaland south -> KrF
    "4228": "KRF",
    # Central coalition pockets
    "3437": "ANA", "3452": "ANA", "3332": "ANA", "3428": "ANA", "3419": "ANA",
    # Telemark: Hardangervidda -> centre, coast -> government
    "4026": "CEN", "4036": "CEN", "3334": "ANA",
    **{k: "GOV" for k in "4001 4003 4012 4010 4005".split()},
    # Lower Buskerud / south Innlandet -> government
    **{k: "GOV" for k in "3301 3312 3314 3316 3310 3305 3303".split()},
    **{k: "GOV" for k in "3401 3416 3415".split()},
}


def project(lon, lat):
    # Simple equal-ish projection centred on Norway
    return (lon * math.cos(math.radians(65)), lat)


def rings(geom):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for p in polys:
        yield [project(x, y) for x, y in p.exterior.coords]


def draw(ax, geom, **kw):
    for ring in rings(geom):
        ax.add_patch(MplPoly(ring, closed=True, **kw))


def main(kommuner_path, countries_path, out_path):
    kom = json.load(open(kommuner_path))["features"]
    groups = {}
    for f in kom:
        nr = f["properties"]["kommunenummer"]
        fac = OVERRIDES.get(nr, COUNTY[nr[:2]])
        groups.setdefault(fac, []).append(shape(f["geometry"]).buffer(0))

    fig, ax = plt.subplots(figsize=(10, 13), dpi=160)
    fig.patch.set_facecolor("#cfe0ea")
    ax.set_facecolor("#cfe0ea")

    for c in json.load(open(countries_path))["features"]:
        if c["properties"]["ADMIN"] in ("Sweden", "Finland", "Russia", "Denmark"):
            draw(ax, shape(c["geometry"]), facecolor="#e4e1d8", edgecolor="#a8a49a", lw=0.6)

    merged = {fac: unary_union(g).simplify(0.0015) for fac, g in groups.items()}
    order = [k for k in FACTIONS if k != "ANA"] + ["ANA"]
    for fac in order:
        if fac not in merged:
            continue
        col = FACTIONS[fac][1]
        if fac == "ANA":
            draw(ax, merged[fac], facecolor=col, edgecolor="#e8e2d0", lw=0.9, hatch="////", zorder=3)
        else:
            draw(ax, merged[fac], facecolor=col, edgecolor="#ffffff", lw=0.8, zorder=2)

    x0, x1 = project(4.3, 0)[0], project(31.5, 0)[0]
    ax.set_xlim(x0, x1)
    ax.set_ylim(57.8, 71.3)
    ax.set_aspect(1)
    ax.axis("off")

    handles = [Patch(facecolor=c, edgecolor="#555", hatch="////" if k == "ANA" else None, label=n)
               for k, (n, c) in FACTIONS.items()]
    leg = ax.legend(handles=handles, loc="upper left", fontsize=9, frameon=True,
                    title="Norway, 1 January 2030", title_fontsize=11)
    leg.get_frame().set_facecolor("#f6f4ee")
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.1, facecolor=fig.get_facecolor())


if __name__ == "__main__":
    main(*sys.argv[1:4])
