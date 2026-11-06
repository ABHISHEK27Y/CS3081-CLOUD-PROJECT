#!/usr/bin/env bash
# Full bring-up: cluster -> images -> storage -> model seed -> service. Idempotent where possible.
set -euo pipefail
cd "$(dirname "$0")/.."
CLUSTER=cloud-mini

[ -f .env ] || { echo "Copy .env.example to .env first."; exit 1; }

# 1. cluster
if ! k3d cluster list | grep -q "^${CLUSTER} "; then
  k3d cluster create --config cluster/k3d.yaml
fi

# 2. images
docker build -f service/Dockerfile -t cloud-mini/service:v1 .
docker build -f worker/Dockerfile  -t cloud-mini/worker:v1 .
k3d image import cloud-mini/service:v1 cloud-mini/worker:v1 -c "$CLUSTER"

# 3. storage + app (secrets, seaweedfs, buckets, model seed, service)
bash scripts/deploy.sh
echo "up complete. Service at http://localhost:8080/parse"
