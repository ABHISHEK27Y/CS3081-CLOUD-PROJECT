"""FastAPI service for the command parser (Task 3).

Routes:
  POST /parse   {"text": "..."} -> 200 with four-key JSON + headers
                X-Model-Version, X-Served-By. Invalid model output -> 500
                {"error": "invalid_model_output"} (never broken JSON with 200).
  GET  /healthz -> 200 (process alive)
  GET  /readyz  -> 503 until model loads, then 200

Config via env (AWS_* from K8s Secret):
  MODEL_URI, MODEL_VERSION, S3_ENDPOINT, MAX_NEW_TOKENS, FAULT_INJECT (test hook).
"""
import os
import socket
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

import model_runner

MODEL_VERSION = os.environ.get("MODEL_VERSION", "unknown")
POD_NAME = os.environ.get("POD_NAME") or os.environ.get("HOSTNAME") or socket.gethostname()

runner = model_runner.Runner()


def _safe_load():
    """Load model in background; on failure process stays alive but /readyz returns 503."""
    try:
        runner.load()
        print(f"model loaded (version {MODEL_VERSION})", flush=True)
    except Exception as e:
        print(f"model load failed: {e}", flush=True)


@asynccontextmanager
async def lifespan(_app):
    # Non-blocking startup: model downloads in background thread; readiness probe gates traffic.
    threading.Thread(target=_safe_load, daemon=True).start()
    yield


app = FastAPI(title="command-parser", lifespan=lifespan)


class ParseIn(BaseModel):
    text: str


def _headers():
    return {"X-Model-Version": MODEL_VERSION, "X-Served-By": POD_NAME}


@app.get("/healthz")
def healthz():
    return Response(status_code=200)


@app.get("/readyz")
def readyz():
    return Response(status_code=200 if runner.ready else 503)


@app.post("/parse")
def parse(body: ParseIn):
    if not runner.ready:
        return JSONResponse({"error": "not_ready"}, status_code=503, headers=_headers())
    raw = runner.raw_output(body.text)
    if os.environ.get("FAULT_INJECT") == "1":
        raw = "not json"  # test hook: force invalid output path
    obj = model_runner.validate(raw)
    if obj is None:
        return JSONResponse({"error": "invalid_model_output"}, status_code=500, headers=_headers())
    return JSONResponse(obj, status_code=200, headers=_headers())
