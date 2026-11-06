# Runbook

This project uses a two-node k3d cluster on one laptop. The nodes share the
same host, so they do not provide machine-level fault tolerance. Model weights
are stored in SeaweedFS and in the [`model-v1` GitHub Release](https://github.com/ABHISHEK27Y/CS3081-CLOUD-PROJECT/releases/tag/model-v1), not in Git or the service image.

## Fresh clone

Install Docker, k3d, kubectl, Git Bash/make, Python 3.11, boto3, and `gh`.
Then, from the repository root:

```bash
cp .env.example .env       # set a private local SeaweedFS secret
make up                    # cluster, images, storage, model seed, service
```

The model Release must already exist. `make down` deletes the cluster. The
Release includes `v1.tar.gz`, `v2.tar.gz`, both SHA-256 files, and a version
manifest. `scripts/publish_models.py` verifies the archives and uploads the
assets using `GH_TOKEN` or a saved Git credential; it never stores a token.

## Reproduce the teacher and student

Run Ollama with `phi3.5` reachable from the cluster, then:

```bash
make label
python scripts/verify_teacher_shards.py
make clean-data
make train SUBSET=50
make train
make train-v2
make eval
```

The indexed Job places 1,500 commands in each shard. `clean.py` writes
`datasets/v1/train.jsonl` and `train.sha256` to SeaweedFS. Training uses only
the first 1,500 cleaned rows. Install the pinned packages in
`training/requirements.txt` before the training commands. If running tools on
the host through a SeaweedFS port-forward, set `S3_ENDPOINT` to
`http://127.0.0.1:8333` and provide the local credentials from `.env` as
environment variables.

## Validate the service

```bash
docker build -f service/Dockerfile -t cloud-mini/service:v1 .
docker image inspect cloud-mini/service:v1 --format '{{.Size}}'
kubectl -n app get deployment,service,ingress,hpa,pods -o wide
curl -i -X POST http://localhost:8080/parse -H 'Content-Type: application/json' -d '{"text":"what is the weather in london"}'
```

The service downloads its model from SeaweedFS. `/readyz` returns 503 while
loading and 200 once Ready; `/healthz` reports process health. To check the
1 CPU/1 GiB requirement, run the image with `--cpus=1 --memory=1g`, the v1
model URI, S3 endpoint, and local credentials, then use
`python scripts/measure_50_requests.py --container <name> --url <url>/parse`.
With `FAULT_INJECT=1`, `/parse` must return HTTP 500 and exactly
`{"error":"invalid_model_output"}`.

## Measure Kubernetes reliability and cost

Make sure two v1 Pods are Ready. For the two-replica tests, temporarily hold
the HPA minimum at two, then restore it to one afterward so the committed
`k8s/hpa.yaml` remains authoritative.

```bash
python scripts/measure_cold_start.py --runs 3 --replicas 2
locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m --host http://localhost:8080 --csv results/cluster_loadtest
python scripts/measure_reliability.py rollout
python scripts/measure_reliability.py recovery
python scripts/cost.py --replicas 2 --cpu-limit 1 --mem-gib 1 --rps <measured-rps>
```

Record `kubectl -n app top pods` repeatedly during the load run. The scripts
save cold-start times and model-download logs, Locust statistics and headers,
rolling-update and rollback headers, recovery, and the measured failure rates
under `results/`. The standard Locust run must use all commands in
`data/validation.jsonl`; invalid model responses are counted as failures.

## CI and submission

`.github/workflows/ci.yml` runs lint, unit tests, Release-model evaluation,
the 95% JSON-validity gate, and gitleaks. To demonstrate the gate, manually run
it once with `model_source=base` and save the failed run link in the report.
The final report is `report/report.pdf` (at most eight pages). Tag the final
commit `final` and include the scanned three-page handwritten reflection named
exactly `230103041.pdf` in the submission ZIP. Keep `AI_USE.md` unchanged.
