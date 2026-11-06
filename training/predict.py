"""Generate predictions with a model, in the format score.py expects (Task 2, step 6).

  python training/predict.py --model models/v1 --input data/validation.jsonl --out results/pred_student_v1.jsonl
  python training/predict.py --model EleutherAI/pythia-70m --input data/validation.jsonl --out results/pred_base.jsonl

--model is a local directory (your trained model) or a Hugging Face name (the untrained base).
Each output line is {"id": "...", "prediction": "<raw model text>"}; score.py parses it.
"""
import argparse
import json


def extract_json(generated):
    """Return the model's JSON object as raw text: from the first '{' to its matching '}'.

    Kept identical to the service's extractor so training-time and serving-time scores line up.
    """
    s = generated.strip()
    start = s.find("{")
    if start == -1:
        return s
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return s[start:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-new-tokens", type=int, default=64)
    a = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(a.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(a.model)
    model.eval()

    rows = [json.loads(line) for line in open(a.input, encoding="utf-8") if line.strip()]
    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as out:
        for r in rows:
            prompt = f"Command: {r['text']}\nJSON:"  # no trailing space (must match training)
            enc = tokenizer(prompt, return_tensors="pt")
            with torch.no_grad():
                gen = model.generate(
                    **enc, max_new_tokens=a.max_new_tokens, do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                )
            new = gen[0][enc["input_ids"].shape[1]:]
            text = tokenizer.decode(new, skip_special_tokens=True)
            out.write(json.dumps({"id": r["id"], "prediction": extract_json(text)}) + "\n")
    print(f"wrote {a.out} ({len(rows)} predictions)")


if __name__ == "__main__":
    main()
