# Video editor: the pipeline contract

This folder is an AI video editor. Claude cannot open Premiere, so every stage is
built from things Claude can actually do: read a transcript, make a decision, write
code, and run a command line tool.

## Two halves

- **Taste, permanent, shared by every video:** `brand.md`, `styles/`, `assets/`.
- **Jobs, disposable:** `projects/<job>/`.

Anything that does not clearly belong to one of those halves means the design has
drifted. Do not add notes files, config files or "temp" folders.

## The pipeline

| # | Stage     | Skill        | Runs on                 |
|---|-----------|--------------|-------------------------|
| 0 | Setup     | (done once)  | Claude                  |
| 1 | Rough cut | `rough-cut`  | WhisperX + FFmpeg       |
| 2 | Graphics  | `graphics`   | HyperFrames             |
| 3 | B-roll    | `broll`      | HyperFrames + Higgsfield|
| 4 | Finishing | `finishing`  | FFmpeg                  |
| 5 | Export    | `export`     | FFmpeg                  |

Short form and long form run the same five stages. Only how graphics and captions
behave inside stages 2 and 4 changes, and that is driven entirely by the style file.
Every stage renders, then gets reviewed with the `watch` skill in sub-agents
(see "Review loop" below) before the next stage starts.

## Job layout

```
projects/<job>/            kebab-case, named after the content
├── raw/                   source clips, copied in, never moved
├── broll/                 screen recordings and supporting footage
├── audio/                 licensed music, sound samples for this video
├── assets/                references, screenshots, logos for this video
├── transcript/            transcript.json and cutsheet.json, the durable record
├── graphics-build/        the composition source. This is the real progress
└── outputs/               renders and the cut-aligned transcript
```

Job naming is a rule: name the folder after what the video is about, in kebab case.
Never the camera filename, never a date, never a stage suffix like `-final` or `-v2`.
One folder carries one content piece through every stage.

## Standing rules

- **Plan first, every time.** Before starting any editing job or stage, and before acting on
  any notes or corrections, use the `edit-plan` skill: show numbered steps with a time
  estimate for each and a total, then start. Report actual time against it as you go.
- **Plan first, every time.** Before starting any editing job or stage, and before acting on
  any notes or corrections, use the `edit-plan` skill: show numbered steps with a time
  estimate for each and a total, then start. Report actual time against it as you go.
- Read `brand.md` and the chosen `styles/<style>/style.md` + `style.json` before any
  creative decision. Colours are always referenced as tokens (`$accent`, `$bg`), never hex.
- Every rule lives in the skill that owns it. Read the skill before running its stage.
- Local direction (script comments, one-off asks) never silently overrides a style
  convention. Flag the conflict and ask.
- Any correction in final review that should apply to every future video gets written
  back into the style file (show the user the diff first) before the job is closed.
  One-off notes are applied and forgotten.
- Keep build source durable, never only in a temp folder.
- Never prefix commands with cd; you're already in the project folder. Use relative paths, run one
  command at a time (no &&, ; or pipes unless necessary).
- Helper scripts go in the current project's tmp/ folder (projects/<job>/tmp/), never in
  $CLAUDE_JOB_DIR, /tmp or anywhere else. Run them as `python3 tmp/<name>.py` from the project folder.

## Review loop

Claude cannot see video; the `watch` skill extracts frames so it can. After every render:

1. Send the review to **sub-agents** (frame dumps flood the main context). They return
   timestamped findings.
2. Pass one, **technical QA** as a checklist: stretched assets, vanished elements, wrong
   colours, brightness dips at seams, safe-zone violations, bad tail frames.
3. Pass two, **composition** as its own named step: every overlay re-checked against what
   the style file says for that element category; every distinct visual moment in the
   direction accounted for as built or explicitly flagged as skipped, never silently
   simplified away.
4. Fix, re-render, review again until it passes.
5. Also run an early spot review after the first ~10% of a graphics build.

Use frame extraction, not a video-understanding model: Claude decides exactly where to look.

## Verify the stack

Before the first job, and whenever something "doesn't work":

```bash
ffmpeg -version && ffprobe -version
node --version        # must be >= 22
uv --version
python3 -c "import PIL"
npx hyperframes@<pinned> doctor   # upgrade nag and Docker-not-running are expected
```

Then confirm the `watch` skill appears in Claude's tool list.
HyperFrames is pinned per workspace; never upgrade it silently.
