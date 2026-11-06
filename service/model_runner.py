"""Model runner for command-parser inference service (Task 3).

Weights are NOT baked into the Docker image. On startup, the service pulls model artifacts
from the S3-compatible object store (SeaweedFS) at MODEL_URI, using creds injected via
a K8s Secret into env vars.
"""
import json
import os
import tempfile
from pathlib import Path

_SCHEMA_FILE = Path(__file__).with_name("schema.json")
with _SCHEMA_FILE.open(encoding="utf-8") as fh:
    _SCHEMA = json.load(fh)
_REQUIRED_KEYS = set(_SCHEMA["keys"])
_VALID_INTENTS = set(_SCHEMA["intents"])


def extract_json(text: str) -> str:
    """Grab the first balanced {...} block from model output. Mirrors training/predict.py."""
    s = text.strip()
    start = s.find("{")
    if start == -1:
        return s
    depth = 0
    for idx, ch in enumerate(s[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start:idx + 1]
    return s[start:]


def validate(raw: str):
    """Parse and validate against schema.json. Returns dict on success, None on failure."""
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(obj, dict) or set(obj.keys()) != _REQUIRED_KEYS:
        return None
    if obj.get("intent") not in _VALID_INTENTS:
        return None
    for slot in ("date", "time", "place"):
        if obj[slot] is not None and not isinstance(obj[slot], str):
            return None
    if not isinstance(obj["intent"], str):
        return None
    return obj


def _resolve_model_dir(uri: str) -> str:
    """Map MODEL_URI to a local directory containing the model files.

    Handles s3://bucket/prefix (downloads from SeaweedFS), file:///path, and bare /path.
    """
    if uri.startswith("s3://"):
        return _download_model(uri)
    if uri.startswith("file://"):
        uri = uri[len("file://"):]
    if not os.path.isdir(uri):
        raise RuntimeError(f"MODEL_URI local path not found: {uri}")
    return uri


def _download_model(uri: str) -> str:
    """Pull model artifacts from S3 endpoint into a temp directory."""
    assert uri.startswith("s3://"), "MODEL_URI must be s3://<bucket>/<prefix>"
    _, _, rest = uri[len("s3://"):].partition("/")
    bucket, _, prefix = rest.partition("/")
    prefix = (prefix or "").rstrip("/") + "/"

    import boto3
    from botocore.client import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    dest = tempfile.mkdtemp(prefix="model-")
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    objects = resp.get("Contents", [])
    if not objects:
        raise RuntimeError(f"no objects found under {uri}")

    for obj in objects:
        key = obj["Key"]
        if not key.startswith(prefix):
            continue
        name = key[len(prefix):]
        if not name:
            continue
        s3.download_file(bucket, key, os.path.join(dest, name))
    return dest


class Runner:
    """Loads tokenizer + model, runs inference, validates output."""

    def __init__(self):
        self.ready = False
        self.model = None
        self.tokenizer = None
        self.max_new_tokens = int(os.environ.get("MAX_NEW_TOKENS", "64"))

    def load(self):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        local_dir = _resolve_model_dir(os.environ["MODEL_URI"])
        self.tokenizer = AutoTokenizer.from_pretrained(local_dir)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(local_dir)
        self.model.eval()
        self.ready = True

    def raw_output(self, text: str) -> str:
        """Generate raw JSON text for a single command."""
        import torch
        prompt = f"Command: {text}\nJSON:"  # exact same prefix as training (no trailing space)
        enc = self.tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            gen = self.model.generate(
                **enc,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        new_tokens = gen[0][enc["input_ids"].shape[1]:]
        decoded = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        return extract_json(decoded)
