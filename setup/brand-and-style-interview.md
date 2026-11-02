# Brand and style interview

Run this once per channel, after the skills are installed and before the first edit.
It produces `brand.md` at the project root and one starter style in `styles/<style>/`.
The skill scripts read both files, so the field names below are not optional.

Ask one topic at a time, in plain words, and wait for the answer. Offer two or three
concrete suggestions when the user is unsure, instead of leaving a field blank. Nothing in
brand.md may stay empty or say "TBD": if the user truly has no answer, pick a sensible
default, say so, and mark it in the prose as a default they can change later.

When done, show the user both files and the folder tree, then delete this `setup/` folder.

---

## Part 1: brand.md

Start from `setup/brand.template.md`. Fill it in from these questions.

1. **The channel.** What is it called, who is on camera, and what is it about in one or
   two sentences? Who watches it, and what do they already know (so captions and graphics
   never over- or under-explain)?
2. **The feel.** Three or four words for how everything on screen should feel. Ask for a
   channel or video they love the look of, if they have one.
3. **Colours.** Six tokens, each with one role and one hex value:
   - `bg` background base, also light text over footage if that suits the brand
   - `ink` main text colour on light surfaces
   - `accent` the one loud colour, used sparingly (one element per scene)
   - `accent-soft` a quieter tint of the accent for soft highlights
   - `rule` hairlines and dividers
   - `muted` secondary labels
   Add `shadow` (usually `#000000`) if text will sit over footage. Extra brand colours are
   fine as extra tokens, but keep the core six. If they have a logo, pull candidate colours
   from it and confirm. Check `bg`/`ink` contrast is readable.
4. **Logo.** Ask for logo files (PNG with transparency, a light and a dark version if they
   exist). Save them to `assets/logos/` and list which goes on light vs dark.
5. **Fonts.** One display font (titles, cards) and one caption font; they may be the same.
   The actual font files must go in `assets/fonts/` because renders cannot use system
   fonts. Prefer open-licence fonts (Google Fonts, SIL OFL) and save the licence file next
   to the font. Ask: all caps or mixed case?
6. **Caption voice.** Exact words or lightly cleaned? Spelling (US/UK)? Emoji allowed in
   captions (default no: emoji hang the graphics renderer)? Any emphasis colour?
7. **Hook.** How should a video open: straight on the strongest line, a cold open, a hook
   card? Is there a default hook text, or none?
8. **Speaker.** Name and role as they should appear on screen; whether lower thirds are used.
9. **Mishear list.** Names, places, products and jargon the transcriber will get wrong:
   the user's own name, the channel name, brand and product names. Write each as heard ->
   correct. Only single-word, whole-word swaps go in the machine block (multi-word fixes
   would break word timings); note multi-word ones in the prose for manual fixing.

Keep the colours in two places: the readable table and the JSON block at the bottom.
They must match. Styles then refer to colours only as tokens (`$accent`), never hex.

---

## Part 2: the starter style

Start from `setup/style.template.json` and write `styles/<name>/style.json` plus
`styles/<name>/style.md`. Name the style after the look, in kebab case (e.g. `talking-head`,
`explainer-shorts`).

The bar for style.md: someone should be able to edit a new video in this style from the
file alone, without seeing the reference. Adjectives are not enough.

1. **Formats.** Which of `long` (16:9), `short-explainer` (9:16, graphics top, face
   bottom) and `short-raw` (9:16, face full frame, one hook card) is this style for?
   One style can cover several.
2. **Reference.** Is there a reference video (their own or one they admire)? If yes, study
   it in two passes with the watch skill:
   - Pass one over the whole runtime at roughly a hundred scene-change frames: what scene
     types appear, what they are called, how often they alternate, typical shot length.
   - Pass two at a high frame rate on three to five boundaries (face into full-screen
     graphic, graphic back to face, graphic into graphic, anything odd from pass one):
     how the joins actually work.
   Take the mechanics, pacing and placement; map them onto this brand's colours and fonts.
   Never copy another channel's assets. If the reference is the user's own channel, its
   colours are the brand and can be used as they are.
   If there is no reference, ask the questions below directly.
3. **Pacing.** How tight is the cut: keep short pauses or cut every gap? Longest pause
   to keep, in seconds.
4. **Graphics.** Which kinds are allowed (stat, card, screenshot, takeover, zoom, diagram,
   b-roll slot), how often, and where on screen. Transitions: hard cuts or animated?
   Zooms/punch-ins on the face: yes or no?
5. **Captions.** On or off per format (long form usually off). Words per line, size,
   position, case, colour tokens. Highlight: `karaoke` (each word lights up as spoken),
   `keywords` (only key words coloured) or `none`.
6. **Audio.** Music under voice: yes/no, and how loud. Sound effects: sparse, a handful per
   video, real samples only. Natural sound kept or muted under voice.
7. **Ending.** End screen space, outro card, or none.

Write every decision as a value in style.json and as a sentence (with the reason) in
style.md. Leave `learned` as an empty list: corrections from future reviews that should
apply to every video get added there, after showing the user the diff.
