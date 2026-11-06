"""Run Locust while performing a rolling update or Pod recovery in k3d."""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def kubectl(*args):
    return subprocess.check_output(["kubectl", "-n", "app", *args], text=True).strip()


def ready_pods():
    items = json.loads(kubectl("get", "pods", "-l", "app=command-parser", "-o", "json"))["items"]
    return [pod for pod in items if not pod["metadata"].get("deletionTimestamp")
            and any(c["type"] == "Ready" and c["status"] == "True"
                    for c in pod.get("status", {}).get("conditions", []))]


def wait_ready(expected=2, new_name=None):
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        ready = ready_pods()
        if len(ready) == expected and (new_name is None or any(p["metadata"]["name"] != new_name for p in ready)):
            return [p["metadata"]["name"] for p in ready]
        time.sleep(2)
    raise TimeoutError("replacement Pods did not become Ready")


def version_header():
    request = urllib.request.Request(
        "http://127.0.0.1:8080/parse",
        data=b'{"text":"what is the weather in london"}',
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return f"HTTP {response.status}, X-Model-Version={response.headers.get('X-Model-Version')}"
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}, X-Model-Version={error.headers.get('X-Model-Version')}"


def wait_version(expected):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        observed = version_header()
        if observed == f"HTTP 200, X-Model-Version={expected}":
            return observed
        time.sleep(2)
    raise TimeoutError(f"Ingress never served model version {expected}; last: {observed}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("rollout", "recovery"))
    args = parser.parse_args()
    prefix = f"cluster_{args.mode}_loadtest"
    log_path = ROOT / "results" / f"{prefix}.txt"
    env = os.environ.copy()
    env["LOADTEST_HEADERS_OUT"] = str(ROOT / "results" / f"{prefix}_headers.json")
    command = [sys.executable, "-m", "locust", "-f", "tools/locustfile.py", "--headless",
               "--users", "4", "--spawn-rate", "4", "--run-time", "2m",
               "--host", "http://127.0.0.1:8080", "--csv", f"results/{prefix}", "--only-summary"]
    lines = [f"mode: {args.mode}", f"initial Ready Pods: {wait_ready()}"]
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            time.sleep(10)
            if process.poll() is not None:
                raise RuntimeError("Locust ended before the reliability action")
            if args.mode == "rollout":
                kubectl("set", "env", "deployment/command-parser", "MODEL_VERSION=v2", "MODEL_URI=s3://models/v2")
                lines.append("set MODEL_VERSION=v2, MODEL_URI=s3://models/v2 while Locust ran")
                lines.append(kubectl("rollout", "status", "deployment/command-parser", "--timeout=300s"))
                lines.append("after rollout: " + wait_version("v2"))
                kubectl("rollout", "undo", "deployment/command-parser")
                lines.append(kubectl("rollout", "status", "deployment/command-parser", "--timeout=300s"))
                lines.append("after rollback: " + wait_version("v1"))
            else:
                victim = ready_pods()[0]["metadata"]["name"]
                kubectl("delete", "pod", victim, "--wait=false")
                lines.append(f"deleted {victim} while Locust ran")
                lines.append(f"replacement Ready Pods: {wait_ready(new_name=victim)}")
            lines.append(f"Locust still running after action: {process.poll() is None}")
        finally:
            process.wait(timeout=240)
    rows = list(csv.DictReader((ROOT / "results" / f"{prefix}_stats.csv").open(encoding="utf-8", newline="")))
    stats = rows[-1]
    count, failures = int(stats["Request Count"]), int(stats["Failure Count"])
    lines.extend([f"requests: {count}", f"failures: {failures}", f"failure rate: {100 * failures / count:.2f}%",
                  f"p95: {stats['95%']} ms", f"Locust exit code: {process.returncode}"])
    summary = ROOT / "results" / f"cluster_{args.mode}.txt"
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
