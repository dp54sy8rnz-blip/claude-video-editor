#!/usr/bin/env python3
"""Move a montage cut's picture cuts onto the music's beat grid (the style's "cut on the beat").

The grid on the video timeline is first_beat + n * beat (from the music plan: the video time
where the track's beat lands, and the beat length). Each cut goes to the nearest eighth, or the
nearest quarter for the shots listed in --quarter (section changes, key cuts), if that is
within --max seconds; otherwise it stays and is flagged. Cuts before the music starts stay put.
Only shot durations change: a B-roll shot keeps its source in-point, a sync shot keeps
following its line. It warns when a sync shot would run outside its line.
Usage: beat_snap.py projects/<job> --first-beat 1.80 --beat 0.43478 [--quarter 2,5] [--max 0.3]
       [--fixed 7] [--at 21=25.28] [--write]    (shot indices as montage.py prints them, from 0)
"""
import argparse
import json
from pathlib import Path

import montage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job", type=Path)
    ap.add_argument("--first-beat", type=float, required=True)
    ap.add_argument("--beat", type=float, required=True)
    ap.add_argument("--quarter", default="", help="shot indices whose END cut goes on a quarter")
    ap.add_argument("--fixed", default="", help="shot indices whose END cut must not move")
    ap.add_argument("--max", type=float, default=0.3)
    ap.add_argument("--at", action="append", default=[], help="n=T: put shot n's END cut at T (e.g. on an ending hit)")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    sheet = montage.load_sheet(a.job)
    fps = montage.output_fps(a.job, sheet)
    pic, total = montage.picture_timeline(sheet, fps)
    quarter = {int(x) for x in a.quarter.split(",") if x}
    fixed = {int(x) for x in a.fixed.split(",") if x}
    at = {int(k): float(v) for k, v in (x.split("=") for x in a.at)}
    atl = montage.audio_timeline(sheet["segments"])

    cuts = []
    for n, (o0, o1, clip, src, nf, sh) in enumerate(pic[:-1]):
        res = a.beat if n in quarter else a.beat / 2
        new, flag = o1, ""
        if n in at:
            new, flag = float(round(at[n] * fps) / fps), "placed by hand"
        elif n in fixed:
            flag = "fixed"
        elif o1 < a.first_beat - 0.1:
            flag = "before the music"
        else:
            target = a.first_beat + round((o1 - a.first_beat) / res) * res
            target = round(target * fps) / fps
            if abs(target - o1) <= a.max + 1e-6:
                new = float(target)
            else:
                flag = f"OFF GRID (nearest {target:.2f} is {target - o1:+.2f}s away)"
        cuts.append((new, flag))

    prev, durs = 0.0, []
    print(f"{'#':>2} {'cut':>6} -> {'new':>6}  {'shift':>6}  {'grid':>7}  shot")
    for n, (o0, o1, clip, src, nf, sh) in enumerate(pic):
        end = cuts[n][0] if n < len(cuts) else float(round(total * fps) / fps)
        durs.append(round(end - prev, 4))
        if n < len(cuts):
            kind = "quarter" if n in quarter else "eighth"
            print(f"{n:2d} {o1:6.2f} -> {end:6.2f}  {end - o1:+6.2f}  {kind:>7}  "
                  f"{sh.get('note', '')[:50]} {cuts[n][1]}")
        if sh.get("sync"):
            a0, a1, s = max(atl, key=lambda x: min(x[1], end) - max(x[0], prev))
            if prev < a0 - 0.5 / float(fps) or end > a1 + 0.5 / float(fps):
                print(f"   WARNING: sync shot {n} ({prev:.2f}-{end:.2f}) runs outside its line "
                      f"({a0:.2f}-{a1:.2f})")
        prev = end
    if a.write:
        for sh, d in zip(sheet["shots"], durs):
            sh["dur"] = d
        sheet["shots"][-1].pop("dur", None)  # the last shot is fitted to the audio
        (a.job / "transcript" / "cutsheet.json").write_text(json.dumps(sheet, indent=1))
        print("written")


if __name__ == "__main__":
    main()
