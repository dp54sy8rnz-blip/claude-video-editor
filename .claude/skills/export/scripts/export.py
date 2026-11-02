#!/usr/bin/env python3
"""Promote the newest render to one final file, retire drafts, optionally reclaim scratch.

Dry run by default: prints the plan and changes nothing until --apply.
Guard (not overridable): never delete anything newer than the deliverable.
"""
import argparse
import shutil
import sys
from pathlib import Path

KEEP_IN_OUTPUTS = {"base.mp4", "transcript.cut.json"}
NEVER_TOUCH = {"raw", "broll", "audio", "assets", "outputs", "transcript"}
SCRATCH = ["graphics-build/renders", "graphics-build/.cache", "graphics-build/node_modules"]


def size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def guard(deliverable: Path, victims):
    limit = deliverable.stat().st_mtime
    newer = [v for v in victims if v.stat().st_mtime > limit]
    if newer:
        print(f"ABORT: these are newer than the deliverable {deliverable.name}:")
        for v in newer:
            print(f"  {v}")
        print("Something was rendered after the file being promoted. Nothing was changed.")
        sys.exit(2)


def promote(job: Path, apply: bool, copy_to: Path):
    outputs = job / "outputs"
    final = outputs / f"{job.resolve().name}.mp4"
    # Skip macOS AppleDouble files ("._music.mp4"): on exFAT/FAT drives every file gets one,
    # it is written at the same moment as the real file, and it would win "newest" and be
    # promoted while the real render was deleted as a draft.
    renders = [p for p in outputs.glob("*.mp4") if p != final and not p.name.startswith("._")]
    if not renders:
        if final.exists():
            print(f"Already exported: {final}")
            return
        sys.exit(f"No renders in {outputs}")
    newest = max(renders, key=lambda p: p.stat().st_mtime)
    if final.exists() and final.stat().st_mtime > newest.stat().st_mtime:
        sys.exit(f"{final.name} is newer than every render; nothing to promote.")

    retire = [p for p in renders if p != newest and p.name not in KEEP_IN_OUTPUTS]
    if final.exists():
        retire.append(final)  # superseded earlier final
    keep = sorted(p for p in outputs.iterdir() if p.name in KEEP_IN_OUTPUTS and p != newest)

    guard(newest, retire)

    print(f"PROMOTE  {newest.name} -> {final.name}  ({human(size(newest))})")
    for p in retire:
        print(f"DELETE   {p.relative_to(job)}  ({human(size(p))})")
    for p in keep:
        print(f"KEEP     {p.relative_to(job)}")
    print("KEEP     transcript/, graphics-build/ source, raw/, broll/, audio/, assets/")
    print(f"COPY     {final.name} -> {copy_to}/")

    if not apply:
        print("\nDry run. Nothing changed. Re-run with --apply after reading the plan.")
        return
    if newest.name in KEEP_IN_OUTPUTS:
        shutil.copy2(newest, final)
    else:
        newest.replace(final)
    for p in retire:
        if p != final:
            p.unlink()
    copy_to.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final, copy_to / final.name)
    print(f"\nDone: {final} (copy in {copy_to})")


def clean(job: Path, apply: bool):
    final = job / "outputs" / f"{job.resolve().name}.mp4"
    if not final.exists():
        sys.exit("No exported final yet. Run promote first.")
    victims = []
    for rel in SCRATCH:
        p = job / rel
        if p.exists():
            victims.append(p)
    for nm in job.rglob("node_modules"):
        top = nm.relative_to(job).parts[0]
        if top not in NEVER_TOUCH and nm not in victims and not any(v in nm.parents for v in victims):
            victims.append(nm)
    for v in victims:
        if v.relative_to(job).parts[0] in NEVER_TOUCH:
            sys.exit(f"refusing: {v} is protected")
    files = [f for v in victims for f in ([v] if v.is_file() else v.rglob("*")) if f.is_file()]
    guard(final, files)

    total = 0
    for v in victims:
        total += size(v)
        print(f"DELETE   {v.relative_to(job)}/  ({human(size(v))})")
    print(f"Reclaims {human(total)}. Never touches raw/, broll/, audio/, assets/, outputs/, transcript/.")
    if not victims:
        print("Nothing to reclaim.")
        return
    if not apply:
        print("\nDry run. Nothing changed. Re-run with --apply after reading the plan.")
        return
    for v in victims:
        shutil.rmtree(v) if v.is_dir() else v.unlink()
    print("Done.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["promote", "clean"])
    ap.add_argument("job", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--copy-to", type=Path, default=Path.home() / "Downloads")
    args = ap.parse_args()
    if not (args.job / "outputs").is_dir():
        sys.exit(f"{args.job}/outputs not found")
    if args.action == "promote":
        promote(args.job, args.apply, args.copy_to)
    else:
        clean(args.job, args.apply)


if __name__ == "__main__":
    main()
