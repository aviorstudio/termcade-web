#!/usr/bin/env python3
"""Allow only the install clipboard module and inert JSON-LD in static output."""
from html.parser import HTMLParser
from pathlib import Path
import sys


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.modules = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if any(name.lower().startswith('on') for name in attrs):
            raise ValueError('Inline event handlers are not allowed')
        if tag != 'script':
            return
        if attrs.get('type') == 'module' and attrs.get('src') == '/install-copy.js':
            self.modules += 1
        elif attrs.get('type') != 'application/ld+json' or 'src' in attrs:
            raise ValueError(f'Unexpected executable script: {attrs}')


def main(root):
    root = Path(root)
    assets = {p.relative_to(root).as_posix() for p in root.rglob('*')
              if p.is_file() and p.suffix.lower() in {'.js', '.mjs', '.cjs'}}
    if assets != {'install-copy.js'}:
        raise ValueError(f'Unexpected JavaScript assets: {sorted(assets)}')
    if (root / 'install-copy.js').read_bytes() != Path('public/install-copy.js').read_bytes():
        raise ValueError('Built clipboard module differs from its source')
    pages = list(root.rglob('*.html'))
    if not pages:
        raise ValueError('Missing built HTML')
    for path in pages:
        page = Page()
        page.feed(path.read_text())
        if path == root / 'index.html' and page.modules != 1:
            raise ValueError('The landing page must load the clipboard module exactly once')
        if page.modules > 1:
            raise ValueError(f'Duplicate clipboard modules: {path}')
    print('Static script checks passed: install clipboard module and JSON-LD only.')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'dist')
