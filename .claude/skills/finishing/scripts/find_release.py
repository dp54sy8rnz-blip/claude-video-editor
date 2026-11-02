#!/usr/bin/env python3
"""Find candidate "release" moments in a music track: where the music opens up after a build.

Measures short-term loudness (EBU R128, 3 s window) every 0.1 s and ranks the moments with
the biggest sustained rise: the mean over the next 4 s minus the mean over the previous 4 s.
Prints the top candidates as track times. Always listen/verify: a release can also be a
change in texture or harmony that loudness does not show.

Usage: find_release.py <track> [--top 5] [--min-gap 6]
"""
import argparse
import re
import subprocess


def loudness_curve(path):
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-v", "verbose", "-i", path, "-af", "ebur128",
         "-f", "null", "-"], capture_output=True, text=True).stderr
    pts = []
    for m in re.finditer(r"t:\s*([\d.]+)\s+TARGET.*?S:\s*(-?[\d.]+|-inf)", err):
        s = m.group(2)
        pts.append((float(m.group(1)), -70.0 if s == "-inf" else max(float(s), -70.0)))
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("track")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--min-gap", type=float, default=6.0, help="seconds between candidates")
    args = ap.parse_args()

    pts = loudness_curve(args.track)
    if len(pts) < 100:
        raise SystemExit("track too short to analyse")
    step = pts[1][0] - pts[0][0]
    win = max(int(round(4.0 / step)), 1)
    scored = []
    # Skip the first 3 s: the short-term window is still filling from silence there.
    first = next((i for i, (t, _) in enumerate(pts) if t >= 3.0), 0) + win
    for i in range(first, len(pts) - win):
        before = sum(v for _, v in pts[i - win:i]) / win
        after = sum(v for _, v in pts[i:i + win]) / win
        scored.append((after - before, pts[i][0], before, after))
    scored.sort(reverse=True)

    picked = []
    for rise, t, before, after in scored:
        if rise <= 0 or len(picked) >= args.top:
            break
        if all(abs(t - p[1]) >= args.min_gap for p in picked):
            picked.append((rise, t, before, after))
    for rise, t, before, after in picked:
        print(f"track_t ~{t:6.1f}s  rise {rise:+5.1f} LU  ({before:.1f} -> {after:.1f} LUFS)")


if __name__ == "__main__":
    main()
