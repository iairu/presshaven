import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * Load the catalogue that both the dashboard and this docs site render.
 *
 * Resolve from the docs-astro package root instead of `import.meta.url`:
 * Vite moves this module into `dist/.prerender/chunks` during the build, so a
 * URL-relative path would point outside the repository.
 */
export function loadPatternCatalog() {
  const path = resolve(process.cwd(), '..', 'patterns', 'patterns.json');
  return JSON.parse(readFileSync(path, 'utf8'));
}
