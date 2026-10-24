// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  integrations: [mdx()],
  vite: {
    plugins: [tailwindcss()],
  },
  // Keep HTML whitespace as authored. With compressHTML (the default) Astro
  // strips the whitespace between a text node and an adjacent inline element
  // when they sit on separate source lines, so prose like `word\n<strong>…`
  // renders as `word<strong>…` with the words joined. Disabling it lets the
  // browser collapse that whitespace to a single space, as normal HTML.
  compressHTML: false,
  site: 'https://honeypot-ids.local',
});