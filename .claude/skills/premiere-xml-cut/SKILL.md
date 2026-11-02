---
name: premiere-xml-cut
description: Stage 1 (Premiere route). Read the transcripts of a multi-camera shoot, work out the storyline and share it with the user, then build a Premiere Pro rough-cut XML (FCP7 xmeml) with a story-first cut, the style's opening and hook, synced camera tracks, B-roll covers, on-screen callouts, a suggested-B-roll track and every unused clip for cross-reference. Use when the user wants the edit handed to Premiere instead of an FFmpeg render, or asks to turn a transcript or footage folder into a Premiere timeline or XML.
---

# Premiere XML cut

Its whole job: turn a shoot's transcripts into a story the user agrees with, then into a
Premiere timeline they can open, relink and refine. Claude cannot open Premiere, so every
decision is made from transcripts, frames and file metadata, and the XML is validated by
script before the user sees it.

Use this instead of `rough-cut` when the user says "Premiere", "XML" or "timeline", or when
the shoot has several cameras that need to stay editable. The transcription step is shared
with `rough-cut` (`scripts/transcribe.sh`, run once per video).

## Inputs and outputs

| Reads                                                | Writes                                                   |
|------------------------------------------------------|----------------------------------------------------------|
| every camera folder in `projects/<job>/`             | `transcript/transcript.json`, `transcript/cutsheet.json` |
| `brand.md`, `styles/<style>/style.md` + `style.json` | `outputs/<job>-rough-cut.xml`                            |
| `assets/fonts`, the style's callout spec             | `outputs/<job>-hook-montage.xml` (only if asked)         |
| the user's notes and corrections                     | `graphics-build/callouts/*.png`                          |

There are no shared scripts for this skill: each shoot's cut data differs. Write the job's
scripts in `projects/<job>/tmp/` (all paths relative to the project, never absolute):
`build_xml.py` (cut data + XML writer), `validate_xml.py`, `check_sync.py`,
`make_callouts.py`, and `make_sync_test.py` when a new camera appears. Keep the cut data
(order, covers, opener) in one clearly marked block at the top of `build_xml.py`.

## Steps

1. **Read the taste files.** `brand.md`, the style's `style.md` (its opening, callout,
   colour and workflow sections) and `style.json`. Colours as tokens, never hex.
2. **Inventory.** `ffprobe` every clip: camera, fps, resolution, duration, audio channels.
   Check whether the voice camera's audio is dual mono (left and right identical). If it
   is, the timeline gets one voice track, never two.
3. **Transcribe once** with WhisperX, B-roll takes included (creators narrate direction in
   them). Run the mishear pass from `rough-cut` step 3.
4. **Understand the story, then share it. Stop and wait.** Read every transcript and write,
   in plain words:
   - the story in a few lines, and the sections in the proposed order with a one-line
     reason each
   - per section: the key point, the most vivid detail and the payoff
   - which clips are voiceover, which are face to camera, which are B-roll narration
   - the length, and a cut-first list if it runs long
   - what is missing (a promised shot that was never filmed, no sign-off, a jump cut that
     needs cover)

   Ask for: section order, must-keep lines, voiceover pickups, music if relevant. Put every
   question the user must answer on its own line at the end. Do not build until they answer.
5. **Write the cutsheet.** `transcript/cutsheet.json`, one entry per cut with a `text` field.
   Reading the texts top to bottom must read as the video. Never cut mid-sentence: check the
   words past every cut.
6. **Sync the cameras.** Offset by transcript words, refined by GCC-PHAT cross-correlation on
   the audio (`camB_t = camA_t + offset`). Check per-cut word overlap and a median residual
   near zero. Cameras that never share audio (B-roll only) are not synced and are used as
   cover.
7. **Open the way the style says**, then the hook. If the style asks for an opening that
   shows a specific moment, check frames for each shot before using it. If the shoot has
   no real version of the promised shot, say so and offer the closest one.
8. **Cover with B-roll.** Anchor each cover to the spoken phrase using word timings, not to
   a guessed second. Show the thing being named at the moment it is named, and mix with
   action. Keep the speaker's face on the camera they are looking at. Anywhere the voice
   continues under a cover it stays on the voice track; only the picture is carved.
9. **Callouts.** One PNG per named item the style wants called out (a product, a place, a
   person), with placeholder text where a detail is unknown, rendered from the style's
   callout spec and the brand fonts, on their own track at the item's first mention.
10. **Suggested B-roll.** A switched-off track of tag-scored cover candidates that need not
    be audio synced. Say plainly that windows come from tags and stills, not from watching.
11. **Build the XML** with the conventions below, then run the validator. It must report no
    overlaps, range errors, dangling links, missing files, or file references before their
    definition.
12. **Test unfamiliar cameras first.** The first time a new camera or frame rate appears,
    send a two-clip test XML in a few in/out-point variants and ask the user which variant
    lines up. Only then build the full file.
13. **Hand over** with the handoff note below, questions last.

## XML conventions (each one cost a failed import or a rework)

- **Names:** clip name is the exact source filename, because the user relinks by name.
- **Tracks:** one video track per camera so colour is per camera (V1 voice camera, then one
  track per other camera), then callouts, then switched-off alternates, then switched-off
  suggested B-roll. One audio track when the voice is dual mono.
- **`sourcetrack` trackindex is 1 for every video clip.** 2 or 3 makes the import fail with an
  empty error dialog.
- **No overlaps on a track.** Trim after all items exist, with an explicit final pass.
- **In and out points:** by spec they are frames in the clip's own rate, but Premiere has
  read 23.976 fps clips at the sequence rate (25 per source second) in a 25 fps sequence.
  Confirm with the test in step 12 for any new frame-rate mix. Compute clip and file
  durations with one function.
- **File definitions** appear once, in full; later uses are `<file id=.../>` references and
  must come after the definition.
- **Disabled clips** use `<enabled>FALSE</enabled>`.
- **PNG stills** import as a clip whose file duration is 18000 with
  `<alphatype>straight</alphatype>`.
- **Unused clips sit to the right of the cut**, on their own camera's track, starting 250 frames
  after the end, all switched off. First come the **recommended shots**: tag-scored action
  windows (about 4 s, natural sound, no crew or camera in frame, not static) cut from unused
  clips and labelled `REC section N: ...`. After them come the **whole unused clips**, so
  nothing is hidden. Say what the block is, because it looks like a second timeline.
- **Linked audio:** link elements carry `linkclipref`, `mediatype`, `trackindex`, `clipindex`.
- **Never let a standalone file overwrite the main one.** A montage-only file is its own
  script and its own output.

## Handoff note (every time)

Tell the user, in plain words:
- what is on each track, and which tracks are switched off on purpose
- the block to the right of the cut (recommended shots first, then the whole unused clips),
  and to set the out point at the cut end before export
- how to relink: select the offline clips, Link Media, point at the camera folder; proxies
  attach afterwards via Attach Proxies; importing into a project that already has the
  footage does not duplicate it if they relink rather than re-import
- what is untested (cover windows chosen from tags, not from watching) and what to check first

## Checklist before handing over

- [ ] The story was shared and the user answered before the build
- [ ] The opening follows the style, then the hook
- [ ] Every section has its key point and payoff; the sign-off is kept
- [ ] No cut lands mid-sentence; no crew voice or retake line in the cut
- [ ] Every second camera's mouth matches the voice in a spot check at three cuts
- [ ] Callouts exist for every item the style calls out, on their own track
- [ ] Validator is clean; stills and covers each checked in a frame
- [ ] Runtime reported against the style's target, with a cut-first list if over
- [ ] The handoff note was sent and ends with the user's questions

## Gotchas

- Claude cannot hear. Sync and cover timing come from word timings and cross-correlation,
  never from "sounds right".
- Do not describe a shot you have not seen in a frame. One wrong description of what a shot
  showed cost a full rebuild.
- A short clip will not span a long cover. Check duration before assigning.
- `sed -i` fails on macOS; edit with Python or the Edit tool.
