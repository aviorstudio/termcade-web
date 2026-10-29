#!/usr/bin/env bash
set -euo pipefail
test -s dist/index.html
python3 tools/check_scripts.py dist
python3 tools/check_domain.py dist
node tools/browser-check.mjs dist
for want in 'class="logo b"' 'class="on void"' 'ASTEROID'; do
  grep -qF "$want" dist/index.html || { echo "missing from dist/index.html: $want"; exit 1; }
done
