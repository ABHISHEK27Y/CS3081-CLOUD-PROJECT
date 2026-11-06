import subnet_calc


def test_plan_matches_documented_table():
    p = {s["name"]: s for s in subnet_calc.plan()}

    assert p["app"]["cidr"] == "10.20.0.0/22"
    assert p["app"]["usable_hosts"] == 1022
    assert p["app"]["first_host"] == "10.20.0.1"
    assert p["app"]["last_host"] == "10.20.3.254"
    assert p["app"]["broadcast"] == "10.20.3.255"

    assert p["public"]["cidr"] == "10.20.4.0/24"
    assert p["public"]["usable_hosts"] == 254

    assert p["data"]["cidr"] == "10.20.5.0/25"
    assert p["data"]["usable_hosts"] == 126
    assert p["data"]["broadcast"] == "10.20.5.127"

    assert p["management"]["cidr"] == "10.20.5.128/27"
    assert p["management"]["usable_hosts"] == 30
    assert p["management"]["last_host"] == "10.20.5.158"


def test_no_overlaps_and_contiguous():
    import ipaddress
    nets = [ipaddress.ip_network(s["cidr"]) for s in subnet_calc.plan()]
    for a, b in zip(nets, nets[1:]):
        assert int(b.network_address) == int(a.broadcast_address) + 1
