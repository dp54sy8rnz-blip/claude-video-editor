# Brand: <channel name>

<Who is on camera and what the channel is about, in two or three sentences.>

**Audience:** <who watches, what they already know, what never to assume.>

Everything on screen should feel **<three or four words>**.

## Logo

Files in `assets/logos/`.

| File | Use on |
|------|--------|
| `<logo-dark>.png` | light backgrounds (default) |
| `<logo-light>.png` | dark backgrounds and over footage |

## Colours

Six core tokens. Styles refer to these as `$token`, never as hex.

| Token        | Role                                   | Hex       |
|--------------|----------------------------------------|-----------|
| bg           | <background base>                      | `#......` |
| ink          | <main text on light surfaces>          | `#......` |
| accent       | <the one loud colour, used sparingly>  | `#......` |
| accent-soft  | <quieter tint of the accent>           | `#......` |
| rule         | <hairlines and dividers>               | `#......` |
| muted        | <secondary labels>                     | `#......` |
| shadow       | <drop shadow behind text over footage> | `#000000` |

## Type

- **Display font:** <name> (`assets/fonts/<file>`), for titles and cards. Licence: <licence file>.
- **Caption font:** <name> (`assets/fonts/<file>`).
- <case: all caps or mixed; weights used.>

## Caption voice

<Exact words or lightly cleaned; spelling; emoji rule; emphasis rule.>

## Hook rule

<How every video opens; default hook text or none.>

## Mishear list

Single-word, whole-word swaps only (they are applied automatically to every transcript).

| Heard | Correct |
|-------|---------|
| <heard> | <correct> |

<Multi-word fixes to make by hand, if any.>

## Speaker

- **Name:** <name>
- **Role:** <role>
- <lower thirds: used or not.>

## Machine-readable

Skills parse this block. Keep it in sync with the tables above.

```json
{
  "name": "<channel name>",
  "logo": "assets/logos/<logo-dark>.png",
  "logos": {
    "dark": "assets/logos/<logo-dark>.png",
    "light": "assets/logos/<logo-light>.png"
  },
  "colors": {
    "bg": "#FFFFFF",
    "ink": "#111111",
    "accent": "#FF5500",
    "accent-soft": "#FFD9C7",
    "rule": "#E5E5E5",
    "muted": "#6B6B6B",
    "shadow": "#000000"
  },
  "fonts": {
    "display": "<display font name>",
    "caption": "<caption font name>"
  },
  "font_files": {
    "display": ["assets/fonts/<display file>"],
    "caption": ["assets/fonts/<caption file>"]
  },
  "speaker": {"name": "<name>", "role": "<role>"},
  "hook_default": null,
  "mishears": {"<heard lowercase>": "<Correct>"}
}
```
