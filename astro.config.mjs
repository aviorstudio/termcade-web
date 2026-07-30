// @ts-check
import { defineConfig } from 'astro/config';

import qwikdev from '@qwikdev/astro';

import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  integrations: [qwikdev()],

  vite: {
    plugins: [tailwindcss()]
  }
});