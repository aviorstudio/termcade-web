// @ts-check
import { defineConfig } from 'astro/config';

// No integrations. The site is one static page that ships no JavaScript, so
// there is no framework runtime to add and nothing to hydrate. The arcade and
// its registry are the application; this is only the front door.
// https://astro.build/config
export default defineConfig({});
