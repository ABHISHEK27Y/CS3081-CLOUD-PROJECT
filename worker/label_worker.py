"""Teacher labelling worker (Task 1) — sharded, resumable.

Splits the command pool by line index modulo SHARD_COUNT. Each worker calls the
Ollama API (phi3.5, temp=0, seed=42) with the teacher prompt and writes raw
replies to datasets/teacher/shard-<idx>.jsonl. Replies are stored verbatim; no
post-processing here — cleaning happens in clean.py.

Env vars:
  SHARD_INDEX / SHARD_COUNT   shard ID + total shards (SHARD_INDEX can also come
                              from K8s JOB_COMPLETION_INDEX in an indexed Job)
  OLLAMA_HOST                 default http://localhost:11434 (inside cluster use
                              http://host.k3d.internal:11434 for laptop Ollama)
  TEACHER_MODEL               default phi3.5
  PROMPT_FILE                 default prompts/teacher_prompt.txt
  DATASETS_BUCKET             default "datasets"
  S3_ENDPOINT                 if set, use SeaweedFS; else local filesystem
"""
import json
import os
import sys
import time
import urllib.request

import storage

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
TEACHER_MODEL = os.environ.get("TEACHER_MODEL", "phi3.5")
PROMPT_FILE = os.environ.get("PROMPT_FILE", "prompts/teacher_prompt.txt")
DATASETS_BUCKET = os.environ.get("DATASETS_BUCKET", "datasets")
SEED = int(os.environ.get("TEACHER_SEED", "42"))
MAX_TOKENS = int(os.environ.get("TEACHER_MAX_TOKENS", "128"))


def shard_index() -> int:
    """Get shard ID from env (supports K8s indexed Job via JOB_COMPLETION_INDEX)."""
    for var in ("SHARD_INDEX", "JOB_COMPLETION_INDEX"):
        val = os.environ.get(var)
        if val not in (None, ""):
            return int(val)
    sys.exit("SHARD_INDEX (or JOB_COMPLETION_INDEX) must be set")


def load_prompt() -> str:
    with open(PROMPT_FILE, encoding="utf-8") as f:
        return f.read()


def call_teacher(template: str, command: str) -> str:
    """Send one command to Ollama, return the raw JSON reply."""
    prompt = template.replace("{{COMMAND}}", command)
    payload = json.dumps({
        "model": TEACHER_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",  # forces valid JSON output
        "options": {"temperature": 0, "seed": SEED, "num_predict": MAX_TOKENS},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body.get("response", "").strip()


def read_command_pool() -> list[dict]:
    """Load commands_pool.jsonl from object storage, fallback to local file."""
    try:
        text = storage.read_text(DATASETS_BUCKET, "commands_pool.jsonl")
    except Exception:
        with open(os.path.join("data", "commands_pool.jsonl"), encoding="utf-8") as f:
            text = f.read()
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def already_done(path: str) -> set[str]:
    """Return set of command IDs already written to local shard file."""
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    pass
    return done


def main():
    idx = shard_index()
    count = int(os.environ.get("SHARD_COUNT", "2"))
    prompt_tmpl = load_prompt()
    commands = read_command_pool()
    mine = [(i, c) for i, c in enumerate(commands) if i % count == idx]

    storage.ensure_bucket(DATASETS_BUCKET)
    local_path = os.path.join("datasets", "teacher", f"shard-{idx}.jsonl")
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    done = already_done(local_path)

    obj_key = f"teacher/shard-{idx}.jsonl"
    print(f"[shard {idx}/{count}] {len(mine)} commands, {len(done)} already done", flush=True)

    with open(local_path, "a", encoding="utf-8") as out:
        for n, (i, cmd) in enumerate(mine, 1):
            if cmd["id"] in done:
                continue
            # retry up to 3 times on transient errors
            for attempt in range(3):
                try:
                    raw = call_teacher(prompt_tmpl, cmd["text"])
                    break
                except Exception as e:
                    print(f"[shard {idx}] retry {cmd['id']} ({e})", flush=True)
                    time.sleep(2 * (attempt + 1))
            else:
                raw = ""  # clean.py will drop empty replies

            out.write(json.dumps(
                {"id": cmd["id"], "text": cmd["text"], "teacher_raw": raw},
                ensure_ascii=False,
            ) + "\n")
            out.flush()

            if n % 25 == 0:
                print(f"[shard {idx}] {n}/{len(mine)}", flush=True)
                storage.upload_file(DATASETS_BUCKET, obj_key, local_path)

    storage.upload_file(DATASETS_BUCKET, obj_key, local_path)
    print(f"[shard {idx}] done -> {DATASETS_BUCKET}/{obj_key}", flush=True)


if __name__ == "__main__":
    main()
