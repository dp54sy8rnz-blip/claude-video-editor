INSTRUCTIONS FOR CLAUDE CODE (read this page first)

This PDF is a channel-neutral AI video-editing toolkit: the pipeline contract (CLAUDE.md), six editing skills
with their helper scripts, a planning skill, settings and a safety hook. It carries no brand, style, preferences, fonts, logos
or music. Those are supplied later, per channel or per video.

1. GET THE FILES FROM THE ZIP, NOT FROM THE PRINTED TEXT.
   Text copied out of a PDF loses indentation, and Python scripts break without it. The exact files are in
   claude-editing-setup-pack.zip, which should sit next to this PDF; it is also attached inside this PDF. If only the PDF is
   here, pull the attachment out with:
       uv run --with pypdf python -c "import pypdf;[open(n,'wb').write(d[0]) for n,d in pypdf.PdfReader('claude-editing-setup-pack.pdf').attachments.items()]"
   The printed pages are the human-readable reference and the fallback if the zip is lost (then recreate
   each file at the path in its grey header bar, restoring indentation carefully, and keep characters
   exact; a few symbols such as arrows and emoji are printed as plain-text stand-ins).

2. PICK THE PROJECT FOLDER. Ask the user where the editing folder should live. Unzip so that the contents of
   the zip's video-editor/ folder land in it: CLAUDE.md at its root, skills in .claude/skills/<name>/. Keep
   scripts executable (chmod +x .claude/skills/rough-cut/scripts/transcribe.sh). Then create the empty
   folders projects/, styles/ and assets/ (with assets/fonts, assets/logos, assets/music, assets/sfx,
   assets/luts inside). Jobs go in projects/, one kebab-case folder per video.

3. BRAND AND STYLE. CLAUDE.md and the skills expect brand.md at the root and styles/<style>/style.md +
   style.json; the scripts stop without brand.md. Ask the user: do they already have a brand and style to
   feed in, or should you build them from zero? If they have them, write them to those paths. If not,
   run the interview in setup/brand-and-style-interview.md, using setup/brand.template.md and
   setup/style.template.json (they carry the exact field names the scripts read). Never invent brand
   choices without asking. Delete setup/ when brand.md and the first style are done.

4. PLAN FIRST, ALWAYS. CLAUDE.md makes the edit-plan skill a standing rule: before any editing stage, and
   before acting on any notes, show numbered steps with a time estimate for each and a total. Tell the user
   this is how every edit will start. The premiere-xml-cut skill has no shared scripts on purpose; it says
   which scripts to write inside each job.

5. INSTALL THE STACK (next page), then run the "Verify the stack" block from CLAUDE.md and report what fails.

6. NOT INCLUDED ON PURPOSE: a filled-in brand.md or style, fonts, logos, LUTs, music, sound effects,
   editing-preference memories, .claude/settings.local.json, old projects.

7. When everything checks out, tell the user in plain words what works, and list anything they must do
   themselves (installs that need their password, brand/style files to provide).


INSTALL CHECKLIST (macOS, Homebrew)

Command line tools
  - Homebrew, then:  brew install ffmpeg uv node git
  - Node must be version 22 or newer (node --version).
  - Python 3 with Pillow:  python3 -m pip install pillow  (or uv pip). numpy is used by several scripts too.
  - HyperFrames (motion graphics), pinned:  npm install  in the project root (package.json pins
    hyperframes 0.8.73). Never upgrade it silently. Check:  npx hyperframes@0.8.73 doctor
    (an upgrade nag and "Docker not running" are expected and fine).
  - WhisperX (word-level transcripts): .claude/skills/rough-cut/scripts/transcribe.sh runs it through uv;
    the first run downloads the model. Read the rough-cut SKILL.md for the exact call.

Claude Code plugin
  - The "watch" plugin (skill watch:watch): lets Claude see renders by extracting frames. Install it from the
    Claude Code plugin marketplace, then add GROQ_API_KEY or OPENAI_API_KEY to ~/.config/watch/.env if you
    want its Whisper fallback (optional).
  - Connectors are not part of this setup yet. Where a skill mentions one (Higgsfield in broll and
    graphics), skip that route and ask the user.

What each skill does (pipeline order, from CLAUDE.md)
  - edit-plan         runs first every time: numbered steps, a time estimate each, a total
  1 rough-cut        WhisperX transcript -> cutsheet.json -> one FFmpeg splice
  1 premiere-xml-cut  same stage, but hands Premiere Pro an FCP7 XML timeline instead of a render
  2 graphics          HyperFrames (HTML/CSS/GSAP) cards and callouts composited with FFmpeg
  3 broll             HyperFrames motion graphics for beats with no footage
  4 finishing         captions, music bed, sound effects
  5 export            promote the final render, tidy the job folder
  hook guard-delete   blocks risky delete commands before they run

Style is chosen per video from styles/ and brand.md holds colour tokens and fonts, both supplied later.
Always refer to colours as tokens ($accent, $bg), never hex.
