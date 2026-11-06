"""Upload local models/<version>/ files into the models bucket (used by `make up`)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "worker"))
import storage  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def main():
    storage.ensure_bucket("models")
    seeded = False
    for version in ("v1", "v2"):
        d = os.path.join(ROOT, "models", version)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            fp = os.path.join(d, name)
            if os.path.isfile(fp):
                storage.upload_file("models", f"{version}/{name}", fp)
        print(f"seeded models/{version}/ ({len(os.listdir(d))} files)")
        seeded = True
    if not seeded:
        print("no local models to seed (train first, or let fetch_model.sh pull the release)")


if __name__ == "__main__":
    main()
