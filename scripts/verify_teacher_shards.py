"""Verify that two teacher shards cover the command pool exactly once."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
import storage  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shards", type=int, default=2)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--out", default="results/teacher_shard_check.json")
    args = parser.parse_args()

    pool = [json.loads(line) for line in storage.read_text("datasets", "commands_pool.jsonl").splitlines() if line]
    expected = {row["id"]: (i % args.shards, row["text"]) for i, row in enumerate(pool)}
    observed = Counter()
    wrong_shard = []
    wrong_text = []
    per_shard = {}
    for shard in range(args.shards):
        key = f"teacher/shard-{shard}.jsonl"
        rows = [json.loads(line) for line in storage.read_text("datasets", key).splitlines() if line]
        per_shard[str(shard)] = len(rows)
        for row in rows:
            sid = row["id"]
            observed[sid] += 1
            if sid not in expected or expected[sid][0] != shard:
                wrong_shard.append(sid)
            if sid in expected and expected[sid][1] != row["text"]:
                wrong_text.append(sid)
            if not isinstance(row.get("teacher_raw"), str):
                raise ValueError(f"teacher_raw is not text for {sid}")

    missing = sorted(set(expected) - set(observed))
    repeated = sorted(sid for sid, count in observed.items() if count != 1)
    result = {
        "expected": len(pool),
        "observed": sum(observed.values()),
        "per_shard": per_shard,
        "missing": len(missing),
        "repeated": len(repeated),
        "wrong_shard": len(wrong_shard),
        "wrong_text": len(wrong_text),
        "complete": not (missing or repeated or wrong_shard or wrong_text),
    }
    if args.allow_partial:
        result["missing_examples"] = missing[:5]
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["complete"] and not args.allow_partial:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
