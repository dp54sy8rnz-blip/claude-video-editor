#!/usr/bin/env python3
"""Profile candidate music tracks without listening: loudness range, how busy and how swelling
they are, and how they end.

For each file prints integrated loudness and LRA (a large LRA means big dynamic swells, which
reads as theatrical under a voice), the spread of 2 s short-term levels, and the ending: the
level of the last 8 s in 0.5 s steps, so a track that finishes on a clean final hit (a sharp
drop to silence) can be told from one that fades or stops mid-phrase.
Usage: track_profile.py <file> [<file> ...]
"""
import re
import subprocess
import sys


def main():
    for f in sys.argv[1:]:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-af", "ebur128", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        summary = r[r.rfind("Summary:"):]  # the per-frame lines come first
        i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
        lra = re.search(r"LRA:\s+([\d.]+) LU", summary)
        st = [float(m) for m in re.findall(r" S:\s*(-?[\d.]+)", r) if float(m) > -70]
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "csv=p=0", f], capture_output=True, text=True).stdout)
        tail = []
        t = max(dur - 8, 0)
        while t < dur - 0.25:
            out = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{t:.2f}", "-t", "0.5", "-i", f, "-af",
                                  "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
            m = re.search(r"max_volume: (-?[\d.]+) dB", out)
            tail.append(f"{float(m.group(1)):.0f}" if m else "-inf")
            t += 0.5
        spread = (max(st) - min(st)) if st else 0
        print(f"{f.split('/')[-1][:40]:40s} {dur:6.1f}s  I {i.group(1) if i else '?'}  "
              f"LRA {lra.group(1) if lra else '?'}  short-term spread {spread:.0f} dB")
        print(f"   last 8 s (0.5 s max dB): {' '.join(tail)}")


if __name__ == "__main__":
    main()
