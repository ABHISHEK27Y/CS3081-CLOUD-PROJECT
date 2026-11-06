"""Task 3 API behaviour, exercised with FastAPI's TestClient (no model/S3 needed).

The model runner is stubbed so these tests check the HTTP contract: status codes, the exact
headers, schema validation (invalid output -> 500), and the FAULT_INJECT hook.
"""
import importlib
import os

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

VALID = '{"intent":"weather_query","date":null,"time":null,"place":"london"}'


def make_client(ready=True, raw=VALID, fault="0"):
    os.environ["MODEL_VERSION"] = "v1"
    os.environ["FAULT_INJECT"] = fault
    import app as appmod
    importlib.reload(appmod)
    appmod.runner.load = lambda: None       # don't hit S3 on startup
    appmod.runner.ready = ready
    appmod.runner.raw_output = lambda text: raw
    return TestClient(appmod.app)


def test_healthz_always_200():
    assert make_client().get("/healthz").status_code == 200


def test_readyz_503_until_ready():
    assert make_client(ready=False).get("/readyz").status_code == 503
    assert make_client(ready=True).get("/readyz").status_code == 200


def test_parse_ok_body_and_headers():
    r = make_client().post("/parse", json={"text": "what is the weather in london"})
    assert r.status_code == 200
    assert r.json() == {"intent": "weather_query", "date": None, "time": None, "place": "london"}
    assert r.headers["X-Model-Version"] == "v1"
    assert r.headers.get("X-Served-By")


def test_parse_invalid_output_500():
    r = make_client(raw="not json").post("/parse", json={"text": "x"})
    assert r.status_code == 500
    assert r.json() == {"error": "invalid_model_output"}


def test_fault_inject_forces_500():
    r = make_client(fault="1").post("/parse", json={"text": "what is the weather in london"})
    assert r.status_code == 500
    assert r.json() == {"error": "invalid_model_output"}


def test_parse_503_when_not_ready():
    assert make_client(ready=False).post("/parse", json={"text": "x"}).status_code == 503
