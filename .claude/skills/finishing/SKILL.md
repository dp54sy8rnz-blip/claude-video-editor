---
name: finishing
description: Stage 4. The finishing pass on a graphics-composited cut, in fixed order - burned-in captions from the remapped transcript (optional, off for long form), a flat licensed music bed, then a handful of real sound effects - followed by review. Use when the user asks for captions, music, sound effects, or to finish/polish a video.
---

# Finishing pass

Its whole job: captions, a music bed, and a few sound effects, then review.

Three sub-steps. Each can run alone, but when run together they **always run in this order**,
because each operates on whatever the previous one produced:

1. Captions -> `outputs/captioned.mp4`
2. Music -> `outputs/music.mp4`
3. SFX -> `outputs/sfx.mp4`

Each script picks its own input: the newest of the prior-stage files that exist
(`graphics.mp4` -> `base.mp4` for captions; `captioned.mp4` -> `graphics.mp4` -> `base.mp4`
for music; and so on). Do not hand them an input path.

## 1. Captions

- Burned in from `outputs/transcript.cut.json`, styled from `style.json` `captions.<format>`
  and the caption font in `brand.md` (optional `shadow_px` / `shadow_color` / `shadow_opacity`
  for a drop shadow, `uppercase`). Words are grouped per the style's `words_per_line`,
  breaking early at sentence punctuation. Highlighting follows the style's `highlight`:
  `karaoke` colours each word as spoken; `keywords` colours only the words you choose, listed
  as word indices into `transcript.cut.json` in `transcript/caption-emphasis.json`
  (`{"indices": [12, 57]}`); `none` colours nothing. For `keywords`, pick load-bearing words
  per the caption voice in `brand.md` before running the script.
- **Never caption a file that is already captioned.** `captions.py` refuses any input whose
  name or metadata says captioned.
- **Genuinely optional.** Long form skips captions entirely: YouTube serves its own and
  burn-ins clutter a 16:9 frame. If the style says `enabled: false`, the script exits
  without writing anything and later steps fall through to the graphics/base file.
- Short form: caption block must sit inside the safe zone (y 200-1620) and not cover the face
  or a graphic. Check with `watch`.
- **Lines are chosen as phrases**, not filled greedily: a caption never spans a sentence end, a
  pause over 0.4 s or hidden words; breaks prefer punctuation and the end of an audio piece;
  a line never ends on "the", "of", "a"... and never runs wider than the frame minus 160 px.
- **Not captioned:** cut-sheet segments whose text is bracketed (`[SOUND: ...]`: sound, not
  speech), and any window where the graphics plan has `"hide_captions": true` (a big
  title card or text already showing those words).
- **No libass?** `captions.py` checks for ffmpeg's `subtitles` filter. Without it (Homebrew's
  default ffmpeg has none) it draws each line with PIL from the brand font file and overlays
  it; same size, colour, shadow and baseline. Karaoke highlighting needs libass.
- Run: `scripts/captions.py projects/<job> --format short-explainer --style <style>`

## 2. Music

- A **flat bed at about -18 dB** (or the style's `music_db`). No ducking. No fade in. A short
  fade out on the tail (`"fade_out": 0` is a hard cut, for Shorts that loop).
- **When the style gives `music_under_voice_lu`, set the level by measurement, not by the
  number:** render the bed alone (the `[bed]` chain from `audio-filtergraph.txt`) and the
  voice alone, measure integrated LUFS per section, and set `db` so the body sits that many
  LU under the voice. The same gain is 7 dB apart on two different tracks.
- Every pass ends on a limiter (`alimiter`, -1.9 dBFS, `level=disabled`), so a bed on top of a
  speech track that already peaks at -1.5 dBTP does not push it over.

### Music edits and cutting on the beat (when the style asks for them)

- **Beat grid:** `npx hyperframes@<pinned> beats <dir>` on a scratch project whose `<audio>`
  has `data-timeline-role="music"` writes `beats/<track>.json` (a quantised grid; its bpm is
  often the eighth-note rate). Find which eighths carry the beat by low-passed energy.
- **Pieces:** `"pieces": [{"video_t", "track_t", "db_offset"?}, ...]` lays stretches of the
  track at set video times with a short crossfade (`xfade_ms`). Use it to stitch the track's
  own ending under the last line: find the ending's hits (onset scan of the last bars) and
  place the join in a break or on a beat, so the final hit lands on the last word.
- **Cut on the beat:** in a montage cut the picture is independent of the audio, so move each
  picture cut in `cutsheet.json` onto the grid (up to ~0.3 s) and re-splice, re-time the
  graphics plan, rebuild graphics and captions, then mix. Check every shot's new source window
  against camera cuts (scene score on a proxy) and keep sync shots inside their line: a cut
  that cannot move stays off-grid and is named to the user.
- The track is **user-supplied and licensed**, in `projects/<job>/audio/`. Never pick or download
  one on your own. When the user asks for suggestions, search their licensed music library
  (if one is connected), shortlist with reasons and preview links, and download only the track the user picks,
  into `audio/`. `scripts/track_profile.py` compares candidates without listening: a large
  loudness range reads as theatrical under a voice; check the ending is a clean close.
  If there is no track, ask the user; do not skip silently.
- **Prefer the track's own ending, unstitched:** start the track at the beat that makes its real
  final chord land on the last word or action (count back from the ending on the grid from
  `scripts/beat_grid.py`); a stitch is the fallback. The music must reach silence before the loop,
  never cut off mid-ring.
- Ducking (`--duck`) and fade-in (`--fade-in`) exist as opt-in flags. Almost never reach
  for them. If the bed is not audible enough, change the level; do not add a sidechain.

### Music arc (when the style has `music_arc`)

The build and release are in the track itself; the pipeline only lines them up.

1. Pick the video's release moment from the transcript per the style (e.g. the turn from
   problem to answer), at a word onset or a scene cut measured on the rendered file.
2. Find the track's release: `scripts/find_release.py audio/<track>` ranks moments where the
   music opens up. It measures loudness only, so confirm the pick (a release can be a change
   of harmony or texture) and tell the user which moment you chose and why.
3. Add `release` to the music entry in the audio plan:
   ```json
   "music": {"file": "audio/bed.mp3", "db": -20, "fade_out": 2,
             "release": {"video_t": 9.4, "track_t": 31.2, "pre_db": -17, "ramp_s": 1.0}}
   ```
   `mix.py` trims the track's head (or delays its start) so `track_t` lands on `video_t`, holds
   `pre_db` before the release and eases to `db` over `ramp_s`.
4. If the track's build is longer than the video's intro, the head is trimmed; if it is
   shorter, the music starts late. Either is fine; say which in the review.

## 3. Sound effects

- **Sparse.** A handful of moments per video, not a hit on every cut.
- **Real sample files** at around -10 dB, from `assets/sfx/` (the growing library) or
  `projects/<job>/audio/`. **Never a synthesised tone.** A generated sine wave is instantly
  recognisable as not-a-sound-effect. If there are no samples, skip the step rather than
  fabricate one, and tell the user.
- When a video uses a good new sample, copy it into `assets/sfx/` so the library grows.

## Pure audio passes

- **Never pass a long filtergraph inline on macOS.** XProtect blocks ffmpeg launched with a
  long multi-line `-filter_complex` argument as "Malicious Script Blocked" and kills the
  terminal (and Claude Code) with it. Write the graph to a file and pass it with
  `-/filter_complex <file>` (ffmpeg 7+); `splice.py` and `mix.py` do this via `graph_args()`.
  Applies to any ad-hoc ffmpeg command too, including composites.


Music and SFX **copy the video stream (`-c:v copy`) and never re-encode it.**

## Plan on disk

Write the audio plan to `projects/<job>/transcript/audio-plan.json`:

```json
{
  "music": {"file": "audio/bed.mp3", "db": -18, "fade_out": 1.5, "duck": false, "fade_in": false},
  "sfx": [
    {"t": 3.40, "file": "assets/sfx/whoosh-soft.wav", "db": -10, "why": "hook card lands"}
  ]
}
```

`mix.py` also writes the exact filtergraph it ran to `transcript/audio-filtergraph.txt`.
When a graphics tweak later re-renders the base, re-apply the same plan
(`scripts/mix.py projects/<job>`) instead of re-deciding every placement. SFX times are on
the edited timeline, anchored to measured moments (scene cuts, word onsets), not guesses.

## Review

Then review the finished file with the `watch` skill in sub-agents (technical QA checklist,
then composition). Listen-equivalents: check `ffmpeg -af ebur128` integrated loudness is
around -14 LUFS and the true peak stays below -1 dBTP.

## Scripts

- `scripts/captions.py <job> --format <long|short-explainer|short-raw> [--style editorial]`
- `scripts/mix.py <job> [--music-only | --sfx-only] [--dry-run]`
- `scripts/find_release.py <track> [--top 5]`
- `scripts/beat_grid.py <track> --bpm N [--json out]`: exact beat grid, printed bar by bar
- `scripts/track_profile.py <file>...`: loudness range, swell and ending of candidate tracks
