#!/usr/bin/env python3
"""Second mishear pass: print transcript words that are neither ordinary English nor known.

Compares every word against a system dictionary plus the brand.md and per-video
mishear lists. Judge each hit in context: recurring -> brand.md, one-off ->
transcript/mishears.json.

--long-spans also lists words longer than 1.2 s: WhisperX sometimes merges a stumble
and its retake into one span. Run silencedetect across those before cutting.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from remap import clip_words, load_mishears  # noqa: E402

DICTS = ["/usr/share/dict/words", "/usr/share/dict/american-english", "/usr/share/dict/british-english"]


def load_dictionary():
    words = set()
    for d in DICTS:
        p = Path(d)
        if p.exists():
            words |= {w.strip().lower() for w in p.read_text(errors="ignore").splitlines()}
    if not words:
        sys.exit("No system dictionary found. macOS ships /usr/share/dict/words; "
                 "on Debian/Ubuntu: sudo apt install wamerican")
    return words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job", type=Path)
    ap.add_argument("--long-spans", action="store_true")
    args = ap.parse_args()

    dictionary = load_dictionary()
    fixes = load_mishears(args.job)
    known = dictionary | set(fixes) | {v.lower() for v in fixes.values()}

    hits, contexts = Counter(), {}
    for name in ("transcript.json", "broll.json"):
        path = args.job / "transcript" / name
        if not path.exists():
            continue
        for clip, data in json.loads(path.read_text())["clips"].items():
            words = list(clip_words(data))
            for i, w in enumerate(words):
                core = re.sub(r"[^\w'-]", "", w["word"]).lower().strip("'-")
                if args.long_spans and float(w["end"]) - float(w["start"]) > 1.2:
                    print(f"LONG  {clip} {w['start']:.2f}-{w['end']:.2f} '{w['word']}'")
                if not core or core.isdigit():
                    continue
                base = re.sub(r"('s|s|es|ed|ing)$", "", core)
                if core in known or base in known:
                    continue
                hits[core] += 1
                ctx = " ".join(x["word"] for x in words[max(i - 5, 0): i + 6])
                contexts.setdefault(core, f"{clip} @{w['start']:.1f}s: ...{ctx}...")

    for word, n in hits.most_common():
        print(f"{n:3d}x  {word:<20} {contexts[word]}")
    if not hits:
        print("No unknown words.")


if __name__ == "__main__":
    main()
