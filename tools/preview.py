"""Check images for eyeballing build stages against the approved faction map."""
import numpy as np
from PIL import Image

from tools import geo, raster


def owner_colours() -> np.ndarray:
    """RGB lookup per state raster index."""
    factions = geo.load_factions()
    states = geo.load_states()
    lut = np.zeros((len(raster.all_state_keys()) + 1, 3), np.uint8)
    lut[0] = (190, 214, 230)
    for i, s in enumerate(states):
        lut[i + 1] = factions[geo.state_owner(s)].colour
    for j, (_, owner, _) in enumerate(raster.wasteland()):
        lut[len(states) + j + 1] = (np.array(factions[owner].colour) * 0.3 + 160).astype(np.uint8)
    return lut


def preview_states(path, scale=0.5) -> None:
    r = raster.state_raster()
    img = owner_colours()[r]
    border = np.zeros(r.shape, bool)
    border[:-1] |= r[:-1] != r[1:]
    border[:, :-1] |= r[:, :-1] != r[:, 1:]
    img[border & (r > 0)] = (255, 255, 255)
    img[raster.lake_mask()] = (120, 170, 210)
    im = Image.fromarray(img)
    im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS).save(path)


def preview_political(path, scale=0.5) -> None:
    """Owner colours with province borders (faint) and state borders (dark), like the game's political map."""
    from tools import provinces, terrain

    pm = provinces.provinces()
    states = raster.state_raster()
    img = owner_colours()[states].astype(np.float32)
    hm = raster.heightmap().astype(np.float32)
    land = states > 0
    img[land] *= (0.8 + 0.35 * ((hm[land] - 95) / 160))[:, None]
    img[~land] = (70, 110, 150)
    img[raster.lake_mask()] = (90, 140, 190)
    ids = pm.ids
    pb = np.zeros(ids.shape, bool)
    pb[:-1] |= ids[:-1] != ids[1:]
    pb[:, :-1] |= ids[:, :-1] != ids[:, 1:]
    sb = np.zeros(ids.shape, bool)
    sb[:-1] |= states[:-1] != states[1:]
    sb[:, :-1] |= states[:, :-1] != states[:, 1:]
    img[pb & land] *= 0.85
    img[sb & land] = (30, 30, 30)
    rivers = terrain.river_bitmap() < terrain.R_WATER
    img[rivers] = (60, 120, 200)
    im = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS).save(path)
