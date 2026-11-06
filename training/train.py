"""Fine-tune EleutherAI/pythia-70m on teacher-labelled commands (Task 2).

Sequence-level knowledge distillation: each training example pairs the user command
with the teacher's JSON output. Prompt tokens are masked in the loss so only the
completion (the JSON) contributes to the gradient.

Usage:
  python train.py --version v1               # full run (config.yaml params)
  python train.py --version v1 --subset 50   # quick smoke test
  python train.py --version v2 --seed 7      # second model for Task 4 rollout demo

Outputs written under models/<version>/:
  - model weights + tokenizer (HF format)
  - <version>.tar.gz  (Release asset)
  - model.sha256      (checksum of the tarball)
  - training/loss.csv (per-epoch loss)
"""
import argparse
import csv
import hashlib
import json
import random
import sys
import tarfile
from pathlib import Path

import yaml

# Make worker/storage importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
import storage  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load_config() -> dict:
    with (HERE / "config.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_train_rows(cfg: dict, limit: int) -> list[dict]:
    """Fetch train.jsonl from object storage, with local fallback."""
    try:
        text = storage.read_text(cfg["datasets_bucket"], cfg["train_file"])
    except Exception:
        text = (ROOT / "datasets" / "v1" / "train.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    return rows[:limit]


def build_example(tokenizer, row: dict, max_len: int) -> tuple[list[int], list[int]]:
    """Convert one row to (input_ids, labels) with prompt tokens masked (-100)."""
    target = json.dumps(
        {k: row[k] for k in ("intent", "date", "time", "place")},
        ensure_ascii=False,
    )
    # Prompt MUST end at "JSON:" (no trailing space). The completion owns the leading space.
    # This keeps the prompt a clean token prefix of the full sequence so the mask boundary
    # is exact and the model learns to emit the opening brace.
    prompt = f"Command: {row['text']}\nJSON:"
    full = prompt + " " + target + tokenizer.eos_token
    ids = tokenizer(full, truncation=True, max_length=max_len)["input_ids"]
    prompt_len = min(len(tokenizer(prompt)["input_ids"]), len(ids))
    labels = [-100] * prompt_len + ids[prompt_len:]
    return ids, labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1")
    ap.add_argument("--subset", type=int, default=0, help="limit to first N rows (smoke test)")
    ap.add_argument("--seed", type=int, default=None, help="override config seed")
    ap.add_argument("--epochs", type=int, default=None, help="override config epochs")
    ap.add_argument("--no-upload", action="store_true", help="skip object-storage upload")
    args = ap.parse_args()

    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer

    cfg = load_config()
    seed = args.seed if args.seed is not None else cfg["seed"]
    epochs = args.epochs if args.epochs is not None else cfg["epochs"]
    limit = args.subset if args.subset else cfg["train_limit"]

    random.seed(seed)
    torch.manual_seed(seed)

    tokenizer = AutoTokenizer.from_pretrained(cfg["model_name"])
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(cfg["model_name"])
    model.train()

    rows = load_train_rows(cfg, limit)
    print(f"[train] {len(rows)} examples, version={args.version}, seed={seed}, epochs={epochs}")

    examples = [build_example(tokenizer, r, cfg["max_seq_len"]) for r in rows]

    class DS(Dataset):
        def __len__(self):
            return len(examples)

        def __getitem__(self, i):
            return examples[i]

    pad_id = tokenizer.pad_token_id

    def collate(batch):
        max_len = max(len(ids) for ids, _ in batch)
        input_ids, attn_masks, labels = [], [], []
        for ids, lab in batch:
            pad = max_len - len(ids)
            input_ids.append(ids + [pad_id] * pad)
            attn_masks.append([1] * len(ids) + [0] * pad)
            labels.append(lab + [-100] * pad)
        return (
            torch.tensor(input_ids),
            torch.tensor(attn_masks),
            torch.tensor(labels),
        )

    loader = DataLoader(
        DS(), batch_size=cfg["batch_size"], shuffle=True, collate_fn=collate
    )
    optim = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"])

    loss_rows = []
    for epoch in range(1, epochs + 1):
        total_loss, batches = 0.0, 0
        for input_ids, attn_mask, labels in loader:
            optim.zero_grad()
            out = model(input_ids=input_ids, attention_mask=attn_mask, labels=labels)
            out.loss.backward()
            optim.step()
            total_loss += out.loss.item()
            batches += 1
        avg = total_loss / max(batches, 1)
        loss_rows.append((epoch, round(avg, 6)))
        print(f"[train] epoch {epoch}/{epochs} loss {avg:.6f}")

    # Persist per-epoch loss
    with (HERE / "loss.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "loss"])
        w.writerows(loss_rows)

    # Save model + tokenizer
    out_dir = ROOT / "models" / args.version
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print(f"[train] saved model + tokenizer to {out_dir}")

    # Create release tarball + checksum
    archive = ROOT / "models" / f"{args.version}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in sorted(out_dir.iterdir()):
            if name.name == "model.sha256":
                continue
            tar.add(name, arcname=name.name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out_dir / "model.sha256").write_text(f"{digest}  {args.version}.tar.gz\n", encoding="utf-8")
    print(f"[train] {args.version}.tar.gz sha256 {digest}")

    if not args.no_upload:
        try:
            storage.ensure_bucket(cfg["models_bucket"])
            for name in sorted(out_dir.iterdir()):
                storage.upload_file(
                    cfg["models_bucket"],
                    f"{args.version}/{name.name}",
                    str(name),
                )
            print(f"[train] uploaded files to {cfg['models_bucket']}/{args.version}/")
        except Exception as e:
            print(f"[train] WARNING: upload skipped ({e}). Files remain in {out_dir}.")


if __name__ == "__main__":
    main()
