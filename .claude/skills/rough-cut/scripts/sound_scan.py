#!/usr/bin/env python3
"""Scan a stretch of audio in 20 ms steps: overall level, low band (80-400 Hz, voiced hum) and
high band (>2.5 kHz, slurp/crunch/sizzle noise).

Answers the questions a fragment or montage cut needs: where a word really starts (WhisperX can
stretch a word over the silence before it), whether a moment is live sound (room tone
under it) or voice-over / silent B-roll (digital silence, -180 dB), and whether a closing sound
is a sip or crunch (high band) or a voiced "mm" (low band only).
Usage: sound_scan.py <media> <start_s> <dur_s> [--every N]   (print every Nth row)
"""
import array
import math
import subprocess
import sys


def band(media, a0, dur, af):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a0), "-t", str(dur), "-i", media, "-ac", "1",
                          "-ar", "16000", *(["-af", af] if af else []), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    x = array.array("h")
    x.frombytes(raw)
    hop = 320
    return [20 * math.log10(math.sqrt(sum(v * v for v in x[i:i + hop]) / hop) / 32768 + 1e-9)
            for i in range(0, len(x) - hop, hop)]


def main():
    if len(sys.argv) < 4:
        sys.exit("usage: sound_scan.py <media> <start_s> <dur_s> [--every N]")
    media, a0, dur = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 1
    full = band(media, a0, dur, None)
    low = band(media, a0, dur, "highpass=f=80,lowpass=f=400")
    high = band(media, a0, dur, "highpass=f=2500")
    for i, (f, l, h) in enumerate(zip(full, low, high)):
        if i % every:
            continue
        tag = ("silent" if f < -100 else
               "HUM" if l > -45 and l - h > 8 else
               "noise" if h > -50 and h >= l - 3 else "")
        print(f"{a0 + i * 0.02:8.2f}  all {f:6.1f}  low {l:6.1f}  high {h:6.1f}  {tag}")


if __name__ == "__main__":
    main()
