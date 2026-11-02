#!/usr/bin/env python3
"""Fit an exact beat grid to a music track and print it bar by bar, to plan a music edit.

HyperFrames' `beats` gives irregular onsets; a cut-on-the-beat edit needs a straight grid.
This fits the period and phase (near --bpm, the track's catalogue tempo) to the track's onset
strength, then prints every bar: its downbeat time, and per beat the level (dB) and the low
band's onset (kick / bass hits). Read it for the song's structure: where the groove enters,
the breaks, and the ending's stop-time hits and final chord.

The downbeat is guessed as the beat phase with the most low-band onset; check it by ear-proxy
(a groove entry or the final chord should land on beat 1) and pass --downbeat to override.
Usage: beat_grid.py <track> --bpm 138 [--beats 4] [--downbeat T] [--json out.json] [--from S --to S]
"""
import argparse
import array
import json
import math
import subprocess

SR, HOP = 8000, 80  # 10 ms frames


def energy(path, af):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-af", af,
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = array.array("h")
    x.frombytes(raw)
    return [math.sqrt(sum(v * v for v in x[i:i + HOP]) / HOP) / 32768 + 1e-9
            for i in range(0, len(x) - HOP, HOP)]


def onset(e):
    db = [20 * math.log10(v) for v in e]
    return [0.0] + [max(db[i] - db[i - 1], 0.0) for i in range(1, len(db))]


def score(on, period, phase):
    s, t, n = 0.0, phase, 0
    while t < len(on) * HOP / SR:
        i = int(round(t * SR / HOP))
        s += max(on[max(i - 1, 0):i + 2])
        t += period
        n += 1
    return s / max(n, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("track")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--beats", type=int, default=4, help="beats per bar")
    ap.add_argument("--downbeat", type=float, help="a known downbeat time (s)")
    ap.add_argument("--json")
    ap.add_argument("--from", dest="t0", type=float, default=0)
    ap.add_argument("--to", dest="t1", type=float, default=1e9)
    a = ap.parse_args()

    full = energy(a.track, "highpass=f=40")
    low = energy(a.track, "lowpass=f=150")
    on_full, on_low = onset(full), onset(low)
    on = [f + 2 * l for f, l in zip(on_full, on_low)]

    best = (0, None, None)
    for k in range(-60, 61):  # +-1.5 % around the catalogue tempo
        period = 60 / (a.bpm * (1 + k * 0.00025))
        for p in range(int(period * 100)):
            s = score(on, period, p / 100)
            if s > best[0]:
                best = (s, period, p / 100)
    _, period, phase = best
    # Downbeat: the beat phase (of --beats) with the most low-band onset, unless given.
    if a.downbeat is not None:
        first = a.downbeat - math.floor((a.downbeat - phase) / period / a.beats) * a.beats * period
        first = first % (period * a.beats)
    else:
        sums = []
        for b in range(a.beats):
            t, s = phase + b * period, 0.0
            while t < len(on_low) * HOP / SR:
                i = int(round(t * SR / HOP))
                s += max(on_low[max(i - 1, 0):i + 2])
                t += period * a.beats
            sums.append(s)
        first = phase + sums.index(max(sums)) * period
    print(f"tempo {60 / period:.3f} bpm (beat {period:.4f} s), first downbeat {first:.3f} s")

    grid, bar, t = [], 1, first
    end = len(full) * HOP / SR
    while t < end:
        cells = []
        for b in range(a.beats):
            tb = t + b * period
            i = int(round(tb * SR / HOP))
            if i >= len(full):
                break
            w = full[i:i + int(period * SR / HOP)] or [1e-9]
            lvl = 20 * math.log10(max(w))
            kick = max(on_low[max(i - 1, 0):i + 2])
            cells.append((tb, lvl, kick))
            grid.append({"t": round(tb, 4), "bar": bar, "beat": b + 1, "db": round(lvl, 1),
                         "kick": round(kick, 1)})
        if a.t0 <= t <= a.t1:
            print(f"bar {bar:3d} {t:7.3f}  " + "  ".join(
                f"{c[1]:5.1f}dB{'K' if c[2] > 6 else ('k' if c[2] > 3 else ' ')}" for c in cells))
        t += period * a.beats
        bar += 1
    if a.json:
        json.dump({"bpm": 60 / period, "beat_s": period, "first_downbeat": first, "beats": grid},
                  open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
