"""Twin-scale car cluster: one big dial, two needles, at the panel's real size.

Outer scale (yellow-green) is the 5-hour session; inner scale (red) is the
7-day week. Two needles because these are two different readings, not one
reading in two units - the long one takes the outer scale, the short one the
inner, the way a clock's hands are told apart.

320x240 drawn at 4x. Nothing here runs on the board."""
from PIL import Image, ImageDraw, ImageFont
import math

S = 4
W, H = 320*S, 240*S
CX, CY, R = 160*S, 118*S, 88*S

BG       = (6, 7, 9)
FACE     = (11, 13, 17)
BEZEL    = (34, 39, 47)
OUTER    = (200, 230, 75)      # the MPH-scale yellow-green
OUTER_D  = (120, 140, 46)
INNER    = (224, 52, 42)       # the km/h-scale red
INNER_D  = (140, 36, 30)
LCD_BG   = (150, 190, 60)
LCD_INK  = (18, 28, 8)
TEXT     = (232, 236, 242)
DIM      = (138, 148, 164)
GREEN    = (46, 204, 113)
AMBER    = (241, 170, 60)
RED      = (231, 76, 60)

F  = "/System/Library/Fonts/Supplemental/Arial.ttf"
FB = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
f = lambda p, b=False: ImageFont.truetype(FB if b else F, int(p*S))

im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)

def ctr(txt, font, cx, cy, fill):
    x0,y0,x1,y1 = d.textbbox((0,0), txt, font=font)
    d.text((cx-(x1-x0)/2-x0, cy-(y1-y0)/2-y0), txt, font=font, fill=fill)

def ang(v):  return 135 + 270*max(0, min(100, v))/100.0
def polar(r, a):
    t = math.radians(a); return (CX + r*math.cos(t), CY + r*math.sin(t))

def severity(v):
    return GREEN if v < 60 else (AMBER if v < 80 else RED)

# --- face -------------------------------------------------------------
d.ellipse([CX-R, CY-R, CX+R, CY+R], fill=BEZEL)
ir = R - int(4*S)
d.ellipse([CX-ir, CY-ir, CX+ir, CY+ir], fill=FACE)

# --- outer scale: the session, chunky blocks like the reference's MPH --
for v in range(0, 101, 5):
    major = (v % 20 == 0)
    a = ang(v)
    r_out = ir - int(2*S)
    r_in  = r_out - (int(11*S) if major else int(6*S))
    d.line([polar(r_in, a), polar(r_out, a)],
           fill=OUTER if major else OUTER_D,
           width=int((4.5 if major else 2.0)*S))
    if major:
        nx, ny = polar(r_in - int(9*S), a)
        ctr(str(v), f(11, True), nx, ny, OUTER)

# --- inner scale: the week, small red dots and numbers -----------------
r_dot = ir - int(42*S)
for v in range(0, 101, 10):
    a = ang(v)
    px, py = polar(r_dot, a)
    rr = int(1.6*S)
    d.ellipse([px-rr, py-rr, px+rr, py+rr], fill=INNER)
    if v == 50:
        nx, ny = polar(r_dot - int(9*S), a)
        ctr(str(v), f(7, True), nx, ny, INNER)

# --- the legends, where MPH and km/h sit -------------------------------
ctr("USAGE", f(11, True), CX, CY - int(44*S), TEXT)
ctr("claude", f(7), CX, CY + int(16*S), INNER)

# --- LCD window --------------------------------------------------------
lw, lh = int(58*S), int(26*S)
ly = CY + int(26*S)
d.rounded_rectangle([CX-lw/2, ly, CX+lw/2, ly+lh], radius=int(2*S),
                    fill=LCD_BG, outline=(60, 78, 24), width=int(1*S))
ctr("Hello",  f(13, True), CX, ly + int(9*S), LCD_INK)
ctr("Mark",   f(8,  True), CX, ly + int(19*S), LCD_INK)

# --- needles: long = session (outer), short = week (inner) -------------
def needle(value, length, half_w, tail, col):
    a = ang(value)
    tip  = polar(length, a)
    l    = polar(half_w, a - 90)
    r_   = polar(half_w, a + 90)
    back = polar(tail, a + 180)
    d.polygon([tip, l, back, r_], fill=col)

SESSION, WEEK = 67, 41
needle(WEEK,    r_dot - int(4*S), int(2.4*S), int(10*S), severity(WEEK))
needle(SESSION, ir - int(6*S),    int(3.2*S), int(15*S), severity(SESSION))

hub = int(9*S)
d.ellipse([CX-hub, CY-hub, CX+hub, CY+hub], fill=(20, 24, 30),
          outline=BEZEL, width=int(1.5*S))

# --- header and the two countdowns ------------------------------------
d.text((10*S, 7*S), "21:04", font=f(9), fill=DIM)
for i, c in enumerate([GREEN, GREEN, AMBER, DIM]):
    x = 10*S + i*8*S
    d.rounded_rectangle([x, 19*S, x+5*S, 23*S], radius=int(1.5*S), fill=c)
ctr("OVERWATCH", f(9, True), W - 52*S, 11*S, DIM)

ctr("SESSION 5h", f(8), 62*S, 216*S, OUTER_D)
ctr("2h 14m",     f(12, True), 62*S, 230*S, OUTER)
ctr("WEEKLY 7d",  f(8), 258*S, 216*S, INNER_D)
ctr("4d 09h",     f(12, True), 258*S, 230*S, INNER)

im.save("dial_mockup.png")
im.resize((320*3, 240*3), Image.LANCZOS).save("dial_mockup_3x.png")
print("wrote dial_mockup.png (%dx%d)" % im.size)
