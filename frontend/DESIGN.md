# PitchSwitch — design system

The app and the landing page (`/about`, `public/about.html`, built with the taste skill) share one look.
The landing page is the reference; the app takes its tokens in `app/globals.css`.

## Colour

| Token | Value | Role |
| --- | --- | --- |
| `--background` | `#f7f9fa` | Page ground |
| `--foreground` / `--press` | `#1f3038` | Slate ink: text, dark panels (Skip roll call, Conflict verdict), footer |
| `--slate` | `#2c3c44` | Hairlines on dark |
| `--muted` | `#5d6b72` | Helper text (5.4:1 on the ground) |
| `--sage` | `#c3ccd0` | Text on dark |
| `--line` / `--surface` | `#dde3e6` / `#ecf0f2` | Hairlines; tinted rows and tracks |
| `--accent` | `#0d7480` | Teal: the primary button, active nav, score bars and numbers. White text on it |
| `--echo` / `--moss` | `#d7ecee` / `#9fc7cc` | Pale teal: citations, "you", primary sources |
| `--control` | `#7d8a90` | Input outlines (3.4:1) |

One accent, never violet. Source reliability shows by weight (teal tint → ink outline → faint → dashed), not hue.

## Type

Instrument Sans everywhere (`display`: 500, 96% width, -0.032em, line-height 1); DM Mono for source
publishers and dates. Labels (`label`) are sentence case, 13px / 500.

## Shapes and parts

- `window`: white, 1px ink/12% hairline, 14px corners, a long soft shadow. Cards, forms and the brief sit in one.
- `lit-ground`: the landing page's teal-lit gradient, 20px corners, behind a form window (home, Slush prep)
  and the closing call to action.
- Dark panels: `bg-press`, 20px corners, for the conflict verdicts.
- `btn-primary`: teal pill with a chevron that steps 3px on hover, presses on click. `btn-ghost`: tinted pill.
- Page labels: a white pill with a hairline ("Founder report", "Investor check", "Slush prep").
- Header: arc mark + name, links, "Run a check"; footer: dark, mark, one line, links.
