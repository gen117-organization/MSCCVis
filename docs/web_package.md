# web パッケージ — 設定UI・パイプライン実行

## パッケージ構成

```
src/web/
├── __init__.py          # パッケージマーカー (空)
├── app.py               # FastAPI アプリケーション本体
├── pipeline_runner.py   # 6ステップ分析パイプライン
├── validation.py        # リクエストパラメータ検証
├── stdout_proxy.py      # スレッドローカル stdout プロキシ
└── static/
    ├── index.html        # 設定UI (HTML/CSS/JS 統合)
    └── app.js            # フロントエンドロジック (i18n, WebSocket)
```

---

### 1. 設計方針

- **目的**: GitHub リポジトリURLを入力し,クローン検出パイプラインをワンクリックで実行する Web UI を提供する.
- **アプローチ**: FastAPI + バックグラウンドスレッド + WebSocket ログストリーム. パイプラインの6ステップ (クローン → コミット選定 → 検出 → 分析 → 同時修正 → 可視化CSV) をシーケンシャルに実行し,リアルタイムでログをクライアントに配信する.
- **制約・トレードオフ**: `threading.Thread` による並行実行のため,複数ジョブが CPU を共有し,重いジョブの同時実行には不向き. `config` モジュールのグローバル変数をランタイムパッチする設計のため,同時ジョブ間でパラメータ競合の可能性がある (Step 2 の `finally` で復元を保証).

---

### 2. 入出力

**入力** (REST API):
- `POST /api/run` — パイプライン実行パラメータ (JSON)

```json
{
  "url": "https://github.com/owner/repo",
  "detection_method": "normal",
  "min_tokens": 50,
  "import_filter": true,
  "force_recompute": true,
  "analysis_method": "merge_commit",
  "search_depth": -1,
  "max_analyzed_commits": -1,
  "analysis_frequency": 1
}
```

**出力**:
- `{"job_id": "abc12345"}` — ジョブ識別子
- `WebSocket /ws/logs/{job_id}` — ログストリーム

```json
{"type": "log", "line": "[step 1/6] Cloning repository..."}
{"type": "status", "status": "completed"}
```

**生成ファイル** (パイプライン出力):
- `dest/projects/{owner.repo}/` — クローンしたリポジトリ
- `dest/clones_json/{owner.repo}/` — クローン検出結果 (JSON)
- `dest/modified_clones/{owner.repo}/` — 同時修正分析結果
- `dest/scatter/{owner.repo}/csv/` — 可視化用CSV
- `dest/services_json/{owner.repo}.json` — マイクロサービス検出結果

---

### 3. 処理フロー

```
Browser                    FastAPI (app.py)              Background Thread
   │                           │                              │
   ├── GET / ──────────────────┤                              │
   │◄── index.html ────────────┤                              │
   │                           │                              │
   ├── POST /api/run ──────────┤                              │
   │   {url, min_tokens, ...}  ├─ validate_run_params()       │
   │                           ├─ uuid 生成                   │
   │◄── {job_id} ──────────────┤                              │
   │                           ├─ Thread.start() ─────────────┤
   │                           │                  run_job()    │
   ├── WS /ws/logs/{job_id} ───┤                              │
   │                           │◄── log.lines ────────────────┤
   │◄── {type: "log", ...} ────┤   (0.3秒ポーリング)          │
   │                           │                              ├─ Step 1: clone_repo
   │◄── {type: "log", ...} ────┤                              ├─ Step 2: determine_commits
   │                           │                              ├─ Step 3: collect_datas
   │                           │                              ├─ Step 4: analyze_cc
   │                           │                              ├─ Step 5: analyze_modification
   │                           │                              ├─ Step 6: generate_viz_csv
   │◄── {type: "status",       │                              │
   │     status: "completed"}──┤                              │
```

---

### 4. コード解説

#### app.py — FastAPI アプリケーション

```python
app = FastAPI(title="MSCCATools Web UI")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"))
_dash_app = create_dash_app("/visualize/")
app.mount("/visualize", WSGIMiddleware(_dash_app.server))

_jobs: dict[str, dict] = {}
_stdout_proxy = ThreadLocalStdoutProxy(sys.stdout)
sys.stdout = _stdout_proxy
```

- **何をしているか**: FastAPI にDash アプリと静的ファイルをマウントし,標準出力をスレッドローカルプロキシに置換する.
- **なぜそうしているか**: 既存の `modules` パッケージが `print()` でログを出力するため,`sys.stdout` を差替えてジョブごとにログを分離する必要がある. Dash は WSGI アプリとして Starlette の `WSGIMiddleware` 経由でマウントし,FastAPI の ASGI と共存させる.

---

#### app.py — ジョブ起動とログストリーム

```python
@app.post("/api/run")
async def start_job(params: dict):
    validated = validate_run_params(params)
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"status": "queued", "log": None}
    thread = threading.Thread(
        target=run_job, args=(job_id, validated),
        kwargs={"jobs": _jobs, "stdout_proxy": _stdout_proxy, "project_root": project_root},
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id}

@app.websocket("/ws/logs/{job_id}")
async def stream_logs(websocket, job_id):
    await websocket.accept()
    sent = 0
    while True:
        log = _jobs[job_id].get("log")
        if log:
            while sent < len(log.lines):
                await websocket.send_json({"type": "log", "line": log.lines[sent]})
                sent += 1
        if _jobs[job_id]["status"] in ("completed", "error"):
            await websocket.send_json({"type": "status", "status": _jobs[job_id]["status"]})
            break
        await asyncio.sleep(0.3)
```

- **何をしているか**: バリデーション後にデーモンスレッドでパイプラインを起動し,WebSocket で 0.3 秒間隔のポーリングによりログ行を配信する.
- **なぜそうしているか**: 長時間 (数十分) かかるパイプラインをブロックせずに実行するため. `daemon=True` によりメインプロセス終了時にスレッドも自動終了する. WebSocket のポーリング方式は実装がシンプルで,`LogCapture.lines` リストの追記をそのまま差分送信できる.

---

#### pipeline_runner.py — 6ステップパイプライン

```python
def run_job(job_id, params, *, jobs, stdout_proxy, project_root):
    log = LogCapture(job_id)
    jobs[job_id]["log"] = log
    with stdout_proxy.redirect(log):
        url = params["url"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]

        # Step 1: クローン
        modules.clone_repo.clone_repo(url)

        # Step 2: コミット選定 (config をランタイムパッチ)
        _cfg.ANALYSIS_METHOD = analysis_method
        try:
            target_commits = dac.determine_analyzed_commits_by_mergecommits(workdir)
        finally:
            _cfg.ANALYSIS_METHOD = _orig_method  # 必ず復元

        # Step 3-5: 検出・分析・同時修正
        modules.collect_datas.collect_datas_of_repo(project, ...)
        modules.analyze_cc.analyze_repo(project)
        modules.analyze_modification.analyze_repo(project)

        # Step 6: 可視化CSV (失敗しても全体は止めない)
        try:
            _generate_visualization_csv(...)
        except Exception:
            log.write("[warn] Visualization CSV generation failed\n")
```

- **何をしているか**: 6ステップの分析パイプラインを順次実行し,各ステップのログを `LogCapture` に記録する.
- **なぜそうしているか**: Step 6 (可視化CSV) は必須ではないため `try/except` で囲み,失敗しても全体を完了扱いにする. Step 2 では `config` モジュールのグローバル変数を一時的にパッチするが,`finally` ブロックで必ず復元することでジョブ間の干渉を防止.

---

#### pipeline_runner.py — config ランタイムパッチ

```python
# Temporarily patch the config values
_orig_method = _cfg.ANALYSIS_METHOD
_cfg.ANALYSIS_METHOD = analysis_method
# Also patch the module that already imported them
dac.ANALYSIS_METHOD = analysis_method

try:
    target_commits = dac.determine_analyzed_commits_by_mergecommits(workdir)
finally:
    _cfg.ANALYSIS_METHOD = _orig_method
```

- **何をしているか**: `config` モジュールと `determine_analyzed_commits` モジュールの両方のグローバル変数をパッチし,`finally` で復元する.
- **なぜそうしているか**: `determine_analyzed_commits` は `from config import ANALYSIS_METHOD` でインポート時にコピーが作成されるため,両方をパッチする必要がある. この設計は依存性注入への移行が望ましいが,既存の `modules` パッケージとの互換性を維持するための妥協.

---

#### validation.py — パラメータ検証

```python
def validate_run_params(params: dict) -> dict:
    url = (params.get("url") or "").strip()
    if not url:
        raise ValueError("url is required")
    if not re.match(r"https?://", url):
        raise ValueError(f"url must start with http:// or https://")

    detection_method = params.get("detection_method", "normal")
    if detection_method not in ("normal", "tks", "rnr"):
        raise ValueError(f"detection_method must be 'normal', 'tks', or 'rnr'")

    tks = _parse_int(params.get("tks", 12), "tks")
    rnr = _parse_float(params.get("rnr", 0.5), "rnr")
    min_tokens = _parse_int(params.get("min_tokens", 50), "min_tokens")
    # ...
    return {"url": url, "detection_method": detection_method, ...}
```

- **何をしているか**: JSON パラメータの型変換・範囲検証を行い,不正な場合は `ValueError` を送出する.
- **なぜそうしているか**: フロントエンド (app.js) でもバリデーションを行うが,直接API呼び出しへの防御としてサーバー側でも二重チェックする. `_parse_int` / `_parse_float` により,文字列で送信されても正しく型変換する.

---

#### stdout_proxy.py — スレッドローカル stdout

```python
class ThreadLocalStdoutProxy:
    def __init__(self, default_stream: TextIO):
        self._default_stream = default_stream
        self._local = threading.local()

    @contextmanager
    def redirect(self, stream: TextIO) -> Iterator[None]:
        previous_stream = getattr(self._local, "stream", None)
        self._local.stream = stream
        try:
            yield
        finally:
            if previous_stream is None:
                delattr(self._local, "stream")
            else:
                self._local.stream = previous_stream

    def write(self, text: str) -> int:
        return self._get_stream().write(text)
```

- **何をしているか**: `threading.local()` を使い,各スレッドの `write()` 呼び出しを対応する `LogCapture` にルーティングする.
- **なぜそうしているか**: 既存モジュールの `print()` 出力をジョブごとに分離するため. `sys.stdout` をグローバルに1回だけ差替え,以降は `redirect()` コンテキストマネージャで各スレッドのストリームを切替える. コンテキスト終了時に前のストリームを復元するネスト対応設計.

---

#### static/app.js — フロントエンドロジック

```javascript
async function startAnalysis() {
    const params = {
        url: document.getElementById("url").value.trim(),
        detection_method: document.getElementById("detection_method").value,
        min_tokens: parseInt(document.getElementById("min_tokens").value),
        // ...
    };
    const errors = validateParams(params);
    if (errors.length > 0) { alert(errors.join("\n")); return; }

    const res = await fetch("/api/run", { method: "POST", body: JSON.stringify(params) });
    const { job_id } = await res.json();

    // WebSocket接続
    const ws = new WebSocket(`ws://${location.host}/ws/logs/${job_id}`);
    ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "log") appendLog(msg.line);
        if (msg.type === "status") { /* 完了/エラー表示 */ }
    };
}
```

- **何をしているか**: フォームからパラメータを収集し,クライアント側バリデーション後に `POST /api/run` を呼び出し,WebSocket でログをリアルタイム表示する.
- **なぜそうしているか**: サーバー側バリデーションの前にUXを向上させるクライアント側チェック. ログの色分け (`classifyLine`) で `[step]`, `[error]`, `[job]` の各行を視覚的に区別.

---

### 5. 課題・TODO

- TODO(gen): `detection_method` が `"normal"` 以外 (TKS, RNR) の場合,`run_job` が即時エラーで終了する. TKS/RNR パイプラインの実装が未完了.
- TODO(gen): `comod_method` が `"clone_set"` 以外の場合も同様にエラー終了. `clone_pair` 方式は未実装.
- TODO(gen): 同時ジョブ実行時の `config` モジュールパッチ競合. 排他制御 (`threading.Lock`) または依存性注入への移行を検討.
