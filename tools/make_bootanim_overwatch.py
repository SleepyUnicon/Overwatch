#!/usr/bin/env python3
"""Draw the Overwatch boot clip: the mark assembling itself, from the mark.

Two steps, on purpose:

    tools/make_bootanim_overwatch.py --out build/bootanim-frames
    tools/encode_bootanim.py --frames build/bootanim-frames --fps 12 \\
        --threshold 0 --bg 253,250,241 --out firmware/src/bootanim.h

The shipped clip this replaces was the Blink eyes, and its own header records
the problem worth not repeating: "Originally, from the source clip ... (the mp4
is not in the tree)". Frames encoded out of a temporary directory leave a blob
nobody can regenerate. Everything here comes from design/overwatch-logo.png,
which IS in the tree, so the animation can be rebuilt from source at any time.

WHY THE REVEAL IS FREE. The mark is four disconnected shapes -- tower, bar,
inner arc, outer arc -- so they are found by connected-component labelling
rather than by hand-placed coordinates. Nothing here knows where anything is;
move a shape in the PNG and the animation follows it. Revealed bottom-up, the
tower is built and then starts broadcasting, which is what the mark already
depicts standing still.

It also costs almost nothing to store. encode_bootanim delta-encodes against
what is currently displayed, and each step changes only the shape that just
appeared: 27 frames come to 37 KB, against 502 KB for the clip this replaces.
A fade of the whole logo would have dirtied the full canvas every frame.
"""
import argparse
import os

import numpy as np
from PIL import Image
from scipy import ndimage

CANVAS = (320, 240)
# The logo's OWN ground, which is how its ink is found in the PNG. Not the
# same thing as the ground the clip is drawn on -- a Codex-edition board
# wants the same mark on its own colour, so both are options below.
SRC_BG = (253, 250, 241)
TARGET_H = 186            # the mark's height on the panel, leaving a margin
FADE = (0.35, 0.7, 1.0)   # three steps per shape: quick, and not a hard cut
HOLD = 14                 # frames on the finished mark, ~1.2 s at 12 fps


def shapes(path, ink):
    """The mark's disconnected parts, bottom-most first, and their bbox.

    Bottom-most first is the reveal order and it is derived, not declared:
    sorting by the LOWEST row each component occupies gives tower, bar, inner
    arc, outer arc for this mark, and something sensible for any other.
    """
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(int)
    mask = np.abs(rgb - np.array(SRC_BG)).sum(2) > 60
    lab, n = ndimage.label(mask)
    if n == 0:
        raise SystemExit("%s: no ink found against the background" % path)

    ys, xs = np.where(mask)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)

    order = sorted(range(1, n + 1),
                   key=lambda i: np.where(lab == i)[0].max(), reverse=True)
    out = []
    for i in order:
        # Flat ink, not the PNG's own pixels. The mark is one solid colour
        # anyway, and recolouring it here is what lets one source drawing
        # serve both editions instead of needing a second PNG per palette.
        rgba = np.zeros(rgb.shape[:2] + (4,), np.uint8)
        rgba[..., :3] = np.array(ink, np.uint8)
        rgba[..., 3] = ((lab == i) * 255).astype(np.uint8)
        out.append(Image.fromarray(rgba).crop(box))
    return out, box


def frames(path, ground, ink):
    parts, box = shapes(path, ink)
    w, h = CANVAS
    scale = TARGET_H / (box[3] - box[1])
    size = (max(1, round((box[2] - box[0]) * scale)), TARGET_H)
    at = ((w - size[0]) // 2, (h - size[1]) // 2)
    parts = [p.resize(size, Image.LANCZOS) for p in parts]

    canvas = Image.new("RGB", CANVAS, ground)
    out = [canvas.copy()]                     # a beat on the bare ground
    for part in parts:
        for alpha in FADE:
            step = canvas.copy()
            faded = part.copy()
            faded.putalpha(part.getchannel("A").point(
                lambda v, a=alpha: int(v * a)))
            step.paste(faded, at, faded)
            out.append(step)
        canvas = out[-1]                      # it stays for what follows
    return out + [canvas.copy()] * HOLD


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--logo", default="design/overwatch-logo.png")
    ap.add_argument("--bg", default="fdfaf1", help="ground colour, hex")
    ap.add_argument("--ink", default="de6a47", help="mark colour, hex")
    ap.add_argument("--out", required=True, metavar="DIR")
    a = ap.parse_args()

    def hexrgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    ground, ink = hexrgb(a.bg), hexrgb(a.ink)

    os.makedirs(a.out, exist_ok=True)
    for stale in os.listdir(a.out):
        if stale.endswith(".png"):
            os.remove(os.path.join(a.out, stale))

    fr = frames(a.logo, ground, ink)
    for i, f in enumerate(fr):
        f.save(os.path.join(a.out, "f%03d.png" % i))
    print("%d frames -> %s  (%.1f s at 12 fps)" % (len(fr), a.out, len(fr) / 12))
    print("now: tools/encode_bootanim.py --frames %s --fps 12 --threshold 0 \\"
          % a.out)
    print("       --bg %d,%d,%d --out firmware/src/bootanim.h" % ground)


if __name__ == "__main__":
    main()
