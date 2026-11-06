"""Deterministic subnet allocator for Task 5 (largest requirement first, contiguous).

Prints the same table that network/subnets.md documents, and is importable by the tests.
"""
import ipaddress

BASE = "10.20.0.0/16"
REQUIREMENTS = [("app", 1000), ("public", 250), ("data", 100), ("management", 20)]


def smallest_prefix(hosts):
    """Smallest subnet (largest prefix) whose usable-host count covers `hosts`."""
    for prefix in range(32, 0, -1):
        if (2 ** (32 - prefix)) - 2 >= hosts:
            return prefix
    raise ValueError(hosts)


def plan(base=BASE, requirements=REQUIREMENTS):
    cur = int(ipaddress.ip_network(base).network_address)
    out = []
    for name, hosts in requirements:
        prefix = smallest_prefix(hosts)
        net = ipaddress.ip_network((cur, prefix))
        out.append({
            "name": name,
            "hosts_needed": hosts,
            "cidr": str(net),
            "prefix": prefix,
            "network": str(net.network_address),
            "first_host": str(net.network_address + 1),
            "last_host": str(net.broadcast_address - 1),
            "broadcast": str(net.broadcast_address),
            "usable_hosts": net.num_addresses - 2,
        })
        cur = int(net.broadcast_address) + 1
    return out


if __name__ == "__main__":
    for s in plan():
        print(f"{s['name']:11} {s['cidr']:16} hosts {s['usable_hosts']:>5}  "
              f"{s['first_host']} - {s['last_host']}  bcast {s['broadcast']}")
