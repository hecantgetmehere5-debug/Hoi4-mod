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
