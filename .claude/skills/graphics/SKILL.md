---
name: graphics
description: Stage 2. Decide which lines of the rough cut earn a graphic, write a validated graphics plan, then build every graphic as HyperFrames code (HTML/CSS/GSAP) and composite it over the base cut with FFmpeg. Use after the rough cut, or whenever the user asks to add, change or fix a graphic, card, takeover, zoom, stat or screenshot in a video.
---

# Graphics

Its whole job: decide which lines earn a graphic, then build each one.

Two halves that stay separate: **plan, then build**. Planning is a judgment problem,
building is an engineering problem. Mixing them produces a plan written to be easy to
build, which is the wrong optimisation. Finish and validate the plan before writing any
composition.

Read first: `brand.md`, `styles/<style>/style.md` + `style.json`. If a taste skill is
installed, apply it: every graphic is front-end design.

---

## Part 1: the plan

### Read three things before deciding a single beat

1. `outputs/transcript.cut.json` from the rough cut.
2. Comments in the user's script document. For a .docx, pull them from the document XML
   (`word/comments.xml`, anchored via `commentRangeStart` in `word/document.xml`), not a
   library that drops them. For Google Docs, read comments through the Drive API/connector.
3. The B-roll narration in `transcript/broll.json`.

### For every beat, answer in order

**1. Does this line need a graphic? Default to no.** A graphic on every line is wrong.
Plain beats give rhythm and let the face carry the moment. A beat earns a graphic when:
- it is the hook;
- it names something concrete and showable (a stat, a screenshot, a before and after);
- it is a payoff worth emphasising;
- it describes a process a picture would make instantly clearer;
- the user explicitly asked for one.

Leave connective tissue, transitions, asides and emotional delivery plain.

**2. What kind?** Think in rich terms first, then flatten to exactly one of seven kinds:
`stat`, `card`, `screenshot`, `takeover`, `zoom`, `diagram`, `broll` (slot filled by the
`broll` skill). Reach for showing over telling: screen recordings, screenshots, diagrams
and stats beat text cards almost every time. Reserve cards for the hook and punchlines,
and even then give them motion and a visual element, not a wall of type.

**3. Where?**
| Format           | Placement                                                   |
|------------------|-------------------------------------------------------------|
| Short explainer  | Graphics in the top half, face in the bottom half.          |
| Short raw        | Whatever the style file allows, nothing more (often one hook card or none; never a title card the style does not ask for). |
| Long form        | Full-frame takeovers, lower thirds, no reframe.             |

**4. What exactly?** Write the actual creative direction: what is on screen, the
hierarchy, the hero element, and critically **what animates and in what order**.
Concrete enough that the build step is not guessing.

### Write the plan

`transcript/graphics-plan.json`, plus a human-readable table shown to the user for review:

```json
{
  "format": "long",
  "style": "editorial",
  "beats": [
    {"id": "g01", "start": 0.00, "end": 3.40, "kind": "card",
     "direction": "Hook card. Eyebrow 'THE $90 EDITOR' clip-reveals, then title word by word...",
     "notes": "script comment: 'start zoomed in and rapidly zoom out'"}
  ]
}
```

Beats with no graphic are simply not in the list.

### Validate before the build ever sees it

`scripts/validate_plan.py projects/<job>` checks: required fields present, kind is one of
the seven, start < end, sorted ascending, no overlaps, and **consecutive beats either abut
exactly or leave a gap of more than 1 s**. A gap of a few tenths flashes raw footage for a
fraction of a second in the composite and almost always means the plan meant to abut.

### Safe zones

| Format     | Frame     | Keep key visuals inside                                          |
|------------|-----------|------------------------------------------------------------------|
| Short form | 1080x1920 | y 200 to 1620. Top 200 px and bottom 300 px are background only. |
| Long form  | 1920x1080 | Title safe, 10% margins. Outro: keep the right 40% clear for end-screen cards. |

The short-form bands are not a guideline. The platform UI, username, audio tag and
progress bar all land there.

---

## Part 2: the build

### Generate, do not hand-write

One build script in `projects/<job>/graphics-build/` (e.g. `build.mjs`) holds the shared
CSS, the per-graphic markup and the per-graphic animation, and emits one composition per
part plus `render.sh` and `assemble.sh`. That folder is the real progress on the job, so it
lives in the project, never in a temp directory. Only heavy regenerable renders go to
`graphics-build/renders/` (git-ignored).

Pin HyperFrames in `graphics-build/package.json` to the version `doctor` passed on. Never
upgrade it silently.

### Classify every part: does it change the footage underneath, or float on top?

- **Overlay**: a card, panel, callout. Renders standalone to a transparent file
  (ProRes 4444 / VP9 alpha) and composites over the base at its timestamp.
- **Segment**: a takeover, full-screen cutaway, anything that replaces the frame. Renders
  with its own slice of the base baked in, as an opaque file covering the base for its window.

**The base rough cut is never re-rendered.** Editing one graphic = regenerate one
composition, re-render one part in seconds, run one FFmpeg composite pass. Lock parts one
at a time.

### Non-negotiables

- **Graphics hold until the next part starts.** No early fade leaving dead air.
- **The PiP enters once per graphics run.** Chain everything between entries. Bouncing
  full frame -> PiP -> full frame is the single most amateur-looking thing an AI editor
  does. Hard cuts between card contents are fine; a full-screen bounce never is.
- **Continuous motion on any beat of 20 s or longer.** Write out explicitly what is moving
  across its entire duration, not just the entrance. A count-up done at 6 s of a 19 s beat
  reads as a frozen frame for 13 s.
- **Real assets over recreations.** The actual logo, screenshot, chart, with a slow pan or
  push. Never a redrawn approximation. If an icon or illustration cannot be built in HTML
  and does not exist, generate it mid-edit with the Higgsfield MCP and composite it in.
- **Measure, do not estimate.** Pull the actual frame, measure the element's bounding box
  in pixels, set the zoom from that measurement.
- **Check the tail of every clip, not just the start.** A retake seam leaves a bad frame at
  the out point and nobody watches the last second.
- **Assets outlast their window.** Every part gets ~0.5 s of tail margin past its nominal end.
- **Local direction never silently overrides a style convention.** A script comment that
  conflicts with the style file is a conflict to flag to the user, not a decision to make
  quietly. Following the more recent instruction is recency bias, not judgment.

---

## HyperFrames: the timeline contract

Compositions are **seeked, not played**. The renderer jumps to arbitrary frames.

- One master timeline, created paused, every tween at an **absolute second**. No relative offsets.
- **Never random values.** The same frame must render identically on every seek.
- **Never real-time timers.** No `setTimeout`, no `requestAnimationFrame` loops. Everything
  comes off timeline position.
- Every exit landing on a boundary needs an **explicit hard kill**: opacity set to 0 at that
  exact time. An unresolved tween pops instead of finishing.
- Time is always in **seconds**, never frames.
- Every entrance is a **`fromTo`**, never a bare `to` (no defined start state when seeked into).
- Never put a CSS transform and a GSAP tween on the same property.

### Things that silently do not render (nothing errors)

- **Never transform a `<video>` directly.** Scale/move on a video gets composited away in
  the headless render; the face just vanishes. Reframe through layout: wrap the video in a
  `div` with `overflow: hidden` and animate the wrapper's `left/top/width/height`.
- **CSS `blur()` filters are not render-safe.** For a blur-in text reveal use a per-letter
  opacity stagger, ~0.045 s between letters.
- **Grayscale filters fail the same way.** Fake desaturation by tweening colour toward a flatter value.
- **Class-name tweens do not survive the seek** and can wipe the base class styling. Tween
  the actual CSS properties.
- **Near-zero-duration tweens are unreliable.** Give every instant state change 0.2-0.35 s.
  It still reads as a cut.
- **Raw emoji glyphs hang the render** at full CPU, forever, no error. Use the brand font or
  a pre-rendered transparent PNG. Tell: a render still going at 3x the length of a same-sized
  part is an emoji, not a real hang.
- **Transparent overlays have nothing behind them, so `backdrop-filter` does nothing.**
  Design frosted panels to read on their own fill.

### Linter and workflow

- `lint` and `validate` are the gate. Run both on every part before rendering.
- Contrast warnings on deliberately dim text: raise opacity, not brightness.
- A dense-track warning on a short build is normal. Do not refactor into sub-compositions to silence it.

---

## The composite traps (FFmpeg, show up only at assembly)

- **Match every part to the base frame rate exactly**, probed with ffprobe (`24000/1001`,
  not `24`). Mixed rates drift.
- **Segments carry their own base slice**, cut once from the base, so first and last frames
  match at the seam.
- **Cut that slice at the time it is placed, not the time it was built.** If the base is
  re-spliced and graphics shift, re-cut and re-render every segment. Overlays just slide.
- **Every overlay gets `eof_action=pass`, not repeat.** Chaining short overlays over a long
  base otherwise makes the scheduler duplicate output frames on a periodic cadence (measured
  1 in 4): constant frame rate on paper, ~18 real frames/s in a 24 fps costume. Visible
  judder; every input measures clean alone. The one exception is a deliberately held frame
  (e.g. an outro push-in that must not zoom back out): that one gets `repeat`.
  ```
  [0:v][1:v]overlay=enable='gte(t,12.4)*lt(t,17.9)':eof_action=pass[v1]; ...
  ```
  (Offset each overlay input with `-itsoffset <start>` so its t=0 lands at its window.)
- **Gate overlays with a half-open window, `gte(t,a)*lt(t,b)`, never `between(t,a,b)`.**
  `between` includes both ends, so where one overlay abuts the next, the frame at the
  boundary draws both: two overlays stacked on top of each other for one frame.
- **`assemble.sh` must run `scripts/dupe_check.py` on the output and fail above 8%.** Clean
  is under 3%, the bug is ~25%. Do not mask it by forcing a frame rate; the output is already constant.
- **Never use frame padding (`tpad`) to hold a zoom.** It never reaches EOF and can balloon
  a few-second clip into gigabytes.
- **Browser segments darken the footage ~3% luma**, so the face dips at every seam. Fix at
  the root, in order:
  1. Do footage motion in FFmpeg, not the browser. A zoom or push-in is pure geometry. Only
     use a browser segment when live graphics must reveal behind the moving face.
  2. If it must be a browser segment, render its source frames as PNG (halves the dip), then
     close the rest with a gamma correction at assemble time (`eq=gamma=1.03` or measured),
     not a flat gain, so black and white stay pinned and highlights do not clip.
- **An FFmpeg zoom on a mid-video slice needs its frame counter reset**, or it comes out
  constant and reads as a hard cut. Build the slice with `trim=...,setpts=PTS-STARTPTS`
  inside the filtergraph, not with `-ss`. An intro zoom works by luck at t=0; later ones silently do not.
- **Anchor footage motion to measured scene cuts, not nominal ones.** The rendered base
  drifts from the cut sheet by a few hundred ms by the end of a reel. Detect the real cut:
  `ffmpeg -i base.mp4 -vf "select='gt(scene,0.3)',showinfo" -f null -`.
- **Screen recordings carry black bars.** Run `cropdetect` before compositing one into a card.
  And size the card bigger than feels right: numbers that look generous in CSS render small.

---

## Review (with the `watch` skill, in sub-agents)

- **Early spot review** after the first ~10% of parts are rendered and composited. A wrong
  placement habit caught once is a fix; caught at the end it is a rebuild.
- **Final review, two passes:** technical QA as a checklist, then composition as its own
  named step (every overlay against the style's rules for its category; every visual moment
  in the direction built or explicitly flagged as skipped).
- Inspect every seam and every part's last second.

## Scripts

- `scripts/validate_plan.py <job>`: gate before any build.
- `scripts/dupe_check.py <video> [--max 8]`: duplicate-frame ratio (near-identical, since lossy encodes break byte-exact matches; exact count reported too); exit 1 above max.

## macOS: filtergraphs

- **Never pass a long filtergraph inline on macOS.** XProtect blocks ffmpeg launched with a
  long multi-line `-filter_complex` argument as "Malicious Script Blocked" and kills the
  terminal (and Claude Code) with it. Write the graph to a file and pass it with
  `-/filter_complex <file>` (ffmpeg 7+); `splice.py` and `mix.py` do this via `graph_args()`.
  Applies to any ad-hoc ffmpeg command too, including composites.
