#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
tag=$(cat "$root/tools/termcade-release")
base="https://github.com/aviorstudio/termcade/releases/download/$tag"
curl --fail --silent --show-error --location --connect-timeout 20 --max-time 120 --retry 2 \
  "$base/termcade_Linux_x86_64.tar.gz" -o "$scratch/termcade_Linux_x86_64.tar.gz"
(cd "$scratch" && sha256sum --check --strict "$root/tools/termcade-release.sha256")
tar -xzf "$scratch/termcade_Linux_x86_64.tar.gz" -C "$scratch" termcade
cd "$root"
python3 tools/capture.py --check "$scratch/termcade"
