---
# gstack: design-md-format=spec
name: decider-ai
description: A utilitarian field manual for a private decision model. Plain, precise, real commands and real numbers, nothing staged.
colors:
  ground: "#F5F6F4"
  surface: "#FFFFFF"
  code: "#EBF2EE"
  text: "#15201B"
  text-muted: "#55615B"
  line: "#D9DED9"
  primary: "#12704F"
  primary-hover: "#0D5A3F"
  on-primary: "#FFFFFF"
  tint: "#E3EFE9"
  series-local: "#16875C"
  series-baseline: "#4C6FB0"
  warning: "#9A6200"
  warning-tint: "#F6ECDA"
  error: "#B42318"
  error-tint: "#F9E3E1"
  dark-ground: "#0F1512"
  dark-surface: "#161E1A"
  dark-code: "#1A201D"
  dark-text: "#E6ECE8"
  dark-text-muted: "#A9B6AF"
  dark-line: "#3A4740"
  dark-primary: "#4FBF8F"
  dark-primary-hover: "#6FD3A6"
  dark-on-primary: "#0B1410"
  dark-tint: "#1D3D30"
  dark-series-local: "#33A070"
  dark-series-baseline: "#7E8FD6"
  dark-warning: "#E0A23A"
  dark-warning-tint: "#3A2C10"
  dark-error: "#F0706A"
  dark-error-tint: "#3A1A18"
typography:
  display:
    fontFamily: Archivo
    fontWeight: 700
    fontSize: clamp(2rem, 1.4rem + 2.6vw, 3.25rem)
    letterSpacing: 0em
  h2:
    fontFamily: Archivo
    fontWeight: 700
    fontSize: 1.75rem
  h3:
    fontFamily: Archivo
    fontWeight: 700
    fontSize: 1.25rem
  reading:
    fontFamily: Libron
    fontSize: 1.125rem
    lineHeight: 1.6
  body:
    fontFamily: Source Sans 3
    fontSize: 1.0625rem
    lineHeight: 1.6
  label:
    fontFamily: Source Sans 3
    fontWeight: 600
    fontSize: 0.9375rem
    letterSpacing: 0em
  mono:
    fontFamily: JetBrains Mono
    fontSize: 0.875rem
    fontFeature: tnum
rounded:
  sm: 4px
  md: 6px
  lg: 10px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  3xl: 64px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    borderColor: "{colors.line}"
    rounded: "{rounded.md}"
  button-secondary-hover:
    backgroundColor: "{colors.tint}"
  input:
    borderColor: "{colors.line}"
    rounded: "{rounded.sm}"
  code-block:
    backgroundColor: "{colors.code}"
    borderColor: "{colors.line}"
    rounded: "{rounded.lg}"
  card:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.line}"
    rounded: "{rounded.lg}"
  callout-info:
    backgroundColor: "{colors.tint}"
    rounded: "{rounded.md}"
  callout-warning:
    backgroundColor: "{colors.warning-tint}"
    rounded: "{rounded.md}"
  callout-error:
    backgroundColor: "{colors.error-tint}"
    rounded: "{rounded.md}"
  nav-link:
    textColor: "{colors.text-muted}"
  nav-link-active:
    textColor: "{colors.text}"
    backgroundColor: "{colors.tint}"
---

# decider-ai

## Overview

**Creative North Star:** a utilitarian field manual. The product's own commands, output and measured uncertainty are the only imagery, because the promise is "running in five minutes, your data never leaves, measured not claimed", in that order.
**Product context:** open-source, self-hosted decision endpoint (one Docker container) that routes messages with a private model and learns from corrections. Readers: developers setting it up, and privacy-bound German SMB staff (law firms first) judging whether to trust it.
**Mode per surface:**
- Landing page: Persuade, through proof rather than claims.
- Docs and tutorial: Read.
- Eval report: Read, and printed.
- A later studio UI: Operate.

**Reference sites:** none; research was skipped by choice.
**Key characteristics:**
- The first screen is a real command transcript and its JSON reply, not a headline beside a screenshot.
- Deep green on pale grey; one accent, used sparingly.
- Calm serif for paragraphs, sturdy grotesk for headings, sans for anything you click or scan.
- Every metric carries its interval; no naked numbers.
- Light code blocks: docs read as one surface and print cleanly.

## Colors

**Strategy:** restrained. One accent plus neutrals derived from it (greys carry a slight green tint).
**Light or dark:** light is the designed default, because office staff read on bright screens and reports get printed. Dark is first-class, follows `prefers-color-scheme`, and uses its own `dark-*` tokens. Those are separate steps, not an inversion.

- **Primary** marks interaction (links, primary buttons, focus ring) and the "running / ready" state. Never use it for decoration.
- **Tint** is the quiet surface for the active nav item, info callouts and hover.
- **Warning and error** are reserved for status. They always come with an icon and words, never color alone, and never serve as a chart series.
- **Chart series:** the local model is `series-local` (green) and the LLM baseline is `series-baseline` (slate blue). The pair passed the dataviz validator (lightness, chroma, CVD separation, normal-vision floor, contrast) in both themes. Intervals draw the series color at about 50% opacity (62% in dark). A difference between two models is not a series: draw it in `text` at low opacity.
- Text never wears a series color; values and labels stay in `text` / `text-muted`.

## Typography

- **Archivo** (Google Fonts, OFL) for headings h1 to h4.
  - Settings: weight 700, `font-stretch: 90%`, `word-spacing: 0.12em`, `text-wrap: balance`.
  - The word spacing is required. At narrow widths Archivo's space collapses and headings read as typos.
  - It's a sturdy industrial grotesk; the slight condensing fits German compound words.
- **Libron** (OFL, self-hosted) for reading text.
  - Used for paragraphs in docs and the tutorial, intro and lede text, callout text, the report's methodology line and verdicts.
  - Size 1.125rem / 1.6, `text-wrap: pretty`.
  - It's a calm e-reader serif and does the "manual" part of the voice.
  - Source: `nicoverbruggen/libron` release v0.30, `Libron_Web.zip` (WOFF2: Regular, Italic, Bold, BoldItalic). It's derived from Newsreader, which is too common as a display face, so Libron is never used for headings.
- **Source Sans 3** (Google Fonts, OFL) for UI text: nav, tables, labels, buttons, form fields, figure captions, chart text. Body size 1.0625rem.
- **JetBrains Mono** (Google Fonts, OFL) only for code, commands, JSON, IDs and table numerals (`tabular-nums`). Never use it as decoration or for labels.
- **Scale:** 52 / 28 / 20 / 17px for headings and body. Levels differ in size, not just weight.
- **Case:** sentence case everywhere. No uppercase eyebrows, no tracked caps, no kicker labels above headings.
- **Loading:** Google Fonts `css2` with `display=swap` for Archivo (`wdth,wght@62..125,100..900`), Source Sans 3 and JetBrains Mono. Libron uses `@font-face` from self-hosted WOFF2 files.

## Layout

- **Docs:** left nav (about 210px), a reading column of at most 70ch, and a right "on this page" list (about 190px).
  - At 960px and below, the right list is hidden and the nav becomes a wrapped row above the content.
- **Landing:** a single column of at most 880px. Hero text and the transcript share that width.
- **Report:** a single column of full-width cards. Charts that compare the same metric share one card and one left edge.
- **Spacing:** 4px base, comfortable density. Use 64px between page sections, 24px inside cards, 16px between paragraphs.
- **Gutters:** 16px side gutter on phones, and no horizontal page scroll. Code blocks may scroll sideways; commands are never wrapped mid-token.

## Elevation & Depth

- Use only the three layered shadow tokens. Each is an inset top highlight, a dark drop and a soft drop.
  - `--shadow-s`: inset 0 1px 2px #ffffff30, 0 1px 2px #00000030, 0 2px 4px #00000015
  - `--shadow-m`: inset 0 1px 2px #ffffff50, 0 2px 4px #00000030, 0 4px 8px #00000015
  - `--shadow-l`: inset 0 1px 2px #ffffff70, 0 4px 6px #00000030, 0 6px 10px #00000015
- Uses:
  - Cards and the primary button use `s`.
  - Primary hover and tooltips use `m`.
  - `l` is reserved for overlays.
- Never use flat single-layer shadows or zero-offset glows.

## Shapes

- Radii are 4px (inputs, small chips), 6px (buttons, callouts, nav items) and 10px (cards, code blocks).
- A nested element's radius is the outer radius minus the gap.
- No pills, no fully rounded buttons.

## Components

Every button and link gets `cursor: pointer`, a hover state, and a 2px primary `:focus-visible` outline.

- **Primary button:** primary background with on-primary text, `shadow-s`. Hover uses primary-hover and `shadow-m`. Pressed moves down 1px. Disabled uses the ground background, muted text and a line-colored border, with no shadow.
- **Secondary button:** surface background, line-colored border, no shadow. Hover uses the tint.
- **Code block:** code background, line border, 10px radius, 96px right padding reserved for the Copy button. Copy confirms with "✓ Copied" for 1.4s.
  - Commands start with a primary-colored `$` that can't be selected; output and comments are muted.
  - Command and response go in separate blocks. The response block gets a "Response" caption and no Copy button.
- **Callout:** tinted background, an icon and plain text. Variants are info (tint), warning (warning-tint) and error (error-tint). No colored side border.
- **Interval chart:** a point estimate (7px dot with a 2px surface ring) on an interval bar (14px tall, nearly square ends). The value label sits above its dot.
  - Gridlines are recessive (line color).
  - The margin or threshold is a dashed `warning` line with a label.
  - Every chart has a hover tooltip and an `aria-label` with the numbers.
- **Line chart:** 2px lines, ≥8px markers with surface rings, and a seed or uncertainty band at reduced opacity. End labels sit right of the last point. Legend glyphs match the marks (line plus band, dashed line).
- **Table:** Source Sans headers, Mono numerals right-aligned, row rules only, first column flush with the card heading.
- **States:** each component designs its empty, loading, error and long-content states. For example, the "No trained model for `urgency` yet" error callout states the next action.

## Do's and Don'ts

- Do show the real command and its real output wherever a claim could go.
- Do draw every metric with its interval and name the sample size.
- Do state what the user can do next in error and empty states.
- Do keep retrain and activation as explicit user actions in all copy. Nothing in the UI implies the model updates itself.
- Do check pages with the lab probes: heading word space ≥ 0.25em, chart text ≥ 11px, no clipped chart labels, no page overflow, no oversized icons.
- Don't put Libron on buttons, nav, tables or headings, or Mono on labels or headings.
- Don't use eyebrow labels, pills, badges, icon tiles above headings, or 3-column feature grids.
- Don't show big naked numbers ("95% accurate"), testimonial rows, or logo strips.
- Don't use dark code slabs on light pages, gradients, glows or decorative illustration.
- Don't add diagnostic or bookkeeping copy to the product UI (skip counts, provenance caveats). That belongs in logs.

## Motion

- **Approach:** minimal-functional.
- **Easing:** enter ease-out, exit ease-in, move ease-in-out.
- **Duration:** micro 100ms, short 150–200ms (hover, theme switch), medium 300ms. Nothing longer.
- **The one authored moment:** the Copy button's "✓ Copied" confirmation on a command block.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-08 | Initial design system created | /design-consultation from the office-hours design doc. Memorable thing, ranked: running in five minutes, data never leaves, measured not claimed, learns from you. |
| 2026-10-08 | Green accent over blue | Chosen in a side-by-side palette lab. Green means "running/ready" and stands apart from blue dev tools. Green/slate chart pair reads as "ours vs the cloud LLM". |
| 2026-10-08 | Libron for reading text | Founder's choice after a current-vs-Libron lab. Serif where people read, sans where people click. |
| 2026-10-08 | Archivo needs word-spacing 0.12em | Independent screenshot review found collapsed word spaces at width 87–90. Enforced by a lab probe. |
| 2026-10-08 | Display face must be OFL | Fontshare's Cabinet Grotesk licence could not be verified, and fonts ship in an open-source repo. |
