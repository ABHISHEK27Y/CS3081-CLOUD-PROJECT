#!/usr/bin/env bash
# Create the Kubernetes secrets from .env (never committed). Idempotent.
#   - s3-credentials        in data, pipeline, app  (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
#   - seaweedfs-s3-config   in data                 (SeaweedFS S3 identities file)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and edit it." >&2
  exit 1
fi
set -a; . ./.env; set +a

for ns in data pipeline app; do
  kubectl get ns "$ns" >/dev/null 2>&1 || kubectl create namespace "$ns"
  kubectl -n "$ns" delete secret s3-credentials --ignore-not-found >/dev/null
  kubectl -n "$ns" create secret generic s3-credentials \
    --from-literal=AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    --from-literal=AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
done

tmp="$(mktemp)"
cat > "$tmp" <<JSON
{
  "identities": [
    {
      "name": "app",
      "credentials": [
        {"accessKey": "${AWS_ACCESS_KEY_ID}", "secretKey": "${AWS_SECRET_ACCESS_KEY}"}
      ],
      "actions": ["Admin", "Read", "Write", "List", "Tagging"]
    }
  ]
}
JSON
kubectl -n data delete secret seaweedfs-s3-config --ignore-not-found >/dev/null
kubectl -n data create secret generic seaweedfs-s3-config --from-file=s3.json="$tmp"
rm -f "$tmp"
echo "secrets created."
