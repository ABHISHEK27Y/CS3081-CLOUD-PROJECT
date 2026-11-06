import json
import os

import nacl_sim

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_sample_packets_all_match():
    rules = nacl_sim.load_rules(os.path.join(ROOT, "network", "nacl.json"))
    with open(os.path.join(ROOT, "network", "packets_sample.jsonl"), encoding="utf-8") as f:
        packets = [json.loads(line) for line in f if line.strip()]
    assert packets, "no sample packets found"
    for p in packets:
        action, _rule = nacl_sim.decide(rules, p)
        assert action == p["expected"], f"{p['id']}: got {action}, expected {p['expected']}"


def test_abusive_range_denied_on_web_port():
    rules = nacl_sim.load_rules(os.path.join(ROOT, "network", "nacl.json"))
    pkt = {"direction": "inbound", "protocol": "tcp", "port": 443, "address": "198.51.100.200"}
    action, rule = nacl_sim.decide(rules, pkt)
    assert action == "deny" and rule == 100
