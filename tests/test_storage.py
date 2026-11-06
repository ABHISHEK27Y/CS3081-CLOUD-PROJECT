"""Local worker uploads must never truncate their own shard file."""

import storage


def test_upload_file_preserves_same_local_path(monkeypatch, tmp_path):
    monkeypatch.delenv("S3_ENDPOINT", raising=False)
    monkeypatch.setattr(storage, "LOCAL_ROOT", str(tmp_path))
    shard = tmp_path / "datasets" / "teacher" / "shard-0.jsonl"
    shard.parent.mkdir(parents=True)
    shard.write_text('{"id":"C0001"}\n', encoding="utf-8")

    storage.upload_file("datasets", "teacher/shard-0.jsonl", str(shard))

    assert shard.read_text(encoding="utf-8") == '{"id":"C0001"}\n'
