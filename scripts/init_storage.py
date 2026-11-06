"""Create the datasets and models buckets and upload commands_pool.jsonl to datasets (Task 1).

Run with S3_ENDPOINT + AWS_* set (from .env). For a local run against the cluster, port-forward
SeaweedFS first:
    kubectl -n data port-forward svc/seaweedfs 8333:8333
    S3_ENDPOINT=http://localhost:8333 python scripts/init_storage.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "worker"))
import storage  # noqa: E402


def main():
    for bucket in ("datasets", "models"):
        storage.ensure_bucket(bucket)
        print(f"bucket ready: {bucket}")
    with open(os.path.join("data", "commands_pool.jsonl"), encoding="utf-8") as f:
        storage.write_text("datasets", "commands_pool.jsonl", f.read())
    print("uploaded commands_pool.jsonl -> datasets/commands_pool.jsonl")


if __name__ == "__main__":
    main()
