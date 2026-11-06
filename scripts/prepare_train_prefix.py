"""Prepare the stable first 1,500 cleaned rows while later teacher labels run.

Only a contiguous command-ID prefix is considered. Once it has 1,500 cleaned
rows, later IDs cannot change those rows because duplicate removal keeps the
smallest ID. The complete Task 1 cleaning must still run after both workers end.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
import clean  # noqa: E402
import storage  # noqa: E402


def main():
    pool = [json.loads(line) for line in storage.read_text("datasets", "commands_pool.jsonl").splitlines() if line]
    records = clean.read_all_shards("datasets", "teacher/shard-")
    by_id = {row["id"]: row for row in records}
    prefix = []
    for command in pool:
        if command["id"] not in by_id:
            break
        prefix.append(by_id[command["id"]])
    rows, counts = clean.clean_records(prefix)
    print(f"contiguous raw prefix: {len(prefix)}; cleaned rows: {len(rows)}; counts: {counts}")
    if len(rows) < 1500:
        raise SystemExit("first 1,500 cleaned rows are not ready")

    dest = ROOT / "datasets" / "v1" / "train.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8"))
    print(f"wrote {dest}; first 1,500 IDs end at {rows[1499]['id']}")


if __name__ == "__main__":
    main()
