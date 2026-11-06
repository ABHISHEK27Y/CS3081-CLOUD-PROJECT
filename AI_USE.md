# AI Use Declaration

This project was developed with AI assistance, consistent with the course policy ("You'll be using AI and no one can stop you. But do use it with your eyes wide open."). Below is an honest accounting of tooling, how it was applied, and how outputs were validated.

## Tools Employed

- **Claude (Anthropic) / Claude Code** — primary coding assistant for scaffolding the repo, authoring Python modules, Dockerfiles, Kubernetes manifests, the NACL/subnet design, CI/CD pipeline, and initial drafts of documentation (README, report). Used iteratively across all seven tasks.
- **Ollama + phi3.5** — the designated teacher model (not a coding aid). Ran locally to label the 3,000-command pool at temperature 0, seed 42, with JSON-constrained decoding.

## Breakdown by Task

| Task | What the AI Did | What I Did |
|------|----------------|------------|
| **1. Object Storage & Labelling** | Wrote `label_worker.py` (sharding logic, Ollama client, resume/upload), `clean.py` (validation rules, dedup, checksum), `storage.py` (S3 wrapper), `init_storage.py` (bucket setup), K8s Job manifest | Pulled phi3.5, ran `make up`, launched the indexed Job (`make label`), executed `make clean-data`, verified counts add up (3000 = 0+1+3+86+49+2861), confirmed SHA-256 stability across re-runs |
| **2. Student Training** | Authored `train.py` (sequence-level distillation, prompt masking, checkpointing), `predict.py`, `config.yaml` (hyperparams), loss logging, tarball + checksum generation | Installed CPU-only PyTorch, ran `make train` (full) and `make train SUBSET=50` (smoke), executed `make train-v2` (seed 7), ran `make eval` to score teacher/base/student, published `v1.tar.gz`/`v2.tar.gz` to GitHub Release `model-v1` |
| **3. Inference Container** | Produced `service/app.py` (FastAPI, /parse + /healthz + /readyz, schema validation, FAULT_INJECT hook), `service/model_runner.py` (S3 download, HF load, generation), `service/Dockerfile` (CPU torch, multi-stage, <2 GB), `schema.json` | Built image (`docker build -f service/Dockerfile -t cloud-mini/service:v1 .`), confirmed 1.74 GB, tested all three endpoints locally, validated headers and 500 path via `FAULT_INJECT=1` |
| **4. K8s Deploy & Reliability** | Wrote Deployment (2 replicas, resources, probes, RollingUpdate maxUnavailable=0), Service, Ingress, HPA (1–2 @ 70% CPU), `seaweedfs.yaml` (PVC + Deployment + Service), `deploy.sh` (secrets + apply order) | Imported image to k3d (`k3d image import`), ran `make deploy`, executed rolling update v1→v2 under load, rollback, pod deletion recovery, 3× cold-start timing, load-balance verification, HPA observation |
| **5. Networking** | Designed subnet plan for 10.20.0.0/16 (largest-first contiguous), authored `nacl.json` (stateless rules with reply allowances, rule ordering for abusive CIDR denial) | Verified 6/6 sample packets via `nacl_sim.py`, re-derived subnet math manually, documented rationale in `network/subnets.md` |
| **6. CI/CD** | Created `.github/workflows/ci.yml` (lint → test → model eval from Release → quality gate `score.py --min-validity 95` → gitleaks), `Makefile` (all targets), `.gitleaks.toml` | Pushed commits, watched pipeline pass on trained model (99% validity ≥ 95%), manually triggered `model_source=base` run to confirm gate fails at 0% validity (run 41300788338) |
| **7. Performance & Cost** | Wrote `tools/locustfile.py` (standard command), `scripts/cost.py` (INR calculation from rate card), `scripts/subnet_calc.py` | Ran `make load` (4 users, 90s, 213 req, 2.41 rps, p95 3300 ms), captured `kubectl top pods` (~0.95 vCPU, 460 MiB), computed cost: 7.90 INR/hr → 0.91 INR/1k req |

## Verification Discipline

- **Every reported number is from my own execution.** Nothing in the report is copied from AI output; all metrics (accuracy, latency, memory, cold-start, cost) come from `results/` artifacts produced on my machine / the GitHub Actions `live-cluster` workflow.
- **Provided checkers used as ground truth.** `nacl_sim.py` for NACL, `score.py` for model quality, Locust for load. These are deterministic validators, not AI claims.
- **Unit tests cover critical paths.** `tests/` exercises `clean.py`, output validation, subnet math; they run in CI on every push.
- **Code comprehension.** I can walk through every file; where I diverged from AI suggestions (e.g., prompt token boundary fix, resource limits, NACL rule order), I documented the reasoning.

## Known Limitations (Honest Assessment)

- **Student capacity.** 70M parameters on ~1,500 noisy teacher labels underfits slot rules; full-frame 43% vs teacher 48% is expected and reported transparently.
- **AI hallucinations caught by running code.** The assistant occasionally invented plausible-but-wrong details (library versions, K8s field names, boto3 config keys). These were caught because I actually built, deployed, and load-tested — the provided checkers and real infrastructure are the ultimate validators.
- **Single-node cluster.** k3d on one machine means no true cross-zone fault tolerance; HPA scale-out adds replicas on the same CPUs. This is noted in the report.
- **Teacher latency.** CPU-only phi3.5 labelling took ~1.1 h for 3k commands across 2 shards; a work queue would handle stragglers better than static modulo sharding.

---

*Declaration: I, Abhishek Yadav (Roll 230103041), confirm that the above reflects my actual use of AI tooling and my personal verification of all submitted artifacts.*