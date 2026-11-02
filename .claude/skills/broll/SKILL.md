---
name: broll
description: Stage 3. Turn a beat that has no footage into a rendered clip, either a HyperFrames motion graphic from one of eight scene templates or AI footage generated through the Higgsfield MCP, then write a manifest entry. Does not pick windows in existing footage and does not composite. Use for the "broll" slots in the graphics plan or when the user asks for generated B-roll.
---

# AI B-roll

Its whole job: turn a beat that has no footage into a rendered clip.

What it does **not** do:
- Pick windows in footage the user already shot. That belongs to `graphics`.
- Composite anything into the final video. That also belongs to `graphics`.

It generates a clip and writes a manifest entry, and that is it. Keeping generation separate
from placement is what makes both debuggable.

Inputs: `broll` beats from `transcript/graphics-plan.json`, `brand.md`, the style file.
Outputs: `projects/<job>/graphics-build/broll/<beat-id>.mov|mp4` and an entry in
`projects/<job>/graphics-build/broll/manifest.json`.

## Pick the scene template first

Map every slot to one of eight templates **before** writing a prompt. Picking the right
one up front is most of what stops the output reading generic.

| The beat is about          | Reach for        |
|----------------------------|------------------|
| One big number landing     | Stat reveal      |
| Several categories at once | Data breakdown   |
| Parts of a whole           | Pie or donut     |
| Things ranked              | Podium           |
| A system or process        | Flowchart        |
| "Look what showed up"      | Phone notification |
| Old versus new             | Before and after |
| Words as the payoff        | Kinetic type     |

Build data-shaped templates in HyperFrames (it follows every rule in the `graphics` skill's
HyperFrames section). Use Higgsfield for footage and imagery HTML cannot draw.
Higgsfield costs a few dollars per generated segment: tell the user the count before
generating more than three.

## The twelve design rules

These separate motion design from PowerPoint. **Make at least six of them explicit in every
single prompt or composition brief** rather than hoping the render figures them out.

1. Text never just fades in. Clip-mask reveals, or word by word.
2. Nothing animates simultaneously. Stagger everything by at least 0.4 s.
3. The background is never flat. Gradient, vignette, or a fine grid.
4. The accent colour appears on exactly one element per scene.
5. Numbers count up or flip. They never just appear.
6. Exits are designed. Elements leave with purpose.
7. Generous whitespace. More than feels right.
8. One focal point per frame. Never more than two things moving.
9. Scale is dramatic. Primary numbers 160 px minimum.
10. Connectors and dividers draw in, never appear.
11. Small premium details. Thin highlights, low-opacity reflections.
12. Motion blur on fast travel, removed once settled.

**The failure list** (check every brief against it): the same layout reused for every beat;
"fade in" instead of a real entrance; no stagger; a flat background; a vague ease like
"smooth" instead of a named one (`power3.out`, `expo.inOut`); small type; no exits; too many
colours; everything moving at once.

## Technical rules

- **Render at the base video's exact frame rate, probed, never guessed.** If the base is
  23.976, pass `24000/1001`, not `24`. `scripts/finalize.py` probes it for you.
- **Every generated clip is silent.** The base voice keeps playing underneath. If a render
  produces an audio stream anyway, strip it before writing the manifest.
- **Duration = beat window + 0.5 s tail margin.** A clip that ends exactly on its boundary
  is a bug waiting for the next composite.
- Review each clip with the `watch` skill (sub-agent) before it goes in the manifest: both
  the first and last second.

## Scripts

`scripts/finalize.py <job> <beat-id> <clip>`: probes the base frame rate, conforms the clip
to it, strips audio, checks duration >= window + 0.5 s, writes it to
`graphics-build/broll/<beat-id>.mp4` and upserts the manifest entry
`{id, file, start, end, duration, fps, template, source}`.
Pass `--template` and `--source higgsfield|hyperframes`.
