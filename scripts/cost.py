"""Cost-per-1000-requests estimator for Task 7, using data/rate_card.json.

  cost_per_1000 = (hourly cost of all running replicas / requests served per hour) * 1000
  hourly cost of a replica = cpu_limit * vcpu_hour + mem_limit_gib * gib_memory_hour

Example:
  python scripts/cost.py --replicas 2 --cpu-limit 1 --mem-gib 1 --rps 8
"""
import argparse
import json
import os


def estimate(replicas, cpu_limit, mem_gib, rps, card):
    per_replica_hour = cpu_limit * card["vcpu_hour"] + mem_gib * card["gib_memory_hour"]
    hourly = replicas * per_replica_hour
    requests_per_hour = rps * 3600.0
    cost_per_1000 = hourly / requests_per_hour * 1000.0
    return {
        "per_replica_hour": round(per_replica_hour, 4),
        "hourly_all_replicas": round(hourly, 4),
        "requests_per_hour": round(requests_per_hour, 2),
        "cost_per_1000_requests": round(cost_per_1000, 4),
        "currency": card.get("currency", ""),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicas", type=int, required=True)
    ap.add_argument("--cpu-limit", type=float, required=True, help="vCPU limit per replica")
    ap.add_argument("--mem-gib", type=float, required=True, help="memory limit (GiB) per replica")
    ap.add_argument("--rps", type=float, required=True, help="requests per second (from the load test)")
    ap.add_argument("--rate-card", default=os.path.join("data", "rate_card.json"))
    a = ap.parse_args()
    with open(a.rate_card, encoding="utf-8") as f:
        card = json.load(f)
    r = estimate(a.replicas, a.cpu_limit, a.mem_gib, a.rps, card)
    print(f"per replica/hour      {r['per_replica_hour']} {r['currency']}  "
          f"(= {a.cpu_limit}*{card['vcpu_hour']} + {a.mem_gib}*{card['gib_memory_hour']})")
    print(f"all {a.replicas} replicas/hour   {r['hourly_all_replicas']} {r['currency']}")
    print(f"requests/hour         {r['requests_per_hour']}  (= {a.rps} rps * 3600)")
    print(f"cost per 1000 reqs     {r['cost_per_1000_requests']} {r['currency']}")


if __name__ == "__main__":
    main()
