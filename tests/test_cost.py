import cost


def test_cost_arithmetic():
    card = {"vcpu_hour": 3.50, "gib_memory_hour": 0.45, "currency": "INR"}
    r = cost.estimate(replicas=2, cpu_limit=1, mem_gib=1, rps=10, card=card)
    assert r["per_replica_hour"] == 3.95
    assert r["hourly_all_replicas"] == 7.9
    assert r["requests_per_hour"] == 36000
    assert abs(r["cost_per_1000_requests"] - 0.2194) < 0.001
