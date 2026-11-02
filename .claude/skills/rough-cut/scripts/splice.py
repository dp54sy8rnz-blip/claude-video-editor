#!/usr/bin/env python3
"""Splice transcript/cutsheet.json into outputs/base.mp4 with ONE FFmpeg filtergraph.

One trim per kept segment, concat, then amplify + limit the audio once on the
assembled track. Audio stays PCM inside the graph, so it is encoded exactly once.
Video is re-encoded (stream copy desyncs on arbitrary cut points).

With --style/--format, a style whose rough_cut.reframe has an entry for the format puts
widescreen source on a vertical canvas: scale to picture_height, crop to the canvas width
(shifted per segment by x_offset px, positive = picture moves right), pad with black bars.

A cut sheet with "mode": "montage" takes its audio from the segments and its picture from
a separate shots track (see montage.py).
"""
import argparse
import json
import re
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

import montage


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


def default_encoder():
    if platform.system() == "Darwin":
        return ["-c:v", "h264_videotoolbox", "-b:v", "40M"]  # 4K masters: 16M blocked up visibly
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]


def root_of(job: Path) -> Path:
    for d in [job.resolve(), *job.resolve().parents]:
        if (d / "brand.md").exists():
            return d
    sys.exit("brand.md not found above the job folder")


def probe_size(path: Path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    w, h = out.splitlines()[0].split(",")[:2]
    return int(w), int(h)


def reframe_filter(size, cfg, x_offset):
    """scale -> crop (shifted, clamped to fill the width) -> pad to the canvas."""
    cw, ch = cfg["canvas"]
    ph = int(cfg["picture_height"])
    iw, ih = size
    sw = max(cw, round(iw * ph / ih / 2) * 2)
    x = min(max((sw - cw) // 2 - int(round(x_offset)), 0), sw - cw)
    return (f"scale={sw}:{ph},crop={cw}:{ph}:{x}:0,"
            f"pad={cw}:{ch}:0:{(ch - ph) // 2}:black,setsar=1")


def zoom_filter(size, z):
    """Crop a 1/scale window around (cx, cy), clamped inside the frame, and scale back to size.

    For a punch-in on a wide (a reaction, a key moment). Keep scale at or under ~1.8 on 4K sources:
    beyond that the upscale softens visibly.
    """
    iw, ih = size
    s = float(z["scale"])
    cw, ch = round(iw / s / 2) * 2, round(ih / s / 2) * 2
    x = min(max(round(float(z.get("cx", 0.5)) * iw - cw / 2), 0), iw - cw)
    y = min(max(round(float(z.get("cy", 0.5)) * ih - ch / 2), 0), ih - ch)
    return f"crop={cw}:{ch}:{x}:{y},scale={iw}:{ih}:flags=lanczos,setsar=1"


def build_montage(job: Path, sheet: dict, encoder_args, reframe=None):
    """Audio from the segments (the spine), picture from the shots (see montage.py)."""
    segs = sheet["segments"]
    fps = montage.output_fps(job, sheet)
    pic, total, warn = montage.validate(job, sheet, fps)
    for w in warn:
        print("WARNING:", w, file=sys.stderr)

    # Audio: one shared input per clip (cheap to buffer). Picture: one input PER SHOT, seeked
    # to just before its in-point. Trimming every shot out of one shared input makes ffmpeg hold
    # decoded 4K frames for every later branch while it decodes up to an earlier-needed one; an
    # edit that jumps around a long take (a cold open from its end, then back to its start) then
    # runs out of memory and is killed.
    clips = []
    for c in [s["clip"] for s in segs] + [p[2] for p in pic]:
        if c not in clips:
            clips.append(c)
    for c in clips:
        if not (job / c).exists():
            sys.exit(f"missing clip: {job / c}")
    # A segment may take its sound from another file while its picture (sync shots) stays on "clip":
    # "audio": path, "audio_start": the clip time that file's 0 s lines up with (e.g. a stem separated from
    # clip 4.0 s onwards has audio_start 4.0). Used for music-free stems (copyright) and similar cleanups.
    asrc = lambda s: s.get("audio") or s["clip"]
    for s in segs:
        if s.get("audio") and not (job / s["audio"]).exists():
            sys.exit(f"missing audio: {job / s['audio']}")
    inputs, aidx = [], {}
    for c in [asrc(s) for s in segs]:
        if c not in aidx:
            aidx[c] = len(aidx)
            inputs += ["-i", str(job / c)]
    sizes = {c: probe_size(job / c) for c in clips} if reframe else {}
    rates = {c: montage.probe_fps(job / c) for c in clips}

    parts, alabels, vlabels, beds = [], [], [], []
    e = montage.EDGE_FADE
    # "audio_xfade" (s, sheet level): every audio join is a crossfade of that length centred on the cut, so
    # room tone and street noise blend from one piece to the next instead of jumping (no harsh audio
    # switches). Each piece borrows half the crossfade from its source on both sides, so the total length
    # and every cut point stay exactly where the cut sheet puts them.
    xf = float(sheet.get("audio_xfade", 0) or 0) if len(segs) > 1 else 0.0
    for n, s in enumerate(segs):
        i = aidx[asrc(s)]
        shift = float(s.get("audio_start", 0) or 0) if s.get("audio") else 0.0
        start, end = float(s["start"]) - shift, float(s["end"]) - shift
        pre = xf / 2 if (xf and n > 0) else 0.0
        post = xf / 2 if (xf and n < len(segs) - 1) else 0.0
        # Every piece must come out exactly (end - start) + pre + post long, or every later join drifts out
        # of sync (seen in a real render: a handle cut short at two clip ends put the sound 160 ms ahead of the
        # lips for the rest of the video). A handle that runs past either end of the clip's audio is filled
        # with silence instead of being borrowed from elsewhere in the clip.
        dur = end - start + pre + post
        head = max(pre - start, 0.0)
        start, end = max(start - pre, 0.0), end + post
        if head and float(s.get("gain_db", 0) or 0) > -60:
            print(f"note: segment {n} starts {s['start'] - shift:.3f}s into its audio; {head:.3f}s of its "
                  f"crossfade handle is silence", file=sys.stderr)
        fade = max(float(s.get("fade_out", 0) or 0), e if not post else 0)
        fin = max(float(s.get("fade_in", 0) or 0), e if not pre else 0)  # e.g. ease a J-cut's street noise in
        gain = f"volume={float(s['gain_db'])}dB," if s.get("gain_db") else ""  # e.g. a faint natural sound
        if s.get("afilter"):  # a per-segment audio filter, e.g. notches for a beep under one take
            gain += s["afilter"].rstrip(",") + ","
        fades = (f"afade=t=in:d={fin:.3f}," if fin else "") + (f"afade=t=out:st={max(dur - fade, 0):.3f}:d={fade:.3f}," if fade else "")
        delay = f"adelay=delays={head * 1000:.0f}:all=1," if head else ""
        parts.append(f"[{i}:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,{delay}"
                     f"apad=whole_dur={dur:.3f},atrim=end={dur:.3f},{gain}{fades}anull[a{n}]")
        alabels.append(f"[a{n}]")
    if xf:
        prev = alabels[0]
        for n, lab in enumerate(alabels[1:], 1):
            out = "[voice]" if n == len(alabels) - 1 else f"[ax{n}]"
            parts.append(f"{prev}{lab}acrossfade=d={xf:.3f}:c1=tri:c2=tri{out}")
            prev = out
    else:
        parts.append("".join(alabels) + f"concat=n={len(segs)}:v=0:a=1[voice]")

    half = 0.5 / float(fps)
    dissolves = any(p[5].get("dissolve") for p in pic)
    orig_nf = [p[4] for p in pic]
    for n, (o_start, o_end, clip, src, nf, sh) in enumerate(pic):
        r = rates[clip]
        if n and sh.get("dissolve"):
            # Cross-dissolve in from the previous shot: take d extra seconds from before this
            # shot's in-point and overlap them on the previous shot, so the cut's timing (and
            # every later shot's sync) stays exactly where it was.
            dzf = round(float(sh["dissolve"]) * float(fps))
            src -= dzf / float(fps)
            nf += dzf
        slow = r > fps and not sh.get("sync") and not sh.get("realtime")
        used = nf / float(r if slow else fps)
        seek = max(src - 0.5, 0.0)
        i = len(aidx) + n
        inputs += ["-ss", f"{seek:.4f}", "-t", f"{src - seek + used + 0.5:.4f}", "-i", str(job / clip)]
        src -= seek  # times below are now relative to this shot's own input
        if slow:
            # Picture-only B-roll shot faster than the cut (29.97 into 25): play every source
            # frame at the cut's rate, a gentle slow-motion, instead of dropping frames (judder).
            # "realtime": true on the shot plays it at normal speed instead (conformed below).
            sh_half = 0.5 / float(r)
            v = (f"[{i}:v]trim=start={src - sh_half:.4f}:end={src + nf / float(r) - sh_half:.4f},"
                 f"setpts=N/({fps.numerator}/{fps.denominator}*TB)")
        else:
            v = (f"[{i}:v]trim=start={src - half:.4f}:end={src + nf / float(fps) - half:.4f},"
                 f"setpts=PTS-STARTPTS")
            if r != fps:  # synced to its own sound: conform by dropping/repeating frames
                v += f",fps={fps.numerator}/{fps.denominator}"
        # Exactly nf frames per shot: a conform can come up a frame short, which would slide every
        # later shot early against the audio (lips out of sync). Clone the tail, cut to the count.
        v += f",tpad=stop_mode=clone:stop=2,trim=end_frame={nf},setpts=PTS-STARTPTS"
        if sh.get("eq"):  # per-shot grade, e.g. "brightness=-0.1:contrast=1.15" for a blown-out shot
            v += f",eq={sh['eq']}"
        if sh.get("vf"):  # any per-shot filter, e.g. highlight recovery or "deshake,crop=..." on a shaky insert
            v += "," + sh["vf"]
        if sh.get("zoom"):  # punch-in: {"scale": 1.6, "cx": 0.46, "cy": 0.40}, centre as a share of the frame
            v += "," + zoom_filter(probe_size(job / clip), sh["zoom"])
        grade = sheet.get("grade") or {}
        for prefix, match in (grade.get("match") or {}).items():  # per-camera match, e.g. {"raw/CAM-B/": "eq=..."}
            if clip.startswith(prefix):
                v += "," + match
        # The video's look, after the camera match; "look_skip" lists clip prefixes it is not applied to.
        if grade.get("look") and not any(clip.startswith(p) for p in grade.get("look_skip") or []):
            v += "," + grade["look"]
        if sh.get("extra_vf"):  # a per-shot adjustment after the shared look (e.g. boost one colour range)
            v += "," + sh["extra_vf"]
        if reframe:
            v += "," + reframe_filter(sizes[clip], reframe, sh.get("x_offset", 0) or 0)
        if dissolves:  # xfade needs every stream on the same rate, timebase and pixel format
            v += f",fps={fps.numerator}/{fps.denominator},settb=AVTB,format=yuv420p,setsar=1"
        parts.append(v + f"[v{n}]")
        vlabels.append(f"[v{n}]")
        if "sound_db" in sh and not sh.get("sync"):
            d = nf / float(fps)
            parts.append(f"[{i}:a]atrim=start={src:.3f}:end={src + d:.3f},asetpts=PTS-STARTPTS,"
                         f"volume={float(sh['sound_db'])}dB,afade=t=in:d={e},"
                         f"afade=t=out:st={max(d - e, 0):.3f}:d={e},"
                         f"adelay={round(o_start * 1000)}:all=1[n{n}]")
            beds.append(f"[n{n}]")
    # Picture and sound end on the same frame: the concat can come up a frame short, so clone the
    # last frame and cut to the exact count; the sound is cut there too, with a short fade, so the
    # loop restarts clean.
    n_frames = sum(p[4] for p in pic)
    end = n_frames / float(fps)
    if not dissolves:
        parts.append("".join(vlabels) + f"concat=n={len(pic)}:v=1:a=0,"
                     f"tpad=stop_mode=clone:stop=2,trim=end_frame={n_frames}[vc]")
    else:
        # Hard cuts are concatenated in runs; a dissolve shot is xfaded onto the run before it.
        run, cur, acc = [vlabels[0]], None, 0
        for n in range(1, len(pic) + 1):
            if n < len(pic) and not pic[n][5].get("dissolve"):
                run.append(vlabels[n])
                continue
            lab = f"[r{n}]"
            src_labels = ([cur] if cur else []) + run
            parts.append("".join(src_labels) + f"concat=n={len(src_labels)}:v=1:a=0{lab}")
            acc = sum(orig_nf[:n])
            cur = lab
            if n == len(pic):
                break
            d = round(float(pic[n][5]["dissolve"]) * float(fps)) / float(fps)
            xl = f"[x{n}]"
            parts.append(f"{cur}{vlabels[n]}xfade=transition=fade:duration={d:.4f}:"
                         f"offset={acc / float(fps) - d:.4f}{xl}")
            cur, run = xl, []
        parts.append(f"{cur}tpad=stop_mode=clone:stop=2,trim=end_frame={n_frames}[vc]")
    tail = f"atrim=end={end:.4f},afade=t=out:st={max(end - 0.025, 0):.4f}:d=0.025"
    if beds:
        parts.append("[voice]" + "".join(beds) +
                     f"amix=inputs={1 + len(beds)}:duration=first:normalize=0,{tail}[ac]")
    else:
        parts.append(f"[voice]{tail}[ac]")
    return parts, inputs, end


def build(job: Path, encoder_args, reframe=None):
    sheet = json.loads((job / "transcript" / "cutsheet.json").read_text())
    if montage.is_montage(sheet):
        parts, inputs, total = build_montage(job, sheet, encoder_args, reframe)
        # Constant output rate: without it the last frame leaves the graph with no duration and
        # the mp4 edit list hides it (the picture ends a frame before the sound).
        fps = montage.output_fps(job, sheet)
        rate = ["-fps_mode", "cfr", "-r", f"{fps.numerator}/{fps.denominator}"]
        return finish(job, parts, inputs, encoder_args + rate, total, sheet.get("voice"))
    segs = sheet["segments"]
    if not segs:
        sys.exit("cutsheet has no segments")

    clips = []
    for s in segs:
        for key in ("clip", "start", "end", "text"):
            if key not in s:
                sys.exit(f"segment missing '{key}': {s}")
        if s["end"] <= s["start"]:
            sys.exit(f"segment end <= start: {s}")
        if s["clip"] not in clips:
            clips.append(s["clip"])

    inputs = []
    for c in clips:
        path = job / c
        if not path.exists():
            sys.exit(f"missing clip: {path}")
        inputs += ["-i", str(path)]

    sizes = {c: probe_size(job / c) for c in clips} if reframe else {}

    parts, labels = [], []
    for n, s in enumerate(segs):
        i = clips.index(s["clip"])
        start, end = float(s["start"]), float(s["end"])
        dur = end - start
        v = f"[{i}:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS"
        if reframe:
            v += "," + reframe_filter(sizes[s["clip"]], reframe, s.get("x_offset", 0) or 0)
        parts.append(v + f"[v{n}]")
        # pad to the exact length: audio that ends before its picture would shift every later segment's sound
        a = (f"[{i}:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,"
             f"apad=whole_dur={dur:.3f},atrim=end={dur:.3f}")
        fade = float(s.get("fade_out", 0) or 0)
        if fade > 0:
            a += f",afade=t=out:st={max(dur - fade, 0):.3f}:d={fade:.3f}"
        parts.append(a + f"[a{n}]")
        labels.append(f"[v{n}][a{n}]")
    parts.append("".join(labels) + f"concat=n={len(segs)}:v=1:a=1[vc][ac]")
    return finish(job, parts, inputs, encoder_args,
                  sum(float(s["end"]) - float(s["start"]) for s in segs))


def measure_loudness(parts, inputs, pre):
    """First loudnorm pass on the audio branch alone (no video decoded), for a linear second pass.

    Returns loudnorm's measured values, or None when the audio branch isn't separable from the
    video (a plain cut sheet concats picture and sound together)."""
    audio = [p for p in parts if not re.search(r":v\]|\[v\d+\]|\[vc\]", p)]
    if not any(p.endswith("[ac]") for p in audio):
        return None
    graph = ";\n".join(audio + [f"[ac]{pre}loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[m]"])
    path = Path(tempfile.mkstemp(suffix=".txt")[1])
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *inputs, *graph_args(graph, path),
                        "-map", "[m]", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    return json.loads(m.group(0)) if m else None


def finish(job: Path, parts, inputs, encoder_args, total, voice=None):
    """Polish the assembled [ac] once, map [vc], encode to outputs/base.mp4.

    Loudness goes to -14 LUFS with ONE steady gain (two-pass linear loudnorm) when the audio
    branch can be measured on its own. Single-pass loudnorm is dynamic: it lifts quiet stretches
    toward the target, so room noise under a silent moment gets pushed up.
    voice.denoise_db (optional, from the cut sheet): gentle afftdn noise reduction before loudness,
    e.g. 6. Keep it light; the voice must keep its body and the room must not sound gated.
    """
    voice = voice or {}
    pre = ""
    if voice.get("rnnoise"):
        # RNNoise (ffmpeg arnndn, a small speech-denoising network): measured on street and
        # busy-room audio it drops the background ~7-9 dB further than afftdn at 10 dB, with the
        # voice level unchanged. mix < 1 keeps a little of the room so it never sounds gated; the
        # low-cut takes the traffic/AC rumble without touching the voice's body.
        model = root_of(job) / "assets" / "audio-models" / voice.get("rnnoise_model", "sh.rnnn")
        pre = (f"highpass=f={float(voice.get('lowcut_hz', 85))},"
               f"arnndn=m='{model}':mix={float(voice.get('rnnoise_mix', 0.85))},")
    if voice.get("denoise_db"):  # alone, or as a light second pass after RNNoise for what it leaves
        pre += f"afftdn=nr={float(voice['denoise_db'])}:nf=-45:tn=1,"
    ln = "loudnorm=I=-14:TP=-1.5:LRA=11"
    # voice.gain_db pins the overall gain. Use it once the main dialogue (e.g. the main scene) sits at
    # -14 and other sections are balanced with per-segment gain_db: re-measuring the whole mix after
    # each trim swings the gain, because the loudest section dominates the measurement.
    mv = None if voice.get("gain_db") is not None else measure_loudness(parts, inputs, pre)
    if voice.get("gain_db") is not None:
        ln = f"volume={float(voice['gain_db']):.2f}dB"
        print(f"loudness: pinned fixed gain {float(voice['gain_db']):+.2f} dB", file=sys.stderr)
    if mv:
        # A plain fixed gain, not loudnorm's linear mode: with quiet camera audio (-44 LUFS needs
        # ~+30 dB) linear mode can't keep the true peak and silently falls back to dynamic, which
        # lifts the room tone under quiet moments again. The limiter below only catches peaks (clinks).
        gain = -14.0 - float(mv["input_i"])
        ln = f"volume={gain:.2f}dB"
        print(f"loudness: measured {mv['input_i']} LUFS, fixed gain {gain:+.2f} dB to -14", file=sys.stderr)
    if ln.startswith("volume="):
        # Gain FIRST, then denoise: RNNoise is tuned for speech at normal level. Fed raw camera
        # audio (~-45 LUFS) it starts classing a quieter section's voice as noise, so a -4 dB trim
        # came out -22 dB. At working level the trims stay linear.
        parts.append(f"[ac]{ln},{pre}alimiter=limit=0.89:level=disabled[ao]")
    else:
        parts.append(f"[ac]{pre}{ln},alimiter=limit=0.89:level=disabled[ao]")
    out = job / "outputs" / "base.mp4"
    cmd = ["ffmpeg", "-y", "-hide_banner", *inputs,
           *graph_args(";\n".join(parts), job / "outputs" / "base.filtergraph.txt"),
           "-map", "[vc]", "-map", "[ao]", "-map_chapters", "-1",
           *encoder_args, "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
           "-movflags", "+faststart", str(out)]
    return cmd, out, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="print the command, do not run")
    ap.add_argument("--encoder", help="e.g. h264_nvenc; overrides the platform default")
    ap.add_argument("--style", help="style name; applies its rough_cut.reframe for --format")
    ap.add_argument("--format", choices=["long", "short-explainer", "short-raw"])
    args = ap.parse_args()

    reframe = None
    if args.style:
        if not args.format:
            sys.exit("--style needs --format")
        style = json.loads((root_of(args.job) / "styles" / args.style / "style.json").read_text())
        reframe = style.get("rough_cut", {}).get("reframe", {}).get(args.format)

    enc = ["-c:v", args.encoder] if args.encoder else default_encoder()
    cmd, out, total = build(args.job, enc, reframe)
    print(f"{total:.2f}s of output from cutsheet -> {out}")
    if args.dry_run:
        print(" ".join(repr(c) if " " in c or "\n" in c else c for c in cmd))
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
