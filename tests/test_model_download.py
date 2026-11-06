"""Check that MODEL_URI selects the expected object-storage bucket and prefix."""

import boto3

import model_runner


def test_model_download_uses_bucket_and_prefix(monkeypatch, tmp_path):
    class FakeS3:
        def list_objects_v2(self, *, Bucket, Prefix):
            assert (Bucket, Prefix) == ("models", "v1/")
            return {"Contents": [{"Key": "v1/config.json"}]}

        def download_file(self, bucket, key, destination):
            assert (bucket, key) == ("models", "v1/config.json")
            with open(destination, "w", encoding="utf-8") as stream:
                stream.write("{}")

    monkeypatch.setenv("S3_ENDPOINT", "http://127.0.0.1:8333")
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: FakeS3())
    monkeypatch.setattr(model_runner.tempfile, "mkdtemp", lambda **kwargs: str(tmp_path))

    directory = model_runner._download_model("s3://models/v1")
    assert (tmp_path / "config.json").read_text(encoding="utf-8") == "{}"
    assert directory == str(tmp_path)
