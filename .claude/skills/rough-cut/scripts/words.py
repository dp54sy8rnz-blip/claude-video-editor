#!/usr/bin/env python3
"""Print source word timings, and the gap before each word, for windows of a job's transcript.

The gaps are what montage and fragment cuts are chosen from: cut in a gap, keep short natural
pauses, and lift a fragment whole from pause to pause.
Usage: words.py projects/<job> a-b [a-b ...]      (seconds in the source clip)
"""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: words.py projects/<job> a-b [a-b ...]")
    job = Path(sys.argv[1])
    clips = json.loads((job / "transcript" / "transcript.json").read_text())["clips"]
    for name, clip in clips.items():
        words = [w for s in clip["segments"] for w in s["words"] if "start" in w]
        for win in sys.argv[2:]:
            a, b = map(float, win.split("-"))
            prev_end, row = None, []
            for w in words:
                if w["end"] > a and w["start"] < b:
                    gap = "" if prev_end is None else f"(+{w['start'] - prev_end:.2f})"
                    row.append(f"{gap}{w['word']}[{w['start']:.2f}-{w['end']:.2f}]")
                if w["start"] < b:
                    prev_end = w["end"]
            print(f"--- {name} {win}\n" + " ".join(row))


if __name__ == "__main__":
    main()
