"""Package the tracked final project plus the student's scanned reflection."""

import argparse
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLL = "230103041"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reflection", type=Path, required=True, help="three-page handwritten PDF")
    parser.add_argument("--out", type=Path, default=ROOT.parent / f"{ROLL}.zip")
    args = parser.parse_args()
    if not args.reflection.is_file() or args.reflection.name != f"{ROLL}.pdf":
        raise SystemExit(f"reflection must exist and be named exactly {ROLL}.pdf")
    if not (ROOT / "report" / "report.pdf").is_file():
        raise SystemExit("report/report.pdf is missing")

    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    files = [name for name in tracked if name and (ROOT / name).is_file()]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(ROOT / name, arcname=f"CS3081-CLOUD-PROJECT/{name}")
        archive.write(args.reflection, arcname=f"{ROLL}.pdf")
        archive.write(ROOT / "report" / "report.pdf", arcname="report.pdf")
        archive.write(ROOT / "README.md", arcname="README.md")
    with zipfile.ZipFile(args.out) as archive:
        names = archive.namelist()
        assert f"{ROLL}.pdf" in names
        assert "CS3081-CLOUD-PROJECT/report/report.pdf" in names
        assert "report.pdf" in names
        assert "README.md" in names
        assert not any(Path(name).name == ".env" or name.endswith(".safetensors") for name in names)
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"corrupt ZIP entry: {bad}")
    print(f"created {args.out} with {len(names)} files")


if __name__ == "__main__":
    main()
