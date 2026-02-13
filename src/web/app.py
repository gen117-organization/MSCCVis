"""Web UI for MSCCATools clone-detection settings."""

import asyncio
import json
import sys
import threading
import uuid
from pathlib import Path
import shutil
import re

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

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

import modules.clone_repo
import modules.collect_datas
import modules.analyze_cc
import modules.analyze_modification
from commands.pipeline import determine_analyzed_commits as dac

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="MSCCATools Web UI")
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)

# Store running job logs keyed by job_id
_jobs: dict[str, dict] = {}


def _parse_bool(value: object, name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{name} must be boolean")


def _parse_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip() != "":
        try:
            return int(value)
        except ValueError as e:
            raise ValueError(f"{name} must be integer") from e
    raise ValueError(f"{name} must be integer")


def _parse_float(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be number")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip() != "":
        try:
            return float(value)
        except ValueError as e:
            raise ValueError(f"{name} must be number") from e
    raise ValueError(f"{name} must be number")


def _validate_run_params(params: dict) -> dict:
    url = str(params.get("url", "")).strip()
    if not url:
        raise ValueError("url is required")
    if not re.fullmatch(r"https://github\.com/[^/\s]+/[^/\s]+/?", url):
        raise ValueError("url must be GitHub repository URL")

    detection_method = str(params.get("detection_method", "normal"))
    if detection_method not in {"normal", "tks", "rnr"}:
        raise ValueError("detection_method must be one of normal,tks,rnr")
    if detection_method in {"tks", "rnr"}:
        raise ValueError("detection_method tks/rnr is not implemented")

    tks = _parse_int(params.get("tks", 12), "tks")
    if tks <= 0:
        raise ValueError("tks must be > 0")

    rnr = _parse_float(params.get("rnr", 0.5), "rnr")
    if not (0 < rnr <= 1):
        raise ValueError("rnr must satisfy 0 < rnr <= 1")

    min_tokens = _parse_int(params.get("min_tokens", 50), "min_tokens")
    if min_tokens <= 0:
        raise ValueError("min_tokens must be > 0")

    import_filter = _parse_bool(params.get("import_filter", True), "import_filter")
    force_recompute = _parse_bool(
        params.get("force_recompute", True), "force_recompute"
    )

    comod_method = str(params.get("comod_method", "clone_set"))
    if comod_method not in {"clone_set", "clone_pair"}:
        raise ValueError("comod_method must be one of clone_set,clone_pair")
    if comod_method == "clone_pair":
        raise ValueError("comod_method clone_pair is not implemented")

    analysis_method = str(params.get("analysis_method", "merge_commit"))
    if analysis_method not in {"merge_commit", "tag", "frequency"}:
        raise ValueError("analysis_method must be one of merge_commit,tag,frequency")

    analysis_frequency = _parse_int(
        params.get("analysis_frequency", 50),
        "analysis_frequency",
    )
    if analysis_frequency <= 0:
        raise ValueError("analysis_frequency must be > 0")

    search_depth = _parse_int(params.get("search_depth", -1), "search_depth")
    if search_depth < -1:
        raise ValueError("search_depth must be >= -1")

    max_analyzed_commits = _parse_int(
        params.get("max_analyzed_commits", -1),
        "max_analyzed_commits",
    )
    if max_analyzed_commits < -1:
        raise ValueError("max_analyzed_commits must be >= -1")

    return {
        "url": url,
        "detection_method": detection_method,
        "tks": tks,
        "rnr": rnr,
        "min_tokens": min_tokens,
        "import_filter": import_filter,
        "force_recompute": force_recompute,
        "comod_method": comod_method,
        "analysis_method": analysis_method,
        "analysis_frequency": analysis_frequency,
        "search_depth": search_depth,
        "max_analyzed_commits": max_analyzed_commits,
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return html_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Job execution (runs in a background thread)
# ---------------------------------------------------------------------------


class _LogCapture:
    """Redirect print() to an in-memory buffer that the WebSocket can read."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.lines: list[str] = []

    def write(self, text: str):
        if text.strip():
            self.lines.append(text.rstrip("\n"))
        sys.__stdout__.write(text)

    def flush(self):
        sys.__stdout__.flush()


def _build_languages_dict(workdir: Path) -> dict:
    """run_github_linguist で取得した言語情報を project['languages'] 形式に変換する。"""
    from modules.github_linguist import run_github_linguist
    from config import TARGET_PROGRAMING_LANGUAGES

    raw = run_github_linguist(str(workdir))
    return {
        lang: data for lang, data in raw.items() if lang in TARGET_PROGRAMING_LANGUAGES
    }


def _clear_previous_results(repo_name: str) -> None:
    """Remove previous analysis outputs for the repository."""
    targets = [
        project_root / "dest/clones_json" / repo_name,
        project_root / "dest/modified_clones" / repo_name,
        project_root / "dest/moving_lines" / repo_name,
        project_root / "dest/csv" / repo_name,
        project_root / "dest/temp/ccfswtxt" / repo_name,
    ]
    for target in targets:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    analyzed_file = project_root / "dest/analyzed_commits" / f"{repo_name}.json"
    if analyzed_file.exists():
        analyzed_file.unlink()


def _run_job(job_id: str, params: dict):
    """Execute the full pipeline for a single repo URL with given params."""
    job = _jobs[job_id]
    log = _LogCapture(job_id)
    old_stdout = sys.stdout
    sys.stdout = log  # type: ignore[assignment]
    job["log"] = log
    try:
        url: str = params["url"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]
        job["status"] = "running"
        log.write(f"[job] Starting analysis for {url}\n")

        detection_method: str = params.get("detection_method", "normal")
        if detection_method != "normal":
            log.write(f"[error] Unsupported detection_method: {detection_method}\n")
            job["status"] = "error"
            return

        comod_method: str = params.get("comod_method", "clone_set")
        if comod_method != "clone_set":
            log.write(f"[error] Unsupported comod_method: {comod_method}\n")
            job["status"] = "error"
            return

        force_recompute = bool(params.get("force_recompute", True))
        if force_recompute:
            log.write("[job] Clearing previous results to apply selected filters.\n")
            _clear_previous_results(name)

        # ------------------------------------------------------------------
        # 1. Clone repository
        # ------------------------------------------------------------------
        log.write("[step 1/5] Cloning repository...\n")
        modules.clone_repo.clone_repo(url)
        workdir = project_root / "dest/projects" / name

        # ------------------------------------------------------------------
        # 2. Determine analysed commits  (overriding config values at runtime)
        # ------------------------------------------------------------------
        log.write("[step 2/5] Determining analysed commits...\n")
        analysis_method: str = params.get("analysis_method", "merge_commit")
        search_depth: int = int(params.get("search_depth", -1))
        max_commits: int = int(params.get("max_analyzed_commits", -1))
        frequency: int = int(params.get("analysis_frequency", 1))

        # Temporarily patch the config values used by determine_analyzed_commits
        import config as _cfg

        _orig_method = _cfg.ANALYSIS_METHOD
        _orig_depth = _cfg.SEARCH_DEPTH
        _orig_max = _cfg.MAX_ANALYZED_COMMITS
        _orig_freq = _cfg.ANALYSIS_FREQUENCY
        _cfg.ANALYSIS_METHOD = analysis_method
        _cfg.SEARCH_DEPTH = search_depth
        _cfg.MAX_ANALYZED_COMMITS = max_commits
        _cfg.ANALYSIS_FREQUENCY = frequency
        # Also patch the module that already imported them
        dac.ANALYSIS_METHOD = analysis_method
        dac.SEARCH_DEPTH = search_depth
        dac.MAX_ANALYZED_COMMITS = max_commits
        dac.ANALYSIS_FREQUENCY = frequency

        try:
            if analysis_method == "merge_commit":
                target_commits = dac.determine_analyzed_commits_by_mergecommits(workdir)
            elif analysis_method == "tag":
                target_commits = dac.determine_by_tag(workdir)
            elif analysis_method == "frequency":
                target_commits = dac.determine_by_frequency(workdir)
            else:
                target_commits = dac.determine_analyzed_commits_by_mergecommits(workdir)
        finally:
            _cfg.ANALYSIS_METHOD = _orig_method
            _cfg.SEARCH_DEPTH = _orig_depth
            _cfg.MAX_ANALYZED_COMMITS = _orig_max
            _cfg.ANALYSIS_FREQUENCY = _orig_freq

        if not target_commits:
            log.write("[error] No target commits found.\n")
            job["status"] = "error"
            return

        log.write(f"  Found {len(target_commits)} target commits.\n")
        analyzed_commits_dir = project_root / "dest/analyzed_commits"
        analyzed_commits_dir.mkdir(parents=True, exist_ok=True)
        with open(analyzed_commits_dir / f"{name}.json", "w") as f:
            json.dump(target_commits, f)

        # Build a project dict compatible with existing modules
        languages = _build_languages_dict(workdir)
        project = {"URL": url, "languages": languages}

        # ------------------------------------------------------------------
        # 3. Collect data (clone detection + moving lines)
        # ------------------------------------------------------------------
        log.write("[step 3/5] Collecting clone data...\n")

        # Optionally patch minimum-token param (CCFinderSW -w flag)
        min_tokens: int = int(params.get("min_tokens", 50))
        _orig_detect_cc = modules.collect_datas.detect_cc

        # Wrap detect_cc to inject min_tokens
        use_import_filter: bool = params.get("import_filter", True)

        def _patched_detect_cc(project_path, repo_name, language, commit_hash, exts):
            """detect_cc with runtime min_tokens override."""
            import subprocess
            from config import (
                CCFINDERSW_JAR,
                CCFINDERSW_JAVA_XMX,
                CCFINDERSW_JAVA_XSS,
                ANTLR_LANGUAGE,
            )
            from modules.collect_datas import convert_language_for_ccfindersw
            from config import CCFINDERSWPARSER

            try:
                dest_dir = project_root / "dest/temp/ccfswtxt" / repo_name / commit_hash
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file = dest_dir / language
                language_arg = convert_language_for_ccfindersw(language)
                base_cmd = [
                    "java",
                    f"-Xmx{CCFINDERSW_JAVA_XMX}",
                    f"-Xss{CCFINDERSW_JAVA_XSS}",
                    "-jar",
                    str(CCFINDERSW_JAR),
                    "D",
                    "-d",
                    str(project_path),
                    "-l",
                    language_arg,
                    "-o",
                    str(dest_file),
                ]
                token_str = str(min_tokens)
                if language in ANTLR_LANGUAGE:
                    cmd = [
                        *base_cmd,
                        "-antlr",
                        "|".join(exts),
                        "-w",
                        "2",
                        "-t",
                        token_str,
                        "-ccfsw",
                        "set",
                    ]
                else:
                    cmd = [*base_cmd, "-w", "2", "-t", token_str, "-ccfsw", "set"]
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                if result.stdout:
                    log.write(result.stdout)
                if result.stderr:
                    log.write(result.stderr)

                json_dest_dir = (
                    project_root / "dest/clones_json" / repo_name / commit_hash
                )
                json_dest_dir.mkdir(parents=True, exist_ok=True)
                json_dest_file = json_dest_dir / f"{language}.json"
                ccfsw_parser = _cfg.CCFINDERSWPARSER
                cmd = [
                    str(ccfsw_parser),
                    "-i",
                    str(f"{dest_file}_ccfsw.txt"),
                    "-o",
                    str(json_dest_file),
                ]
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                if result.stdout:
                    log.write(result.stdout)
                if result.stderr:
                    log.write(result.stderr)
            except subprocess.CalledProcessError as e:
                if e.stdout:
                    log.write(e.stdout)
                if e.stderr:
                    log.write(e.stderr)
                log.write("[error] CCFinderSW failed.\n")
                raise RuntimeError(
                    f"CCFinderSW failed for {repo_name} {commit_hash} {language}"
                ) from e

        # Monkey-patch for this run
        modules.collect_datas.detect_cc = _patched_detect_cc

        try:
            modules.collect_datas.collect_datas_of_repo(
                project,
                apply_import_filter=use_import_filter,
            )
        finally:
            modules.collect_datas.detect_cc = _orig_detect_cc

        # ------------------------------------------------------------------
        # 4. Analyse code clones
        # ------------------------------------------------------------------
        log.write("[step 4/5] Analysing code clones...\n")
        modules.analyze_cc.analyze_repo(project)

        # ------------------------------------------------------------------
        # 5. Analyse co-modification
        # ------------------------------------------------------------------
        log.write("[step 5/5] Analysing co-modification...\n")
        modules.analyze_modification.analyze_repo(project)

        log.write("[job] All steps completed successfully.\n")
        job["status"] = "completed"

    except Exception as exc:
        import traceback

        log.write(f"[error] {exc}\n")
        log.write(traceback.format_exc() + "\n")
        job["status"] = "error"
    finally:
        sys.stdout = old_stdout


# ---------------------------------------------------------------------------
# REST / WebSocket endpoints
# ---------------------------------------------------------------------------


@app.post("/api/run")
async def start_job(params: dict):
    """Start a new analysis job."""
    try:
        validated = _validate_run_params(params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"status": "queued", "log": None}
    thread = threading.Thread(target=_run_job, args=(job_id, validated), daemon=True)
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
            log: _LogCapture | None = job.get("log")
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
