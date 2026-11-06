# Cloud Computing Mini Project — Command Parser (CS3081)

> **Student:** Abhishek Yadav · **Roll:** 230103041 · **Repository:** https://github.com/ABHISHEK27Y/CS3081-CLOUD-PROJECT.git

Distills a command-parsing capability from `phi3.5` (teacher) into a compact `pythia-70m` student, then serves it behind a FastAPI endpoint on a local k3d (k3s-in-Docker) cluster backed by SeaweedFS for model storage.

## What it does
```
POST /parse  {"text": "set an alarm for seven thirty am tomorrow"}
→ {"intent": "alarm_set", "date": "tomorrow", "time": "seven thirty am", "place": null}
```

## Prerequisites
| Tool | Purpose |
|------|---------|
| Docker | Build images, run k3d |
| k3d + kubectl | Local Kubernetes (k3s in Docker) |
| Ollama + `phi3.5` | Teacher model (~2.2 GB) |
| Python 3.11 | Training, scripts, tests (CPU) |
| make, locust, gh | Orchestration, load testing, releases |

> **Windows:** run `.sh` scripts via Git Bash, or install `make` (`choco install make`). All `make` targets delegate to scripts in `scripts/`.

## Repository Structure
```
cluster/        k3d.yaml                      (Task 1 cluster config)
prompts/        teacher_prompt.txt            (Task 1 teacher prompt)
worker/         label_worker.py, clean.py     (Task 1 sharded labelling + cleaning)
training/       train.py, predict.py, config  (Task 2 student training + inference)
service/        app.py, model_runner.py, Dockerfile  (Task 3 FastAPI /parse)
k8s/            *.yaml                        (Tasks 1 & 4: NS, SeaweedFS, deploy, svc, ingress, HPA)
network/        subnets.md, nacl.json         (Task 5: subnetting + NACL)
scripts/        up/deploy/evaluate/cost/...   (Tasks 1–7 helpers)
tools/          score.py, nacl_sim.py, locustfile.py  (provided checkers)
tests/          unit tests                    (Task 6)
data/           commands_pool, validation, schema, rate_card  (provided kit)
results/        logs, score reports, locust output  (Task 7 evidence)
report/         report.pdf                    (final report)
```

## Quick Start (3 commands)
```bash
cp .env.example .env            # 1. local dev secret (edit value)
make up                         # 2. cluster + storage + build + deploy
make train                      # 3. produce the model (needs dataset; see below)
```
`make up` spins up the k3d cluster, deploys SeaweedFS, creates `datasets`/`models` buckets, builds & imports images, seeds the model from the GitHub Release (if available), and exposes the service at `http://localhost:8080/parse` via Traefik Ingress.

## Full Workflow

### Task 1 — Object Storage + Parallel Teacher Labelling
```bash
ollama pull phi3.5 && ollama serve          # teacher on laptop
make up                                      # cluster + SeaweedFS + buckets (uploads commands_pool.jsonl)
make label                                   # indexed Job: 2 workers (SHARD_INDEX 0, 1)
# (or locally without k8s:)  bash scripts/run_workers_local.sh
make clean-data                              # → datasets/v1/train.jsonl + train.sha256, prints counts
```

### Task 2 — Train the Student
```bash
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r training/requirements.txt
make train SUBSET=50          # smoke test (fast)
make train                    # full v1 → models/v1/ (+ v1.tar.gz + model.sha256)
make train-v2                 # v2 (seed 7) → models/v2/ (for Task 4 rollout)
make eval                     # scores teacher, base, student → results/
```
Publish `models/v1.tar.gz` (and `v2.tar.gz`) as **GitHub Release assets** under tag `model-v1`; the checksum in `models/v1/model.sha256` must match. **Never commit weights.**

### Task 3 — The Container
```bash
docker build -f service/Dockerfile -t cloud-mini/service:v1 .
docker images cloud-mini/service:v1           # confirm ≤ 2 GB
# local smoke test:
docker run --rm -p 8000:8000 -e MODEL_URI=s3://models/v1 -e MODEL_VERSION=v1 \
  -e S3_ENDPOINT=http://host.docker.internal:8333 -e MAX_NEW_TOKENS=64 \
  -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... cloud-mini/service:v1
curl -s localhost:8000/parse -H 'content-type: application/json' -d '{"text":"weather in london"}'
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/parse \
  -H 'content-type: application/json' -d '{"text":"x"}'   # with FAULT_INJECT=1 → 500
```

### Task 4 — Deploy, Scale, Reliability
```bash
make deploy                                   # Deployment(2) + Service + Ingress + HPA
kubectl -n app get deploy,svc,ingress,hpa,pods
curl -s localhost:8080/parse -H 'content-type: application/json' -d '{"text":"weather in london"}' -i | head
# rolling update / rollback, recovery, cold start, load balancing: see docs/RUNBOOK.md
```

### Task 5 — Networking (no cluster needed)
```bash
python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check   # 6/6
python scripts/subnet_calc.py                                                      # subnet table
```

### Task 6 — Tests & CI
```bash
make lint && make test        # pyflakes + pytest (runs in CI too)
```
CI (`.github/workflows/ci.yml`): lint → tests → model eval from Release → quality gate (`score.py --min-validity 95`) → gitleaks. Trigger gate failure on untrained base: Actions → **ci** → *Run workflow* → `model_source = base`.

### Task 7 — Performance & Cost
```bash
make load                                                     # Locust, standard marking command
python scripts/cost.py --replicas 2 --cpu-limit 1 --mem-gib 1 --rps <measured>  # from loadtest
```

## Teardown
```bash
make down            # k3d cluster delete cloud-mini
```

See [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for detailed steps (rolling update, recovery, cold-start timing, load-balancing evidence) and the 4-day commit plan.