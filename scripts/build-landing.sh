#!/usr/bin/env bash
# Rebuild the self-hosted 3D bundle using the frontend's locked dependencies.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
NODE_PATH="$root/frontend/node_modules" "$root/frontend/node_modules/.bin/esbuild" \
  "$root/docs/landing/scene.js" --bundle --minify --format=esm \
  --outfile="$root/docs/landing/scene.bundle.js"
cp "$root/frontend/node_modules/three/LICENSE" "$root/docs/landing/THREE-LICENSE.txt"
