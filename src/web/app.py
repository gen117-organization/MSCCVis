"""Web UI for MSCCATools clone-detection settings."""

import asyncio
import sys
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.wsgi import WSGIMiddleware
from .stdout_proxy import ThreadLocalStdoutProxy
from .validation import validate_run_params

# ---------------------------------------------------------------------------
# Path setup (same pattern as the rest of the project)
# ---------------------------------------------------------------------------


def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return start


project_root = _find_repo_root(Path(__file__).resolve())
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))

from src.visualize.scatter import create_dash_app
from .pipeline_runner import run_job, LogCapture

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="MSCCATools Web UI")
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
_dash_app = create_dash_app("/visualize/")
app.mount("/visualize", WSGIMiddleware(_dash_app.server))

# Store running job logs keyed by job_id
_jobs: dict[str, dict] = {}
_stdout_proxy = ThreadLocalStdoutProxy(sys.stdout)
sys.stdout = _stdout_proxy  # type: ignore[assignment]


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return html_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# REST / WebSocket endpoints
# ---------------------------------------------------------------------------


@app.post("/api/run")
async def start_job(params: dict):
    """Start a new analysis job."""
    try:
        validated = validate_run_params(params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"status": "queued", "log": None}
    thread = threading.Thread(
        target=run_job,
        args=(job_id, validated),
        kwargs={
            "jobs": _jobs,
            "stdout_proxy": _stdout_proxy,
            "project_root": project_root,
        },
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id}


@app.websocket("/ws/logs/{job_id}")
async def stream_logs(websocket: WebSocket, job_id: str):
    """Stream log lines for a running job."""
    await websocket.accept()
    sent = 0
    try:
        while True:
            job = _jobs.get(job_id)
            if not job:
                await websocket.send_json({"type": "error", "message": "Job not found"})
                break
            log: LogCapture | None = job.get("log")
            if log:
                while sent < len(log.lines):
                    await websocket.send_json({"type": "log", "line": log.lines[sent]})
                    sent += 1
            status = job.get("status", "queued")
            if status in ("completed", "error"):
                await websocket.send_json({"type": "status", "status": status})
                break
            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        pass
