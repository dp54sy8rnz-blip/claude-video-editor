---
name: export
description: Stage 5. Turn a messy outputs folder into one unambiguous final file - promote the newest real render to projects/<job>/outputs/<job>.mp4, retire superseded drafts, keep what's needed to reopen the job, copy the final to Downloads - and optionally reclaim scratch space. Dry run by default. Use when the user says the video is done, asks to export, ship, finalise or clean up a job.
---

# Export

Its whole job: turn a messy outputs folder into one unambiguous file.

By the end of a job there is a base cut, a graphics pass, a captions pass, a music pass,
an SFX pass and some drafts, and in a week nobody will know which one shipped.

## Promote (`scripts/export.py promote <job>`)

- Promotes the **newest real render** (by modification time, among `sfx.mp4`, `music.mp4`,
  `captioned.mp4`, `graphics.mp4`, `base.mp4`, and any other `.mp4` in `outputs/`) to
  `outputs/<job>.mp4`, a single clearly named final. The job name is the folder name, so
  the final is named after the content.
- **Retires** the superseded drafts (deletes them).
- **Keeps**, always: `base.mp4` (so graphics can be re-composited), `transcript.cut.json`,
  everything in `transcript/`, and `graphics-build/` source, so the job can be reopened.
- Copies the final to `~/Downloads/` (override with `--copy-to`).

## Reclaim (`scripts/export.py clean <job>`)

Separate and optional. Deletes render scratch: `graphics-build/renders/`, cached intermediate
renders, stray `node_modules/`. **Never** source footage (`raw/`, `broll/`, `audio/`,
`assets/`), **never** anything in `outputs/`.

## Two rules that make it safe to trust

1. **Dry run by default, always.** Both commands print exactly what they would promote,
   delete and keep, and do nothing until `--apply` is passed. Show the plan to the user and
   get a yes before re-running with `--apply`.
2. **Never delete anything newer than the deliverable.** The guard is inside the script,
   comparing modification times, and aborts the whole operation. Do not work around it: if it
   trips, something was rendered after the file you think is final. Ask the user.

## Close out the job

Before calling the job done, go back through the final-review notes. Any correction that
should apply to every future video gets written into `styles/<style>/style.md` and the
`learned` array in `style.json`. Show the user the diff first. One-off notes are just applied
and forgotten.
