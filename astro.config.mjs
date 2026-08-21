// @ts-check
import { defineConfig } from 'astro/config';

// No integrations. The site is one static page that ships no JavaScript, so
// there is no framework runtime to add and nothing to hydrate. The arcade and
// its registry are the application; this is only the front door.
//
// `site` is the one place the host is configured. The apex termca.de redirects
// 308 to www in the Vercel project settings, so the canonical URL is www.
// Everything on the page that names the host — canonical link, og:url, and
// the SoftwareApplication JSON-LD — derives from Astro.site; robots.txt and
// sitemap.xml live in public/, are copied as-is, and carry the host literally.
// https://astro.build/config
export default defineConfig({
	site: 'https://www.termca.de',
});
