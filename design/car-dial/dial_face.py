"""The dial's artwork, drawn once and used twice.

`make_dial_mockup.py` renders it for a preview; `tools/encode_dial.py`
rasterises the same functions into firmware/src/dial_gen.h. One source, so the
picture we argue about and the picture the board draws cannot drift.

Everything is drawn at SS times final size and downsampled with LANCZOS. That
is the whole reason the face is a bitmap rather than LVGL primitives: the
ESP32 draws a hard-edged tick, and anti-aliasing 21 ticks and six numerals on
a 2.8 inch panel is the difference between a dial and a diagram.
"""
from PIL import Image, ImageDraw, ImageFont
import math

# Final geometry, in panel pixels.
R        = 88          # dial radius -> a 176 px face
FACE_PX  = R * 2
SWEEP0   = 135         # 0% sits lower-left,
SWEEP    = 270         # ...and 100% lower-right
REDLINE  = 80

# The LCD window, in panel pixels, measured from the dial's centre.
LCD_W, LCD_H, LCD_Y = 58, 26, 26

BG       = (0x0E, 0x11, 0x16)   # COL_BG in usage_view.c - the face blends in
FACE     = (11, 13, 17)
BEZEL    = (34, 39, 47)
BEZEL_HI = (62, 71, 86)
OUTER    = (200, 230, 75)
OUTER_D  = (120, 140, 46)
INNER    = (224, 52, 42)
LCD_BG   = (150, 190, 60)
LCD_INK  = (18, 28, 8)
TEXT     = (232, 236, 242)

GREEN = (0x0D, 0xA2, 0x43)
AMBER = (0xBA, 0x81, 0x07)
RED   = (0xFF, 0x19, 0x00)
SEVERITY = {"green": GREEN, "amber": AMBER, "red": RED}

F  = "/System/Library/Fonts/Supplemental/Arial.ttf"
FB = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def ang(v):
    return SWEEP0 + SWEEP * max(0.0, min(100.0, v)) / 100.0


def render_face(SS=6):
    """The static half: bezel, both scales, numbers, USAGE. No needles, no
    LCD text - those move."""
    f = lambda p, b=False: ImageFont.truetype(FB if b else F, int(p * SS))
    W = FACE_PX * SS
    im = Image.new("RGB", (W, W), BG)
    d = ImageDraw.Draw(im)
    C = W / 2
    RR = R * SS

    def polar(r, a):
        t = math.radians(a)
        return (C + r * math.cos(t), C + r * math.sin(t))

    def ctr(txt, font, cx, cy, fill):
        x0, y0, x1, y1 = d.textbbox((0, 0), txt, font=font)
        d.text((cx - (x1 - x0) / 2 - x0, cy - (y1 - y0) / 2 - y0), txt,
               font=font, fill=fill)

    d.ellipse([0, 0, W - 1, W - 1], fill=BEZEL)
    d.arc([0, 0, W - 1, W - 1], 180, 360, fill=BEZEL_HI, width=int(1.5 * SS))
    ir = RR - int(4 * SS)
    d.ellipse([C - ir, C - ir, C + ir, C + ir], fill=FACE)

    # outer scale - the session
    for v in range(0, 101, 5):
        major = (v % 20 == 0)
        a = ang(v)
        r_out = ir - int(2 * SS)
        r_in = r_out - (int(11 * SS) if major else int(6 * SS))
        d.line([polar(r_in, a), polar(r_out, a)],
               fill=OUTER if major else OUTER_D,
               width=int((4.5 if major else 2.0) * SS))
        if major:
            nx, ny = polar(r_in - int(9 * SS), a)
            ctr(str(v), f(11, True), nx, ny, OUTER)

    # inner scale - the week. Dots only: at 2.8 inches a second ring of
    # numerals sits under the first one and neither can be read.
    r_dot = ir - int(42 * SS)
    for v in range(0, 101, 10):
        px, py = polar(r_dot, ang(v))
        rr = int(1.6 * SS)
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=INNER)
    # One numeral on the inner scale, at the top. A full second ring of
    # numbers sits under the outer one at this size; a single midpoint is
    # enough to say which way the short needle reads.
    nx, ny = polar(r_dot - int(9 * SS), ang(50))
    ctr("50", f(7, True), nx, ny, INNER)

    ctr("USAGE", f(11, True), C, C - int(44 * SS), TEXT)

    # The LCD's bezel is static, so it belongs in the bitmap. Only the two
    # words on it are objects - one rounded rect the ESP32 never has to draw.
    lw, lh = int(LCD_W * SS), int(LCD_H * SS)
    ly = C + int(LCD_Y * SS)
    d.rounded_rectangle([C - lw / 2, ly, C + lw / 2, ly + lh],
                        radius=int(2 * SS), fill=LCD_BG,
                        outline=(60, 78, 24), width=int(1 * SS))
    return im.resize((FACE_PX, FACE_PX), Image.LANCZOS), r_dot / SS, ir / SS


def render_needle(length, half_w, tail, colour, SS=6):
    """A needle pointing RIGHT (0 degrees), pivoting about its hub.

    Drawn along +x so the firmware can rotate it by ang(value) with no offset
    to remember. The pivot is returned in final pixels.
    """
    pad = int(tail + 4)
    W = int((length + pad) * SS)
    Hh = int((half_w + 4) * 2 * SS)
    im = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    px, py = pad * SS, Hh / 2
    d.polygon([(px + length * SS, py),
               (px, py - half_w * SS),
               (px - tail * SS, py),
               (px, py + half_w * SS)], fill=colour + (255,))
    return (im.resize((W // SS, Hh // SS), Image.LANCZOS), pad, (Hh // SS) // 2)
