# Task 1 — Teacher labelling worker (sharded, resumable)
FROM python:3.11-slim@sha256:65bd3d9f1d7fa268dd1909973ba7eb4bdf41f6dcf2cfbe76ba9528b170f3fd79 AS worker

WORKDIR /app

# Dependencies (boto3 for S3, urllib3 for Ollama)
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Worker code + prompt template
COPY worker/storage.py worker/label_worker.py worker/clean.py ./
COPY prompts/teacher_prompt.txt ./prompts/teacher_prompt.txt

ENV PROMPT_FILE=/app/prompts/teacher_prompt.txt \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "label_worker.py"]
