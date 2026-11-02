#!/usr/bin/env python3
"""Remap the source transcript onto the edited timeline.

Reads transcript/transcript.json + transcript/cutsheet.json, applies the mishear
lists (brand.md, then transcript/mishears.json), and writes
outputs/transcript.cut.json: {"duration": s, "words": [{"word","start","end","segment"}]}.
Every downstream skill reads that file. Nothing re-transcribes.

Only single-word, whole-word swaps are applied: changing the word count would break
every timestamp downstream.
"""
import json
import re
import sys
from pathlib import Path

PUNCT = re.compile(r"^(\W*)(.*?)(\W*)$")


def find_brand(start: Path) -> Path:
    for d in [start.resolve(), *start.resolve().parents]:
        if (d / "brand.md").exists():
            return d / "brand.md"
    sys.exit("brand.md not found above the job folder")


def brand_json(brand: Path) -> dict:
    m = re.search(r"```json\s*(\{.*?\})\s*```", brand.read_text(), re.S)
    return json.loads(m.group(1)) if m else {}


def load_mishears(job: Path) -> dict:
    fixes = {k.lower(): v for k, v in brand_json(find_brand(job)).get("mishears", {}).items()}
    local = job / "transcript" / "mishears.json"
    if local.exists():
        fixes.update({k.lower(): v for k, v in json.loads(local.read_text()).items()})
    # Enforce single-word -> single-word only.
    return {k: v for k, v in fixes.items() if len(k.split()) == 1 and len(v.split()) == 1}


def fix_word(word: str, fixes: dict) -> str:
    lead, core, trail = PUNCT.match(word.strip()).groups()
    rep = fixes.get(core.lower())
    return f"{lead}{rep}{trail}" if rep else word.strip()


def clip_words(clip_json: dict):
    for seg in clip_json.get("segments", []):
        for w in seg.get("words", []):
            if "start" in w and "end" in w:  # WhisperX leaves some tokens unaligned
                yield w


def main():
    job = Path(sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: remap.py projects/<job>"))
    transcript = json.loads((job / "transcript" / "transcript.json").read_text())["clips"]
    segs = json.loads((job / "transcript" / "cutsheet.json").read_text())["segments"]
    fixes = load_mishears(job)

    out, offset = [], 0.0
    for n, s in enumerate(segs):
        start, end = float(s["start"]), float(s["end"])
        if s.get("text", "").startswith("["):  # a sound ("[SOUND: ...]"), not speech: no words
            offset += end - start
            continue
        # A B-roll sound (a natural-sound open from broll/) may have no transcript: it has no words.
        for w in clip_words(transcript.get(s["clip"], {})):
            ws, we = float(w["start"]), float(w["end"])
            if we <= start or ws >= end:
                continue
            out.append({
                "word": fix_word(w["word"], fixes),
                "start": round(max(ws, start) - start + offset, 3),
                "end": round(min(we, end) - start + offset, 3),
                "segment": n,
            })
        offset += end - start

    dest = job / "outputs" / "transcript.cut.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"duration": round(offset, 3), "words": out}, indent=1))
    print(f"Wrote {dest}: {len(out)} words, {offset:.2f}s")


if __name__ == "__main__":
    main()
