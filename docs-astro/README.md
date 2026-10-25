# PressHaven — Knowledge Hub

The Astro site in this directory is the documentation hub for PressHaven.
It documents the architecture, detection pipeline, honeypot engine, observability stack,
operations and testing strategy of the project in `../`.

Repository: <https://github.com/presshaven/presshaven>

## Commands

```bash
npm install
npm run dev       # local dev server
npm run build     # static output in dist/
npm run preview   # preview the production build
```

## Structure

```text
src/
  components/     Icon, DocCard and CardGrid used across docs pages
  layouts/        Layout.astro (hub) and DocsLayout.astro (documentation shell)
  pages/          Homepage, docs routes and the quick reference page
  styles/         global.css — design tokens, docs prose, cards, diagrams
public/           favicon assets
```

Documentation pages are plain `.astro` files under `src/pages/docs/`. Use `DocCard` and
`CardGrid` for navigation or summary blocks inside a page. Inline SVG graphics use
`currentColor` or the shared `diagram-*` classes in `global.css`, so they follow the theme
without hard-coded colours.

## Conventions

- Keep the existing grayscale + neon green palette; do not introduce new colour families.
- Prefer existing tokens (`var(--color-accent-green)`, `var(--color-border)`, …) over hex values.
- Documentation cards belong inside `.md-typeset` pages and should link to a real page.
- Site-wide links to the source repository point at `https://github.com/presshaven/presshaven`.
