#!/usr/bin/env bash
# Apply namespaces, secrets, SeaweedFS, seed buckets + model, then deploy the service.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

kubectl apply -f k8s/00-namespaces.yaml
bash scripts/create_secrets.sh
kubectl apply -f k8s/seaweedfs.yaml
kubectl -n data rollout status deploy/seaweedfs --timeout=180s

# Seed buckets + model through a temporary port-forward (python + boto3 run on the host).
export S3_ENDPOINT=http://localhost:8333
bash scripts/fetch_model.sh          # get models/v1 (+v2) from the GitHub Release if not present

# A kubectl port-forward can drop a connection during the large model upload, so run the seed with a
# fresh port-forward and retry a few times (boto3 itself also retries individual parts).
seed_once() {
  kubectl -n data port-forward svc/seaweedfs 8333:8333 >/tmp/seaweed-pf.log 2>&1 &
  local pf=$!
  for _ in $(seq 1 30); do curl -sf http://localhost:8333/status >/dev/null 2>&1 && break; sleep 1; done
  python scripts/init_storage.py && python scripts/seed_model.py
  local rc=$?
  kill "$pf" 2>/dev/null || true
  wait "$pf" 2>/dev/null || true
  return $rc
}
seeded=0
for attempt in 1 2 3; do
  if seed_once; then seeded=1; break; fi
  echo "seed attempt $attempt failed; retrying with a fresh port-forward..." >&2
  sleep 3
done
[ "$seeded" = 1 ] || { echo "model seed failed after 3 attempts" >&2; exit 1; }

kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -f k8s/ingress.yaml -f k8s/hpa.yaml
kubectl -n app rollout status deploy/command-parser --timeout=300s
