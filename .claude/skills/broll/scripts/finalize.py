#!/usr/bin/env python3
"""Conform a generated B-roll clip to the base cut and record it in the manifest.

- frame rate: probed from outputs/base.mp4, passed as an exact rational (24000/1001)
- audio: stripped, always
- duration: must be >= beat window + 0.5 s tail margin
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

TAIL = 0.5
TEMPLATES = {"stat-reveal", "data-breakdown", "pie", "podium", "flowchart",
             "phone-notification", "before-after", "kinetic-type", "footage"}


def probe(path: Path, entries: str, stream="v:0") -> str:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", entries,
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job", type=Path)
    ap.add_argument("beat_id")
    ap.add_argument("clip", type=Path)
    ap.add_argument("--template", required=True, choices=sorted(TEMPLATES))
    ap.add_argument("--source", required=True, choices=["higgsfield", "hyperframes"])
    args = ap.parse_args()

    plan = json.loads((args.job / "transcript" / "graphics-plan.json").read_text())
    beat = next((b for b in plan["beats"] if b["id"] == args.beat_id), None)
    if not beat:
        sys.exit(f"beat {args.beat_id} not in graphics-plan.json")
    if beat["kind"] != "broll":
        sys.exit(f"beat {args.beat_id} is kind '{beat['kind']}', not broll")

    need = float(beat["end"]) - float(beat["start"]) + TAIL
    fps = probe(args.job / "outputs" / "base.mp4", "stream=r_frame_rate")
    have = float(probe(args.clip, "format=duration", stream="v:0") or 0)
    if have + 1e-3 < need:
        sys.exit(f"clip is {have:.2f}s, needs >= {need:.2f}s (window + {TAIL}s tail). Regenerate longer.")

    out_dir = args.job / "graphics-build" / "broll"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{args.beat_id}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(args.clip),
         "-t", f"{need:.3f}", "-an", "-vf", f"fps={fps}", "-r", fps,
         "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", str(out)],
        check=True)
    if probe(out, "stream=index", stream="a"):
        sys.exit(f"{out} still has audio. Refusing to write manifest.")

    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"clips": []}
    manifest["clips"] = [c for c in manifest["clips"] if c["id"] != args.beat_id]
    manifest["clips"].append({
        "id": args.beat_id, "file": out.name,
        "start": beat["start"], "end": beat["end"], "duration": round(need, 3),
        "fps": fps, "template": args.template, "source": args.source,
    })
    manifest["clips"].sort(key=lambda c: c["start"])
    manifest_path.write_text(json.dumps(manifest, indent=1))
    print(f"{out} @ {fps} fps, {need:.2f}s, silent. Manifest updated.")


if __name__ == "__main__":
    main()
