#!/usr/bin/env python3
"""Burn captions from outputs/transcript.cut.json into the newest un-captioned render.

Picks its own input (graphics.mp4, else base.mp4). Never captions a captioned file.
Exits cleanly without writing anything when the style has captions disabled for the format.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

INPUT_ORDER = ["graphics.mp4", "base.mp4"]


def root_of(job: Path) -> Path:
    for d in [job.resolve(), *job.resolve().parents]:
        if (d / "brand.md").exists():
            return d
    sys.exit("brand.md not found above the job folder")


def brand_json(root: Path) -> dict:
    m = re.search(r"```json\s*(\{.*?\})\s*```", (root / "brand.md").read_text(), re.S)
    return json.loads(m.group(1)) if m else {}


def resolve(value, brand):
    """$accent -> brand hex, $caption -> brand font, anything else unchanged."""
    if isinstance(value, str) and value.startswith("$"):
        key = value[1:]
        v = brand.get("colors", {}).get(key) or brand.get("fonts", {}).get(key)
        if not v or v == "TODO":
            sys.exit(f"brand.md has no value for {value}. Finish the brand interview first.")
        return v
    return value


def ass_color(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def ass_alpha_color(hex_color: str, opacity: float) -> str:
    """ASS colour with alpha: 00 is opaque, FF is transparent."""
    a = round(255 * (1 - max(0.0, min(1.0, opacity))))
    return f"&H{a:02X}" + ass_color(hex_color)[4:]


def ts(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


# Words a caption line should not end on (they lean on the next word), and words a line is
# happy to start with (the natural places to break a phrase).
DANGLING = {"a", "an", "the", "of", "in", "on", "to", "my", "is", "your", "at", "for", "with", "and",
            "no", "are", "such", "very", "was", "were", "be", "that", "just", "they"}
OPENERS = {"and", "with", "where", "so", "in", "but", "because", "that", "which", "like", "or"}


def group(words, lo, hi, max_gap=0.4, min_dur=0.4, fits=lambda text: True):
    """Split words into caption lines of lo-hi words.

    Hard breaks: the end of a sentence, a pause over max_gap, or hidden words in between. Inside each run the
    break points are chosen together (dynamic programming), so the lines read as phrases:
    breaking at sentence punctuation or the end of an audio piece is free, breaking before
    an opener ("and", "with", ...) is cheap, ending a line on a dangling word ("the", "of",
    ...) is expensive, and so is a line on screen for under min_dur (a flash).
    """
    runs, cur = [], []
    for w in words:
        if cur and (w.get("_brk") or w["start"] - cur[-1]["end"] > max_gap
                    or re.search(r"[.!?]$", cur[-1]["word"])):
            runs.append(cur)
            cur = []
        cur.append(w)
    if cur:
        runs.append(cur)

    def bare(w):
        return re.sub(r"[^a-z']", "", w["word"].lower())

    def cost(run, i, j):  # line = run[i:j]
        n = j - i
        c = 0.0 if lo <= n <= hi else (0.5 if n < lo and len(run) < lo else 50.0)
        if run[j - 1]["end"] - run[i]["start"] < min_dur:
            c += 3.0
        if j < len(run):
            last, nxt = run[j - 1], run[j]
            if re.search(r"[.!?,;:]$", last["word"]):
                pass
            elif nxt.get("segment") != last.get("segment"):
                c += 0.3
            elif bare(nxt) in OPENERS:
                c += 1.0
            else:
                c += 2.0
            if bare(last) in DANGLING:
                c += 4.0
            elif bare(last) in OPENERS:
                c += 2.0
        if not fits(" ".join(w.get("_shown", w["word"]) for w in run[i:j])):
            c += 100.0
        return c

    lines = []
    for run in runs:
        best = [0.0] + [float("inf")] * len(run)
        back = [0] * (len(run) + 1)
        for j in range(1, len(run) + 1):
            for i in range(max(0, j - hi), j):
                c = best[i] + cost(run, i, j)
                if c < best[j]:
                    best[j], back[j] = c, i
        cuts, j = [], len(run)
        while j > 0:
            cuts.append((back[j], j))
            j = back[j]
        lines += [run[i:j] for i, j in reversed(cuts)]
    return lines


def silent_segments(job: Path) -> set:
    """Cut-sheet segments whose text is bracketed ("[SOUND: ...]") are sound, not speech."""
    sheet = job / "transcript" / "cutsheet.json"
    if not sheet.exists():
        return set()
    segs = json.loads(sheet.read_text())["segments"]
    return {n for n, s in enumerate(segs) if s.get("text", "").lstrip().startswith("[")}


def title_windows(job: Path) -> list:
    """Graphics that already show the spoken words (hide_captions) suppress captions."""
    plan = job / "transcript" / "graphics-plan.json"
    if not plan.exists():
        return []
    return [(float(b["start"]), float(b["end"])) for b in json.loads(plan.read_text())["beats"]
            if b.get("hide_captions")]


def hidden(word, silent, windows) -> bool:
    if word.get("segment") in silent:
        return True
    mid = (word["start"] + word["end"]) / 2
    return any(s <= mid < e for s, e in windows)


def graph_args(graph: str, path: Path):
    """ffmpeg args that read the filtergraph from a file, never inline on the command line.

    macOS XProtect blocks ffmpeg launched with a long multi-line filtergraph argument as
    "Malicious Script Blocked" (and kills the terminal with it). A graph file avoids that.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph)
    ver = subprocess.run(["ffmpeg", "-hide_banner", "-version"],
                         capture_output=True, text=True).stdout
    m = re.search(r"ffmpeg version n?(\d+)\.", ver)
    if m and int(m.group(1)) < 7:
        return ["-filter_complex_script", str(path)]
    return ["-/filter_complex", str(path)]


def has_libass() -> bool:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return re.search(r"\ssubtitles\s", out) is not None


def esc(path: Path) -> str:
    """Escape a path for a quoted filter option (spaces are fine inside quotes; ' and : are not)."""
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def burn_with_pil(job, src, lines, cfg, brand, font_file, size, color, active, enc):
    """No-libass fallback: one transparent PNG per caption line, drawn with the real font
    (baseline at cfg y, centred, offset drop shadow), overlaid in its window. Same look as
    the ASS path for highlight none/keywords."""
    from PIL import Image, ImageDraw, ImageFont
    w, h = size
    fonts = {}
    sx = sy = int(cfg.get("shadow_px", 0))
    sh = resolve(cfg.get("shadow_color", "#000000"), brand).lstrip("#")
    shadow = (int(sh[0:2], 16), int(sh[2:4], 16), int(sh[4:6], 16),
              round(255 * float(cfg.get("shadow_opacity", 1.0))))
    rgb = lambda c: tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    y = int(cfg.get("y", int(h * 0.62)))
    tmp = job / "transcript" / "caption-png"
    tmp.mkdir(exist_ok=True)
    for old in tmp.glob("*.png"):
        old.unlink()
    inputs, chain, prev = [], [], "0:v"
    for n, (start, end, words, fs) in enumerate(lines):
        font = fonts.setdefault(fs, ImageFont.truetype(str(font_file), fs))
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        text = " ".join(x for x, _ in words)
        x = (w - d.textlength(text, font=font)) / 2
        if sx:
            d.text((x + sx, y + sy), text, font=font, fill=shadow, anchor="ls")
        for word, emph in words:
            d.text((x, y), word, font=font, fill=rgb(active if emph else color), anchor="ls")
            x += d.textlength(word + " ", font=font)
        png = tmp / f"line{n:03d}.png"
        img.save(png)
        inputs += ["-loop", "1", "-t", f"{end + 0.1:.3f}", "-i", str(png)]
        out = "vout" if n == len(lines) - 1 else f"c{n}"
        chain.append(f"[{prev}][{n + 1}:v]overlay=enable='gte(t,{start:.3f})*lt(t,{end:.3f})'"
                     f":eof_action=pass[{out}]")
        prev = out
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), *inputs,
                    *graph_args(";\n".join(chain), job / "outputs" / "captioned.filtergraph.txt"),
                    "-map", "[vout]", "-map", "0:a", *enc],
                   check=True)


def probe_size(path: Path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    w, h = out.split(",")
    return int(w), int(h)


def is_captioned(path: Path) -> bool:
    if "caption" in path.name.lower():
        return True
    tags = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
                           "-of", "default=nw=1:nk=1", str(path)],
                          capture_output=True, text=True).stdout
    return "captioned" in tags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job", type=Path)
    ap.add_argument("--format", required=True, choices=["long", "short-explainer", "short-raw"])
    ap.add_argument("--style", default="editorial")
    args = ap.parse_args()

    root = root_of(args.job)
    brand = brand_json(root)
    style = json.loads((root / "styles" / args.style / "style.json").read_text())
    cfg = dict(style["captions"].get(args.format, {"enabled": False}))
    # A recipe's own caption rules (the cut sheet names its recipe), e.g. a short's
    # {"break_each_segment": true}: every fragment on its own line.
    sheet = args.job / "transcript" / "cutsheet.json"
    recipe = json.loads(sheet.read_text()).get("recipe") if sheet.exists() else None
    cfg.update(style.get("recipes", {}).get(recipe, {}).get("captions", {}))
    # Per-job overrides (a one-off ask that is not yet a style rule), e.g. {"strip_punctuation": true}
    override = args.job / "transcript" / "captions-override.json"
    if override.exists():
        cfg.update(json.loads(override.read_text()))
    if not cfg.get("enabled"):
        print(f"Captions disabled for {args.format} in style '{args.style}'. Nothing written.")
        return

    outputs = args.job / "outputs"
    src = next((outputs / n for n in INPUT_ORDER if (outputs / n).exists()), None)
    if not src:
        sys.exit("No graphics.mp4 or base.mp4 in outputs/")
    if is_captioned(src):
        sys.exit(f"{src} is already captioned. Refusing to caption it twice.")

    words = json.loads((outputs / "transcript.cut.json").read_text())["words"]
    lo, hi = cfg.get("words_per_line", [2, 4])
    font = resolve(brand.get("fonts", {}).get("caption", "$caption"), brand)
    base_c = ass_color(resolve(cfg["color"], brand))
    act_c = ass_color(resolve(cfg["active_word_color"], brand))
    stroke_c = ass_color(resolve(cfg["stroke_color"], brand))
    # Optional drop shadow: shadow_px offset, shadow_color at shadow_opacity.
    shadow_px = cfg.get("shadow_px", 0)
    shadow_c = ass_alpha_color(resolve(cfg.get("shadow_color", "#000000"), brand),
                               cfg.get("shadow_opacity", 1.0))
    w, h = probe_size(src)

    ass = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
        # Bold 0: the brand fonts are single-weight; Bold 1 makes libass fake a heavier cut.
        f"Style: Cap,{font},{cfg.get('size_px', 64)},{base_c},{stroke_c},{shadow_c},0,1,"
        f"{cfg.get('stroke_px', 6)},{shadow_px},2,80,80,{h - int(cfg.get('y', int(h * 0.62)))}",
        "", "[Events]", "Format: Layer, Start, End, Style, Text",
    ]
    # highlight: "karaoke" colours each word as it is spoken; "keywords" colours only the
    # word indices listed in transcript/caption-emphasis.json ({"indices": [...]}), for the
    # whole time their line is on screen; "none" colours nothing.
    mode = cfg.get("highlight", "karaoke")
    emphasis = set()
    if mode == "keywords":
        ep = args.job / "transcript" / "caption-emphasis.json"
        emphasis = set(json.loads(ep.read_text()).get("indices", [])) if ep.exists() else set()
    silent, windows = silent_segments(args.job), title_windows(args.job)
    segs = json.loads(sheet.read_text())["segments"] if sheet.exists() else []
    kept, skipped = [], False
    for wd in words:
        if hidden(wd, silent, windows):
            skipped = True
            continue
        wd["_brk"], skipped = skipped, False  # a caption never bridges hidden words
        if cfg.get("break_each_segment") and kept and kept[-1].get("segment") != wd.get("segment"):
            # One line per cut-sheet piece (a fragment said in one go), unless the piece is
            # marked "caption_joins_next": one phrase the pause trim split into two pieces.
            prev = kept[-1].get("segment")
            if not (isinstance(prev, int) and prev < len(segs) and segs[prev].get("caption_joins_next")):
                wd["_brk"] = True
        kept.append(wd)
    words = kept
    # {"break_before": ["new york", ...]}: start a new line on each occurrence of a phrase
    # (lowercase, punctuation ignored), for phrase boundaries the chunker cannot see, such as a
    # line that runs across a section cut, or keeping "35 to 45 dollars" together.
    bare_words = [re.sub(r"[^a-z0-9']", "", w["word"].lower()) for w in words]
    for phrase in cfg.get("break_before", []):
        p = phrase.lower().split()
        for n in range(len(words) - len(p) + 1):
            if bare_words[n:n + len(p)] == p:
                words[n]["_brk"] = True
    for n, word in enumerate(words):
        word["_i"] = n
        if cfg.get("uppercase"):
            word["word"] = word["word"].upper()
        word["_shown"] = re.sub(r"[.,!?;:\"]", "", word["word"]) if cfg.get("strip_punctuation") \
            else word["word"]

    def paint(x, on):
        return f"{{\\c{act_c}}}{x['_shown']}{{\\c{base_c}}}" if on else x["_shown"]

    plain = []  # (start, end, [(word, emphasised)]) for the non-libass path
    fits = lambda text: True
    line_size = lambda text: int(cfg.get("size_px", 64))
    try:
        from PIL import ImageFont
        size_px = int(cfg.get("size_px", 64))
        min_px = int(cfg.get("min_size_px", size_px))  # shrink a long phrase to fit, down to this
        font_path = str(root / brand["font_files"]["caption"][0])
        cap_font = ImageFont.truetype(font_path, min_px)
        fits = lambda text: cap_font.getlength(text.upper() if cfg.get("uppercase") else text) <= w - 160

        def line_size(text):
            s = size_px
            while s > min_px and ImageFont.truetype(font_path, s).getlength(text) > w - 160:
                s -= 2
            return s
    except (ImportError, KeyError, OSError):
        pass
    vid_dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(src)], capture_output=True, text=True).stdout.strip() or 0)
    for line in group(words, lo, hi, fits=fits):
        # A line ending a frame or two before a hard cut out (a loop point) holds to the last
        # frame; otherwise the final frame blinks to no caption.
        if vid_dur and 0 < vid_dur - line[-1]["end"] < 0.12:
            line[-1] = dict(line[-1], end=vid_dur)
        end = min([line[-1]["end"], *[s for s, _ in windows if s >= line[0]["start"]]])
        shown = " ".join(x["_shown"] for x in line)
        fs = line_size(shown)
        fs_tag = f"{{\\fs{fs}}}" if fs != int(cfg.get("size_px", 64)) else ""
        plain.append((line[0]["start"], end, [(x["_shown"], x["_i"] in emphasis) for x in line], fs))
        if mode == "karaoke":
            for i, active in enumerate(line):
                end = line[i + 1]["start"] if i + 1 < len(line) else active["end"]
                text = " ".join(paint(x, j == i) for j, x in enumerate(line))
                ass.append(f"Dialogue: 0,{ts(active['start'])},{ts(end)},Cap,{fs_tag}{text}")
        else:
            text = " ".join(paint(x, x["_i"] in emphasis) for x in line)
            ass.append(f"Dialogue: 0,{ts(line[0]['start'])},{ts(line[-1]['end'])},Cap,{fs_tag}{text}")

    ass_path = args.job / "transcript" / "captions.ass"
    ass_path.write_text("\n".join(ass) + "\n")
    out = outputs / "captioned.mp4"
    enc = ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-metadata", "comment=captioned", str(out)]
    if has_libass():
        fonts_dir = root / "assets" / "fonts"
        vf = f"subtitles=filename='{esc(ass_path.resolve())}':fontsdir='{esc(fonts_dir.resolve())}'"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
                        "-vf", vf, *enc], check=True)
    else:
        if mode == "karaoke":
            sys.exit("This ffmpeg has no libass (subtitles filter) and karaoke needs it: "
                     "install an ffmpeg built with libass.")
        font_file = root / brand["font_files"]["caption"][0]
        burn_with_pil(args.job, src, plain, cfg, brand, font_file, (w, h),
                      resolve(cfg["color"], brand), resolve(cfg["active_word_color"], brand), enc)
    print(f"{src.name} -> {out} ({len(words)} words)")


if __name__ == "__main__":
    main()
