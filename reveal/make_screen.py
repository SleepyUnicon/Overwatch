"""The three widget pages, drawn to the layouts in firmware/src/*.c, at 8x the
panel's 320x240 so they stay crisp when the camera is close.

Writes one page per file plus `screen_strip.png`, the three stacked into a
single tall texture. The reveal maps a third of that strip onto the panel and
slides the mapping to swipe between pages - one image, no texture swapping,
and the slide is free."""
from PIL import Image, ImageDraw, ImageFont
import math

S = 8
W, H = 320*S, 240*S
BG, TRACK, ARC = (11,16,26), (34,42,56), (120,190,255)
TEXT, DIM, PANEL = (232,236,242), (126,140,158), (22,26,32)
GREEN, GREEN_INK, AMBER = (46,204,113), (6,33,15), (241,196,15)

F  = "/System/Library/Fonts/Supplemental/Arial.ttf"
FB = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
f = lambda p, b=False: ImageFont.truetype(FB if b else F, int(p*S))

def new():
    im = Image.new("RGB", (W, H), BG)
    return im, ImageDraw.Draw(im)

def ctr(d, txt, font, cx, cy, fill):
    x0,y0,x1,y1 = d.textbbox((0,0), txt, font=font)
    d.text((cx-(x1-x0)/2-x0, cy-(y1-y0)/2-y0), txt, font=font, fill=fill)

def rail(d, active, n=3):
    """The page rail ui_pages.c draws: position carried by WIDTH, so colour
    stays free to mean something else later."""
    x = 136*S
    for i in range(n):
        w = 20*S if i == active else 8*S
        d.rounded_rectangle([x, 218*S, x+w, 222*S], radius=2*S,
                            fill=TEXT if i == active else TRACK)
        x += w + 8*S

# ---------------------------------------------------------------- 1 gauges
def gauges():
    im, d = new()
    def gauge(cx, cy, r, pct, label, sub):
        cx, cy, r = cx*S, cy*S, r*S
        wdt = int(7*S); box = [cx-r, cy-r, cx+r, cy+r]
        d.arc(box, 135, 45, fill=TRACK, width=wdt)
        d.arc(box, 135, 135+270*pct/100, fill=ARC, width=wdt)
        a = math.radians(135+270*pct/100)
        hx, hy = cx+r*math.cos(a), cy+r*math.sin(a); rr = wdt*0.62
        d.ellipse([hx-rr,hy-rr,hx+rr,hy+rr], fill=(198,226,255))
        ctr(d, "%d%%" % pct, f(26, True), cx, cy-2*S, TEXT)
        ctr(d, label, f(9), cx, cy+r+13*S, DIM)
        ctr(d, sub, f(11, True), cx, cy+r+26*S, TEXT)
    ctr(d, "OVERWATCH", f(12, True), W//2, 17*S, TEXT)
    d.text((13*S, 11*S), "21:04", font=f(11), fill=DIM)
    for i, c in enumerate([GREEN, GREEN, AMBER, DIM]):
        x = 13*S + i*9*S
        d.rounded_rectangle([x, 26*S, x+6*S, 30*S], radius=2*S, fill=c)
    gauge(88, 116, 42, 67, "SESSION 5h", "2h 14m")
    gauge(232, 116, 42, 41, "WEEKLY 7d", "4d 09h")
    ctr(d, "Claude", f(10), W//2, 200*S, DIM)
    rail(d, 0)
    return im

# ---------------------------------------------------------------- 2 spotify
def spotify():
    """firmware/src/ui_spotify.c: header, title, artist, bar, time, three
    transport buttons at y=140. Playing, so the centre offers pause."""
    im, d = new()
    d.text((16*S, 14*S), "Now playing", font=f(9), fill=DIM)
    d.text((16*S, 44*S), "Midnight Train", font=f(16, True), fill=TEXT)
    d.text((16*S, 72*S), "Sauti Sol", font=f(11), fill=DIM)
    d.rounded_rectangle([16*S, 108*S, 304*S, 114*S], radius=3*S, fill=TRACK)
    d.rounded_rectangle([16*S, 108*S, (16+288*0.386)*S, 114*S], radius=3*S, fill=GREEN)
    d.text((16*S, 122*S), "1:33 / 4:01", font=f(10), fill=DIM)
    for x, kind in [(36, "prev"), (124, "play"), (212, "next")]:
        on = kind == "play"
        d.rounded_rectangle([x*S, 140*S, (x+72)*S, 196*S], radius=6*S,
                            fill=GREEN if on else PANEL)
        cx, cy = (x+36)*S, 168*S; ink = GREEN_INK if on else TEXT
        if kind == "play":
            d.rounded_rectangle([cx-11*S, cy-20*S, cx-3*S, cy+20*S], radius=2*S, fill=ink)
            d.rounded_rectangle([cx+3*S, cy-20*S, cx+11*S, cy+20*S], radius=2*S, fill=ink)
        elif kind == "next":
            d.polygon([(cx-12*S,cy-18*S),(cx-12*S,cy+18*S),(cx+6*S,cy)], fill=ink)
            d.rounded_rectangle([cx+8*S, cy-18*S, cx+13*S, cy+18*S], radius=S, fill=ink)
        else:
            d.polygon([(cx+12*S,cy-18*S),(cx+12*S,cy+18*S),(cx-6*S,cy)], fill=ink)
            d.rounded_rectangle([cx-13*S, cy-18*S, cx-8*S, cy+18*S], radius=S, fill=ink)
    rail(d, 1)
    return im

# ---------------------------------------------------------------- 3 launcher
ICONS = ["claude", "illustrator", "photoshop", "spotify", "brave", "pcsx2"]

def launcher():
    """firmware/src/ui_launcher.c: three columns of 96 at an 8 px gap, two rows
    of 62 from y=52. Icons rather than names - the real icons off this Mac,
    which is what the daemon's table points at anyway.

    NOTE the firmware still draws TEXT labels. Either ui_launcher.c grows
    bitmap support or this is aspirational; it is flagged in the README."""
    im, d = new()
    d.text((8*S, 16*S), "Launch", font=f(10), fill=DIM)
    for i, nm in enumerate(ICONS):
        col, row = i % 3, i // 3
        x, y = 8 + col*104, 52 + row*70
        bg = PANEL
        if i == 1: bg = AMBER       # tapped
        if i == 3: bg = GREEN       # launched
        d.rounded_rectangle([x*S, y*S, (x+96)*S, (y+62)*S], radius=6*S, fill=bg)
        ic = Image.open("icons/%s.png" % nm).convert("RGBA")
        k = int(44*S)
        ic = ic.resize((k, k), Image.LANCZOS)
        im.paste(ic, (int((x+48)*S - k/2), int((y+31)*S - k/2)), ic)
    rail(d, 2)
    return im

pages = [("gauges", gauges()), ("spotify", spotify()), ("launcher", launcher())]
for nm, im in pages:
    im.save("page_%s.png" % nm)

# Stacked BOTTOM-UP: UV v=0 is the bottom of the image, so page 0 goes last.
strip = Image.new("RGB", (W, H*3), BG)
for i, (_, im) in enumerate(pages):
    strip.paste(im, (0, H*(2-i)))
strip.save("screen_strip.png")
print("wrote 3 pages + screen_strip.png %dx%d" % strip.size)
