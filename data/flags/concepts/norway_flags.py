"""Render flag masters NOR, WFR, FRP, SAP into data/flags/.

Usage: python -I norway_flags.py <repo>   (needs Pillow, resvg_py; WFR needs data/flags/src/ emblem SVG)
"""
import io
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

REPO = Path(sys.argv[1])
OUT = REPO / "data" / "flags"
SS = 4  # supersampling factor

RED, BLUE, WHITE = (0xBA, 0x0C, 0x2F), (0x00, 0x20, 0x5B), (255, 255, 255)
U = 50  # px per unit -> 22:16 = 1100x800


def norway(u=U):
    im = Image.new("RGB", (22 * u, 16 * u), RED)
    d = ImageDraw.Draw(im)
    d.rectangle([6 * u, 0, 10 * u - 1, 16 * u], fill=WHITE)
    d.rectangle([0, 6 * u, 22 * u, 10 * u - 1], fill=WHITE)
    d.rectangle([7 * u, 0, 9 * u - 1, 16 * u], fill=BLUE)
    d.rectangle([0, 7 * u, 22 * u, 9 * u - 1], fill=BLUE)
    return im


def outlined(emb, width, colour=WHITE):
    """Return emblem with a solid outline halo so it separates from the red field."""
    a = emb.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    halo = a.filter(ImageFilter.MaxFilter(width * 2 + 1)).filter(ImageFilter.GaussianBlur(1))
    base = Image.new("RGBA", emb.size, colour + (0,))
    base.putalpha(halo)
    base.alpha_composite(emb)
    return base


def place(flag, emb, cx, cy):
    flag = flag.convert("RGBA")
    flag.alpha_composite(emb, (int(cx - emb.width / 2), int(cy - emb.height / 2)))
    return flag.convert("RGB")


def wfr():
    import resvg_py
    svg = (OUT / "src" / "Coat_of_arms_of_the_Norwegian_Armed_Forces.svg").read_text()
    h = 600
    w = round(h * 114.55525 / 140.65898)
    svg = re.sub(r'width="[\d.]+mm"', f'width="{w}"', svg, count=1)
    svg = re.sub(r'height="[\d.]+mm"', f'height="{h}"', svg, count=1)
    emb = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg)))).convert("RGBA")
    emb = outlined(emb, 8)
    return place(norway(), emb, 8 * U, 8 * U)


def torch_layer(h):
    """Gold torch of liberty with white flame, drawn supersampled; returns RGBA of height h."""
    S = SS
    W, H = int(h * 0.5) * S, h * S
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    gold, dgold, flame_o, flame_i = (0xF2, 0xC2, 0x30), (0xB8, 0x86, 0x0B), (0xFF, 0x9A, 0x1F), (255, 246, 210)
    cx = W / 2
    # flame: teardrop with flicker
    fb, ft, fw = H * 0.40, H * 0.02, W * 0.34

    def flame(scale, col, lift=0.0):
        top, bot = ft + (fb - ft) * (1 - scale) + lift, fb + fw * scale * 0.3
        left, right = [], []
        for i in range(101):
            v = i / 100  # 0 = tip, 1 = base
            hw = fw * scale * 1.45 * (v ** 0.85) * math.sqrt(max(0.0, 1 - v ** 3))
            sway = W * 0.05 * scale * math.sin(v * math.pi * 1.6) * (1 - v)
            y = top + (bot - top) * v
            left.append((cx + sway - hw, y))
            right.append((cx + sway + hw, y))
        poly = left + right[::-1]
        d.polygon(poly, fill=col)

    flame(1.0, flame_o)
    flame(0.62, flame_i, lift=H * 0.03)
    # cup
    ct, cb = H * 0.44, H * 0.58
    d.polygon([(cx - W * 0.36, ct), (cx + W * 0.36, ct), (cx + W * 0.16, cb), (cx - W * 0.16, cb)], fill=gold)
    d.rectangle([cx - W * 0.40, ct - H * 0.035, cx + W * 0.40, ct + H * 0.01], fill=gold)
    d.line([(cx - W * 0.30, ct + H * 0.05), (cx + W * 0.30, ct + H * 0.05)], fill=dgold, width=int(H * 0.012))
    # knot and handle
    d.ellipse([cx - W * 0.17, cb - H * 0.015, cx + W * 0.17, cb + H * 0.05], fill=gold)
    d.polygon([(cx - W * 0.11, cb + H * 0.03), (cx + W * 0.11, cb + H * 0.03), (cx + W * 0.06, H * 0.97), (cx - W * 0.06, H * 0.97)], fill=gold)
    d.ellipse([cx - W * 0.08, H * 0.94, cx + W * 0.08, H * 0.99], fill=gold)
    im = im.resize((W // S, H // S), Image.LANCZOS)
    return im


def frp():
    t = torch_layer(560)
    pad = Image.new("RGBA", (t.width + 40, t.height + 40), (0, 0, 0, 0))
    pad.alpha_composite(t, (20, 20))
    t = outlined(pad, 7, BLUE)
    t = outlined(t, 6, WHITE)
    return place(norway(), t, 8 * U, 8 * U)


def sap():
    k = 1.5 * SS
    W, H = int(808 * k), int(600 * k)
    im = Image.new("RGB", (W, H), (0x00, 0x35, 0xAD))
    d = ImageDraw.Draw(im)
    s = lambda v: v * k
    d.rectangle([0, 0, s(370), H], fill=(0xFF, 0xCE, 0x00))
    d.rectangle([0, 0, s(314), H], fill=(0x00, 0x72, 0x29))
    d.rectangle([0, 0, s(258), H], fill=(0xDC, 0x24, 0x1F))
    cx, cy = s(314), s(300)
    # blue left half ring (r 160..192) with the little arrow tips as in the official SVG
    ring = Image.new("L", (W, H), 0)
    rd = ImageDraw.Draw(ring)
    rd.pieslice([cx - s(192), cy - s(192), cx + s(192), cy + s(192)], 90, 270, fill=255)
    rd.pieslice([cx - s(160), cy - s(160), cx + s(160), cy + s(160)], 90, 270, fill=0)
    for sy in (1, -1):
        y0 = cy - sy * s(192)
        rd.polygon([(cx, y0), (cx + s(16), y0 + sy * s(16)), (cx, y0 + sy * s(32))], fill=255)
    im.paste((0x00, 0x35, 0xAD), mask=ring)
    ring = Image.new("L", (W, H), 0)
    rd = ImageDraw.Draw(ring)
    rd.pieslice([cx - s(192), cy - s(192), cx + s(192), cy + s(192)], -90, 90, fill=255)
    rd.pieslice([cx - s(160), cy - s(160), cx + s(160), cy + s(160)], -90, 90, fill=0)
    im.paste((0xDC, 0x24, 0x1F), mask=ring)
    return im.resize((W // SS, H // SS), Image.LANCZOS)


if __name__ == "__main__":
    norway().save(OUT / "NOR.png")
    wfr().save(OUT / "WFR.png")
    frp().save(OUT / "FRP.png")
    sap().save(OUT / "SAP.png")
