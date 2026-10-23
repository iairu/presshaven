# Product

<!-- impeccable:product-schema 1 -->

<!-- Fast init from accumulated project context (user-approved, this session). Product truth is drawn from the repository and prior work; no interview round was run. -->

## Platform

web

## Users

Primary: the thesis author and their evaluators/committee reading the work, plus security-minded engineers and students who want to understand how a high-interaction WordPress honeypot IDS is built and operated. They arrive to *understand* a system — its request pipeline, detection scoring, honeypot pooling, observability, and operational runbooks — not to buy anything. Reading happens at a desktop, often alongside the source repository.

## Product Purpose

The site is the **documentation / knowledge hub** for the Honeypot IDS system (a FIIT STU master's thesis project). It explains a real deployment: an OpenResty (nginx + Lua) reverse proxy that scores HTTP requests 0–100 and diverts suspicious sessions into per-session WordPress/WooCommerce honeypot pools, with Suricata network IDS, a SIEM pipeline (Vector → Elasticsearch → Kibana), and a PyQt6 operator dashboard. Success is a reader being able to learn every major capability and find the exact module, flag, or measured figure behind it.

## Positioning

Not marketing for a product — it is the authoritative, source-grounded record of one specific system. Its credibility comes from tracing every claim to a real file, flag, or measured report figure (e.g. segmentation verdicts, detection rates, measured decay half-life). The voice is an engineering reference, not a pitch.

## Operating Context

- Static site built with **Astro 7 + Tailwind 4 (Vite plugin)**; client-side search over a hardcoded page index in `Layout.astro`, plus Pagefind. `npm run dev` / `npm run build`.
- Content is authored as `.astro` pages under `src/pages/docs/**`, rendered through `DocsLayout.astro` (a Material-style doc shell: top header, section tabs, left section sidebar, right table-of-contents) and `Layout.astro`.
- Data-driven navigation: `docsOrder` + `tabs` arrays and a hardcoded search `pages` array; each page declares its own `sidebar` and `toc` in frontmatter.
- Companion surfaces that are **not** this site: the PyQt6 operator dashboard and its in-app Knowledge Base.

## Capabilities and Constraints

- Sections: Getting Started, Architecture, Honeypot Engine (+ Layers), Detection (Capabilities, CVEs, Suricata, Patterns, Advanced, Device/GDPR Signature), Observability (SIEM, Kibana), Operations (single/two-host, hardening, runbooks), Testing (+ blind pentest), Reference (glossary, known issues, roadmap, changelog, literature).
- Reusable components: `DocsLayout`, `CardGrid`, `DocCard`, `Icon`; admonition callouts; tables; code panels; inline SVG diagrams sharing a `diagram-*` class vocabulary.
- Terminology to preserve exactly: honeypot pool, per-session segmentation, pool autoscaling, honeypot layer (reverse-proxy vs database), device/GDPR signature, honeytoken, escalation-aware decay, sophistication classification.
- Constraint: every figure must be traceable to source or a cited report; no fabricated numbers, customers, or benchmarks.

## Brand Commitments

- Name: **Honeypot IDS** — Knowledge Hub (v2.0). Brand mark is a monospace `>` prompt glyph before the name.
- Repo link is always `https://github.com/iairu/honeypot-ids`.
- Binding visual constraint carried through the whole site: a **grayscale + single neon-green accent** palette, expressed only through CSS custom-property tokens (no raw hex in page markup). Mono type (JetBrains Mono) for labels/metadata, Inter for prose. This is an established, deliberate identity — preserve it.
- Footer identifies it as a FIIT STU master's thesis project.

## Evidence on Hand

- Real source tree at repo root (`ids/`, `dashboard/`, `patterns/`), cited throughout the docs.
- Measured figures already surfaced in docs from PDF reports under `reports/` (segmentation EXCLUSIVE verdicts, exploit detection rates, measured ~529 s decay half-life, ~420–430 MB per-pool memory). These are real measurements — do not invent new ones.
- No testimonials, pricing, customers, or deployment claims exist and none may be fabricated.

## Product Principles

1. **Source-grounded or it doesn't ship.** Every capability names its module/flag; every number traces to source or a cited report.
2. **Teach the mechanism, not the marketing.** The reader leaves able to find and change the real thing.
3. **One identity, everywhere.** Grayscale + neon-green, token-only, mono-for-signal — consistency is the credibility.
4. **Structure for comprehension first.** Clear hierarchy, scannable tables, honest "Known Issues / Honest Assessment" sections over polish.

## Accessibility & Inclusion

Dark-theme reference site. Maintain legible contrast for body text (`--color-text-secondary` on dark surfaces), keep the neon-green accent for emphasis/links rather than large body text, preserve visible `:focus-visible` outlines, and keep tables and diagrams readable at phone width.
