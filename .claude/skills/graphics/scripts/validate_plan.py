#!/usr/bin/env python3
"""Validate transcript/graphics-plan.json before the build step sees it. Exit 1 on any error."""
import json
import sys
from pathlib import Path

KINDS = {"stat", "card", "screenshot", "takeover", "zoom", "diagram", "broll"}
REQUIRED = ("id", "start", "end", "kind", "direction")
EPS = 0.001  # "abut exactly" tolerance, one millisecond


def validate(plan: dict, duration: float | None = None) -> list[str]:
    errors = []
    beats = plan.get("beats")
    if not isinstance(beats, list):
        return ["plan has no 'beats' list"]
    ids = set()
    for i, b in enumerate(beats):
        tag = b.get("id", f"#{i}")
        missing = [k for k in REQUIRED if b.get(k) in (None, "")]
        if missing:
            errors.append(f"{tag}: missing {', '.join(missing)}")
            continue
        if b["id"] in ids:
            errors.append(f"{tag}: duplicate id")
        ids.add(b["id"])
        if b["kind"] not in KINDS:
            errors.append(f"{tag}: kind '{b['kind']}' not in {sorted(KINDS)}")
        if not float(b["start"]) < float(b["end"]):
            errors.append(f"{tag}: start {b['start']} is not before end {b['end']}")
        if duration is not None and float(b["end"]) > duration + EPS:
            errors.append(f"{tag}: ends at {b['end']} past the cut's duration {duration}")

    good = [b for b in beats if all(b.get(k) not in (None, "") for k in REQUIRED)]
    for prev, cur in zip(good, good[1:]):
        p, c = prev["id"], cur["id"]
        if float(cur["start"]) < float(prev["start"]):
            errors.append(f"{c}: not sorted ascending (starts before {p})")
            continue
        gap = float(cur["start"]) - float(prev["end"])
        if gap < -EPS:
            errors.append(f"{p} -> {c}: overlap of {-gap:.3f}s")
        elif EPS < gap <= 1.0:
            errors.append(f"{p} -> {c}: gap of {gap:.3f}s. Abut exactly or leave more than 1s "
                          "(a short gap flashes raw footage)")
    return errors


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: validate_plan.py projects/<job>")
    job = Path(sys.argv[1])
    plan = json.loads((job / "transcript" / "graphics-plan.json").read_text())
    cut = job / "outputs" / "transcript.cut.json"
    duration = json.loads(cut.read_text()).get("duration") if cut.exists() else None
    errors = validate(plan, duration)
    for e in errors:
        print("ERROR", e)
    n = len(plan.get("beats") or [])
    print(f"{n} beats, {len(errors)} errors")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
