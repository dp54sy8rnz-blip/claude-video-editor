"""Style rule (no shaky footage in the cut): motion measured in every shot, not sampled.
For every B-roll shot in every cut sheet, read every frame of the span the cut uses (plus 0.5 s either
side for context), measure the global camera translation frame to frame (phase correlation on a
480 px greyscale copy) and flag jerks/whips: a frame-to-frame jump far above the shot's own median, or
an absolute jump over JUMP px. Reports where in the shot (first/last 0.5 s matter most)."""
import json, sys, cv2, numpy as np
from pathlib import Path
JOB = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir() else Path.cwd()
# usage: python3 motion_check.py <job dir> [piece ...]   (run from anywhere)
JUMP = 9.0          # px per frame at 480 px wide: a whip/jerk, not a pan
REL = 4.0           # x the shot's median motion
args = [a for a in sys.argv[1:] if not Path(a).is_dir()]
pieces = args or sorted(p.stem.replace("cutsheet-", "") for p in (JOB / "transcript").glob("cutsheet-*.json"))
def fps_of(p):
    c = cv2.VideoCapture(str(p)); f = c.get(cv2.CAP_PROP_FPS); c.release(); return f or 25.0
report = []
for piece in pieces:
    sheet = json.load(open(JOB / f"transcript/cutsheet-{piece}.json"))
    t = 0.0
    for sh in sheet["shots"]:
        dur = sh["dur"]; out0 = t; t += dur
        if sh.get("sync") or not sh.get("clip"): continue
        clip = JOB / sh["clip"]; r = fps_of(clip)
        span = dur if (sh.get("realtime") or r <= 25.5) else dur * 25.0 / r
        s0 = sh["start"]
        cap = cv2.VideoCapture(str(clip)); cap.set(cv2.CAP_PROP_POS_MSEC, max(0, s0) * 1000)
        prev = None; mags = []; times = []
        n = int(round(span * r))
        for i in range(n + 1):
            ok, fr = cap.read()
            if not ok: break
            g = cv2.cvtColor(cv2.resize(fr, (480, int(480 * fr.shape[0] / fr.shape[1]))), cv2.COLOR_BGR2GRAY).astype(np.float32)
            if prev is not None:
                (dx, dy), _ = cv2.phaseCorrelate(prev, g)
                mags.append(float(np.hypot(dx, dy)) * r / 25.0)   # per output (25 fps) frame
                times.append(i / r)
            prev = g
        cap.release()
        if not mags: continue
        m = np.array(mags); med = float(np.median(m)) + 0.3
        bad = [(times[k], m[k]) for k in range(len(m)) if m[k] > JUMP or m[k] > REL * med and m[k] > 4.0]
        if bad:
            edge = any(tt < 0.5 or tt > span - 0.5 for tt, _ in bad)
            worst = max(bad, key=lambda x: x[1])
            report.append({"piece": piece, "out": round(out0, 2), "clip": sh["clip"].split("/")[-1], "start": s0,
                           "span": round(span, 2), "median": round(med, 1), "worst_at": round(worst[0], 2),
                           "worst_px": round(worst[1], 1), "n_bad": len(bad), "at_edge": edge,
                           "bad_times": [round(b[0], 2) for b in bad][:12], "note": sh["note"][:70]})
(JOB / "outputs/review/motion").mkdir(parents=True, exist_ok=True)
out = JOB / "outputs/review/motion/motion-report.json"
json.dump(report, open(out, "w"), indent=1)
for r_ in report:
    print(f"{r_['piece']:6} @{r_['out']:7.2f} {r_['clip']:28} src {r_['start']:7} worst {r_['worst_px']:5.1f}px at +{r_['worst_at']:5.2f}/{r_['span']} {'EDGE' if r_['at_edge'] else ''} n={r_['n_bad']}  {r_['note']}")
print(len(report), "shots flagged")
