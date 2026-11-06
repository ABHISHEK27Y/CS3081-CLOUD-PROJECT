"""Clean the teacher shards into a single training file (Task 1, step 6).

Reads every datasets/teacher/shard-*.jsonl, removes the bad records listed in the handout,
and writes the survivors in id order to datasets/v1/train.jsonl, together with its SHA-256
checksum in datasets/v1/train.sha256. Prints the counts table required by the report.

Removal reasons (each removed record is counted under exactly one reason, applied in order):
  (a) reply is not a valid JSON object
  (b) keys are not exactly intent, date, time, place
  (c) intent is not one of the eight allowed intents
  (d) a slot value is neither null nor text that appears in the command
  (e) duplicate command text (keep the record with the smallest id)

  input = (a) + (b) + (c) + (d) + duplicates + kept
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import storage  # noqa: E402

KEYS = {"intent", "date", "time", "place"}
INTENTS = {
    "alarm_set", "alarm_query", "calendar_set", "calendar_query",
    "calendar_remove", "weather_query", "datetime_query", "recommendation_events",
}


def norm(s):
    return " ".join(str(s).strip().lower().split())


def classify(rec):
    """Return ('keep', obj) or a one-letter rejection reason 'a'/'b'/'c'/'d'."""
    raw = rec.get("teacher_raw")
    if isinstance(raw, dict):
        obj = raw
    else:
        try:
            obj = json.loads(str(raw).strip())
        except (json.JSONDecodeError, TypeError, ValueError):
            return "a"
    if not isinstance(obj, dict):
        return "a"
    if set(obj.keys()) != KEYS:
        return "b"
    if obj.get("intent") not in INTENTS:
        return "c"
    text = norm(rec.get("text", ""))
    for k in ("date", "time", "place"):
        v = obj[k]
        if v is None:
            continue
        if not isinstance(v, str) or norm(v) not in text:
            return "d"
    return ("keep", obj)


def clean_records(records):
    """records: iterable of {"id","text","teacher_raw"}. Returns (kept, counts)."""
    counts = {"input": 0, "a": 0, "b": 0, "c": 0, "d": 0, "duplicates": 0, "kept": 0}
    survivors = []  # (id, text, obj) that passed a-d
    for rec in records:
        counts["input"] += 1
        result = classify(rec)
        if result == "keep" or (isinstance(result, tuple) and result[0] == "keep"):
            survivors.append((rec["id"], rec["text"], result[1]))
        else:
            counts[result] += 1

    # (e) de-duplicate by command text, keeping the smallest id
    best = {}  # text -> (id, text, obj)
    for sid, text, obj in survivors:
        if text not in best or sid < best[text][0]:
            best[text] = (sid, text, obj)
    counts["duplicates"] = len(survivors) - len(best)

    kept = sorted(best.values(), key=lambda t: t[0])  # id order
    counts["kept"] = len(kept)
    rows = [{"id": sid, "text": text,
             "intent": obj["intent"], "date": obj["date"],
             "time": obj["time"], "place": obj["place"]}
            for sid, text, obj in kept]
    return rows, counts


def read_all_shards(bucket, prefix):
    records = []
    for key in storage.list_keys(bucket, prefix):
        if not key.endswith(".jsonl"):
            continue
        text = storage.read_text(bucket, key)
        for line in text.splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def print_counts(counts):
    print("Cleaning counts")
    print(f"  input records          {counts['input']}")
    print(f"  (a) invalid JSON       {counts['a']}")
    print(f"  (b) wrong keys         {counts['b']}")
    print(f"  (c) bad intent         {counts['c']}")
    print(f"  (d) invented slot      {counts['d']}")
    print(f"  duplicates removed     {counts['duplicates']}")
    print(f"  kept                   {counts['kept']}")
    total = counts['a'] + counts['b'] + counts['c'] + counts['d'] + counts['duplicates'] + counts['kept']
    print(f"  check a+b+c+d+dup+kept  {total} (== input: {total == counts['input']})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bucket", default=os.environ.get("DATASETS_BUCKET", "datasets"))
    ap.add_argument("--prefix", default="teacher/shard-")
    ap.add_argument("--out-prefix", default="v1", help="object prefix for train.jsonl / train.sha256")
    ap.add_argument("--counts-out", help="also write the counts table as JSON here")
    a = ap.parse_args()

    records = read_all_shards(a.bucket, a.prefix)
    rows, counts = clean_records(records)

    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()

    storage.ensure_bucket(a.bucket)
    storage.write_text(a.bucket, f"{a.out_prefix}/train.jsonl", body)
    storage.write_text(a.bucket, f"{a.out_prefix}/train.sha256", f"{digest}  train.jsonl\n")

    print_counts(counts)
    print(f"\nwrote {a.bucket}/{a.out_prefix}/train.jsonl  ({len(rows)} records)")
    print(f"sha256 {digest}")
    if a.counts_out:
        with open(a.counts_out, "w", encoding="utf-8") as f:
            json.dump(counts, f, indent=2)


if __name__ == "__main__":
    main()
