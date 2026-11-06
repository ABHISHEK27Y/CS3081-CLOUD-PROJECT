#!/usr/bin/env bash
# Convenience: run two labelling workers in parallel on the laptop (local filesystem mode),
# with Ollama running locally. Writes datasets/teacher/shard-0.jsonl and shard-1.jsonl, then
# you run clean.py. This mirrors the indexed Job but needs no cluster — handy for development.
#
# Faithful-to-the-handout path is k8s/worker-job.yaml; this is the local equivalent.
set -euo pipefail
cd "$(dirname "$0")/.."

export SHARD_COUNT=2
export TEACHER_MODEL="${TEACHER_MODEL:-phi3.5}"
export OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
unset S3_ENDPOINT   # local filesystem mode: writes under ./datasets/

echo "starting shard 0 and shard 1 (Ollama at $OLLAMA_HOST, model $TEACHER_MODEL)"
SHARD_INDEX=0 python worker/label_worker.py &
pid0=$!
SHARD_INDEX=1 python worker/label_worker.py &
pid1=$!
wait $pid0 $pid1
echo "both shards finished. Now run:  python worker/clean.py --counts-out results/clean_counts.json"
