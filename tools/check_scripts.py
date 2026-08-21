#!/usr/bin/env python3
"""Fail if dist/ ships any executable JavaScript.

The page promises no client JavaScript. The old gate only looked for *.js
files, which an inline <script> sails straight past. This walks every HTML
file in dist/ and rejects:

- any <script src=...>  — external executable script
- any inline <script> whose type is not application/ld+json — that includes a
  missing type, text/javascript, and module. All of them execute.

application/ld+json is data, not code: it is the one script type this site
ships (structured metadata in the layout) and the one the gate allows.

    python3 tools/check_scripts.py dist
"""
import pathlib
import sys
from html.parser import HTMLParser

ALLOWED_TYPES = {'application/ld+json'}


class Scripts(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.bad = []

    def handle_starttag(self, tag, attrs):
        if tag != 'script':
            return
        attrs = dict(attrs)
        line, _ = self.getpos()
        if 'src' in attrs:
            self.bad.append(f'{self.path}:{line}: external script '
                            f'<script src={attrs["src"]!r}>')
        elif attrs.get('type', '').lower() not in ALLOWED_TYPES:
            self.bad.append(f'{self.path}:{line}: inline executable script '
                            f'<script type={attrs.get("type")!r}>')


def main(root):
    bad = []
    pages = sorted(pathlib.Path(root).rglob('*.html'))
    if not pages:
        sys.exit(f'{root}: no HTML files — was the site built?')
    for page in pages:
        parser = Scripts(page)
        parser.feed(page.read_text())
        bad.extend(parser.bad)
    if bad:
        print('dist ships executable JavaScript — this site is meant to '
              'ship none:', file=sys.stderr)
        for line in bad:
            print(f'  {line}', file=sys.stderr)
        sys.exit(1)
    print(f'{root}: no executable scripts in {len(pages)} page(s) '
          '(application/ld+json metadata is allowed)', file=sys.stderr)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: check_scripts.py dist')
    main(sys.argv[1])
