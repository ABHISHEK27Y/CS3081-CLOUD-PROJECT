"""Send 50 sequential requests to one limited Pod or container and sample memory."""

import argparse
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from urllib.error import URLError
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:18000/parse")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--pod")
    target.add_argument("--container")
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()

    commands = [json.loads(line)["text"] for line in Path("data/validation.jsonl").read_text(encoding="utf-8").splitlines()]
    failures = 0
    samples = []
    request_lines = []
    peak_mib = 0
    start = time.monotonic()
    for index in range(args.count):
        payload = json.dumps({"text": commands[index % len(commands)]}).encode()
        request = urllib.request.Request(args.url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                code = response.status
                body = response.read().decode()
        except urllib.error.HTTPError as error:
            code = error.code
            body = error.read().decode()
        except (TimeoutError, URLError) as error:
            code = 0
            body = str(error)
        if code != 200:
            failures += 1
        if index % 5 == 0 or index == args.count - 1:
            if args.pod:
                output = subprocess.check_output(["kubectl", "-n", "app", "top", "pod", args.pod, "--no-headers"], text=True).strip()
            else:
                output = subprocess.check_output(["docker", "stats", args.container, "--no-stream", "--format", "{{.Name}} {{.CPUPerc}} {{.MemUsage}}"], text=True).strip()
            samples.append(output)
            match = re.search(r"\s([\d.]+)MiB(?:\s|$)", output) if args.container else re.search(r"\s(\d+)Mi\s*$", output)
            if match:
                peak_mib = max(peak_mib, float(match.group(1)))
        request_line = f"{index + 1}/{args.count}: HTTP {code} {body[:120]}"
        request_lines.append(request_line)
        print(request_line, flush=True)

    lines = [f"target: {args.pod or args.container}", f"requests: {args.count}", f"HTTP failures: {failures}", f"observed peak memory: {peak_mib:.1f} MiB", f"elapsed seconds: {time.monotonic() - start:.1f}"]
    if args.container:
        details = json.loads(subprocess.check_output(["docker", "inspect", args.container], text=True))[0]
        lines.extend([
            f"CPU limit: {details['HostConfig']['NanoCpus'] / 1e9:.1f} core",
            f"memory limit: {details['HostConfig']['Memory'] / (1024 ** 3):.1f} GiB",
            f"OOM killed: {details['State']['OOMKilled']}",
        ])
    lines.extend(["requests:", *request_lines, "resource samples:", *samples])
    Path("results/cluster_50_requests.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
