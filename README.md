# CS3081 Cloud Computing Mini Project

**Abhishek Yadav · 230103041**
[Repository](https://github.com/ABHISHEK27Y/CS3081-CLOUD-PROJECT) · [Report](report/report.pdf) · [Model Release](https://github.com/ABHISHEK27Y/CS3081-CLOUD-PROJECT/releases/tag/model-v1) · [AI use](AI_USE.md)

This project distils a command parser from an Ollama `phi3.5` teacher into a `pythia-70m` student. A FastAPI service loads the student from SeaweedFS and serves it through a Traefik Ingress on a local two-node k3d cluster.

```text
commands_pool.jsonl → two teacher Job shards → cleaning → train.jsonl
                                                  ↓
                                             student v1/v2
                                                  ↓
                         GitHub Release + SeaweedFS models bucket
                                                  ↓
                          FastAPI Pods → Service → Ingress → /parse
```

## Results at a glance

| Area | Measured result | Evidence |
| --- | --- | --- |
| Teacher data | 3,000 commands, 2 shards; 2,748 cleaned rows kept | [Counts](results/clean_counts.json), [shard audit](results/teacher_shard_check.json) |
| Model quality | Student v1: 100% JSON validity and 50% full-frame accuracy on 100 validation commands | [Scores](results/score_student_v1.json), [predictions](results/pred_student_v1.jsonl) |
| Container | 1.742 GB image; 50 requests at 1 CPU / 1 GiB, peak sample 344.5 MiB | [Image](results/cluster_image_size.txt), [container run](results/cluster_50_requests.txt) |
| Kubernetes | Cold-start median 20 s; two replicas served 129 and 123 counted responses; HPA observed 1 → 2 → 1 | [Cold starts](results/cluster_coldstart.txt), [response headers](results/cluster_loadtest_headers.json), [HPA](results/cluster_hpa.txt) |
| Networking | Subnet plan and NACL sample checker: 6/6 | [Plan](network/subnets.md), [rules](network/nacl.json) |
| Load | 254 requests, 3 failed (1.18%); p50 1,500 ms, p95 3,600 ms, 2.155 rps | [Locust CSV](results/cluster_loadtest_stats.csv) |
| Cost | Estimated ₹1.0183 per 1,000 requests at measured throughput | [Calculation](results/cost_cluster.txt) |

The 1% normal-load error target and 0.5% rollout error target were **not met**; failures were invalid model outputs, not Ingress errors. The [report](report/report.pdf) gives the measurements, limitations, and proposed improvements.

## Repository map

| Path | Contents |
| --- | --- |
| `data/`, `prompts/`, `worker/` | Supplied commands/schema, teacher prompt, labelling and cleaning |
| `training/`, `models/` | Student training/evaluation; generated weights are excluded from Git |
| `service/`, `k8s/`, `cluster/` | API, Dockerfile, Kubernetes manifests, k3d configuration |
| `network/`, `tools/` | Subnet/NACL files and supplied checkers |
| `scripts/`, `Makefile`, `docs/RUNBOOK.md` | Reproduction and measurement commands |
| `tests/`, `.github/workflows/` | Unit tests, CI quality gate, live-cluster workflow |
| `results/`, `report/` | Raw evidence and three-page report |

## Quick start from a fresh clone

Use Docker, k3d, kubectl, Python with `boto3`, GitHub CLI (`gh`), `tar`, `curl`, Git Bash and GNU Make. The released model archives are downloaded during deployment; model weights are never committed or baked into the service image. On Windows, run Make targets from Git Bash or another shell with `bash` and `make`.

```bash
git clone https://github.com/ABHISHEK27Y/CS3081-CLOUD-PROJECT.git
cd CS3081-CLOUD-PROJECT
cp .env.example .env     # replace the local SeaweedFS development secret
make up                  # cluster, images, storage, model download, API
curl -i -X POST http://localhost:8080/parse \
  -H 'Content-Type: application/json' \
  -d '{"text":"what is the weather in london"}'
make down                # delete the local cluster when finished
```

`POST /parse` accepts a text command and returns the intent plus `date`, `time`, and `place` slots. `GET /healthz` checks process health; `GET /readyz` stays at 503 until model loading completes. An invalid model response becomes HTTP 500 with `{"error":"invalid_model_output"}`. See the [runbook](docs/RUNBOOK.md) for endpoint, rollout, recovery, and resource-check commands.

## Reproduce each task

The complete teacher run took about 131 minutes on the tested laptop. Start Ollama with `phi3.5` reachable from the cluster before labelling. Training requires the pinned packages in `training/requirements.txt` and SeaweedFS access as described in the runbook.

```bash
ollama pull phi3.5
make label                         # Task 1: indexed Job, two shards
python scripts/verify_teacher_shards.py
make clean-data                    # Task 1: validation, deduplication, checksum
make train SUBSET=50               # Task 2: quick training smoke test
make train                         # Task 2: v1, first 1,500 cleaned records
make train-v2                      # Task 2: second seed for rollout
make eval                          # Task 2: teacher, base, student scores
make build && make deploy          # Tasks 3–4: container and deployment
python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check
make lint && make test             # Tasks 5–6: NACL, static checks, unit tests
make load                          # Task 7: standard two-minute Locust run
```

Selected model archives, tokenizers, checksums, and version manifest are in the [GitHub Release](https://github.com/ABHISHEK27Y/CS3081-CLOUD-PROJECT/releases/tag/model-v1). The model is fetched into SeaweedFS during `make up`. The network plan is in [`network/subnets.md`](network/subnets.md). The measured reliability and cost commands are in [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## CI and submission

The [CI workflow](.github/workflows/ci.yml) runs lint, unit tests, Release-model evaluation with a 95% JSON-validity gate, and secret scanning. The [trained-model run passed](https://github.com/ABHISHEK27Y/CS3081-CLOUD-PROJECT/actions/runs/42230797041); the [untrained-base run failed at the model gate](https://github.com/ABHISHEK27Y/CS3081-CLOUD-PROJECT/actions/runs/42219523454), as intended. A [fresh-clone cluster workflow passed](https://github.com/ABHISHEK27Y/CS3081-CLOUD-PROJECT/actions/runs/42219651934).

The final submission includes the three-page handwritten reflection as `230103041.pdf` inside `230103041.zip`. The scan is a submission artifact, not a GitHub source file.
