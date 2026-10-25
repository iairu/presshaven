---
name: PressHaven Knowledge Hub
description: Grayscale terminal reference with a single neon-green signal accent
colors:
  bg-primary: "#080808"
  bg-secondary: "#0f0f0f"
  bg-tertiary: "#161616"
  bg-card: "#121212"
  bg-card-hover: "#1a1a1a"
  border: "#222222"
  border-accent: "#333333"
  text-primary: "#f0f0f0"
  text-secondary: "#999999"
  text-muted: "#555555"
  accent-green: "#00ff41"
  accent-green-dim: "#00cc33"
  accent-green-hover: "#33ff66"
typography:
  display:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "clamp(2.7rem, 5.1vw, 4.6rem)"
    fontWeight: 800
    lineHeight: 1.01
    letterSpacing: "-0.045em"
  h1:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "1.9rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.03em"
  h2:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "1.32rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "0.94rem"
    fontWeight: 400
    lineHeight: 1.78
  label:
    fontFamily: "JetBrains Mono, Fira Code, monospace"
    fontSize: "0.68rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.08em"
rounded:
  none: "0px"
spacing:
  xs: "0.4rem"
  sm: "0.65rem"
  md: "1rem"
  lg: "1.4rem"
  xl: "2.5rem"
components:
  button-primary:
    backgroundColor: "{colors.accent-green}"
    textColor: "{colors.bg-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.62rem 1.55rem"
  button-primary-hover:
    backgroundColor: "{colors.accent-green-hover}"
    textColor: "{colors.bg-primary}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.none}"
    padding: "0.62rem 1.55rem"
  card:
    backgroundColor: "{colors.bg-secondary}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.none}"
    padding: "1.4rem 1.5rem"
  doc-card:
    backgroundColor: "{colors.bg-secondary}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.none}"
    padding: "1rem 1.05rem"
  admonition:
    backgroundColor: "{colors.bg-card}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.none}"
    padding: "0.9rem 1.1rem"
---

# Design System: PressHaven Knowledge Hub

## Overview

**Creative North Star: "The Operator's Terminal"**

This is a dark, instrument-panel reference built for people who read documentation the way they read a console: scanning for the exact signal in a field of calm gray. The world is almost entirely grayscale — near-black surfaces stepped in four shades, hairline borders — and a single **neon green (#00ff41)** does all the signalling. Green is never decoration; it marks the live thing: a link, a matched term, a metric, an active nav item, the leading edge of a scan line. Its scarcity is the entire point. The surface carries quiet machine texture (a 64px grid, a faint top-centre green radial bloom) so the page reads as a screen, not paper.

Typography splits labor cleanly: **Inter** carries prose and headings with tight negative tracking at the large sizes; **JetBrains Mono** carries every machine signal — eyebrows, table headers, metadata, badges, code, diagram text — in uppercase with wide tracking. If a label is monospace and uppercase, it is telling you "this is data." Corners are square everywhere (0px radius); depth is conveyed by borders, tonal layering, and one accent-tinted shadow on hover, not by rounded cards.

The rhetoric is confident and dense without being loud: justified body prose framed by two faint vertical rules, tables with mono green headers, admonitions with a green left-rule and a hairline green gradient across the top. The reading experience should feel like a well-instrumented control room — everything legible, nothing shouting, and the one green thing on the screen is always the thing that matters.

**Key Characteristics:**
- Four-step near-black grayscale surface ramp (#080808 → #1a1a1a) with #222/#333 hairline borders.
- Exactly one accent hue: neon green #00ff41, used on ≤10% of any screen.
- Square corners everywhere; depth from borders + tonal layering, not radius.
- Inter for prose, JetBrains Mono (uppercase, tracked) for every machine/data signal.
- Ambient machine texture: 64px grid, faint green radial bloom, scan-line and radar motifs.

## Colors

A grayscale instrument palette with a single high-voltage accent. Everything structural is gray; green is reserved for live signal.

### Primary
- **Neon Green** (#00ff41): The one voice. Links, active nav (left/bottom/underline rules), table headers, metric numbers, badges, diagram accents, button fills, the eyebrow pulse dot, scan lines. Supported by **Green Dim** (#00cc33) and **Green Hover** (#33ff66) for state, plus low-alpha green washes (`rgba(0,255,65,0.06–0.12)`) for subtle fills/glows.

### Neutral
- **BG Primary** (#080808): Page background; the darkest field.
- **BG Secondary** (#0f0f0f): Sidebars, tables, cards, panels, footer.
- **BG Tertiary** (#161616): Inset chips, icon tiles, code inline background, hover wells.
- **BG Card / Card Hover** (#121212 / #1a1a1a): Admonition and card surfaces, lifted on hover.
- **Border / Border Accent** (#222222 / #333333): Hairline dividers and the stronger framing rules.
- **Text Primary** (#f0f0f0): Headings, strong text, emphasized values.
- **Text Secondary** (#999999): Body copy.
- **Text Muted** (#555555): Metadata, captions, mono labels, breadcrumbs, table cell default.

### Named Rules
**The One Voice Rule.** Green appears on ≤10% of any screen and only to mark a live signal (link, metric, active state, accent edge). If green is being used to decorate, it is wrong — reach for a gray step instead.
**The No Second Hue Rule.** There is no blue, amber, or red in the system. Severity and state are expressed through green vs. gray steps (e.g. warning admonitions use a light-gray #d4d4d4 rule, never orange).

## Typography

**Display / Body Font:** Inter (with system-ui, -apple-system, sans-serif)
**Label / Mono Font:** JetBrains Mono (with Fira Code, monospace)

**Character:** Inter runs tight and modern — large headings pull in to −0.03…−0.045em so they read as set type, not default sans. JetBrains Mono is the system's "data voice": wherever information is machine-emitted (labels, table headers, metadata, code, diagram text, badges), it is mono, uppercase, and widely tracked. The contrast between the two is the hierarchy.

### Hierarchy
- **Display** (800, clamp(2.7rem, 5.1vw, 4.6rem), 1.01): Home-hero headline only.
- **Doc H1** (700, 1.9rem, 1.15, −0.03em): Page title in the doc header.
- **H2** (600, 1.32rem, −0.015em): Section headings; mono eyebrow often sits above.
- **H3** (600, 1.06rem): Sub-sections.
- **H4** (600, 0.94rem, uppercase, 0.05em tracking): Minor labels inside prose.
- **Body** (400, 0.94rem, 1.78, justified with hyphens): Doc prose. Headings and list items stay left-aligned.
- **Label / Mono** (500–700, 0.6–0.68rem, uppercase, 0.08–0.12em tracking): Eyebrows, table headers, metadata, badges, nav section titles.

### Named Rules
**The Mono-Means-Data Rule.** If text is monospace and uppercase, it is a machine signal (label, metric, header, code), never prose. Never set a sentence in mono.
**The Justified-Body Rule.** Doc body paragraphs are justified with `hyphens: auto`; headings, list items, and cards opt back to left alignment.

## Layout

A three-column documentation shell inside an 82rem max frame: a 13rem left section-sidebar (sticky), a centered content column (max 49rem) framed by two faint vertical gradient rules, and a 13rem right table-of-contents (sticky). Two sticky headers stack above: a 3.25rem top bar (brand + ⌘K search + primary nav) and a 2.4rem section-tabs strip. Below 900px the card grids collapse toward two columns; below 620px to one. The home page breaks to a two-column hero (copy + console mock) over the same frame. Spacing rhythm is tight and consistent: ~1rem between paragraphs, ~2.1rem above H2s, 0.55rem table cell padding. Section headings often carry a trailing hairline gradient rule or a mono eyebrow with a short green tick.

## Elevation & Depth

Flat by default. Depth comes from the tonal surface ramp and hairline borders, not ambient shadow. Shadows appear only on interaction and only on lifted elements (cards, buttons, search modal), and the accent shadow is green-tinted.

### Shadow Vocabulary
- **Card hover** (`box-shadow: 0 6px 26px rgba(0,0,0,0.45)` + `translateY(-2px)`): Cards/doc-cards rise slightly on hover with a darkening ambient shadow.
- **Primary button hover** (`box-shadow: 0 6px 22px rgba(0,255,65,0.22)`): The one green-tinted glow, for the primary action only.
- **Search modal** (`box-shadow: 0 24px 80px rgba(0,0,0,0.7)`): Deep lift for the overlay panel.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest; borders and tonal steps carry structure. A shadow is a response to state (hover, overlay), never a resting decoration.

## Shapes

Square everywhere — 0px radius on cards, buttons, inputs, badges, panels, chips. The one deliberate non-rectilinear form is the **sheared button**: primary/footer-nav buttons use `clip-path: polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%)` for a parallelogram shear that reads as "terminal action." Borders are 1px hairlines; accent edges are 1–2px green left/top rules. Recurring geometry: a 1px green-to-transparent gradient bar across the top of cards/panels/admonitions on hover or at rest, and `diagram-*` SVG primitives (frame/panel/node/line/arrow) sharing the same token colors.

## Components

### Buttons
- **Shape:** Square base; primary/`btn-sheared` variants carry a 10px parallelogram shear via clip-path.
- **Primary:** Neon-green fill, near-black text, JetBrains Mono 700, 0.62rem 1.55rem padding.
- **Hover / Focus:** Fill shifts to #33ff66, `translateY(-1px)`, green-tinted shadow. `:focus-visible` is a 2px green outline with 2px offset (global).
- **Secondary:** Transparent with a border-accent stroke; on hover the border turns green with a faint green-subtle wash.
- **Ghost:** Transparent with a muted border; hover lifts to tertiary surface, no glow.

### Cards / Containers
- **Corner Style:** Square (0px).
- **Background:** BG Secondary at rest → BG Card Hover on hover.
- **Shadow Strategy:** Flat at rest; on hover `translateY(-2px)` + `0 6px 26px rgba(0,0,0,0.45)` and a green gradient top-edge fades in.
- **Border:** 1px #222; strengthens to #333 on hover.
- **Internal Padding:** 1.4rem 1.5rem (`.card`) / 1rem 1.05rem (`.doc-card`).
- **DocCard:** Icon tile (2.15rem, green glyph on tertiary surface) + mono tag + title + description + mono meta; link variant adds a nudging arrow.

### Admonitions / Callouts
- **Style:** BG Card surface, 1px border with a 2px green left-rule, a faint green→transparent 1px gradient across the top. Title is JetBrains Mono, uppercase, green, 0.68rem.
- **Variants:** `note` (gray-secondary rule), `warning` (light-gray #d4d4d4 rule — never amber), `tip`/`info` (green rule). Severity is a gray step, not a new hue.

### Tables
- **Style:** Full-width, BG Secondary, 1px border, 0.82rem. Header row is BG Tertiary with **green JetBrains Mono uppercase** labels, 0.68rem, tracked.
- **State:** Row hover fills BG Card Hover; last row drops its bottom border.

### Inputs / Fields
- **Style:** The search trigger is a full-width BG-Primary button with a 1px border, muted label, and a mono ⌘K kbd chip; opening it reveals a BG-Secondary modal with a transparent text input.
- **Focus:** Border shifts to border-accent on hover; results get a green left-rule when selected/hovered.

### Navigation
- **Top header:** Sticky, translucent (`rgba(15,15,15,0.96)` + blur). Brand = mono green `>` prompt + name + mono version chip. Primary links are small gray; active link turns green with a green-subtle wash and green border.
- **Section tabs:** Sticky mono-ish strip; active tab turns green with a green bottom-border.
- **Section sidebar (left):** Mono uppercase section title; links are 0.78rem gray with a transparent left-rule that turns green + fills green-subtle when active.
- **ToC (right):** Secondary nav with a left divider; muted links, active link green, level-3 indented and smaller.

### Signature Components
- **Framed content column:** Two faint vertical gradient rules bracket the centered prose column — the visual spine of every doc page.
- **Home console / radar:** A terminal-style console mock with a traffic-light bar, an animated scan line, an SVG radar sweep, and mono "event rows" with green score chips — the hero's instrument motif.

## Do's and Don'ts

### Do:
- **Do** express every token through the CSS custom properties in `global.css` (`var(--color-accent-green)`, `var(--color-bg-secondary)`, …); add new tokens there rather than inlining hex.
- **Do** keep green scarce — links, active states, metrics, and one accent edge per element.
- **Do** set every machine signal (labels, table headers, metadata, badges, code, diagram text) in JetBrains Mono, uppercase, tracked.
- **Do** keep corners square; use the 10px clip-path shear only for primary/footer-nav buttons.
- **Do** convey depth with borders + tonal steps; add shadow only on hover/overlay.

### Don't:
- **Don't** introduce a second accent hue. Severity and state use gray steps and the light-gray #d4d4d4 warning rule, never amber/red/blue.
- **Don't** put raw hex in page markup — tokens only.
- **Don't** round corners or add resting drop-shadows to cards.
- **Don't** set body sentences in monospace, or large body text in neon green (contrast + the One Voice Rule).
- **Don't** fabricate figures; every number traces to source or a cited report (a product-truth rule that also governs visual data like stat tiles).
