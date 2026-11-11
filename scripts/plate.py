#!/usr/bin/env python3
"""Draw the animated keyword title as a transparent PNG sequence.

The keyword the shopper typed sits over the new opening scene, so the picture
and the search agree even with the sound off. Every size is relative to the
frame, so the same title works at 720p, 1080p and vertical.

  plate.py "<keyword>" <outdir> --size 1920x1080 --fps 24 --frames 93
           [--style pop|sticker|kinetic|line|search] [--emphasis "hot dog"] [--font bold|round|serif|clean]
           [--accent D8A848] [--ink-cap 233]

--ink-cap is the brightest luma the text may reach. Text brighter than the
brightest thing in the shot reads as a sticker; openers.py measures the shot
and passes the number in.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import captions

FONTS = Path(__file__).resolve().parent.parent / "fonts"
FACES = {
    "bold": ("ArchivoBlack-400.ttf", True),
    "round": ("Baloo2-800.ttf", False),
    "serif": ("Fraunces-600.ttf", False),
    "clean": ("Outfit-500.ttf", False),
}
FALLBACKS = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
             "C:/Windows/Fonts/arialbd.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


class Type:
    def __init__(self, face):
        name, self.upper = FACES[face]
        path = FONTS / name
        if not path.is_file():
            path = next((Path(p) for p in FALLBACKS if Path(p).is_file()), None)
        if path is None:
            raise SystemExit("no usable font found; the skill's fonts/ folder is missing")
        self.path = str(path)

    def font(self, size):
        return ImageFont.truetype(self.path, max(8, int(size)))

    def case(self, s):
        return s.upper() if self.upper else s

    def fit(self, text, max_w, start, floor):
        size = start
        while size > floor:
            f = self.font(size)
            bb = f.getbbox(text)
            if bb[2] - bb[0] <= max_w:
                return f
            size -= 2
        return self.font(floor)


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def shadow(layer, radius, spread=1.6, alpha=155):
    a = layer.split()[3].point(lambda v: min(255, int(v * spread)))
    a = a.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * alpha / 255))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    return sh


def scrim(size, height_frac=0.46, strength=0.60):
    """A soft dark ramp under the title so it reads on any footage."""
    w, h = size
    g = Image.new("L", (1, h), 0)
    top = int(h * (1 - height_frac))
    for y in range(top, h):
        t = (y - top) / max(1, h - top)
        g.putpixel((0, y), int(255 * strength * (t ** 1.6)))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.putalpha(g.resize((w, h)))
    return out


def split_two(tp, words):
    """Two lines as close in width as possible, so no word is left alone."""
    probe = tp.font(100)

    def w(s):
        b = probe.getbbox(s)
        return b[2] - b[0]

    cut = min(range(1, len(words)),
              key=lambda i: abs(w(" ".join(words[:i])) - w(" ".join(words[i:]))))
    return [" ".join(words[:cut]), " ".join(words[cut:])]


def draw_kinetic(canvas, kw, p, ink, accent, W, H, s, tp, tall):
    """Stacked lines snapping in from the left, last line in the accent."""
    words = tp.case(kw).split()
    lines = split_two(tp, words) if len(words) > 2 else words
    max_w = int(W * (0.84 if tall else 0.58))
    font = min((tp.fit(ln, max_w, 104 * s, 30 * s) for ln in lines),
               key=lambda f: f.size)
    lh = int(font.size * 1.02)
    x = int(W * 0.075)
    y0 = int(H * (0.66 if tall else 0.60))
    d = ImageDraw.Draw(canvas)
    for i, ln in enumerate(lines):
        lp = (p - i * 0.09) / 0.22
        if lp <= 0:
            continue
        e = ease_out(min(1.0, lp))
        col = accent if (i == len(lines) - 1 and len(lines) > 1) else ink
        d.text((x + int(-44 * s * (1 - e)), y0 + i * lh - font.getbbox(ln)[1]), ln,
               font=font, fill=(*col, int(255 * min(1.0, lp * 1.4))))
    bp = ease_out(max(0.0, min(1.0, (p - 0.06) / 0.28)))
    bh = int(len(lines) * lh * bp)
    if bh > 3:
        d.rectangle([x - int(28 * s), y0 - int(8 * s), x - int(19 * s),
                     y0 - int(8 * s) + bh], fill=(*accent, 245))


def draw_line(canvas, kw, p, ink, accent, W, H, s, tp, tall):
    """One centred line over a rule that wipes out from the middle."""
    d = ImageDraw.Draw(canvas)
    text = tp.case(kw)
    font = tp.fit(text, int(W * (0.86 if tall else 0.74)), 92 * s, 26 * s)
    bb = font.getbbox(text)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x, y = (W - tw) // 2, int(H * 0.775)
    rise = int(26 * s * (1 - ease_out(min(1.0, p / 0.20))))
    d.text((x - bb[0], y - bb[1] + rise), text, font=font,
           fill=(*ink, int(255 * min(1.0, p / 0.16))))
    wp = ease_out(max(0.0, min(1.0, (p - 0.10) / 0.26)))
    half = int(tw * 0.5 * wp)
    ry = y + th + int(20 * s)
    if half > 2:
        d.rectangle([W // 2 - half, ry, W // 2 + half, ry + max(3, int(5 * s))],
                    fill=(*accent, 240))


def draw_search(canvas, kw, p, ink, accent, W, H, s, tp, tall):
    """A search field the shopper recognises; the keyword types itself in."""
    d = ImageDraw.Draw(canvas)
    text = kw.lower()
    glyph_w, gap, pad_x, pad_y = int(56 * s), int(20 * s), int(40 * s), int(30 * s)
    font = tp.fit(text, int(W * (0.80 if tall else 0.58)) - glyph_w - gap - 2 * pad_x,
                  60 * s, 20 * s)
    bb = font.getbbox(text)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pill_w, pill_h = glyph_w + gap + tw + pad_x * 2, th + pad_y * 2
    x0, y0 = (W - pill_w) // 2, int(H * 0.735)

    grow = ease_out(min(1.0, p / 0.16)) if p < 0.16 else 1.0
    cw = int(pill_w * (0.55 + 0.45 * grow))
    d.rounded_rectangle([(W - cw) // 2, y0, (W - cw) // 2 + cw, y0 + pill_h],
                        radius=pill_h // 2, fill=(12, 10, 9, 205),
                        outline=(*accent, 150), width=max(2, int(3 * s)))
    if grow < 1.0:
        return
    gx, gy, rr = x0 + pad_x + glyph_w // 2, y0 + pill_h // 2, int(17 * s)
    d.ellipse([gx - rr, gy - rr, gx + rr, gy + rr], outline=(*ink, 225),
              width=max(2, int(4 * s)))
    d.line([gx + rr * .72, gy + rr * .72, gx + rr * 1.5, gy + rr * 1.5],
           fill=(*ink, 225), width=max(2, int(5 * s)))
    tprog = (p - 0.16) / 0.34
    n = len(text) if tprog >= 1 else max(0, int(len(text) * ease_in_out(max(0, tprog))))
    shown = text[:n]
    tx, ty = x0 + pad_x + glyph_w + gap, y0 + pad_y - bb[1]
    d.text((tx, ty), shown, font=font, fill=(*ink, 255))
    sb = font.getbbox(shown) if shown else (0, 0, 0, 0)
    cur = tx + (sb[2] - sb[0]) + int(6 * s)
    if n < len(text) or (p * 5.0) % 1.0 < 0.55:
        d.rounded_rectangle([cur, y0 + pad_y - 2, cur + max(2, int(4 * s)),
                             y0 + pad_y + th + 2], radius=2, fill=(*accent, 235))


STYLES = {"kinetic": draw_kinetic, "line": draw_line, "search": draw_search}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def render(keyword, outdir, size, frames, style="pop", face="bold",
           accent=(216, 168, 72), ink_cap=233, hold_out=0.55, fps=24.0, emphasis=(),
           place=None, scale=1.0):
    """Draws the title. Returns the second the title lands on (the loud styles),
    or None (the quiet ones)."""
    W, H = size
    s = min(W, H) / 720
    tall = H > W
    tp = Type(face)
    keyword = captions.drawable(keyword, tp.path)
    if style in captions.STYLES:
        return captions.STYLES[style](keyword.split(), emphasis, outdir, W, H, float(fps),
                                      frames, tp.path, accent,
                                      scale=scale, **({"place": place} if place else {}))
    ink = (242, 242, 239)
    lum = .2126 * ink[0] + .7152 * ink[1] + .0722 * ink[2]
    if lum > ink_cap:
        ink = tuple(int(c * ink_cap / lum) for c in ink)

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    base = scrim((W, H))
    empty = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fn = STYLES[style]
    for i in range(frames):
        p = i / max(1, frames - 1)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fn(canvas, keyword, p, ink, accent, W, H, s, tp, tall)
        frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        frame.alpha_composite(Image.blend(empty, base, min(1.0, p / 0.10)))
        frame.alpha_composite(shadow(canvas, radius=15 * s))
        frame.alpha_composite(canvas)
        hold_out = max(hold_out, 1 - 0.9 / max(0.5, frames / float(fps)))  # readable until 0.9 s before the cut
        if p > hold_out:
            fade = 1 - ease_in_out(min(1.0, (p - hold_out) / (1 - hold_out)))
            frame.putalpha(frame.split()[3].point(lambda v: int(v * fade)))
        frame.save(out / f"f{i:04d}.png", compress_level=1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword")
    ap.add_argument("outdir")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--fps", type=float, default=24)
    ap.add_argument("--frames", type=int)
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--style", choices=sorted([*STYLES, *captions.STYLES]), default="pop")
    ap.add_argument("--emphasis", default="", help="the words that make this keyword different")
    ap.add_argument("--font", choices=sorted(FACES), default="bold")
    ap.add_argument("--accent", default="D8A848")
    ap.add_argument("--ink-cap", type=int, default=233)
    a = ap.parse_args()
    W, H = (int(v) for v in a.size.lower().split("x"))
    n = a.frames or int(round(a.seconds * a.fps))
    render(a.keyword, a.outdir, (W, H), n, a.style, a.font, hex_rgb(a.accent), a.ink_cap,
           fps=a.fps, emphasis=a.emphasis.split())
    print(f"{n} frames -> {a.outdir}")


if __name__ == "__main__":
    main()
