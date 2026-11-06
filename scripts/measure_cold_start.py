"""Measure Pod creation-to-Ready time for three service replacement runs."""

import argparse
import json
import statistics
import subprocess
import time
from datetime import datetime
from pathlib import Path


def kubectl(*args):
    return subprocess.check_output(["kubectl", "-n", "app", *args], text=True)


def pods():
    return json.loads(kubectl("get", "pods", "-l", "app=command-parser", "-o", "json"))["items"]


def ready_time(pod):
    for condition in pod.get("status", {}).get("conditions", []):
        if condition["type"] == "Ready" and condition["status"] == "True":
            return datetime.fromisoformat(condition["lastTransitionTime"].replace("Z", "+00:00"))
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--replicas", type=int, default=2)
    args = parser.parse_args()

    results = []
    all_logs = []
    for run in range(1, args.runs + 1):
        old_names = {pod["metadata"]["name"] for pod in pods()}
        kubectl("delete", "pod", "-l", "app=command-parser", "--wait=false")
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            replacements = [
                pod for pod in pods()
                if pod["metadata"]["name"] not in old_names
                and not pod["metadata"].get("deletionTimestamp")
                and ready_time(pod) is not None
            ]
            if len(replacements) >= args.replicas:
                break
            time.sleep(2)
        else:
            raise TimeoutError(f"run {run}: {args.replicas} replacement Pods did not become Ready")

        durations = []
        for pod in replacements[:args.replicas]:
            name = pod["metadata"]["name"]
            created = datetime.fromisoformat(pod["metadata"]["creationTimestamp"].replace("Z", "+00:00"))
            seconds = (ready_time(pod) - created).total_seconds()
            durations.append(seconds)
            log = kubectl("logs", name)
            if "downloading" not in log or "model loaded" not in log:
                raise RuntimeError(f"run {run}: model-download evidence missing from {name} logs")
            all_logs.append(f"run {run}, {name}\n{log}\n")
        results.append(max(durations))
        print(f"run {run}: Pod times {durations}; both Ready after {results[-1]:.1f} s", flush=True)

    Path("results/cluster_coldstart.txt").write_text(
        "\n".join(f"run {i}: {value:.1f} s" for i, value in enumerate(results, 1))
        + f"\nmedian: {statistics.median(results):.1f} s\n",
        encoding="utf-8",
    )
    Path("results/cluster_coldstart_logs.txt").write_text("\n".join(all_logs), encoding="utf-8")


if __name__ == "__main__":
    main()
