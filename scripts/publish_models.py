"""Publish checked model archives and checksums as GitHub Release assets.

Uses GH_TOKEN, or the existing Git credential helper. No credential is saved in
the repository. Run after training both versions and pushing the final source.
"""

import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "ABHISHEK27Y/CS3081-CLOUD-PROJECT"
TAG = "model-v1"
ROOT = Path(__file__).resolve().parents[1]


def token():
    value = os.environ.get("GH_TOKEN")
    if value:
        return value
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        text=True,
        capture_output=True,
        check=True,
    )
    credentials = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return credentials["password"]


def request(url, key, method="GET", body=None, content_type="application/vnd.github+json"):
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/vnd.github+json", "User-Agent": "cloud-mini-release", "Content-Type": content_type}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=300) as response:
        content = response.read()
        return json.loads(content) if content else None


def main():
    assets = []
    manifest = {"base_model": "EleutherAI/pythia-70m", "teacher": "phi3.5", "training_examples": 1500, "versions": {}}
    for version, seed, epochs in (("v1", 42, 4), ("v2", 7, 3)):
        archive = ROOT / "models" / f"{version}.tar.gz"
        checksum = ROOT / "models" / version / "model.sha256"
        expected = checksum.read_text(encoding="utf-8").split()[0]
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"{version} archive checksum mismatch")
        manifest["versions"][version] = {"seed": seed, "epochs": epochs, "sha256": actual}
        assets.extend([(archive.name, archive, "application/gzip"), (f"{version}-model.sha256", checksum, "text/plain")])
    manifest_path = ROOT / "models" / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    assets.append((manifest_path.name, manifest_path, "application/json"))

    key = token()
    api = f"https://api.github.com/repos/{REPO}"
    try:
        release = request(f"{api}/releases/tags/{TAG}", key)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        release = request(
            f"{api}/releases", key, "POST",
            json.dumps({"tag_name": TAG, "target_commitish": "main", "name": "Trained Pythia-70M models", "body": "CPU-trained v1 and v2 model and tokenizer archives. SHA-256 values are in the checksum assets and manifest."}).encode(),
        )
    upload_url = release["upload_url"].split("{")[0]
    existing = {asset["name"]: asset for asset in release["assets"]}
    for name, path, media_type in assets:
        local_digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if name in existing and existing[name].get("digest") == local_digest:
            print(f"already present: {name} ({path.stat().st_size} bytes)")
            continue
        if name in existing:
            request(existing[name]["url"], key, "DELETE")
        url = upload_url + "?" + urllib.parse.urlencode({"name": name})
        request(url, key, "POST", path.read_bytes(), media_type)
        print(f"uploaded: {name} ({path.stat().st_size} bytes)")
    print(release["html_url"])


if __name__ == "__main__":
    main()
