#!/usr/bin/env python3
"""Montage mode: lines from anywhere in a long-form transcript, played over re-ordered B-roll.

A montage cut sheet has two tracks:

  segments  the AUDIO spine, as in a plain cut sheet: each line (or trimmed piece of one)
            in play order. remap.py reads only these, so captions stay word-accurate.
  shots     the PICTURE, in play order on the output timeline, independent of the segments,
            so one line can carry several shots and a shot can hide the join between two
            trimmed pieces of a line. Each shot:
              {"clip", "start", "dur", "x_offset", "note"}      B-roll, muted
              {"sync": true, "dur", "x_offset", "note"}          the speaker's own picture,
                                                                 lip-synced to the audio
              optional "sound_db": the shot's own sound mixed under the voice at that level.
            The last shot's dur is fitted so the picture ends exactly with the audio.

Run directly to print the plan (lines, the shots under each, total length) and validate it:
  montage.py projects/<job> [--fps 25]
"""
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

EDGE_FADE = 0.005  # s; de-clicks every audio join without touching the words


def load_sheet(job: Path) -> dict:
    return json.loads((job / "transcript" / "cutsheet.json").read_text())


def is_montage(sheet: dict) -> bool:
    return sheet.get("mode") == "montage"


def probe_fps(path: Path) -> Fraction:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    # Some DJI camera files report v:0 more than once (stream groups); the first line is the camera.
    if not out:   # audio-only (a voiceover recording used as a segment): no picture rate; never used for picture
        return Fraction(25)
    return Fraction(out.splitlines()[0].split(",")[0])


def output_fps(job: Path, sheet: dict) -> Fraction:
    """The cut's frame rate: the main footage's (the first clip in raw/), never a B-roll clip's,
    even when a B-roll sound opens the cut. A sheet may pin it with "fps"."""
    if sheet.get("fps"):
        return Fraction(str(sheet["fps"]))
    clips = [s["clip"] for s in sheet["segments"]]
    main = next((c for c in clips if c.startswith("raw/")), clips[0])
    return probe_fps(job / main)


def audio_timeline(segs):
    """[(out_start, out_end, seg)] for the audio spine."""
    t, out = 0.0, []
    for s in segs:
        d = float(s["end"]) - float(s["start"])
        out.append((t, t + d, s))
        t += d
    return out


def picture_timeline(sheet: dict, fps: Fraction):
    """Resolve shots to frame-exact windows: [(out_start, out_end, clip, src_start, n_frames, shot)].

    Cuts land on the output frame grid, so ~30 shots never drift against the audio.
    Source starts are snapped to the source frame grid (same rate as the output here).
    """
    segs = sheet["segments"]
    atl = audio_timeline(segs)
    total = atl[-1][1] if atl else 0.0
    total_frames = round(total * fps)
    shots = sheet.get("shots", [])
    if not shots:
        sys.exit("montage cut sheet has no shots")

    out, t, frame = [], 0.0, 0
    for n, sh in enumerate(shots):
        last = n == len(shots) - 1
        end_frame = total_frames if last else round((t + float(sh["dur"])) * fps)
        nf = end_frame - frame
        if nf <= 0:
            sys.exit(f"shot {n} has no frames left (picture already covers the audio): {sh}")
        o_start, o_end = float(frame / fps), float(end_frame / fps)
        if sh.get("sync"):
            # The line it overlaps most: frame snapping can start it a hair before its line.
            a, b, s = max(atl, key=lambda x: min(x[1], o_end) - max(x[0], o_start))
            if min(b, o_end) <= max(a, o_start):
                sys.exit(f"sync shot {n} lies outside the audio: {sh}")
            clip, src = s["clip"], float(s["start"]) + (o_start - a)
            if o_end > b + 0.5 / float(fps):
                print(f"WARNING: sync shot {n} runs past the end of its line by "
                      f"{o_end - b:.2f}s; lips drift after the join", file=sys.stderr)
        else:
            clip, src = sh["clip"], float(sh["start"])
        src = round(src * fps) / fps  # snap to the source frame grid
        out.append((o_start, o_end, clip, float(src), nf, sh))
        t, frame = o_end, end_frame
    return out, total


def words_in(transcript: dict, clip: str, a: float, b: float):
    for seg in transcript.get(clip, {}).get("segments", []):
        for w in seg.get("words", []):
            if "start" in w and w["end"] > a and w["start"] < b:
                yield w


def validate(job: Path, sheet: dict, fps: Fraction):
    """Hard errors exit; soft problems come back as warnings."""
    warn = []
    for s in sheet["segments"]:
        for k in ("clip", "start", "end", "text"):
            if k not in s:
                sys.exit(f"segment missing '{k}': {s}")
        if float(s["end"]) <= float(s["start"]):
            sys.exit(f"segment end <= start: {s}")
    for n, sh in enumerate(sheet.get("shots", [])):
        if not sh.get("sync"):
            for k in ("clip", "start"):
                if k not in sh:
                    sys.exit(f"shot {n} missing '{k}': {sh}")
        if "dur" not in sh and n != len(sheet["shots"]) - 1:
            sys.exit(f"shot {n} missing 'dur': {sh}")
    pic, total = picture_timeline(sheet, fps)

    # A shot that asks for more frames than its clip has renders short, silently: every later
    # shot then lands early and sync shots drift off their audio. Refuse it.
    lengths = {}
    for n, (a, b, clip, src, nf, sh) in enumerate(pic):
        if clip not in lengths:
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", str(job / clip)],
                                 capture_output=True, text=True, check=True).stdout
            lengths[clip] = float(out.splitlines()[0])
        r = probe_fps(job / clip)
        slow = r > fps and not sh.get("sync") and not sh.get("realtime")
        used = nf / float(r if slow else fps)  # faster B-roll plays every frame unless "realtime"
        if src + used > lengths[clip] + 0.5 / float(fps):
            sys.exit(f"shot {n} needs {clip} up to {src + used:.2f}s but the clip is "
                     f"{lengths[clip]:.2f}s long: {sh}")
    # Same for the audio spine: a segment past its clip's end comes up short and every later
    # line lands early against the picture.
    for s in sheet["segments"]:
        clip = s["clip"]
        if clip not in lengths:
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", str(job / clip)],
                                 capture_output=True, text=True, check=True).stdout
            lengths[clip] = float(out.splitlines()[0])
        if float(s["end"]) > lengths[clip] + 0.02:
            sys.exit(f"segment needs {clip} up to {float(s['end']):.2f}s but the clip is "
                     f"{lengths[clip]:.2f}s long: {s.get('text', '')[:60]}")

    tpath = job / "transcript" / "transcript.json"
    transcript = json.loads(tpath.read_text())["clips"] if tpath.exists() else {}
    for n, (a, b, clip, src, nf, sh) in enumerate(pic):
        dur = nf / float(fps)
        if dur < 0.4:
            warn.append(f"shot {n} is {dur:.2f}s: shorter than a readable cut")
        if "sound_db" in sh:
            spoken = list(words_in(transcript, clip, src, src + dur))
            if spoken and not sh.get("sync"):
                said = " ".join(w["word"] for w in spoken)
                warn.append(f"shot {n} carries sound_db but its window has speech: \"{said}\"")
    return pic, total, warn


def fmt(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:05.2f}"


def print_plan(sheet: dict, pic, total: float, warn):
    atl = audio_timeline(sheet["segments"])
    print(f"{'OUT':>13}  {'SOURCE':>17}  LINE / SHOTS UNDER IT")
    for a, b, s in atl:
        src = f"{fmt(float(s['start']))}-{fmt(float(s['end']))}"
        print(f"{a:5.2f}-{b:5.2f}s  {src:>17}  \"{s['text']}\"")
        for pa, pb, clip, psrc, nf, sh in pic:
            lo, hi = max(a, pa), min(b, pb)
            if hi - lo > 1e-3:
                kind = "SYNC" if sh.get("sync") else "shot"
                snd = f"  sound {sh['sound_db']} dB" if "sound_db" in sh else ""
                xo = sh.get("x_offset", 0) or 0
                print(f"{'':32}  {kind} {pa:5.2f}-{pb:5.2f}  src {fmt(psrc)}  "
                      f"x{xo:+d}  {sh.get('note', '')}{snd}")
    print(f"\nTotal: {total:.2f}s  ({len(atl)} audio segments, {len(pic)} shots)")
    for w in warn:
        print("WARNING:", w)


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: montage.py projects/<job> [--fps N]")
    job = Path(sys.argv[1])
    sheet = load_sheet(job)
    if not is_montage(sheet):
        sys.exit('cut sheet is not "mode": "montage"')
    if "--fps" in sys.argv:
        fps = Fraction(sys.argv[sys.argv.index("--fps") + 1])
    else:
        fps = output_fps(job, sheet)
    pic, total, warn = validate(job, sheet, fps)
    print_plan(sheet, pic, total, warn)


if __name__ == "__main__":
    main()
