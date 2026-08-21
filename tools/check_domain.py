#!/usr/bin/env python3
"""Fail if the built site names any host other than https://www.termca.de.

The marketing domain is termca.de: the apex redirects 308 to www in the Vercel
project settings, so every host claim the build emits must be www.termca.de.
The claims are spread across three files with two mechanisms — the layout
derives canonical/og:url/JSON-LD from `site` in astro.config.mjs, while
robots.txt and sitemap.xml are public/ files copied verbatim — so no single
source file is a complete picture. This gate reads the built output, which is
the only place all of them land together.

Checks, on dist/:

- index.html: exactly one <link rel="canonical"> and one og:url, both
  https://www.termca.de/; the SoftwareApplication entry in the JSON-LD has
  url https://www.termca.de
- robots.txt: the Sitemap line names https://www.termca.de/sitemap.xml
- sitemap.xml: every <loc> names https://www.termca.de/
- no file anywhere in dist/ contains the old host termcade.com

    python3 tools/check_domain.py dist
"""
import json
import pathlib
import sys
from html.parser import HTMLParser

HOST = 'https://www.termca.de'
OLD_HOST = 'termcade.com'


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = []
        self.og_url = []
        self.ld = []
        self._in_ld = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical.append(attrs.get('href', ''))
        elif tag == 'meta' and attrs.get('property') == 'og:url':
            self.og_url.append(attrs.get('content', ''))
        elif tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json':
            self._in_ld = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self._in_ld = False

    def handle_data(self, data):
        if self._in_ld:
            self.ld.append(data)


def software_application_urls(head):
    urls = []
    for blob in head.ld:
        data = json.loads(blob)
        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            if isinstance(entry, dict) and entry.get('@type') == 'SoftwareApplication':
                urls.append(entry.get('url', ''))
    return urls


def main(root):
    bad = []
    root = pathlib.Path(root)
    index = root / 'index.html'
    if not index.is_file():
        sys.exit(f'{root}: no index.html — was the site built?')

    head = Head()
    head.feed(index.read_text())

    for what, got, want in [
        ('<link rel="canonical">', head.canonical, [f'{HOST}/']),
        ('og:url', head.og_url, [f'{HOST}/']),
        ('SoftwareApplication JSON-LD url', software_application_urls(head), [HOST]),
    ]:
        if got != want:
            bad.append(f'{index}: {what} is {got or ["<missing>"]}, expected {want}')

    for name, want in [
        ('robots.txt', f'Sitemap: {HOST}/sitemap.xml'),
        ('sitemap.xml', f'<loc>{HOST}/</loc>'),
    ]:
        path = root / name
        if not path.is_file():
            bad.append(f'{path}: missing')
        elif want not in path.read_text():
            bad.append(f'{path}: no {want!r}')

    for path in sorted(root.rglob('*')):
        if path.is_file() and OLD_HOST in path.read_bytes().decode('utf-8', 'replace'):
            bad.append(f'{path}: still names the old host {OLD_HOST}')

    if bad:
        print(f'{root}: host claims are wrong — the canonical host is {HOST}:',
              file=sys.stderr)
        for line in bad:
            print(f'  {line}', file=sys.stderr)
        sys.exit(1)
    print(f'{root}: canonical, og:url and JSON-LD name {HOST}; robots and '
          f'sitemap point at it; no {OLD_HOST} anywhere', file=sys.stderr)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: check_domain.py dist')
    main(sys.argv[1])
