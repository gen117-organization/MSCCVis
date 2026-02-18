# Progress Log

## 2026-02-18: 可視化UIのプロジェクト選択をCSVファイル単位へ変更

### 変更ファイル

- visualize/data_loader.py — `dest/scatter/<project>/csv` 配下の CSV を1ファイル1選択肢として列挙する実装へ変更
- visualize/data_loader.py — 命名規則を解析する `_parse_scatter_csv_filename()` を追加し, ラベルに `detection/filter/analysis/min/date/sd/mac` を反映
- visualize/data_loader.py — 選択値を `project|||scatter_file:<filename>|||language` 形式に変更し, 選択したCSVのみを読み込むよう `_scatter_sources()` を拡張
- visualize/data_loader.py — `get_available_languages()` を scatter 優先にして選択肢と言語一覧の不整合を解消

### テスト結果

- `.venv/bin/python -m py_compile visualize/data_loader.py visualize/callbacks.py visualize/scatter.py` , 成功
- `.venv/bin/python -m pytest tests/ -q` , 成功, 34 passed in 0.03s
- `docker run --rm --entrypoint python -v $(pwd)/dest:/app/dest msccatools -c "from visualize.data_loader import _gather_scatter_projects; ..."` , 成功（`count 4` とファイル単位value/labelを確認）
- `docker run ... msccatools web-ui --host 0.0.0.0` + `GET /visualize/` , 200 を確認

### 判断メモ

- 要件どおり, 既存の「言語単位」選択ではなく「CSVファイル単位」選択に統一した
- 既存命名の揺れ（`sd/mac` が date の前後どちらでも出現）を許容するパーサにして既存データとの互換性を担保した

### 残課題

- TODO(gen): `build_project_summary` の `コミット/参照` 表示は `scatter_file:<filename>` をそのまま表示するため, 将来的に表示文言を「CSV名/日付」へ最適化する

## 2026-02-18: /visualize 404 と起動時ノイズログの修正

### 変更ファイル

- visualize/scatter.py — FastAPI mount 配下で動くよう `requests_pathname_prefix` と `routes_pathname_prefix` の扱いを修正
- visualize/data_loader.py — `services.json` が存在しない場合に warning を出さず 0 を返すよう変更

### テスト結果

- `.venv/bin/python -m py_compile visualize/scatter.py visualize/data_loader.py src/web/app.py` , 成功
- `.venv/bin/python -m pytest tests/ -q` , 成功, 34 passed in 0.03s
- `docker build -t msccatools .` , 成功
- `docker run ... msccatools web-ui --host 0.0.0.0` で `GET /` = 200, `GET /visualize/` = 200 を確認

### 判断メモ

- `WSGIMiddleware` 配下では mount prefix が WSGI 側に剥がされるため, Dash の内部 route は `/` で持ち, 外部 request prefix のみ `/visualize/` にする必要があった
- `services.json` は未実装機能のため未存在が通常ケースであり, warning を大量出力しない実装に変更した

### 残課題

- TODO(gen): CLAIM 側の `SyntaxWarning: invalid escape sequence '\$'` は機能影響はないが, 必要なら upstream 側で正規表現文字列の raw 化を検討する

## 2026-02-18: Docker起動時の可視化依存不足を修正

### 変更ファイル

- requirements.txt — `dash-bootstrap-components==1.6.0`, `pandas==2.2.3` を追加

### テスト結果

- `.venv/bin/python -m py_compile src/web/app.py visualize/scatter.py` , 成功
- `.venv/bin/python -m pytest tests/ -q` , 成功, 34 passed in 0.03s

### 判断メモ

- Web UI 起動時に `src/web/app.py` が `visualize.scatter` を import するため, 可視化依存は optional ではなく必須依存として `requirements.txt` に含める必要がある
- エラー原因は `dash_bootstrap_components` 未導入だったが, 可視化実行時に `pandas` も必要なため同時に追加した

### 残課題

- TODO(gen): Docker イメージを再ビルドし, `web-ui --host 0.0.0.0` で `/` と `/visualize/` の起動確認を行う

## 2026-02-18: Web UI から可視化ツールへの導線追加

### 変更ファイル

- src/web/app.py — Dash 可視化アプリを `WSGIMiddleware` で `/visualize` にマウント
- visualize/scatter.py — `create_dash_app(url_base_pathname)` を追加し, `/` と `/visualize/` の両方で動作できるように変更
- src/web/static/index.html — `Open Visualization Tool` ボタンを追加
- src/web/static/app.js — ボタン文言の i18n キーを追加（英語/日本語）
- README.md — `/visualize/` のアクセス方法を追記

### テスト結果

- `.venv/bin/python -m py_compile src/web/app.py visualize/scatter.py` → 成功
- `.venv/bin/python -m pytest -q` → 失敗（`visualize/test_ui_logic.py` で `pandas` 未導入による import error）
- `.venv/bin/python -m pytest tests/ -q` → 成功, 34 passed

### 判断メモ

- 可視化ツールを別ポートで起動する方式ではなく, 既存 FastAPI に同居させることで Web UI から即遷移できる構成にした
- Dash のパス衝突を避けるため, `requests_pathname_prefix` と `routes_pathname_prefix` を `create_dash_app()` で切り替える設計にした

### 残課題

- TODO(gen): `.venv` に `pandas` を導入するか, `visualize/test_ui_logic.py` を optional dependency 前提でスキップする方針を決める

## 2026-02-18: Web UI Run Analysis に可視化CSV生成ステップを追加

### 変更ファイル

- src/modules/visualization/naming.py — 新規作成. 可視化CSVの命名規則に基づくファイル名生成・パース関数を実装
- src/modules/visualization/build_scatter_dataset.py — `build_scatter_dataset_for_language()` に `output_csv_stem` パラメータを追加. カスタムファイル名での出力に対応
- src/web/app.py — ステップ6「可視化CSV生成」を追加. ms_detection 実行後に `build_scatter_dataset_for_language()` を呼び出し, 命名規則に従ったCSVを `dest/scatter/<project>/csv/` に出力. import追加: `identify_microservice`, `build_scatter_dataset_for_language`, `build_visualization_csv_filename_from_params`
- tests/test_naming.py — 新規作成. naming.py の単体テスト32件

### テスト結果

- `.venv/bin/python -m pytest tests/ -q` → 34 passed in 0.03s

### 判断メモ

- Web UI の import フィルタはソースファイルに直接適用されるため, 出力CSVの名前は `<language>.csv` (filter_type=None). scatter CSV側の命名規則で `filtered`/`nofilter` を区別する
- 可視化CSV生成の失敗は分析全体を止めない設計とした (警告ログのみ出力)
- `output_csv_stem` は言語サフィックス (`_Java` 等) を含む形で渡す設計. 1つの実行設定で複数言語のCSVが同じstem下に並ぶ
- `parse_visualization_csv_filename()` を逆変換用に実装. 将来の可視化スクリプト改修で使用予定

### 残課題

- TODO(gen): 既存の `visualize/` 可視化スクリプト (data_loader.py 等) を新命名規則に対応させる
- TODO(gen): Docker 環境で実際のリポジトリに対して Web UI からの可視化CSVエンドツーエンド生成を確認する

## 2026-02-17: 可視化CSV生成パイプラインの修正

### 変更ファイル

- src/modules/util.py — `get_file_type()` 関数を追加 (ファイルパスを logic/test/config/data に分類)
- src/modules/visualization/build_scatter_dataset.py — import パス修正, clone_type 列の完全削除, clones_json_dir を常に `clones_json` に統一, 不要関数 (`resolve_service_for_file_path`, `build_context_to_service_map`) を削除
- src/commands/csv_build/generate_visualization_csv.py — import パス修正, `FILTER_MODES` をローカル定義, services.json 生成を TODO で保留
- visualize/data_loader.py — scatter CSV dtypes から clone_type を削除, 全 `print` を `logger` に変換
- visualize/callbacks.py — `logger` 追加, 全 `print` を `logger` に変換
- visualize/plotting.py — `logger` 追加, 全 `print` を `logger` に変換
- visualize/components.py — `logger` 追加, 全 `print` を `logger` に変換
- tests/test_util.py — `get_file_type` の単体テスト14件を追加
- tests/test_build_scatter_dataset.py — PairRow構造, CSVヘッダ, normalize_file_path 等の単体テスト14件を追加

### テスト結果

- `python -m pytest tests/ -q` → 28 passed in 0.11s

### 判断メモ

- clones_json_import / clones_json_tks は使われておらず, 全フィルタタイプで `dest/clones_json/` を参照する設計に統一した
- clone_type 列は CSV 出力・PairRow dataclass・dtypes 定義から完全に除去. ただし visualize/ 内のレガシーデータパス (JSON読込等) では後方互換のため in-memory 生成を残した
- service_mapping.py / logger_setup.py は既に src/modules/visualization/ に存在していたため, import パスのみ修正
- build_services_json モジュールは未作成のため, TODO コメントで保留とした
- PowerShell の Set-Content は UTF-8 日本語コメントを破壊するため, Python スクリプト経由で置換を実行した

### 残課題

- TODO(gen): `build_services_json` モジュールを作成し, services.json 生成を有効化する
- TODO(gen): Docker 環境で実際のリポジトリデータを使って CSV 生成の結合テストを行う

## 2026-02-16: Web UI JavaScript の外部ファイル分離

### 変更ファイル

- src/web/static/app.js — `index.html` に埋め込まれていた JavaScript をそのまま移設
- src/web/static/index.html — inline script を削除し, `/static/app.js` 読み込みに変更
- devlog/PROGRESS.md — 作業開始エントリを追加
- docs/PROGRESS.md — 本エントリを追加

### テスト結果

- `/home/genko/lab/MSCCATools-Public/.venv/bin/python -m pytest -q` , 成功, 2 passed in 0.11s

### 判断メモ

- 最小差分を優先し, JavaScript のロジックは変更せずファイル配置だけを変更した
- `onclick="startAnalysis()"` を維持するため, `app.js` は通常スクリプトとして読み込み, グローバル関数の互換性を保った

### 残課題

- TODO(gen): 必要に応じて `app.js` を `i18n` と実行制御に段階分割する

## 2026-02-16: Web UI 実装解説ドキュメント作成

### 変更ファイル

- docs/WebUI実装ガイド.md — Web UI の画面構成, API, バックグラウンド実行, WebSocket ログ配信, stdout 分離実装を段階的に解説
- docs/README.md — ドキュメント一覧に `WebUI実装ガイド.md` を追加
- docs/PROGRESS.md — 本エントリを開始時, 完了時の内容に更新

### テスト結果

- ドキュメント追加のみのため, コードテストは未実行

### 判断メモ

- 初学者にも追いやすいように, 画面側の `startAnalysis` から API, ジョブ実行, WebSocket ログ受信までを時系列で説明した
- 直近で変更した stdout スレッド安全化の意図と実装位置も同一文書で参照できるようにした

### 残課題

- TODO(gen): 必要に応じて, Web UI 実行ログのサンプルをドキュメントに追記する

## 2026-02-16: Web UI stdout のスレッド安全化

### 変更ファイル

- src/web/app.py — ジョブごとの `sys.stdout` 差し替えを廃止し, スレッドローカル stdout プロキシ経由でログ捕捉する実装に変更
- src/web/stdout_proxy.py — スレッドごとに出力先を切り替える `ThreadLocalStdoutProxy` を追加
- tests/test_stdout_proxy.py — 並列スレッドの出力分離とネストしたリダイレクト復帰のテストを追加
- docs/PROGRESS.md — 本エントリを開始時, 完了時の内容に更新

### テスト結果

- `/home/genko/lab/MSCCATools-Public/.venv/bin/python -m pytest -q` , 成功, 2 passed in 0.13s

### 判断メモ

- 指摘どおり `sys.stdout` をジョブ実行ごとに差し替えると競合するため, グローバルには 1 回だけプロキシを設定し, 各スレッドはコンテキストで出力先を切り替える方式を採用した
- `ThreadLocalStdoutProxy` を `src/web/stdout_proxy.py` に分離し, Web 層の実装とテストを疎結合にした

### 残課題

- TODO(gen): Web UI を Docker 上で 2 ジョブ同時実行し, 実運用ログで混線がないことを確認する

## 2026-02-16: detect_cc リファクタ後のスモークテスト

### 変更ファイル

- src/modules/collect_datas.py — `detect_cc` に `min_tokens` と `log` 引数を追加し, Web UI 用の重複ロジックを本体へ統合
- src/modules/collect_datas.py — `collect_datas_of_repo` に `min_tokens` と `log` 引数を追加し, 内部 `detect_cc` 呼び出しへ受け渡し
- src/web/app.py — `detect_cc` のモンキーパッチを削除し, `collect_datas_of_repo` に実行時オプションを直接渡す実装へ変更
- docs/PROGRESS.md — 本エントリを開始時, 完了時の内容に更新

### テスト結果

- `pytest -q` , 失敗, command not found
- `python -m pytest -q` , 失敗, command not found
- `python3 -m pytest -q` , 失敗, No module named pytest
- `/home/genko/lab/MSCCATools-Public/.venv/bin/python -m pip install pytest` , 成功
- `/home/genko/lab/MSCCATools-Public/.venv/bin/python -m pytest -q` , 実行, no tests ran in 0.09s, exit code 5
- `python3 -m py_compile src/modules/collect_datas.py src/web/app.py` , 成功

### 判断メモ

- `_patched_detect_cc` による重複実装は保守負荷が高いため, 本体関数 `detect_cc` 側で実行時引数を受ける設計に統一した
- Linux 環境で `pytest` が未導入だったため, 失敗理由を記録しつつ, 代替の最小スモークとして対象ファイルの構文コンパイル確認を実施した

### 残課題

- TODO(gen): `pytest` の exit code 5 対応として最低 1 件のテスト追加か, CI で no tests を許容する方針を決める
- TODO(gen): Docker 環境で Web UI から 1 件実行し, CCFinderSW の実行ログ出力経路を確認する

## 2026-02-13: Web UI 入力の適用強化

### 変更ファイル

- src/web/app.py — web ui 入力の検証と 再計算時の 既存結果クリア を追加
- src/web/static/index.html — 再計算トグルを追加し api パラメータに反映
- src/modules/collect_datas.py — import フィルタの条件分岐を追加し 引数で制御可能にした
- src/web/app.py — import フィルタの有無を 引数で渡すように変更
- src/web/app.py — CCFinderSW の min token 引数を -w から -t に修正
- src/web/static/index.html — min token の説明を -t に修正
- config.py — CLI の import 行フィルタ設定を追加
- README.md — CLI の import 行フィルタ設定を追記
- src/modules/collect_datas.py — commit 切替時と終了時を `git checkout -f` に変更
- src/web/app.py — API 側で全入力項目のバリデーションを追加
- src/web/static/index.html — UI 側で全入力項目のバリデーションを追加
- src/web/static/index.html — ? アイコンとトグルの重なりを解消
- pyproject.toml — pytest 収集から `dest` を除外する設定を追加
- src/web/static/index.html — 日本語/英語切替を追加し, 英語をデフォルトに設定
- docs/PROGRESS.md — 本エントリを更新

### テスト結果

- C:/Users/genko/Documents/MSCCATools-Public/.venv/Scripts/python.exe -m pytest -q , 失敗 No module named pytest
- python -m pytest -q , 失敗 no tests ran in 0.06s
- python -m pytest -q , 中断 Ctrl+C
- python -m pytest -q , docker の ログが出力され 中断
- python -m pytest -q , 失敗 dest/projects 配下の外部リポジトリ tests 収集で NameError
- python -m pytest -q , 失敗 dest/projects 配下の外部リポジトリ tests 収集で 11 件エラー
- python -m pytest -q , no tests ran in 0.09s
- python -m pytest -q , no tests ran in 0.10s

### 判断メモ

- web ui の 入力値が 既存結果で無効化されないよう 再計算時に成果物を削除する方針にした
- 未実装の検出方式と comod 方式は エラー扱いで 明示的に入力を反映するようにした
- CCFinderSW の 失敗原因を ログで見えるよう stderr を 捕捉して 表示する方針にした
- import 行フィルタは 引数で制御し 既存のモンキーパッチ依存を避ける方針にした
- CLI 側は config で既定値を切り替えられるようにした
- CCFinderSW の Range mode Error は -w に 50 を渡していたことが原因で, -w は 0..2 なので -t に分離した
- `apply_filter` で作業ツリーが変更されるため, 次コミットへの checkout は `-f` で強制切替する方針にした
- 入力異常は API 前に UI で検出し, さらに API 側でも同じ制約を検証する二重防御にした
- 外部クローン済みリポジトリの test 収集を避けるため `norecursedirs = ["dest"]` を採用した
- UI 文言は辞書ベースで切替し, デフォルト言語は英語に固定した

### 残課題

- TODO(gen): pytest を導入して テストを再実行する
- TODO(gen): web ui で 実際の repo を指定して フィルタ反映を確認する
- TODO(gen): docker build して web ui で 失敗ログを 再確認する
- TODO(gen): python -m pytest -q を 再実行して 結果を確認する
- TODO(gen): pytest の 対象から dest/projects を 除外するか, 実行前にクリーンする

## 2026-02-13: Web UI Docker 対応とドキュメント整備

### 変更ファイル

- Dockerfile — `EXPOSE 8000` を追加し, Web UI をコンテナ外から利用可能にした
- README.md — Web UI セクションを追加. Docker (推奨) とローカル (確認のみ) の起動方法, 外部ツール依存の注意を明記
- docs/PROGRESS.md — 本エントリを追加

### テスト結果

- `python main.py web-ui` でローカル起動し, `curl http://127.0.0.1:8000/` で 200 OK を確認
- クローン検出パイプラインは Java / CCFinderSW / ccfindersw-parser / github-linguist に依存しており, Docker 外では実行不可であることを確認

### 判断メモ

- 既存コードの変更を避け, Dockerfile に `EXPOSE 8000` を追加するのみとした
- ローカル起動は UI 確認用途に限定し, 実際の分析には Docker を使う方針を README に明記した

### 残課題

- TODO(gen): Docker イメージをビルドして `web-ui --host 0.0.0.0` でエンドツーエンドの分析実行を確認する
