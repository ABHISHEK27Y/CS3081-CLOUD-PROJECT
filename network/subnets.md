# Task 5 — Subnetting and Network Access Control

## 1. Subnet plan for `10.20.0.0/16`

**Method (as required by the handout):** allocate from the largest requirement to the
smallest; start at `10.20.0.0`; place each subnet immediately after the previous one; use
the smallest prefix whose usable-host count covers the requirement. Usable hosts per subnet
= `2^(32 - prefix) - 2` (one address is the network address, one is the broadcast address).

| Order | Subnet       | Hosts needed | Prefix | Block size | Network address | Usable host range            | Broadcast address | Usable hosts |
|-------|--------------|--------------|--------|-----------:|-----------------|------------------------------|-------------------|-------------:|
| 1     | `app`        | 1,000        | /22    | 1024       | `10.20.0.0`     | `10.20.0.1` – `10.20.3.254`  | `10.20.3.255`     | 1022         |
| 2     | `public`     | 250          | /24    | 256        | `10.20.4.0`     | `10.20.4.1` – `10.20.4.254`  | `10.20.4.255`     | 254          |
| 3     | `data`       | 100          | /25    | 128        | `10.20.5.0`     | `10.20.5.1` – `10.20.5.126`  | `10.20.5.127`     | 126          |
| 4     | `management` | 20           | /27    | 32         | `10.20.5.128`   | `10.20.5.129` – `10.20.5.158`| `10.20.5.159`     | 30           |

**Why each prefix is the smallest that fits**

- `app` needs 1,000 → `/23` gives 510 (too small), `/22` gives 1022 ≥ 1,000. **/22**.
- `public` needs 250 → `/25` gives 126 (too small), `/24` gives 254 ≥ 250. **/24**.
- `data` needs 100 → `/26` gives 62 (too small), `/25` gives 126 ≥ 100. **/25**.
- `management` needs 20 → `/28` gives 14 (too small), `/27` gives 30 ≥ 20. **/27**.

**Contiguous placement check**

```
10.20.0.0/22   app          10.20.0.0   .. 10.20.3.255
10.20.4.0/24   public       10.20.4.0   .. 10.20.4.255
10.20.5.0/25   data         10.20.5.0   .. 10.20.5.127
10.20.5.128/27 management   10.20.5.128 .. 10.20.5.159   (next free address: 10.20.5.160)
```

No overlaps; each block starts on a valid boundary for its prefix; all fit inside `10.20.0.0/16`.

## 2. NACL for the `public` subnet

The load balancer lives in `public`. The NACL is in [`nacl.json`](nacl.json). Rules are read
lowest-number-first; the first match wins; if nothing matches the packet is denied.

### Inbound
| Rule | Protocol | Port(s)     | Source CIDR       | Action | Purpose |
|-----:|----------|-------------|-------------------|--------|---------|
| 100  | all      | all         | `198.51.100.0/24` | deny   | Block the abusive range on **every** port, even 80/443. Lower number than 110/120 so it overrides them. |
| 110  | tcp      | 80          | `0.0.0.0/0`       | allow  | HTTP from anywhere. |
| 120  | tcp      | 443         | `0.0.0.0/0`       | allow  | HTTPS from anywhere. |
| 130  | tcp      | 22          | `10.20.5.128/27`  | allow  | SSH only from `management`. |
| 140  | tcp      | 1024–65535  | `10.20.0.0/22`    | allow  | Replies from the `app` subnet (they arrive on the LB's ephemeral ports). |
| —    | —        | —           | —                 | deny   | Default deny (everything else, e.g. the `data` subnet). |

### Outbound
| Rule | Protocol | Port(s)     | Destination CIDR | Action | Purpose |
|-----:|----------|-------------|------------------|--------|---------|
| 100  | tcp      | 8000        | `10.20.0.0/22`   | allow  | Forward `/parse` to the `app` service on port 8000. |
| 110  | tcp      | 1024–65535  | `0.0.0.0/0`      | allow  | Replies going back to clients (their ephemeral ports), anywhere. |
| —    | —        | —           | —                | deny   | Default deny. |

Clients are assumed to use ephemeral ports 1024–65535 for their side of a connection.

### Verification against the sample packets

```
python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check
```

| Packet | Direction | Protocol/Port | Address        | Expected | Decided by |
|--------|-----------|---------------|----------------|----------|------------|
| S01    | inbound   | tcp 443       | `192.0.2.55`   | allow    | rule 120   |
| S02    | inbound   | tcp 22        | `192.0.2.55`   | deny     | default (not management) |
| S03    | outbound  | tcp 8000      | `10.20.1.1`    | allow    | rule 100 (app) |
| S04    | inbound   | tcp 443       | `198.51.100.9` | deny     | rule 100 (abusive range beats 120) |
| S05    | outbound  | tcp 60000     | `192.0.2.55`   | allow    | rule 110 (reply to client) |
| S06    | inbound   | tcp 5432      | `10.20.5.20`   | deny     | default (data subnet, no match) |

All six match. (The assessment uses a hidden set of 20 packets with the same simulator.)

## 3. Why a stateless NACL needs separate reply rules, and why order matters

**Stateless → reply traffic needs its own rules.** A NACL does not remember connections. A
security group is *stateful*: if it allows an outgoing request, the matching reply is let back
in automatically. A NACL checks **every** packet on its own, including replies. So when the
LB forwards a request outbound to the `app` subnet (rule out-100, dst 8000), the app's reply
comes **back inbound** on the LB's ephemeral port and is a brand-new packet to the NACL — it is
only allowed because of the explicit inbound rule 140 (tcp 1024–65535 from `app`). Likewise the
LB's replies to external clients need the explicit outbound rule 110 (tcp 1024–65535 to
anywhere). Remove either rule and one half of every conversation is silently dropped.

**Order matters for `198.51.100.0/24`.** First-match-wins means a `deny` only overrides an
`allow` if its rule number is **lower**. The abusive range must be blocked even on 80/443, which
are allowed from `0.0.0.0/0` by rules 110/120. Putting the `deny` at rule 100 (below 110/120)
makes it win for any packet from `198.51.100.0/24`. If the deny were numbered 200 instead, rule
120 would already have allowed a 443 packet from `198.51.100.9` and the deny would never be
reached (this is exactly packet S04).
