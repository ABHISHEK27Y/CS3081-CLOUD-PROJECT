# Cloud Computing Mini Project — Make targets
# Quick start (fresh clone):
#   1) cp .env.example .env      # edit the dev secret
#   2) make up                   # cluster + storage + build + deploy
#   3) make train                # produce the model (requires Ollama for labelling)
SHELL := /bin/bash
CLUSTER := cloud-mini

.PHONY: up down cluster build deploy train train-v2 label clean-data eval test lint load help

help:
	@echo "Targets: up/down, cluster, build, deploy, label, clean-data, train[/ SUBSET=50], train-v2, eval, test, lint, load"

up:            ## create cluster, build+import images, deploy storage + service
	bash scripts/up.sh

down:          ## tear down the entire k3d cluster
	k3d cluster delete $(CLUSTER)

cluster:       ## create just the k3d cluster (no deploy)
	k3d cluster create --config cluster/k3d.yaml

build:         ## build + import service & worker images into k3d
	docker build -f service/Dockerfile -t cloud-mini/service:v1 .
	docker build -f worker/Dockerfile  -t cloud-mini/worker:v1 .
	k3d image import cloud-mini/service:v1 cloud-mini/worker:v1 -c $(CLUSTER)

deploy:        ## apply namespaces, secrets, storage, and the app
	bash scripts/deploy.sh

label:         ## run 2 labelling workers as an indexed Job (needs Ollama reachable)
	kubectl apply -f k8s/worker-job.yaml
	kubectl -n pipeline wait --for=condition=complete job/teacher-label --timeout=6h

clean-data:    ## merge shards -> datasets/v1/train.jsonl (+ SHA-256)
	python worker/clean.py --counts-out results/clean_counts.json

train:         ## fine-tune v1 (use SUBSET=50 for a quick smoke test)
	python training/train.py --version v1 $(if $(SUBSET),--subset $(SUBSET),)

train-v2:      ## second model for Task 4 rollout demo (different seed)
	python training/train.py --version v2 --seed 7

eval:          ## score teacher, untrained base, and student on validation.jsonl
	bash scripts/evaluate.sh

test:          ## run unit test suite
	python -m pytest -q

lint:          ## static analysis (pyflakes)
	python -m pyflakes worker service training scripts tools

load:          ## marking load test (service at :8080)
	mkdir -p results
	locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m \
	       --host http://localhost:8080 --csv results/loadtest