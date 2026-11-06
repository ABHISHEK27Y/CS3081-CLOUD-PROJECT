#!/usr/bin/env bash
# Score three models on validation.jsonl and save raw outputs + reports in results/ (Task 2, step 6).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p results

# Teacher (same prompt/settings as Task 1) — needs Ollama; skipped if not reachable.
if curl -sf "${OLLAMA_HOST:-http://localhost:11434}/api/tags" >/dev/null 2>&1; then
  python scripts/eval_teacher.py --input data/validation.jsonl --out results/pred_teacher.jsonl
  python tools/score.py results/pred_teacher.jsonl data/validation.jsonl --out results/teacher_validation.json
else
  echo "Ollama not reachable at ${OLLAMA_HOST:-http://localhost:11434}; skipping teacher eval."
fi

# Untrained base model.
python training/predict.py --model EleutherAI/pythia-70m --input data/validation.jsonl --out results/pred_base.jsonl
python tools/score.py results/pred_base.jsonl data/validation.jsonl --out results/score_base.json

# Trained student v1.
python training/predict.py --model models/v1 --input data/validation.jsonl --out results/pred_student_v1.jsonl
python tools/score.py results/pred_student_v1.jsonl data/validation.jsonl --out results/score_student_v1.json

echo "wrote results/*.json and results/pred_*.jsonl"
