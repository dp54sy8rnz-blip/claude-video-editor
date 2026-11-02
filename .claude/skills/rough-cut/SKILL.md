---
name: rough-cut
description: Stage 1. Turn raw talking-head clips in projects/<job>/raw/ into the shortest cut that still delivers the value. Transcribes once with WhisperX (word-level timings), writes transcript/cutsheet.json, splices with one FFmpeg filtergraph, and writes a transcript remapped onto the edited timeline. Use when the user drops footage and asks to edit, cut, or rough-cut a video.
---

# Rough cut

Its whole job: turn raw talking-head clips into the shortest cut that still delivers the value.

Claude cannot hear audio. It only knows where a cut should land because WhisperX gives the
sub-second timing of every word, with forced alignment tight enough that cuts land on the
breath instead of near it.

## Inputs and outputs

| Reads                                  | Writes                                        |
|----------------------------------------|-----------------------------------------------|
| `projects/<job>/raw/*`                 | `transcript/transcript.json` (once, ever)     |
| `projects/<job>/broll/*`               | `transcript/broll.json` (B-roll narration)    |
| `brand.md` mishear list                | `transcript/cutsheet.json`                    |
| `transcript/mishears.json` (per video) | `outputs/base.mp4`                            |
|                                        | `outputs/transcript.cut.json` (remapped)      |

## Steps

1. **Transcribe once.** WhisperX `large-v3` with wav2vec2 alignment:
   `scripts/transcribe.sh projects/<job>`. Result goes to `transcript/transcript.json`.
   Re-running skips straight to the saved copy. This is the slowest step in the pipeline
   and runs exactly once per video.
2. **Also transcribe `broll/`** (same script does it, into `transcript/broll.json`).
   Creators narrate direction inside B-roll takes ("zoom in here", "use this for the
   pricing bit") that never appears in the main script.
3. **Mishear pass.** Run `scripts/unknown_words.py projects/<job>`. It prints only words
   that are neither ordinary English nor already known. Judge each in context: a recurring
   brand name goes into the `brand.md` mishear list (both the table and the JSON block); a
   one-off goes into `transcript/mishears.json` as `{"heard": "correct"}`. Only
   single-word, whole-word swaps are ever auto-applied.
4. **Decide the cut.** Read the transcript and write `transcript/cutsheet.json`:

   ```json
   {
     "segments": [
       {"clip": "raw/A001.mp4", "start": 12.48, "end": 17.02, "text": "the line this segment contains"},
       {"clip": "raw/A001.mp4", "start": 31.10, "end": 36.75, "text": "...", "fade_out": 0.08}
     ]
   }
   ```

   The `text` field is required. Reading the texts top to bottom must read as the finished
   video. That is the sanity check, done without watching anything. Show it to the user.
   Alongside it, propose the hook card title per the hook rule in `brand.md` (script comment
   first, else a tightened version of the strongest opening line, else no card) and show it
   to the user with the cut sheet.
   For a Short cut from long-form footage, use **montage mode** instead (next section).
5. **Motion scan, before every render** (style rule, Shaky footage):
   `scripts/motion_check.py projects/<job> [piece ...]` measures the camera's frame-to-frame motion
   in every frame of every B-roll shot of each cut sheet and writes
   `outputs/review/motion/motion-report.json`. It also fires on big subject motion, so review every
   flagged shot in frames (in sub-agents): keep subject motion, trim every camera jerk, whip,
   tilt-away or zoom so the shot starts after the camera settles and ends before it moves (0.5 s guard).
   Re-run until nothing flagged is a camera move. Never send a render that skipped this.
6. **Splice** with one filtergraph: `scripts/splice.py projects/<job>`. One trim per kept
   segment, concat, then polish the audio once on the assembled track.
7. **Remap** the transcript onto the edited timeline: `scripts/remap.py projects/<job>`.
   Writes `outputs/transcript.cut.json`. Every downstream skill reads that file. Nothing
   re-transcribes, ever.
8. **Review** with the `watch` skill in a sub-agent: every seam, plus the tail of every
   segment, not just the start.

## Montage mode (Shorts from long-form footage)

When the source is a finished long-form video, the Short is not a trim of it: the best lines
are pulled from anywhere in the transcript, re-ordered, and played over B-roll from anywhere
in the shoot. The style file's recipe says what goes where; this is the mechanics.

```json
{
  "mode": "montage",
  "segments": [
    {"clip": "raw/X.mp4", "start": 745.00, "end": 746.20, "text": "[SOUND: door opens]"},
    {"clip": "raw/X.mp4", "start": 7.41, "end": 10.16, "text": "This is the part nobody tells you"}
  ],
  "shots": [
    {"clip": "raw/X.mp4", "start": 745.00, "dur": 1.20, "x_offset": 0, "note": "door opens"},
    {"clip": "raw/X.mp4", "start": 36.50, "dur": 1.30, "x_offset": -120, "note": "street wide"},
    {"sync": true, "dur": 2.00, "x_offset": 60, "note": "host to camera"}
  ]
}
```

- **`segments` is the audio spine**, in play order. `remap.py` reads only these, so captions
  stay word-accurate. A sound-only segment has no words; give it a bracketed `text`.
- **`shots` is the picture**, in play order on the output timeline, independent of the
  segments: several shots can sit under one line, and one shot can straddle the join between
  two trimmed pieces of a line. That is how a trimmed hook's joins are hidden.
  The last shot's `dur` is fitted so the picture ends exactly with the audio.
- **`sync: true`** shows the speaker's own picture under the audio at that moment (lips
  match). Only put a sync shot over an uncut stretch of one line; the joins in a trimmed
  line go under B-roll.
- **B-roll is muted.** A long-form edit carries voice-over across most of its B-roll, so a
  shot's own sound would bring another line in with it. `"sound_db": -18` mixes the shot's
  sound under the voice; only use it on a window with no speech (`montage.py` warns).
- **`x_offset` per shot**, picked from a frame of that shot (see the style's reframe rules).
- **`eq` per shot** (optional): an ffmpeg `eq` grade for one shot that is over- or under-exposed,
  e.g. `"brightness=-0.1:contrast=1.15:saturation=1.15:gamma=0.9"`. Test it on the shot's frame
  first and check the share of near-white pixels drops; the style's colour rules still apply.
- **`zoom` per shot** (optional): `{"scale": 1.6, "cx": 0.46, "cy": 0.40}` crops a punch-in
  around that point (a share of the frame) and scales back to full size. Use it to make a
  reaction on a wide land (a first reaction, a laugh), or to crop a stand or tripod off a frame
  edge (`scale` ~1.1). Works on sync shots too. Keep `scale` at or under ~1.8 on 4K sources.
- **Check the source for burned-in text** (titles, prices, handles) before choosing a
  shot; a finished edit usually has it. Ask for a clean export rather than cropping around it.
- **Preview before splicing:** `scripts/montage.py projects/<job>` prints each line with its
  output and source times, the shots under it, the total length, and warnings. Show the user
  that, not the JSON.
- Cuts are frame-exact: shot boundaries are snapped to the output frame grid so thirty cuts
  never drift against the audio. Every audio join gets a 5 ms edge fade against clicks.

## What gets cut automatically

- Filler words when they are vestigial. Stutters and false starts.
- Long pauses, per the style's `rough_cut.pauses` for this format: keep short natural
  pauses (for example up to ~0.25 s in a fast short), cut long ones (over ~0.3 s) down to ~0.12-0.15 s,
  never to zero. Without that key, cut silences over ~0.4 s (long form in the editorial
  style keeps up to 0.6 s so a key point can land).
- Tangents that do not serve the hook.
- Throat clears, "let me start over".
- Any preamble before the hook lands. **Every video opens on the hook.**
- When a line was recorded several times: **take the last one, always.** It is the warmest
  delivery and comparing takes wastes an hour.

Preserve cadence. Do not surgically remove every "like". Some of them are rhythm.

## Frame rate

**Every style, every format: the cut keeps the frame rate it was shot in.** Never convert
(25 to 30 fps duplicates every fifth frame and the motion stutters). `base.mp4` sets the rate
for every later stage; in montage mode it is the main footage's rate (the first `raw/` clip), even
when a B-roll sound opens the cut, and any shot from a clip at another rate (29.97 fps
B-roll in a 25 fps cut) is conformed to it (`splice.py` adds an `fps` filter to that shot); graphics and B-roll probe it from there. A style's `"fps": "source"`
states this; a style must not name a fixed rate.

## Gotchas

- **Never pass a long filtergraph inline on macOS.** XProtect blocks ffmpeg launched with a
  long multi-line `-filter_complex` argument as "Malicious Script Blocked" and kills the
  terminal (and Claude Code) with it. Write the graph to a file and pass it with
  `-/filter_complex <file>` (ffmpeg 7+); `splice.py` and `mix.py` do this via `graph_args()`.
  Applies to any ad-hoc ffmpeg command too, including composites.

- **Stream copy does not work on arbitrary cut points.** `-c copy` desyncs audio and video.
  Re-encode with hardware acceleration (`splice.py` picks `h264_videotoolbox` on macOS,
  `libx264 -preset veryfast` elsewhere). About 15 s per minute of output.
- **Never encode audio per segment.** It rides through the cut as PCM inside the one
  filtergraph, then gets amplified and limited once on the assembled track. Per-segment
  encoding puts a click at every join.
- **Do not auto-snap cuts to silence.** Word-level alignment is the advantage. Silence
  detection drags deliberate boundaries into filler and awkward pauses.
- **Retake seams clip word tails.** When the speaker cuts in on their own previous word,
  the kept word sounds chopped. Extend the out point slightly into the stumble and set
  `fade_out` (seconds, ~0.05-0.12) on that segment so the word rings out.
- **Stumbles hide inside long word spans.** WhisperX sometimes merges a stumble and its
  retake into one word span over 1.2 s. If a word's duration looks wrong for what it should
  sound like, run silence detection across just that span before deciding the cut:
  `ffmpeg -ss <s> -to <e> -i <clip> -af silencedetect=n=-35dB:d=0.15 -f null -`.
  `unknown_words.py --long-spans` lists them.
- **The transcript will mishear things.** Cross-check before killing a line. "Claude"
  becoming "cloud" makes a good sentence look broken.
- **Screen recordings can carry a chapter track** that inflates reported duration and leaves
  a black tail. Probe with `ffprobe`; `splice.py` strips chapters (`-map_chapters -1`).

## Scripts

- `scripts/transcribe.sh <job>`: WhisperX in an isolated uv environment (never system
  Python). Skips anything already transcribed.
- `scripts/unknown_words.py <job> [--long-spans]`
- `scripts/splice.py <job> [--dry-run] [--encoder X] [--style S --format F]`: with a style
  whose `rough_cut.reframe` covers the format, reframes widescreen onto the vertical canvas;
  each cut sheet segment may then carry `x_offset` (px, positive = picture moves right).
- `scripts/montage.py <job>`: preview and validate a montage cut sheet (`splice.py` runs the
  same validation).
- `scripts/remap.py <job>`
- `scripts/motion_check.py <job> [piece ...]`: camera motion in every frame of every B-roll shot;
  flags jerks/whips (review flagged shots in frames: subject motion is fine)
- `scripts/beat_snap.py <job> --first-beat T --beat S [--quarter i,j] [--fixed i] [--at i=T] [--write]`:
  move the picture cuts onto the music's grid
- `scripts/words.py`, `scripts/sound_scan.py`, `scripts/strip.py`: word gaps, band levels
  (voice vs other sound), labelled frame strips
