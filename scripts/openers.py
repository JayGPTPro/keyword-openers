#!/usr/bin/env python3
"""Keyword openers: one finished product video in, one version per keyword out.

Only the PICTURE of the first seconds is replaced. The video's own soundtrack
(music, voiceover, sound design) is never moved, so each version is exactly as
long as the original and never sounds like two clips glued together. The new
opening always ends on one of the video's OWN cuts, so the return to the
original lands on an edit that was already there.

  openers.py inspect <video> <workdir> [--keywords "kw one; kw two"]
      Reads the video. Writes inspect.json (size, fps, the cuts, the window
      to replace, an accent colour taken from the video), opening-sheet.jpg
      (what is on screen in the first seconds), look-sheet.jpg (the look of
      the whole video, for writing matching prompts) and a starter plan.json.

  openers.py build <workdir>/plan.json
      For every keyword whose opener clip exists: swap the opening picture,
      draw the keyword title, check the result, and write out/<keyword>.mp4,
      a seam sheet per version and out/index.html to review them all.

Needs: ffmpeg + ffprobe on PATH, python3 with numpy and Pillow.
"""
import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plate  # noqa: E402

WINDOW_MIN, WINDOW_MAX, WINDOW_WISH = 2.0, 6.0, 4.0
XFADE_FRAMES = 8


# ------------------------------------------------------------------ helpers

def need_tools():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} is not installed. On a Mac: brew install ffmpeg")


def run(cmd, binary=False):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=not binary)
    if r.returncode:
        err = r.stderr if not binary else r.stderr.decode("utf8", "replace")
        lines = [ln for ln in err.splitlines() if ln.strip()]
        raise RuntimeError((lines[0] if lines else "ffmpeg failed") + (" | " + lines[-1] if len(lines) > 1 else ""))
    return r.stdout


def info(path):
    """Size, frame rate, length and audio of a video file."""
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"file not found: {path}")
    try:
        j = json.loads(run(["ffprobe", "-v", "error", "-count_packets", "-show_streams", "-show_format",
                            "-of", "json", path]))
    except RuntimeError:
        raise SystemExit(f"{path.name} is not a video file this can read (it may be damaged or still downloading).")
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        raise SystemExit(f"no video stream in {path.name}")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    def frac(x):
        try:
            return Fraction(x)
        except (ZeroDivisionError, ValueError, TypeError):
            return Fraction(0)

    avg, nominal = frac(v.get("avg_frame_rate")), frac(v.get("r_frame_rate"))
    rate = avg if avg > 0 else nominal
    if rate <= 0:
        raise SystemExit(f"cannot read the frame rate of {path.name}")
    vfr = nominal > 0 and abs(float(avg) - float(nominal)) / float(nominal) > 0.01
    w, h = int(v["width"]), int(v["height"])
    rots = [str(v.get("tags", {}).get("rotate", ""))] + [str(d.get("rotation", "")) for d in v.get("side_data_list", [])]
    if any(r.lstrip("-") in ("90", "270") for r in rots):
        w, h = h, w
    return {"width": w, "height": h, "fps": rate, "fps_str": f"{rate.numerator}/{rate.denominator}",
            "duration": float(j["format"]["duration"]),
            "audio": a["codec_name"] if a else None,
            "rate": int(a.get("sample_rate") or 0) if a else 0,
            "vcodec": v["codec_name"], "vfr": vfr,
            "vframes": int(v.get("nb_read_packets") or v.get("nb_frames") or 0)}


def gray_frames(path, fps_str, w=160, h=90, seconds=None, start=None):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.4f}"]
    cmd += ["-i", path]
    if seconds is not None:
        cmd += ["-t", f"{seconds:.4f}"]
    cmd += ["-vf", f"fps={fps_str},scale={w}:{h},format=gray", "-f", "rawvideo", "-"]
    raw = run(cmd, binary=True)
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w).astype(np.float32)


def find_cuts(path, fps, fps_str):
    """The video's own edits in its first 20 seconds, by frame difference."""
    fr = gray_frames(path, fps_str, seconds=20)
    if len(fr) < 3:
        return []
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    thr = max(d.mean() + 3 * d.std(), 12.0)
    cuts, last = [], -99.0
    for i, v in enumerate(d):
        t = float((i + 1) / fps)
        if v > thr and t - last > 0.3:
            cuts.append(round(t, 4))
            last = t
    return cuts


def grab(path, t, width=480):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp = Path(f.name)
    try:
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0, t):.4f}", "-i", path,
             "-frames:v", 1, "-vf", f"scale={width}:-2", tmp])
        return Image.open(tmp).convert("RGB").copy()
    finally:
        tmp.unlink(missing_ok=True)


def label_font(size=20):
    for p in (plate.FONTS / "Outfit-500.ttf", *plate.FALLBACKS):
        if Path(p).is_file():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def sheet(tiles, out, cols):
    """A contact sheet. Every tile carries its own time, so nobody guesses."""
    if not tiles:
        return
    tw, th = tiles[0][1].size
    rows = (len(tiles) + cols - 1) // cols
    pad, bar = 8, 30
    im = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + bar + pad) + pad), (18, 18, 20))
    d = ImageDraw.Draw(im)
    f = label_font()
    for i, (label, tile) in enumerate(tiles):
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + bar + pad)
        im.paste(tile, (x, y + bar))
        d.text((x + 2, y + 3), label, font=f, fill=(235, 235, 230))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=88)


def accent_from(path, duration):
    """The video's own strongest colour, so the title belongs to it."""
    px = []
    for k in range(8):
        im = grab(path, duration * (k + 0.5) / 8, width=96).convert("HSV")
        px.append(np.asarray(im).reshape(-1, 3))
    hsv = np.concatenate(px).astype(np.float32)
    strong = hsv[(hsv[:, 1] > 115) & (hsv[:, 2] > 120)]
    if len(strong) < 0.02 * len(hsv):
        return "D8A848"
    bins = (strong[:, 0] // 11).astype(int)
    top = np.bincount(bins).argmax()
    h, s, v = np.median(strong[bins == top], axis=0)
    v = max(v, 205)
    rgb = Image.new("HSV", (1, 1), (int(h), int(s), int(v))).convert("RGB").getpixel((0, 0))
    return "".join(f"{c:02X}" for c in rgb)


def slug(kw):
    return re.sub(r"[^\w]+", "-", kw.lower(), flags=re.UNICODE).strip("-_") or "keyword"


def spec_notes(m):
    """Sponsored Brands video asks for these; say so before the upload does."""
    notes = []
    if not 6 <= m["duration"] <= 45:
        notes.append(f"length is {m['duration']:.1f}s; Sponsored Brands video takes 6 to 45 seconds")
    if min(m["width"], m["height"]) < 720:
        notes.append(f"size is {m['width']}x{m['height']}; Sponsored Brands video needs at least 1280x720")
    ratio = m["width"] / m["height"]
    if abs(ratio - 16 / 9) > 0.02 and abs(ratio - 9 / 16) > 0.02:
        notes.append("the frame is neither 16:9 nor 9:16")
    if not 23.9 <= float(m["fps"]) <= 30.1:
        notes.append(f"frame rate is {float(m['fps']):.2f}; Amazon accepts 23.976 to 30")
    if float(m["fps"]) > 30.1:
        notes.append("the versions keep this frame rate, so Amazon would reject them too; export the video at 30 first")
    if m.get("vfr"):
        notes.append("the frame rate is variable (common for phone and screen recordings); convert the video to a "
                     "constant frame rate first, or the picture and the sound drift apart")
    if m["width"] % 2 or m["height"] % 2:
        notes.append(f"the size {m['width']}x{m['height']} is odd; export it with even numbers")
    if m["audio"] is None:
        notes.append("the video has no sound")
    elif m.get("rate") and m["rate"] > 48000:
        notes.append(f"the sound is {m['rate'] // 1000} kHz; if Amazon rejects the upload, re-export the video at 48 kHz")
    return notes


# ------------------------------------------------------------------ inspect

def choose_window(cuts, limit=WINDOW_MAX):
    ok = [c for c in cuts if WINDOW_MIN <= c <= limit]
    if ok:
        return min(ok, key=lambda c: abs(c - WINDOW_WISH)), "cut"
    return min(WINDOW_WISH, limit), "dissolve"


def cmd_inspect(a):
    need_tools()
    video = Path(a.video).expanduser().resolve()
    work = Path(a.workdir).expanduser()
    work.mkdir(parents=True, exist_ok=True)
    m = info(video)
    fps = m["fps"]
    if m["duration"] < 4.0:
        raise SystemExit(f"This video is {m['duration']:.1f} seconds long. It needs at least 4 seconds, "
                         f"and Sponsored Brands video needs 6.")
    cuts = find_cuts(video, fps, m["fps_str"])
    window, join = choose_window(cuts, limit=min(WINDOW_MAX, m["duration"] - 1.0))

    tall = m["height"] > m["width"]
    tw = 270 if tall else 480
    times = [round(0.25 + 0.5 * i, 2) for i in range(int(min(7.0, m["duration"]) / 0.5))]
    sheet([(f"{t:.2f}s" + ("  REPLACED" if t < window else "  kept"), grab(video, t, tw))
           for t in times], work / "opening-sheet.jpg", cols=6 if tall else 4)
    look = [m["duration"] * (k + 0.5) / 8 for k in range(8)]
    sheet([(f"{t:.1f}s", grab(video, t, tw)) for t in look], work / "look-sheet.jpg",
          cols=8 if tall else 4)

    accent = accent_from(video, m["duration"])
    out = {
        "video": str(video), "width": m["width"], "height": m["height"],
        "fps": round(float(fps), 3), "duration": round(m["duration"], 3),
        "audio": m["audio"],
        "aspect": "9:16" if tall else "16:9",
        "cuts_first_20s": cuts,
        "window_seconds": window,
        "join": join,
        "opener_seconds_to_generate": 5 if window <= 4.6 else int(np.ceil(window + 0.5)),
        "accent": accent,
        "notes": spec_notes(m),
    }
    (work / "inspect.json").write_text(encoding="utf-8", data=json.dumps(out, indent=2))

    plan = work / "plan.json"
    kws = []
    if a.keywords:
        kws = [k.strip() for k in re.split(r"[;\n]" if re.search(r"[;\n]", a.keywords) else r",", a.keywords) if k.strip()]
        seen = {}
        for k in kws:
            if slug(k) in seen:
                out["notes"].append(f'"{k}" and "{seen[slug(k)]}" are the same keyword; the second one is dropped')
            else:
                seen[slug(k)] = k
            if len(k.split()) > 5:
                out["notes"].append(f'"{k}" has {len(k.split())} words; on screen it will be small. '
                                    f'Give it a shorter "title_text" in plan.json')
        kws = list(seen.values())
        (work / "inspect.json").write_text(encoding="utf-8", data=json.dumps(out, indent=2))
    if kws and not plan.exists():
        plan.write_text(encoding="utf-8", data=json.dumps({
            "video": str(video), "window": window, "style": "pop",
            "font": "bold", "accent": accent, "title": True, "opener_audio": "off",
            "variants": [{"keyword": k, "opener": f"openers/{slug(k)}.mp4"} for k in kws],
        }, indent=2))
        (work / "openers").mkdir(exist_ok=True)

    print(json.dumps(out, indent=2))
    if kws and plan.exists() and not (work / "openers").is_dir():
        pass
    elif a.keywords and plan.exists() and plan.stat().st_mtime < (work / "inspect.json").stat().st_mtime - 1:
        print("\nplan.json already exists and was kept as it is. Add new keywords to its variants list by hand, or delete it and run inspect again.")
    if not a.keywords and not plan.exists():
        print('\nNo keywords given, so no plan.json was written. Run again with --keywords "first; second; third".')
    if join == "dissolve":
        print(f"\nNo cut between {WINDOW_MIN:.0f}s and {WINDOW_MAX:.0f}s. The new opening "
              f"will dissolve into the video at {window:.1f}s instead of landing on a cut.")
    print(f"\nLook at {work / 'opening-sheet.jpg'} before going on: if a logo, a price, "
          f"a claim or burned-in text sits in the REPLACED frames, it will be gone.")


# -------------------------------------------------------------------- build

def emphasis_of(keywords):
    """The words that make each keyword different from the others: the words the
    whole list does not share. Those are the ones the title marks."""
    uniq = list(dict.fromkeys(k.lower() for k in keywords))
    sets = [set(k.split()) for k in uniq]
    need = len(sets) if len(sets) <= 2 else (len(sets) + 1) // 2
    shared = {w for st in sets for w in st if sum(w in o for o in sets) >= need} if len(sets) > 1 else set()
    return {k: [w for w in k.split() if w.lower() not in shared] for k in keywords}


def audio_md5(path):
    try:
        out = run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:a:0", "-c", "copy",
                   "-f", "md5", "-"])
        return out.strip()
    except RuntimeError:
        return None


def ink_cap_for(opener, fps_str, start_s, seconds):
    """Brightest thing in the lower part of the shot; the text stays under it."""
    fr = gray_frames(opener, "4", w=160, h=90, seconds=seconds, start=start_s)
    if not len(fr):
        return 233
    return int(np.clip(np.percentile(fr[:, 45:, :], 99.5), 175, 242))


def calm_band(opener, start_s, seconds):
    """Where the title covers less: the top band or the bottom band of the shot.
    The busier band (brighter, more detail) is where the subject is, so the
    title goes to the other one."""
    fr = gray_frames(opener, "4", w=160, h=90, seconds=seconds, start=start_s)
    if not len(fr):
        return "bottom"

    def busy(band):
        gy, gx = np.gradient(band, axis=(1, 2))
        return float(band.mean() * 0.2 + (np.abs(gx) + np.abs(gy)).mean() * 8)

    top, bottom = busy(fr[:, 6:34, 24:136]), busy(fr[:, 52:82, 24:136])
    return "top" if top < bottom * 0.8 else "bottom"


def build_one(film, m, v, plan, base, outdir, td):
    kw = v["keyword"]
    # several takes of one keyword: each carries a label and gets its own file
    name = slug(kw) + (f"-{slug(str(v['label']))}" if v.get("label") else "")
    opener = (base / v["opener"]).expanduser() if not Path(v["opener"]).is_absolute() \
        else Path(v["opener"])
    if not opener.is_file():
        return {"keyword": kw, "status": "waiting", "note": f"no opener clip at {v['opener']}"}

    fps, F = m["fps"], m["fps_str"]
    W, H = m["width"], m["height"]
    om = info(opener)
    op_secs = om["vframes"] / float(om["fps"]) if om["vframes"] else om["duration"]
    op_frames = int(op_secs * float(fps) + 1e-6)
    window = float(v.get("window") or plan.get("window") or WINDOW_WISH)
    N = int(round(window * fps))
    if op_frames < N:
        return {"keyword": kw, "status": "failed",
                "note": f"the opener's picture is {op_secs:.2f}s long and the opening to replace is "
                        f"{window:.2f}s; the opener must be at least {window + 0.1:.1f}s, or pick an earlier cut"}
    if abs(om["width"] / om["height"] - W / H) > 0.2:
        return {"keyword": kw, "status": "failed",
                "note": f"the opener is {om['width']}x{om['height']} and the video is "
                        f"{W}x{H}; generate the opener in the video's own aspect ratio"}
    # which part of the opener to keep: its end (the payoff, the default) or its
    # start (when the action itself is the point, like a stick extending)
    S = 0 if (v.get("take") or plan.get("take")) == "start" else op_frames - N
    cuts = plan.get("_cuts", [])
    on_cut = any(abs(c - window) < 1.5 / float(fps) for c in cuts)

    inputs = ["-i", film, "-i", opener]
    fc = [f"[1:v]fps={F},scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H},setsar=1,trim=start_frame={S}:end_frame={S + N},"
          f"setpts=PTS-STARTPTS,format=yuv420p[o0]"]
    head = "o0"
    if plan.get("title", True):
        plates = td / f"{name}-plates"
        cap = ink_cap_for(opener, F, S / float(fps), N / float(fps))
        text = v.get("title_text") or kw
        place = v.get("place") or plan.get("place") or "auto"
        if place == "auto":
            place = calm_band(opener, S / float(fps), N / float(fps))
        emph = v.get("emphasis")
        emph = emph.split() if isinstance(emph, str) else (emph or plan["_emphasis"].get(kw, []))
        hit = plate.render(text, plates, (W, H), N,
                           plan.get("style", "pop"), plan.get("font", "bold"),
                           plate.hex_rgb(plan.get("accent") or "D8A848"), cap,
                           fps=float(fps), emphasis=emph, place=place)
        P = int(round((hit or 0) * float(fps)))
        if hit and plan.get("punch", True) and 4 < P < N - 8:
            # the jump zoom: a hard cut to a tighter frame on the beat the title
            # lands. An instant cut reads as an edit; a slow push would not.
            z = float(plan.get("punch_zoom", 1.15))
            zw, zh = int(W * z / 2 + 0.5) * 2, int(H * z / 2 + 0.5) * 2
            fc.append(f"[o0]split[pa][pb];[pa]trim=end_frame={P},setpts=PTS-STARTPTS[pa1];"
                      f"[pb]trim=start_frame={P},setpts=PTS-STARTPTS,scale={zw}:{zh},"
                      f"crop={W}:{H},setsar=1,format=yuv420p[pb1];"
                      f"[pa1][pb1]concat=n=2:v=1:a=0[op]")
            head = "op"
        inputs += ["-framerate", F, "-i", plates / "f%04d.png"]
        fc.append(f"[{head}][2:v]overlay=eof_action=pass:format=auto,format=yuv420p[o1]")
        head = "o1"
    if on_cut:
        fc.append(f"[0:v]fps={F},setsar=1,trim=start_frame={N},setpts=PTS-STARTPTS,"
                  f"format=yuv420p[t]")
        fc.append(f"[{head}][t]concat=n=2:v=1:a=0[v]")
    else:
        X = min(XFADE_FRAMES, N // 2)
        fc.append(f"[0:v]fps={F},setsar=1,trim=start_frame={N - X},setpts=PTS-STARTPTS,"
                  f"format=yuv420p[t]")
        fc.append(f"[{head}]settb=AVTB,fps={F}[hx];[t]settb=AVTB,fps={F}[tx]")
        fc.append(f"[hx][tx]xfade=transition=fade:duration={X / float(fps):.5f}:"
                  f"offset={(N - X) / float(fps):.5f},format=yuv420p[v]")

    out = outdir / f"{name}.mp4"
    venc = ["-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart"]
    fold = str(plan.get("opener_audio", "off")).lower()
    copied = False
    if m["audio"] is None:
        run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
             "-map", "[v]", "-an", *venc, out])
    elif fold != "off" and om["audio"]:
        fa = (f"[1:a]atrim=start={S / float(fps):.5f}:duration={N / float(fps):.5f},"
              f"asetpts=PTS-STARTPTS,volume={float(fold)}dB,"
              f"apad=whole_dur={m['duration']:.4f}[oa];"
              # normalize=0 is load-bearing: amix otherwise halves every input,
              # and the video's own track must come out at its own level
              f"[0:a][oa]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
        run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
             ";".join(fc) + ";" + fa, "-map", "[v]", "-map", "[a]", *venc,
             "-c:a", "aac", "-b:a", "192k", out])
    else:
        try:
            run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
                 "-map", "[v]", "-map", "0:a:0", *venc, "-c:a", "copy", out])
            copied = True
        except RuntimeError:  # a track mp4 cannot carry as is
            run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
                 "-map", "[v]", "-map", "0:a:0", *venc, "-c:a", "aac", "-b:a", "256k", out])

    # ---- checks: measured on the file that was written, not on the plan
    got = info(out)
    checks = []
    same_n = got["vframes"] == m["vframes"] if (got["vframes"] and m["vframes"] and not m.get("vfr")) \
        else abs(got["duration"] - m["duration"]) <= 1.5 / float(fps)
    checks.append(("same length as the original", same_n,
                   f"{got['vframes']} frames vs {m['vframes']}"))
    if m["audio"]:
        if copied:
            h1, h2 = audio_md5(out), audio_md5(film)
            same = h1 is not None and h1 == h2
            checks.append(("soundtrack identical to the original", same,
                           "bit for bit" if same else "differs"))
        else:
            checks.append(("soundtrack kept", got["audio"] is not None, "re-encoded"))
    tail = m["duration"] - window
    diffs = []
    for frac_ in (0.08, 0.35, 0.65, 0.92):
        t_ = window + tail * frac_
        a_ = np.asarray(grab(out, t_, 160).convert("L"), dtype=np.float32)
        b_ = np.asarray(grab(film, t_, 160).convert("L"), dtype=np.float32)
        diffs.append(float(np.abs(a_ - b_).mean()))
    checks.append(("the rest of the video is untouched", max(diffs) < 5.0, f"largest difference {max(diffs):.1f}"))
    a_ = np.asarray(grab(out, window * 0.5, 160).convert("L"), dtype=np.float32)
    b_ = np.asarray(grab(film, window * 0.5, 160).convert("L"), dtype=np.float32)
    diff = float(np.abs(a_ - b_).mean())
    checks.append(("the opening is new", diff > 6.0, f"difference {diff:.1f}"))

    tall = H > W
    tw = 270 if tall else 400
    ff = 1 / float(fps)
    marks = [("start", 0.15), ("title in", window * 0.35), ("title held", window * 0.6),
             ("last new frame", window - ff), ("first original frame", window + 0.5 * ff),
             ("after", window + 0.6)]
    sheet([(f"{lab}  {t:.2f}s", grab(out, t, tw)) for lab, t in marks],
          outdir / "check" / f"{name}-seam.jpg", cols=6 if tall else 3)

    ok = all(c[1] for c in checks)
    soft = min(om["width"], om["height"]) < 0.7 * min(W, H)
    return {"keyword": kw + (f" ({v['label']})" if v.get("label") else ""),
            "status": "ready" if ok else "check", "file": out.name,
            "join": "on the video's own cut" if on_cut else "dissolve",
            "window": round(window, 3),
            "seam_sheet": f"check/{name}-seam.jpg",
            **({"note": f"the opener is {om['width']}x{om['height']}, smaller than the video; it will look soft"} if soft else {}),
            "checks": [{"what": c[0], "ok": bool(c[1]), "detail": c[2]} for c in checks]}


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Keyword openers</title><style>
:root{{--bg:#f6f3ee;--ink:#1d1a17;--mute:#6f675e;--card:#fff;--line:#e4ddd2;--ok:#1f7a4d;--bad:#b3261e;--acc:#{accent}}}
@media (prefers-color-scheme:dark){{:root{{--bg:#15130f;--ink:#f1ede6;--mute:#a39a8e;--card:#1e1b17;--line:#322d26;--ok:#59c08a;--bad:#ff8a80}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;padding:32px 16px 64px}}
main{{max-width:1180px;margin:0 auto}}h1{{font-size:30px;margin:0 0 4px;letter-spacing:-.01em}}
p.sub{{color:var(--mute);margin:0 0 28px;max-width:64ch}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax({minw}px,1fr));gap:20px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}}
video{{display:block;width:100%;background:#000}}.b{{padding:14px 16px 16px}}
.k{{font-weight:650;font-size:18px}}.k small{{font-weight:500;color:var(--mute);font-size:13px;margin-left:6px}}
ul{{list-style:none;margin:8px 0 0;padding:0;font-size:14px;color:var(--mute)}}
li.ok::before{{content:"\\2713  ";color:var(--ok)}}li.no::before{{content:"\\2717  ";color:var(--bad)}}
.tag{{display:inline-block;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin-bottom:4px}}
.note{{font-size:14px;color:var(--bad);margin-top:6px}}
</style></head><body><main>
<h1>One video. {n} openings.</h1>
<p class="sub">Each version is the same video with a new first {window:.1f} seconds of picture, matched to one keyword. The soundtrack is the original, untouched. Upload each version to the ad group that targets its keyword.</p>
<div class="grid">{cards}</div></main></body></html>"""


def write_page(outdir, film_rel, results, plan, m):
    cards = [f'<div class="card"><video src="{html.escape(film_rel)}" controls preload="metadata" '
             f'playsinline></video><div class="b"><span class="tag">Original</span>'
             f'<div class="k">Your video</div></div></div>']
    for r in results:
        if r["status"] in ("waiting", "failed"):
            cards.append(f'<div class="card"><div class="b"><span class="tag">{r["status"]}</span>'
                         f'<div class="k">{html.escape(r["keyword"])}</div>'
                         f'<div class="note">{html.escape(r["note"])}</div></div></div>')
            continue
        lis = "".join(f'<li class="{"ok" if c["ok"] else "no"}">{html.escape(c["what"])}</li>'
                      for c in r["checks"])
        cards.append(f'<div class="card"><video src="{html.escape(r["file"])}" controls '
                     f'preload="metadata" playsinline></video><div class="b">'
                     f'<span class="tag">Keyword</span><div class="k">{html.escape(r["keyword"])}'
                     f'<small>{html.escape(r["file"])}</small></div><ul>{lis}</ul></div></div>')
    n = sum(1 for r in results if r["status"] in ("ready", "check"))
    (outdir / "index.html").write_text(encoding="utf-8", data=PAGE.format(
        accent=plan.get("accent") or "D8A848", n=n, cards="".join(cards),
        window=float(plan.get("window") or WINDOW_WISH),
        minw=260 if m["height"] > m["width"] else 420))


STYLES = ("pop", "sticker", "kinetic", "line", "search")
FONTS_OK = ("bold", "round", "serif", "clean")


def validate(plan):
    """Every mistake in plan.json, in words. A typo must never draw the wrong thing quietly."""
    bad = []

    def one_of(where, key, value, allowed):
        if value is not None and value not in allowed:
            bad.append(f'{where}"{key}" is {json.dumps(value)}; it can be: {", ".join(map(str, allowed))}')

    if not plan.get("video"):
        bad.append('"video" is missing: the path of the seller\'s video')
    one_of("", "style", plan.get("style"), STYLES)
    one_of("", "font", plan.get("font"), FONTS_OK)
    one_of("", "place", plan.get("place"), ("auto", "top", "bottom"))
    one_of("", "take", plan.get("take"), ("end", "start"))
    for key in ("title", "punch"):
        if key in plan and not isinstance(plan[key], bool):
            bad.append(f'"{key}" is {json.dumps(plan[key])}; it can be: true, false (no quotes)')
    acc = plan.get("accent")
    if acc is not None:
        if not re.fullmatch(r"#?[0-9a-fA-F]{6}", str(acc)):
            bad.append(f'"accent" is {json.dumps(acc)}; it must be a 6-digit colour such as "CD763C"')
        else:
            plan["accent"] = str(acc).lstrip("#")
    oa = str(plan.get("opener_audio", "off")).lower()
    if oa != "off":
        try:
            float(oa)
        except ValueError:
            bad.append(f'"opener_audio" is {json.dumps(plan["opener_audio"])}; it can be "off" or a number of dB such as -18')
    if plan.get("window") is not None and not isinstance(plan["window"], (int, float)):
        bad.append('"window" must be a number of seconds')
    vs = plan.get("variants")
    if not isinstance(vs, list) or not vs:
        bad.append('"variants" is empty: add one entry per keyword, each with "keyword" and "opener"')
        vs = []
    names = {}
    for i, v in enumerate(vs, 1):
        w = f"variant {i}: "
        if not isinstance(v, dict) or not v.get("keyword"):
            bad.append(w + '"keyword" is missing')
            continue
        if not v.get("opener"):
            bad.append(w + f'"opener" is missing for "{v["keyword"]}": the path of its opening clip')
        one_of(w, "place", v.get("place"), ("auto", "top", "bottom"))
        one_of(w, "take", v.get("take"), ("end", "start"))
        if "style" in v:
            bad.append(w + '"style" belongs at the top of plan.json, one style for all versions')
        n = slug(v["keyword"]) + (f"-{slug(str(v['label']))}" if v.get("label") else "")
        if n in names:
            bad.append(w + f'"{v["keyword"]}" would be written over variant {names[n]} (same file name); give each a "label"')
        names[n] = i
    if bad:
        raise SystemExit("plan.json needs fixing:\n  - " + "\n  - ".join(bad))


def cmd_build(a):
    need_tools()
    plan_path = Path(a.plan).expanduser().resolve()
    if plan_path.is_dir():
        plan_path = plan_path / "plan.json"
    if not plan_path.is_file():
        raise SystemExit(f"No plan.json at {plan_path}. Run inspect with --keywords first.")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"plan.json is not valid JSON (line {e.lineno}: {e.msg}). A stray comma is the usual cause.")
    validate(plan)
    base = plan_path.parent
    film = Path(plan["video"]).expanduser()
    if not film.is_absolute():
        film = base / film
    m = info(film)
    plan["_cuts"] = find_cuts(film, m["fps"], m["fps_str"])
    if not plan.get("window"):
        plan["window"], _ = choose_window(plan["_cuts"])
    plan["_emphasis"] = emphasis_of([v["keyword"] for v in plan["variants"]])
    outdir = base / "out"
    outdir.mkdir(exist_ok=True)

    results = []
    with tempfile.TemporaryDirectory() as td:
        for v in plan["variants"]:
            try:
                r = build_one(film, m, v, plan, base, outdir, Path(td))
            except (RuntimeError, ValueError) as e:
                r = {"keyword": v["keyword"], "status": "failed", "note": str(e)[:400]}
            results.append(r)
            line = f"{r['status']:8} {r['keyword']}"
            if r.get("file"):
                line += f"  ->  out/{r['file']}  ({r['join']})"
            if r.get("note"):
                line += f"  ({r['note']})"
            print(line)
            for c in r.get("checks", []):
                if not c["ok"]:
                    print(f"         FAILED: {c['what']} ({c['detail']})")

    try:
        film_rel = str(Path("..") / film.relative_to(base))
    except ValueError:
        film_rel = film.as_uri()
    write_page(outdir, film_rel, results, plan, m)
    (outdir / "report.json").write_text(encoding="utf-8", data=json.dumps(
        {"video": str(film), "window": plan["window"], "results": results}, indent=2))
    ready = sum(1 for r in results if r["status"] == "ready")
    print(f"\n{ready} of {len(results)} ready. Review page: {outdir / 'index.html'}")
    if any(r["status"] in ("check", "failed") for r in results):
        sys.exit(2)
    if not ready:
        sys.exit(3)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect")
    i.add_argument("video")
    i.add_argument("workdir")
    i.add_argument("--keywords", help='"kw one; kw two; kw three"')
    i.set_defaults(fn=cmd_inspect)
    b = sub.add_parser("build")
    b.add_argument("plan")
    b.set_defaults(fn=cmd_build)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
