#!/usr/bin/env bash
# Download the model archive(s) from the GitHub Release and extract them to models/<version>/.
# No-op if models/v1 already exists locally. Lets `make up` work from a fresh clone.
set -euo pipefail
cd "$(dirname "$0")/.."
TAG="${MODEL_RELEASE_TAG:-model-v1}"
mkdir -p models

fetch() {
  local v="$1"
  [ -d "models/$v" ] && return 0
  if gh release view "$TAG" >/dev/null 2>&1 && gh release download "$TAG" -p "${v}.tar.gz" -D models/ --clobber 2>/dev/null; then
    mkdir -p "models/$v"
    tar -xzf "models/${v}.tar.gz" -C "models/$v"
    echo "fetched models/$v from release $TAG"
  else
    echo "note: no models/$v locally and no release asset ${v}.tar.gz (run 'make train' first)"
  fi
}
fetch v1
fetch v2 || true
