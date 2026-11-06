# Task 3 — Inference service container (CPU-only, no model weights)
# Using the CPU-only PyTorch wheel keeps us comfortably under the 2 GB ceiling.
FROM python:3.11-slim@sha256:65bd3d9f1d7fa268dd1909973ba7eb4bdf41f6dcf2cfbe76ba9528b170f3fd79 AS runtime

WORKDIR /app

# Install CPU torch first (pinned) from the CPU index — avoids pulling CUDA bits.
RUN pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu

# Application dependencies
COPY service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + schema
COPY service/app.py service/model_runner.py ./
COPY data/schema.json ./schema.json

# Runtime config
ENV PYTHONUNBUFFERED=1 \
    MAX_NEW_TOKENS=64

EXPOSE 8000

# Single uvicorn worker per replica; K8s probes handle health/readiness.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
