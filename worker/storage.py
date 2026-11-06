"""Tiny storage helper that works against either SeaweedFS (S3) or the local filesystem.

If the environment variable S3_ENDPOINT is set, objects are read from and written to the
S3-compatible store (SeaweedFS) using boto3. Otherwise everything falls back to the local
filesystem rooted at LOCAL_ROOT (default: the current directory), so the same code can be
run on a laptop with no cluster.

A "key" is always <bucket>/<path>, e.g. datasets/teacher/shard-0.jsonl. In local mode this
maps to <LOCAL_ROOT>/datasets/teacher/shard-0.jsonl.
"""
import os
import glob

LOCAL_ROOT = os.environ.get("LOCAL_ROOT", ".")


def use_s3():
    return bool(os.environ.get("S3_ENDPOINT"))


def _s3_client():
    import boto3  # imported lazily so local mode needs no boto3
    from botocore.client import Config
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        # Retries + timeouts keep large uploads alive when a `kubectl port-forward` tunnel drops a
        # connection mid-transfer (common when seeding the ~220 MB model through a port-forward).
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 10, "mode": "adaptive"},
            read_timeout=120,
            connect_timeout=30,
            tcp_keepalive=True,
        ),
    )


def _transfer_config():
    """Single-threaded multipart with modest parts: gentle on a port-forward, each part retriable."""
    from boto3.s3.transfer import TransferConfig
    mb = 1024 * 1024
    return TransferConfig(multipart_threshold=16 * mb, multipart_chunksize=16 * mb, use_threads=False)


def ensure_bucket(bucket):
    if not use_s3():
        os.makedirs(os.path.join(LOCAL_ROOT, bucket), exist_ok=True)
        return
    c = _s3_client()
    existing = {b["Name"] for b in c.list_buckets().get("Buckets", [])}
    if bucket not in existing:
        c.create_bucket(Bucket=bucket)


def write_text(bucket, path, text):
    if use_s3():
        _s3_client().put_object(Bucket=bucket, Key=path, Body=text.encode("utf-8"))
    else:
        dest = os.path.join(LOCAL_ROOT, bucket, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)


def write_bytes(bucket, path, data):
    if use_s3():
        _s3_client().put_object(Bucket=bucket, Key=path, Body=data)
    else:
        dest = os.path.join(LOCAL_ROOT, bucket, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)


def read_text(bucket, path):
    if use_s3():
        obj = _s3_client().get_object(Bucket=bucket, Key=path)
        return obj["Body"].read().decode("utf-8")
    with open(os.path.join(LOCAL_ROOT, bucket, path), encoding="utf-8") as f:
        return f.read()


def upload_file(bucket, path, local_file):
    if use_s3():
        _s3_client().upload_file(local_file, bucket, path, Config=_transfer_config())
    else:
        with open(local_file, "rb") as f:
            write_bytes(bucket, path, f.read())


def list_keys(bucket, prefix):
    """Return the object paths (keys without the bucket) under <bucket>/<prefix>."""
    if use_s3():
        c = _s3_client()
        keys, token = [], None
        while True:
            kw = {"Bucket": bucket, "Prefix": prefix}
            if token:
                kw["ContinuationToken"] = token
            resp = c.list_objects_v2(**kw)
            keys += [o["Key"] for o in resp.get("Contents", [])]
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return sorted(keys)
    base = os.path.join(LOCAL_ROOT, bucket)
    hits = glob.glob(os.path.join(base, prefix + "*"))
    return sorted(os.path.relpath(h, base).replace(os.sep, "/") for h in hits)
