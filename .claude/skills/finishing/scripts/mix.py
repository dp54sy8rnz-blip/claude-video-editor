#!/usr/bin/env python3
"""Apply transcript/audio-plan.json: music bed pass, then SFX pass.

Pure audio passes: the video stream is copied, never re-encoded.
Each pass picks its own input (the newest prior-stage file) and writes the exact
filtergraph it used to transcript/audio-filtergraph.txt so it can be re-applied verbatim.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MUSIC_INPUTS = ["captioned.mp4", "graphics.mp4", "base.mp4"]
# Every pass that sums tracks ends on a limiter: a bed or a hit on top of a speech track that
# already peaks at -1.5 dBTP pushes it over. -1.9 dBFS sample peak keeps true peak under -1.
# level=disabled: alimiter otherwise normalises back up to 0 dB.
LIMIT = "alimiter=limit=0.8:level=disabled"
SFX_INPUTS = ["music.mp4", *MUSIC_INPUTS]


def root_of(job: Path) -> Path:
    for d in [job.resolve(), *job.resolve().parents]:
        if (d / "brand.md").exists():
            return d
    sys.exit("brand.md not found above the job folder")


def duration(path: Path) -> float:
    """The picture's length (frames / rate): the container adds AAC padding past the last
    frame, and audio running past the picture leaves a stray tail at a Short's loop point."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                          "-show_entries", "stream=nb_read_packets,r_frame_rate", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True).stdout.strip()
    rate, n = out.split(",")[:2]
    num, den = rate.split("/")
    return int(n) * int(den) / int(num)


def pick(outputs: Path, order):
    for n in order:
        if (outputs / n).exists():
            return outputs / n
    sys.exit(f"none of {order} exist in {outputs}")


def resolve_file(job: Path, root: Path, rel: str) -> Path:
    for base in (job, root):
        if (base / rel).exists():
            return base / rel
    sys.exit(f"audio file not found: {rel}")


def gain(db):
    return 10 ** (float(db) / 20)


def pieces_chain(m, dur, inp=1, tag=""):
    """A music edit: stretches of the track laid at set video times.

    Each piece plays track_t onward from video_t until the next piece starts (the last one
    until the end). Joins crossfade over xfade_ms, centred on the join. A piece may carry
    db_offset, relative to the bed level. Used to stitch a
    track's own ending onto the body so the video ends on the music's final hit.
    """
    ps = sorted(m["pieces"], key=lambda p: float(p["video_t"]))
    x = float(m.get("xfade_ms", 20)) / 1000
    parts, labels = [], []
    for i, p in enumerate(ps):
        vt, tt = float(p["video_t"]), float(p["track_t"])
        end_v = float(ps[i + 1]["video_t"]) if i + 1 < len(ps) else dur
        a = max(vt - (x / 2 if i else 0), 0)          # overlap the neighbour by half the fade
        b = min(end_v + (x / 2 if i + 1 < len(ps) else 0), dur)
        if m.get("_track_len"):
            # The music input is looped (-stream_loop); a piece must never run past the end
            # of the file, or the track restarts audibly. A track cut to end early just ends.
            b = min(b, a + float(m["_track_len"]) - (tt - (vt - a)))
        chain = (f"[{inp}:a]atrim=start={tt - (vt - a):.4f}:duration={b - a:.4f},asetpts=PTS-STARTPTS")
        if i:
            chain += f",afade=t=in:d={x:.4f}"
        if i + 1 < len(ps):
            chain += f",afade=t=out:st={b - a - x:.4f}:d={x:.4f}"
        if float(p.get("db_offset", 0)):
            chain += f",volume={float(p['db_offset'])}dB"  # e.g. keep a louder ending under the voice
        chain += f",adelay={round(a * 1000)}:all=1[{tag}p{i}]"
        parts.append(chain)
        labels.append(f"[{tag}p{i}]")
    # asetpts: once one input ends, amix emits frames with no timestamps, and anything
    # downstream that reads t (the envelope) silently sees NaN. Rebuild them from the samples.
    parts.append("".join(labels) + f"amix=inputs={len(ps)}:duration=longest:normalize=0,"
                 f"asetpts=N/SR/TB,atrim=0:{dur:.3f}[{tag}mus]")
    return ";".join(parts) + f";[{tag}mus]"


def envelope(points):
    """Piecewise-linear gain in dB over video time, e.g. [[1.0, 4], [8.5, 4], [10.7, 0]]:
    lift a quiet intro so it is audible, easing back before the groove."""
    pts = sorted((float(t), float(d)) for t, d in points)
    expr = f"{pts[-1][1]}"
    for (t0, d0), (t1, d1) in reversed(list(zip(pts, pts[1:]))):
        seg = f"({d0}+({d1}-({d0}))*(t-{t0})/{t1 - t0:.4f})"
        expr = f"if(lt(t,{t1}),{seg},{expr})"
    expr = f"if(lt(t,{pts[0][0]}),{pts[0][1]},{expr})"
    return f"volume='pow(10,({expr})/20)':eval=frame"


def music_graph(m, dur):
    if isinstance(m, list):
        # Several beds (a long video: each section's track, the bridges' tracks), summed. Each bed is a
        # pieces edit on its own input with its own envelope; set fade_out 0 on beds that end early.
        chains = [bed_chain(b, dur, inp=k + 1, tag=f"b{k}") for k, b in enumerate(m)]
        labels = "".join(f"[b{k}bed]" for k in range(len(m)))
        return ";".join(chains) + f";[0:a]{labels}amix=inputs={len(m) + 1}:duration=first:normalize=0,{LIMIT}[aout]"
    chain = bed_chain(m, dur)
    if m.get("duck"):
        return chain + ";[bed][0:a]sidechaincompress=threshold=0.05:ratio=6[bd];" \
                       f"[0:a][bd]amix=inputs=2:duration=first:normalize=0,{LIMIT}[aout]"
    return chain + f";[0:a][bed]amix=inputs=2:duration=first:normalize=0,{LIMIT}[aout]"


def bed_chain(m, dur, inp=1, tag=""):
    db = m.get("db", -18)
    rel = m.get("release")
    if m.get("pieces"):
        chain = pieces_chain(m, dur, inp, tag) + f"volume={db}dB"
        if m.get("envelope"):
            chain += "," + envelope(m["envelope"])
    elif not rel:
        chain = f"[{inp}:a]atrim=0:{dur:.3f},volume={db}dB"
    else:
        # Line the track's release moment (track_t) up with the video's (video_t): trim the
        # track's head, or delay the track's start. Before the release the bed sits at pre_db,
        # then eases to db over ramp_s. The "build then release" is in the music itself;
        # the level change only settles the bed under the talk once the argument starts.
        vt, tt = float(rel["video_t"]), float(rel["track_t"])
        pre, ramp = gain(rel.get("pre_db", db)), float(rel.get("ramp_s", 1.0))
        post = gain(db)
        chain = f"[{inp}:a]"
        if tt >= vt:
            chain += f"atrim=start={tt - vt:.3f},asetpts=PTS-STARTPTS,"
        else:
            chain += f"adelay={int(round((vt - tt) * 1000))}:all=1,"
        expr = (f"if(lt(t,{vt:.3f}),{pre:.5f},if(lt(t,{vt + ramp:.3f}),"
                f"{pre:.5f}+({post:.5f}-{pre:.5f})*(t-{vt:.3f})/{ramp:.3f},{post:.5f}))")
        chain += f"atrim=0:{dur:.3f},volume='{expr}':eval=frame"
    if m.get("fade_in"):
        chain += ",afade=t=in:d=1.0"
    fo = float(m.get("fade_out", 1.5))
    if fo > 0:  # 0 = cut, not faded (a looping Short must not sound like it ends)
        chain += f",afade=t=out:st={max(dur - fo, 0):.3f}:d={fo:.3f}"
    return chain + f"[{tag}bed]"


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


def sfx_graph(sfx):
    parts, labels = [], ["[0:a]"]
    for i, s in enumerate(sfx, start=1):
        ms = int(round(float(s["t"]) * 1000))
        # Optional "in"/"out" (seconds in the file): lay only that stretch, starting at t.
        trim = ""
        if "in" in s or "out" in s:
            trim = f"atrim=start={float(s.get('in', 0))}" + (f":end={float(s['out'])}" if "out" in s else "") + ",asetpts=PTS-STARTPTS,"
        # Optional "fade_out" (s): dissolve the tail of the laid stretch (needs "out") instead of a hard stop.
        if s.get("fade_out") and "out" in s:
            fo, d = float(s["fade_out"]), float(s["out"]) - float(s.get("in", 0))
            trim += f"afade=t=out:st={max(d - fo, 0):.3f}:d={fo:.3f},"
        parts.append(f"[{i}:a]{trim}aformat=sample_rates=48000:channel_layouts=stereo,volume={s.get('db', -10)}dB,adelay={ms}:all=1[s{i}]")
        labels.append(f"[s{i}]")
    parts.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0,{LIMIT}[aout]")
    return ";".join(parts)


def run(src, extra_inputs, graph, out, log, label, dry, loop=()):
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src)]
    for f in extra_inputs:
        cmd += [*loop, "-i", str(f)]
    cut = graph.rfind("[aout]")  # end the audio with the picture, to the frame
    graph = graph[:cut] + f",atrim=0:{duration(src):.4f}" + graph[cut:]
    # -map_chapters -1: a licensed track's chapter tags would otherwise come along as a stray
    # text stream as long as the song.
    cmd += [*graph_args(graph, out.with_suffix(".filtergraph.txt")), "-map", "0:v", "-map", "[aout]",
            "-map_chapters", "-1", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", str(out)]
    log.append(f"# {label}: {src.name} -> {out.name}\n{graph}\n")
    print(f"{label}: {src.name} -> {out.name}")
    if not dry:
        subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job", type=Path)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--music-only", action="store_true")
    g.add_argument("--sfx-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--plan", type=Path, help="audio plan (default transcript/audio-plan.json)")
    ap.add_argument("--src", type=Path, help="input video (default: newest prior-stage file)")
    ap.add_argument("--prefix", default="", help="output name prefix, e.g. episode- -> outputs/episode-music.mp4")
    args = ap.parse_args()

    root = root_of(args.job)
    plan = json.loads((args.plan or args.job / "transcript" / "audio-plan.json").read_text())
    outputs = args.job / "outputs"
    log = []

    if not args.sfx_only:
        m = plan.get("music")
        beds = m if isinstance(m, list) else [m]
        if not m or not all(b and b.get("file") for b in beds):
            sys.exit("No music file in audio-plan.json. Ask the user for a licensed track; never download one.")
        src = args.src or pick(outputs, MUSIC_INPUTS)
        tracks = []
        for b in beds:
            tracks.append(resolve_file(args.job, root, b["file"]))
            b["_track_len"] = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                 str(tracks[-1])], capture_output=True, text=True, check=True).stdout)
        run(src, tracks, music_graph(m, duration(src)),
            outputs / f"{args.prefix}music.mp4", log, "music", args.dry_run, loop=("-stream_loop", "-1"))

    if not args.music_only:
        sfx = sorted(plan.get("sfx") or [], key=lambda s: float(s["t"]))
        if not sfx:
            print("No SFX in plan. Skipping (never synthesise a tone).")
        else:
            src = (outputs / f"{args.prefix}music.mp4" if (not args.sfx_only and not args.dry_run)
                   else args.src or pick(outputs, SFX_INPUTS))
            files = [resolve_file(args.job, root, s["file"]) for s in sfx]
            run(src, files, sfx_graph(sfx), outputs / f"{args.prefix}sfx.mp4", log, "sfx", args.dry_run)

    if log and not args.dry_run:
        (args.job / "transcript" / "audio-filtergraph.txt").write_text("\n".join(log))
    elif log:
        print("\n".join(log))


if __name__ == "__main__":
    main()
