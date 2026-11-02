# Claude video editor

An AI video-editing toolkit for Claude Code: a pipeline contract (`CLAUDE.md`), editing
skills with their helper scripts, a planning skill, settings and a safety hook. It carries
no brand, style, fonts, logos or music; those are built per channel with the included
interview, or fed in later.

| Skill              | What it does                                                            |
|--------------------|-------------------------------------------------------------------------|
| `edit-plan`        | Runs first every time: numbered steps, a time estimate each, a total    |
| `rough-cut`        | WhisperX transcript, a cut sheet, one FFmpeg splice                     |
| `premiere-xml-cut` | Same stage, but hands Premiere Pro an FCP7 XML timeline instead         |
| `graphics`         | HyperFrames (HTML/CSS/GSAP) cards and callouts composited with FFmpeg   |
| `broll`            | Motion-graphic B-roll for beats with no footage                         |
| `finishing`        | Captions, music bed, sound effects                                      |
| `export`           | Promote the final render, tidy the job folder                           |

## Install

1. Download this repo: the green **Code** button, then **Download ZIP**, and unzip it.
   Rename the folder to `video-editor` and put it where you want your editing folder.
2. Open that folder in Claude Code (desktop app or terminal, macOS or Linux).
3. Tell Claude: **"Read README-FIRST.txt and set this up."**

Claude installs the tools (FFmpeg, Node 22+, uv, Pillow, HyperFrames, WhisperX), runs the
stack check, then asks whether you already have a brand and style or want to build them
from zero with the interview in `setup/`.

`claude-editing-setup-pack.pdf` is the same toolkit as a readable document, with every file
printed in full.

## Start editing

Make a folder per video in `projects/<what-the-video-is-about>/raw/`, drop the clips in, and
say what you want: "edit this" for a finished video, "build a Premiere timeline" for an XML.
Claude shows a plan with time estimates before it starts.
