#!/usr/bin/env python3
"""Count duplicate consecutive video frames in a render.

Catches the overlay eof_action=repeat judder: output is constant frame rate on paper,
but ~1 in 4 frames is a copy of the one before. Clean < 3%, bug ~25%.
Exit 1 when the duplicate ratio exceeds --max (default 8%).

Duplicates are only byte-identical in a lossless render. After a lossy encode, x264
re-codes each copy with small residuals, so this uses mpdecimate with tight thresholds
("near-identical") as the verdict and reports the exact-hash count alongside.

A deliberately held frame (e.g. an outro push-in that holds) adds legitimate
duplicates; pass --ignore-after <seconds> to exclude that tail.
"""
import argparse
import re
import subprocess
import sys


def ffmpeg(args, trim):
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", args.video]
    if trim:
        cmd += ["-t", str(trim)]
    return cmd


def exact_dupes(args):
    out = subprocess.run(ffmpeg(args, args.ignore_after) +
                         ["-map", "0:v:0", "-f", "framemd5", "-"],
                         capture_output=True, text=True, check=True).stdout
    hashes = [ln.rsplit(",", 1)[-1].strip() for ln in out.splitlines() if ln and not ln.startswith("#")]
    return len(hashes), sum(a == b for a, b in zip(hashes, hashes[1:]))


def near_kept(args):
    vf = "mpdecimate=hi=256:lo=128:frac=0.33:max=0,showinfo"
    err = subprocess.run(ffmpeg(args, args.ignore_after) + ["-map", "0:v:0", "-vf", vf, "-f", "null", "-"],
                         capture_output=True, text=True, check=True).stderr
    return len(re.findall(r"Parsed_showinfo.*\bn:\s*\d+", err))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--max", type=float, default=8.0, help="max duplicate %% (default 8)")
    ap.add_argument("--ignore-after", type=float, help="ignore frames after this time (s)")
    args = ap.parse_args()

    total, exact = exact_dupes(args)
    if total < 2:
        sys.exit("not enough frames to check")
    near = total - near_kept(args)
    pct = 100.0 * near / (total - 1)
    verdict = "FAIL" if pct > args.max else "ok"
    print(f"{verdict}: {near}/{total - 1} duplicate frames ({pct:.1f}%, max {args.max}%); "
          f"byte-identical: {exact}")
    sys.exit(1 if pct > args.max else 0)


if __name__ == "__main__":
    main()
