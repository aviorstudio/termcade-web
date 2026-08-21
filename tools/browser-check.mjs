// Browser smoke check for the built site. Serves dist/ over a throwaway
// local HTTP server, loads the page in headless Chrome at two viewports, and
// fails on anything a visitor would notice:
//
//   - console errors, uncaught exceptions, failed requests, HTTP >= 400
//     responses (tolerance: zero, at either viewport)
//   - missing document landmarks: exactly one <h1>, a <header>, <main> and
//     <footer>, html[lang], a title and a meta description
//   - inaccessible content: every link and every unhidden <svg>/<img> has a
//     non-empty COMPUTED accessible name, read from Chrome's accessibility
//     tree (CDP Accessibility.getFullAXTree) rather than from raw markup --
//     an empty aria-label, an aria-labelledby pointing nowhere, or text
//     hidden with display:none all compute to an empty name, and raw
//     attribute checks wave them through. Decorative SVGs carry aria-hidden
//     and never reach the tree. There are no raster images on the page, so
//     no alt rule binds. The terminal frames are text by design -- selectable
//     and readable as text, which is the point of them -- so no label
//     assertion binds to them either; a previous version asserted aria-labels
//     on their plain <div> wrappers, which assistive technology ignores on
//     role-less elements, and the assertion was removed rather than kept as
//     theatre.
//   - horizontal overflow: no page-level horizontal scrollbar, and no
//     top-level section extending past the viewport edge
//   - broken links: every internal href returns 200 from the built site, and
//     every external href answers 200 within LINK_TIMEOUT_MS
//
// Parameters, deliberately written down rather than implied:
//
//   viewports      1280x800 (desktop) and 390x844 (mobile, touch + isMobile)
//   link timeout   10000ms per external link, one attempt, redirects followed
//   accessibility  the landmark assertions above, plus a non-empty computed
//                  accessible name for every link and unhidden SVG/image,
//                  taken from the browser accessibility tree at each viewport
//
// Usage: node tools/browser-check.mjs dist
import { chromium } from 'playwright-core';
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

const VIEWPORTS = [
	{ name: 'desktop', width: 1280, height: 800 },
	{ name: 'mobile', width: 390, height: 844, isMobile: true, hasTouch: true },
];
const LINK_TIMEOUT_MS = 10_000;
// The top-level layout containers: if any of these is wider than the
// viewport, the layout is broken no matter what clips it.
const SECTIONS = ['.site-header', '.hero', '.games', '.pixels', '.principles', '.arcade', '.sdk', '.closing', 'footer'];

const TYPES = {
	'.html': 'text/html; charset=utf-8',
	'.css': 'text/css; charset=utf-8',
	'.svg': 'image/svg+xml',
	'.txt': 'text/plain; charset=utf-8',
	'.xml': 'application/xml; charset=utf-8',
};

function serve(root) {
	const server = http.createServer(async (req, res) => {
		const url = new URL(req.url, 'http://localhost');
		const file = path.join(root, url.pathname === '/' ? 'index.html' : url.pathname);
		try {
			const body = await readFile(file);
			res.writeHead(200, { 'content-type': TYPES[path.extname(file)] ?? 'application/octet-stream' });
			res.end(body);
		} catch {
			res.writeHead(404);
			res.end('not found');
		}
	});
	return new Promise((resolve) => {
		server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }));
	});
}

async function launch() {
	try {
		// CI runners and most dev machines already have Chrome; using it keeps
		// the check free of a browser download.
		return await chromium.launch({ channel: 'chrome' });
	} catch {
		// Fall back to a playwright-managed chromium if one is installed.
		return await chromium.launch();
	}
}

const failures = [];
const fail = (what) => failures.push(what);

async function checkAccessibleNames(context, page, tag) {
	// The browser's own accessibility tree, not the markup: names here are
	// what assistive technology computes, after aria-label/aria-labelledby
	// resolution, display:none, and every other rule of the accName spec.
	const session = await context.newCDPSession(page);
	await session.send('Accessibility.enable');
	const { nodes } = await session.send('Accessibility.getFullAXTree');
	const live = nodes.filter((n) => !n.ignored);
	const describe = async (n) => {
		try {
			const { node } = await session.send('DOM.describeNode', { backendNodeId: n.backendDOMNodeId });
			const attrs = [];
			for (let i = 0; i < node.attributes.length; i += 2) {
				attrs.push(`${node.attributes[i]}="${node.attributes[i + 1]}"`);
			}
			return `<${node.nodeName.toLowerCase()} ${attrs.join(' ')}>`;
		} catch {
			return `<${n.role?.value ?? '?'}>`;
		}
	};
	for (const [role, what] of [
		['link', 'link with an empty computed accessible name'],
		['image', 'unhidden svg or image with an empty computed accessible name'],
	]) {
		const bad = live.filter((n) => n.role?.value === role && !(n.name?.value ?? '').trim());
		for (const n of bad.slice(0, 3)) fail(`${tag} ${what}: ${await describe(n)}`);
		if (bad.length > 3) fail(`${tag} ${bad.length - 3} more ${role} node(s) with empty computed names`);
	}
}

async function checkPage(page, base, viewport) {
	const tag = `[${viewport.name} ${viewport.width}x${viewport.height}]`;
	for (const error of page.consoleErrors) fail(`${tag} console error: ${error}`);
	for (const error of page.pageErrors) fail(`${tag} uncaught exception: ${error}`);
	for (const failure of page.requestFailures) fail(`${tag} request failed: ${failure}`);
	for (const bad of page.badResponses) fail(`${tag} HTTP ${bad}`);

	const doc = await page.evaluate((sections) => {
		const overflowing = sections
			.map((sel) => document.querySelector(sel))
			.filter(Boolean)
			.map((el) => el.getBoundingClientRect())
			.filter((r) => r.left < -1 || r.right > window.innerWidth + 1).length;
		return {
			lang: document.documentElement.lang,
			title: document.title,
			description: document.querySelector('meta[name="description"]')?.content ?? '',
			h1: document.querySelectorAll('h1').length,
			header: document.querySelectorAll('header').length,
			main: document.querySelectorAll('main').length,
			footer: document.querySelectorAll('footer').length,
			horizontalScrollbar: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
			overflowingSections: overflowing,
			hrefs: [...new Set([...document.querySelectorAll('a[href]')].map((a) => a.getAttribute('href')))],
		};
	}, SECTIONS);

	if (doc.lang !== 'en') fail(`${tag} html lang is "${doc.lang}", expected "en"`);
	if (!doc.title) fail(`${tag} no <title>`);
	if (!doc.description) fail(`${tag} no meta description`);
	if (doc.h1 !== 1) fail(`${tag} expected exactly one <h1>, found ${doc.h1}`);
	for (const landmark of ['header', 'main', 'footer']) {
		if (doc[landmark] < 1) fail(`${tag} no <${landmark}> landmark`);
	}
	if (doc.horizontalScrollbar) fail(`${tag} page has a horizontal scrollbar`);
	if (doc.overflowingSections) fail(`${tag} ${doc.overflowingSections} section(s) extend past the viewport`);

	return doc.hrefs;
}

async function checkLinks(hrefs, base) {
	for (const href of hrefs) {
		const url = href.startsWith('http') ? href : new URL(href, base).href;
		try {
			const res = await fetch(url, {
				redirect: 'follow',
				signal: AbortSignal.timeout(LINK_TIMEOUT_MS),
				headers: { 'user-agent': 'termcade-web link check' },
			});
			if (res.status !== 200) fail(`link ${href}: HTTP ${res.status}`);
		} catch (error) {
			fail(`link ${href}: ${error.message} (timeout ${LINK_TIMEOUT_MS}ms)`);
		}
	}
}

async function main() {
	const root = process.argv[2];
	if (!root) {
		console.error('usage: node tools/browser-check.mjs dist');
		process.exit(1);
	}
	const { server, port } = await serve(root);
	const base = `http://127.0.0.1:${port}`;
	const browser = await launch();
	try {
		const allHrefs = new Set();
		for (const viewport of VIEWPORTS) {
			const context = await browser.newContext({
				viewport: { width: viewport.width, height: viewport.height },
				isMobile: viewport.isMobile ?? false,
				hasTouch: viewport.hasTouch ?? false,
			});
			const page = await context.newPage();
			page.consoleErrors = [];
			page.pageErrors = [];
			page.requestFailures = [];
			page.badResponses = [];
			page.on('console', (msg) => msg.type() === 'error' && page.consoleErrors.push(msg.text()));
			page.on('pageerror', (error) => page.pageErrors.push(String(error)));
			page.on('requestfailed', (req) => page.requestFailures.push(`${req.url()} (${req.failure()?.errorText})`));
			page.on('response', (res) => res.status() >= 400 && page.badResponses.push(`${res.status()} ${res.url()}`));
			await page.goto(base + '/', { waitUntil: 'load' });
			const hrefs = await checkPage(page, base, viewport);
			await checkAccessibleNames(context, page, `[${viewport.name} ${viewport.width}x${viewport.height}]`);
			hrefs.forEach((h) => allHrefs.add(h));
			await context.close();
		}
		await checkLinks([...allHrefs], base);
	} finally {
		await browser.close();
		server.close();
	}
	if (failures.length) {
		console.error('browser check failed:');
		for (const f of failures) console.error(`  ${f}`);
		process.exit(1);
	}
	console.log(`browser check passed at ${VIEWPORTS.map((v) => `${v.name} ${v.width}x${v.height}`).join(' and ')}: ` +
		'no console or resource errors, landmarks present, links healthy, no horizontal overflow');
}

main();
