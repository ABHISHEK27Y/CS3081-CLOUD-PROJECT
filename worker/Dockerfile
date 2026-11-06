# Task 1 — Teacher labelling worker (sharded, resumable)
FROM python:3.11-slim AS worker

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