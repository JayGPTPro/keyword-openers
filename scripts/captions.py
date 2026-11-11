#!/usr/bin/env python3
"""The loud titles: the keyword set the way a phone caption editor sets it.

A Sponsored Brands video plays small, in a row of results, with the sound off.
A quiet lower-third does not stop a thumb there. These two styles do:

  pop      big stroked capitals that pop in word by word; the words that make
           THIS keyword different land on a highlighter bar that wipes in
  sticker  the keyword on a tilted white sticker that stamps in at the top,
           with the different words marked

Both are dead still once they have landed, and both are gone before the video's
own first cut, so the return to the original is clean.

Timing is in seconds, never in fractions of the window: a pop that takes 0.14 s
feels the same on a 2.5 s opening and on a 6 s one.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

START = 0.22        # nothing moves before this: let the picture register first
WORD_GAP = 0.09     # between one word's pop and the next
POP = 0.14          # one word's pop: 0.80 -> 1.06 -> 1.00
BAR = 0.20          # the highlighter wipe
OUT = 0.12          # the exit
TAIL = 0.30         # the title is gone this long before the window ends
INK = (20, 20, 20)
WHITE = (255, 255, 255)


def pop_scale(u, over=1.06, start=0.80):
    if u <= 0:
        return start
    if u >= 1:
        return 1.0
    if u < 0.6:
        return start + (over - start) * (1 - (1 - u / 0.6) ** 2)
    return over + (1.0 - over) * ((u - 0.6) / 0.4)


def readable(accent):
    """An accent bright enough to carry dark ink."""
    r, g, b = accent
    lum = .2126 * r + .7152 * g + .0722 * b
    if lum < 150:
        k = 150 / max(lum, 1)
        return tuple(min(255, int(c * k + 18)) for c in accent)
    return accent


def tile(text, font, fill, stroke=0, stroke_fill=INK):
    """One word or line on its own transparent tile, so it can be scaled alone."""
    bb = font.getbbox(text, stroke_width=stroke)
    pad = stroke + 4
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), text, font=font, fill=fill,
                            stroke_width=stroke, stroke_fill=stroke_fill)
    return im


def paste(canvas, im, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.01:
        return
    if abs(scale - 1) > 0.004:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                       Image.LANCZOS)
    if alpha < 0.99:
        im = im.copy()
        im.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
    canvas.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def fit(path, text, max_w, start, floor, stroke_ratio=0.0):
    size = int(start)
    while size > floor:
        f = ImageFont.truetype(path, size)
        bb = f.getbbox(text, stroke_width=int(size * stroke_ratio))
        if bb[2] - bb[0] <= max_w:
            return f
        size -= 2
    return ImageFont.truetype(path, int(floor))


def split(words, emph):
    """[(words, is_emphasis)] in reading order. The emphasis gets its own line
    when it is one run at the start or the end of the keyword."""
    idx = [i for i, w in enumerate(words) if w.lower() in emph]
    if idx and idx == list(range(idx[0], idx[-1] + 1)) and len(idx) < len(words):
        if idx[0] == 0:
            return [(words[:len(idx)], True), (words[len(idx):], False)]
        if idx[-1] == len(words) - 1:
            return [(words[:idx[0]], False), (words[idx[0]:], True)]
    if len(idx) == len(words) or not idx:
        if len(words) <= 2:
            return [(words, True)]
        half = len(words) // 2  # nothing tells the words apart: mark the first half, where a keyword's subject usually is
        return [(words[:half], True), (words[half:], False)]
    # emphasis in the middle: keep the order, mark the line that holds it
    cut = idx[-1] + 1 if idx[-1] < len(words) - 1 else idx[0]
    a, b = words[:cut], words[cut:]
    return [(a, any(w.lower() in emph for w in a)), (b, any(w.lower() in emph for w in b))]


def soft_shadow(canvas, radius, strength=0.55):
    a = canvas.split()[3].filter(ImageFilter.GaussianBlur(radius)).point(
        lambda v: int(v * strength))
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sh.putalpha(a)
    return sh


def exit_state(t, dur):
    """(scale, alpha) of the whole title as it leaves."""
    t_out = max(START + 0.6, dur - TAIL - OUT)
    if t <= t_out:
        return 1.0, 1.0
    u = min(1.0, (t - t_out) / OUT)
    return 1.0 - 0.14 * u, 1.0 - u


# ---------------------------------------------------------------------- pop

def render_pop(words, emph, outdir, W, H, fps, frames, font_path, accent, place="bottom"):
    s = min(W, H) / 720
    tall = H > W
    lines = split([w.upper() for w in words], {e.lower() for e in emph})
    bar_col = readable(accent)

    built = []
    for ws, is_e in lines:
        text = " ".join(ws)
        if is_e:
            f = fit(font_path, text, W * (0.80 if tall else 0.62), 136 * s, 40 * s)
        else:
            f = fit(font_path, text, W * (0.78 if tall else 0.52), 84 * s, 30 * s, 0.11)
        built.append({"words": ws, "emph": is_e, "font": f, "text": text})

    gap = int(14 * s)
    heights = []
    for b in built:
        bb = b["font"].getbbox("HX")
        b["cap"] = bb[3] - bb[1]
        b["h"] = int(b["cap"] * (1.62 if b["emph"] else 1.30))
        heights.append(b["h"])
    block = sum(heights) + gap * (len(built) - 1)
    y = int(H * (0.80 if tall else 0.86)) - block
    if place == "top":
        y = int(H * (0.12 if tall else 0.09))
    t = START
    for b in built:
        b["cy"] = y + b["h"] // 2
        y += b["h"] + gap
        f = b["font"]
        if b["emph"]:
            txt = tile(b["text"], f, INK)
            padx, pady = int(b["cap"] * 0.36), int(b["cap"] * 0.24)
            bar = Image.new("RGBA", (txt.width + 2 * padx, b["cap"] + 2 * pady + 8), (0, 0, 0, 0))
            ImageDraw.Draw(bar).rounded_rectangle(
                [0, 0, bar.width - 1, bar.height - 1], radius=int(b["cap"] * 0.16),
                fill=(*bar_col, 255))
            bar.alpha_composite(txt, ((bar.width - txt.width) // 2, (bar.height - txt.height) // 2))
            b["bar"] = bar.rotate(1.6, resample=Image.BICUBIC, expand=True)
            b["t0"] = t
            t += BAR + 0.10
            b["t1"] = b["t0"] + BAR
        else:
            stroke = max(3, int(f.size * 0.11))
            space = f.getlength(" ")
            tiles = [tile(w, f, WHITE, stroke) for w in b["words"]]
            widths = [f.getlength(w) for w in b["words"]]
            total = sum(widths) + space * (len(widths) - 1)
            x = W / 2 - total / 2
            b["tiles"] = []
            for im, wd in zip(tiles, widths):
                b["tiles"].append((im, x + wd / 2, t))
                x += wd + space
                t += WORD_GAP
            t += 0.04
    hit = max((b["t1"] for b in built if b["emph"]), default=START + POP)

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    dur = frames / fps
    for i in range(frames):
        now = i / fps
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        es, ea = exit_state(now, dur)
        for b in built:
            if b["emph"]:
                u = (now - b["t0"]) / BAR
                if u <= 0:
                    continue
                bar = b["bar"]
                if u < 1:
                    shown = bar.crop((0, 0, max(1, int(bar.width * (1 - (1 - u) ** 2))), bar.height))
                    canvas.alpha_composite(shown, (int(W / 2 - bar.width / 2),
                                                   int(b["cy"] - bar.height / 2)))
                else:
                    land = pop_scale(min(1.0, (now - b["t1"]) / POP), over=1.07, start=1.0)
                    paste(canvas, bar, W / 2, b["cy"], land * es, ea)
            else:
                for im, cx, t0 in b["tiles"]:
                    u = (now - t0) / POP
                    if u <= 0:
                        continue
                    paste(canvas, im, W / 2 + (cx - W / 2) * es, b["cy"],
                          pop_scale(u) * es, min(1.0, u * 2.5) * ea)
        frame = soft_shadow(canvas, 12 * s)
        frame.alpha_composite(canvas)
        frame.save(out / f"f{i:04d}.png", compress_level=1)
    return hit


# ------------------------------------------------------------------ sticker

def render_sticker(words, emph, outdir, W, H, fps, frames, font_path, accent, place="top"):
    s = min(W, H) / 720
    tall = H > W
    emph = {e.lower() for e in emph}
    text = " ".join(words).lower()
    glyph = int(46 * s)
    f = fit(font_path, text, W * (0.82 if tall else 0.60) - glyph, 60 * s, 24 * s)
    bb = f.getbbox("hxg")
    cap = bb[3] - bb[1]
    padx, pady = int(cap * 0.75), int(cap * 0.55)
    tw = int(f.getlength(text))
    w, h = glyph + int(cap * 0.5) + tw + 2 * padx, cap + 2 * pady
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=(255, 255, 255, 255))
    # the search glyph, drawn
    gx, gy, rr = padx + glyph // 2 - int(4 * s), h // 2 - int(2 * s), int(glyph * 0.30)
    lw = max(3, int(cap * 0.13))
    d.ellipse([gx - rr, gy - rr, gx + rr, gy + rr], outline=INK, width=lw)
    d.line([gx + rr * .7, gy + rr * .7, gx + rr * 1.55, gy + rr * 1.55], fill=INK, width=lw + 1)
    x = padx + glyph + int(cap * 0.5)
    space = f.getlength(" ")
    mark = readable(accent)
    for wd in words:
        wl = f.getlength(wd.lower())
        if wd.lower() in emph:
            d.rounded_rectangle([x - cap * 0.14, h / 2 - cap * 0.02, x + wl + cap * 0.14,
                                 h / 2 + cap * 0.62], radius=int(cap * 0.12), fill=(*mark, 255))
        d.text((x, pady - bb[1]), wd.lower(), font=f, fill=INK)
        x += wl + space
    card = card.rotate(2.5, resample=Image.BICUBIC, expand=True)
    cx, cy = W / 2, H * (0.13 if tall else 0.17)
    if place == "bottom":
        cy = H * (0.80 if tall else 0.83)

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    dur = frames / fps
    t0 = START
    for i in range(frames):
        now = i / fps
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        es, ea = exit_state(now, dur)
        u = now - t0
        if u > 0:
            if u < 0.16:
                k = u / 0.16
                sc, al = 1.7 - 0.73 * k * k, k
            elif u < 0.34:
                sc, al = 0.97 + 0.03 * ((u - 0.16) / 0.18), 1.0
            else:
                sc, al = 1.0, 1.0
            paste(canvas, card, cx, cy, sc * es, al * ea)
        frame = soft_shadow(canvas, 16 * s, 0.5)
        frame.alpha_composite(canvas)
        frame.save(out / f"f{i:04d}.png", compress_level=1)
    return t0 + 0.16


STYLES = {"pop": render_pop, "sticker": render_sticker}


def drawable(text, font_path):
    """The keyword without emoji, or a plain error when the font has no letters for it."""
    import re as _re
    text = _re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]", "", text)
    text = " ".join(text.split())
    f = ImageFont.truetype(font_path, 40)
    hole = f.getmask("\uFFFF").getbbox(), bytes(f.getmask("\uFFFF"))
    missing = sorted({c for c in text if not c.isspace() and (f.getmask(c).getbbox(), bytes(f.getmask(c))) == hole})
    if missing:
        raise ValueError(f"the title font has no letters for: {' '.join(missing[:8])}. The built-in fonts draw Latin "
                         f"letters only; give this keyword a \"title_text\" in Latin letters, or set \"title\": false")
    if not text:
        raise ValueError("the keyword has nothing to draw once the emoji are removed")
    return text
