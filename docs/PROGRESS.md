# Progress Log

## 02-25 プロジェクト発見ロジック改善 (services.json ベース)

### 変更ファイル

- `src/visualize/data_loader/project_discovery.py` — `get_project_names()` を `dest/scatter` + `dest/services_json` の両方から走査するよう拡張. `get_csv_options_for_project()` に scatter CSV がないプロジェクト向けの services.json `language_stats` フォールバックを追加. `get_available_projects_enhanced()` を scatter + services_json マージに変更. `_gather_services_json_projects()` 新規追加. `get_available_languages()` も services.json を考慮
- `src/visualize/data_loader/csv_loader.py` — `resolve_services_json_path()` 新規追加 (`dest/services_json/` 優先, `dest/scatter/` フォールバック). `load_and_process_data()` の services.json パスを `resolve_services_json_path` に変更. `load_clone_metrics()` からfilter_type引数を除去 (不要). enriched CSV パスのバグ修正
- `src/visualize/data_loader/__init__.py` — `resolve_services_json_path` をエクスポートに追加
- `src/visualize/components/summary.py` — services.json パスを `resolve_services_json_path` に変更
- `src/web/pipeline_runner.py` — enriched CSV パスを正しい `enriched_dir/name/language.csv` 形式に修正. メトリクス JSON ファイル名を `{name}_{language}.json` に簡略化
- `src/commands/csv_build/generate_visualization_csv.py` — 同上のパス修正
- `tests/test_project_discovery.py` — **新規**: プロジェクト発見テスト (4件). services.json のみのプロジェクト発見, 空 dest, フォールバック, scatter 優先
- `tests/test_load_clone_metrics.py` — filter_type 引数除去に合わせて修正

### テスト結果

- `pytest tests/ -q` — 50 passed (0.66s)

### 判断メモ

- services.json パス統一: `dest/services_json/{project}.json` を主にし `dest/scatter/{project}/services.json` をフォールバックとした. 既存の scatter フローにも対応しつつ, パイプラインで生成される services_json を直接活用可能に
- プロジェクト発見: scatter CSV がある場合は従来の詳細ラベル, ない場合は services.json の language_stats からサービス数・ファイル数・LOC を表示する簡易ラベル
- scatter CSV なしのプロジェクトでは散布図は「No data source found」となるが, Stats ビューの clone metrics は表示可能
- enriched CSV パスバグ: 前セッションで `enriched_dir/name_lang_filter.csv` と書いていたが正しくは `enriched_dir/name/lang.csv`

### 残課題

- TODO(gen): summary.py の return 文後の deadcode (~500 行) を削除するクリーンアップ
- TODO(gen): 大規模データでの modified_commits パース性能最適化

## 02-25 クローンメトリクス パイプライン統合 & Stats ビュー表示

### 変更ファイル

- `src/web/pipeline_runner.py` — enriched_fragments 生成後にクローンメトリクス JSON を `dest/clone_metrics/` へ保存するステップを追加
- `src/commands/csv_build/generate_visualization_csv.py` — CLI バッチでも同様にクローンメトリクス JSON 生成ステップを追加
- `src/visualize/data_loader/csv_loader.py` — `load_clone_metrics()` 関数を新規追加. `dest/clone_metrics/{project}_{language}_{filter_type}.json` を読み込む
- `src/visualize/data_loader/__init__.py` — `load_clone_metrics` をエクスポートに追加
- `src/visualize/components/summary.py` — `_build_clone_metrics_section()` / `_metrics_datatable()` を新規追加. Stats ビューにサービス/クローンセット/ファイル粒度のメトリクスをアコーディオン形式で表示
- `tests/test_load_clone_metrics.py` — **新規**: `load_clone_metrics` の単体テスト (4件)

### テスト結果

- `pytest tests/ -q` — 46 passed (0.65s)

### 判断メモ

- メトリクス保存形式: JSON を選択. 3 粒度の辞書構造がそのまま保持でき, Stats ビューで直接読み込める. CSV だと 3 ファイルに分割が必要だった
- 出力パス: `dest/clone_metrics/{project}_{language}_{filter_type}.json`. enriched_fragments と同じ命名規則に統一
- UI: Dash Accordion + DataTable を使用. 初期状態は折り畳みで, データ量が多い場合もページネーション (10行/ページ) でパフォーマンス維持
- summary.py の deadcode (return 後の ~500 行) は今回は触れず, 別途クリーンアップタスクとする

### 残課題

- TODO(gen): summary.py の return 文後の deadcode (~500 行) を削除するクリーンアップ
- TODO(gen): 大規模データでの modified_commits パース性能最適化

## 02-25 クローンメトリクス計算モジュール実装

### 変更ファイル

- `src/modules/visualization/compute_clone_metrics.py` — **新規**: enriched_fragments.csv から 3 粒度 (サービス/クローンセット/ファイル) のクローンメトリクスを計算するモジュール. pandas groupby ベースの純粋関数群
- `tests/test_compute_clone_metrics.py` — **新規**: compute_clone_metrics の単体テスト (27件). 各粒度の基本計算, エッジケース (空データ, 未解決サービス), 統合テスト
- `src/visualize/clone_analytics.py` — プレースホルダー (`return 0.0`) を compute_service_metrics の ROC 平均値に置き換え
- `docs/compute_clone_metrics.md` — **新規**: クローンメトリクス計算モジュールの設計ドキュメント

### テスト結果

- `pytest -v` — 44 passed (0.85s), 既存17件 + 新規27件

### 判断メモ

- 同時修正の定義: 既存 calculate_comodification_rate.py を踏襲. 同一コミットで 2 つ以上のフラグメントが修正されている場合を「同時修正」とカウント
- クロスサービス判定: service が空文字 (未解決) のフラグメントはサービス数カウントから除外. 2 サービス以上に跨る場合にクロスサービスと判定
- ROC の分母: enriched_fragments.csv にはクローン断片のみ含まれるため, services.json の language_stats.total_loc を使用
- modified_commits の JSON パース: iterrows + json.loads によるパースのため大規模データではボトルネックになり得るが, 現時点では十分な性能

### 残課題

- ~~TODO(gen): compute_all_metrics の出力を CSV/JSON に保存するパイプライン統合~~ → 完了
- ~~TODO(gen): 可視化 UI (Stats ビュー) でのメトリクス表示~~ → 完了
- TODO(gen): 大規模データでの modified_commits パース性能最適化

## 02-25 散布図CSV生成トグル追加

### 変更ファイル

- `src/web/static/index.html` — 「散布図用CSVを生成」トグルスイッチを force_recompute の下に追加
- `src/web/static/app.js` — i18n (en/ja) エントリ追加, `applyLanguage()` にラベル・説明文の反映追加, `startAnalysis()` のパラメータ収集に `generate_scatter_csv` 追加
- `src/web/validation.py` — `generate_scatter_csv` を `_parse_bool()` でバリデーション, 戻り値辞書に追加
- `src/web/pipeline_runner.py` — `_generate_visualization_csv()` 内で `generate_scatter_csv` フラグを参照し, false の場合は scatter CSV 生成をスキップ. enriched fragments CSV は常に生成

### テスト結果

- `pytest -v` — 17 passed (0.89s)

### 判断メモ

- enriched fragments CSV はメトリクス計算の基盤データであり常に必要なため, スキップ対象にしなかった
- トグルのデフォルトは ON (checked) で後方互換を維持
- scatter CSV スキップ時はログに明示的にメッセージを出力

### 残課題

- なし

## 02-25 services.json 拡充・enriched_fragments.csv 新設

### 変更ファイル

- `src/modules/visualization/enrich_services.py` — **新規**: services.json に `language_stats` セクション (サービス別 file_count, total_loc, 未解決ファイル数) を追記するモジュール
- `src/modules/visualization/build_enriched_fragments.py` — **新規**: フラグメント粒度の enriched CSV を生成するモジュール. scatter CSV の O(n²) ペア展開と異なり, O(n) で断片をそのまま出力
- `src/web/pipeline_runner.py` — Web UI パイプラインに enriched_fragments 生成ステップを追加
- `src/commands/csv_build/generate_visualization_csv.py` — CLI バッチにも enriched_fragments 生成ステップを追加. services.json 未実装 TODO を解消
- `pyproject.toml` — `pythonpath = ["src"]` 追加 (tests/ ディレクトリからのインポート解決)
- `tests/test_enrich_services.py` — **新規**: enrich_services の単体テスト (6件)
- `tests/test_build_enriched_fragments.py` — **新規**: build_enriched_fragments の単体・結合テスト (9件)

### テスト結果

- `pytest -v` — 17 passed (3.65s), 既存2件 + 新規15件

### 判断メモ

- scatter CSV はペアベース (散布図専用) で維持. メトリクス計算にはフラグメント粒度が適切なため, 新データソースとして enriched_fragments.csv を並行生成する方針
- services.json の `language_stats` は言語ごとに追記する形式. 既存の `services` / `URL` キーは一切変更せず後方互換を維持
- `enrich_services_json()` は `build_enriched_fragments_for_language()` 内で呼び出される設計. 同じ clones_json / service_contexts を共有するためセットアップの重複を回避
- token_count はユーザー指示により今回スキップ (clones_json の clone_sets がリスト形式の場合に 0 になる既知問題は別途対応)

### 残課題

- TODO(gen): clones_json の clone_sets がリスト形式の場合の token_count パース修正
- TODO(gen): enriched_fragments.csv を使ったメトリクス計算モジュールの実装
- TODO(gen): 散布図の座標順序改善 (file_id をサービス密度順ソート)

## 02-24 サイドバー折りたたみ修正・設計ドキュメント生成

### 変更ファイル

- `src/visualize/components/layout.py` — 折りたたみ時の "M" 短縮テキストを削除. ブランドテキスト自体を非表示にし,トグルボタンのみ表示にする方式に変更
- `src/visualize/assets/02_ide_theme.css` — `.sidebar-brand-short` スタイル削除. 折りたたみ時に `.sidebar-brand-inner` も非表示にするルール追加
- `docs/visualize_overview.md` — **新規**: visualize パッケージ概要・data_loader 設計ドキュメント
- `docs/visualize_callbacks.md` — **新規**: callbacks パッケージ設計ドキュメント (フィルタチェーン, i18n, ビュー切替)
- `docs/visualize_components.md` — **新規**: components パッケージ設計ドキュメント (レイアウト, 差分比較, メトリクス)
- `docs/visualize_utilities.md` — **新規**: ユーティリティモジュール設計ドキュメント (plotting, network, utils, clone_analytics)
- `docs/web_package.md` — **新規**: web パッケージ設計ドキュメント (FastAPI, パイプライン, バリデーション, stdout_proxy)

### テスト結果

- `pytest -q` — 2 passed (4.08s)

### 判断メモ

- 折りたたみ時の "M" テキストはユーザーからの指摘で分かりにくいと判断. トグルボタン (chevron) だけで十分にサイドバーの存在と操作方法が伝わるため,ブランド要素は完全に非表示にする方針に変更
- ドキュメントは visualize と web の2大パッケージについて,機能単位で5ファイルに分割して作成. 各ファイルは「設計方針・入出力・処理フロー・コード解説・課題」の5セクション構成

### 残課題

- TODO(gen): `summary.py` (1481行) の3機能分割検討
- TODO(gen): `explorer_callbacks.py` のファイルパス解決改善 (同名ファイルの誤マッチ)
- TODO(gen): TKS/RNR パイプライン実行の web UI 対応
- TODO(gen): `clone_analytics.py` のクローン比率計算実装

## 02-25 ブランドアイコン削除・言語ドロップダウン修正

### 変更ファイル

- `src/visualize/components/layout.py` — `bi-braces` アイコン削除, 折りたたみ時用の短縮ブランド "M" 追加
- `src/web/static/index.html` — 設定画面側の `bi-braces` アイコン削除
- `src/visualize/assets/02_ide_theme.css` — `.sidebar-brand-icon` → `.sidebar-brand-short` に変更 (通常時非表示, 折りたたみ時表示). `.sidebar-footer` に `position: relative` 追加. 言語ドロップダウンが上方向に開くCSS追加 (`.Select-menu-outer { bottom: 100%; top: auto; }`)

### テスト結果

- `pytest -q` — 2 passed

### 判断メモ

- アイコン削除後,折りたたみ時にブランド領域が空になるため,短縮テキスト "M" を表示する方式を採用
- 言語ドロップダウンが画面外に出る根本原因は `.app-sidebar { overflow: hidden }` で下方向のメニューがクリップされていたこと. `overflow` を変更するとサイドバー全体に影響するため,ドロップダウン自体を上方向に開く方式で対処

### 残課題

- TODO(gen): 設定画面 (index.html) の言語セレクタはネイティブ `<select>` のため今回の修正対象外

## 02-24 CSS読み込み順序修正・サイドバー表示統一

### 変更ファイル

- `src/visualize/assets/` — CSSファイルに番号プレフィックスを付与して読み込み順を制御
  - `reset.css` → `00_reset.css`, `layout.css` → `01_layout.css`, `ide_theme.css` → `02_ide_theme.css`, `components.css` → `03_components.css`, `custom.css` → `04_custom.css`
- `src/visualize/assets/01_layout.css` — bodyグラデーション背景・padding・min-heightを削除 (サイドバーレイアウトと衝突)
- `src/visualize/assets/02_ide_theme.css` — `background-color` → `background` shorthandに変更 (グラデーションを確実にリセット), `line-height: 1.6` 追加
- `src/visualize/data_loader/project_discovery.py` — `SCATTER_FILE_COMMIT_PREFIX` のインポート漏れを修正 (NameError解消)
- `src/web/validation.py` — `tks` を `_parse_bool` → `_parse_int` (デフォルト12, >= 1 検証), `rnr` を `_parse_bool` → `_parse_float` (デフォルト0.5, (0,1] 検証), `detection_method` に "rnr" を追加

### テスト結果

- `pytest src/visualize/test_ui_logic.py -q` — 2 passed
- Dashアプリ起動確認: `create_dash_app('/visualize/')` — OK
- Docker ビルド・起動: 設定画面・可視化画面共に正常表示

### 判断メモ

- CSS読み込み順序の逆転が根本原因: Dashはassets/をアルファベット順で読み込むため, `reset.css`(r) が `ide_theme.css`(i) の後に読み込まれスタイルをリセットしていた
- `layout.css` のbodyグラデーション背景は旧レイアウト用で, 現在のサイドバーレイアウトでは不要と判断して削除
- `background-color` では `background` shorthand (gradient) を上書きできないため,  shorthandに変更

### 残課題

- TODO(gen): 設定画面と可視化画面でカードのbox-shadow/hover効果が異なる — 統一するか要検討

## 07-04 web/visualize パッケージ構造リファクタリング (5段階)

### 変更ファイル

- `visualize/` → `src/visualize/` — パッケージを src/ 配下に移動,インポートパスを統一
- `src/visualize/components.py` (3135行) → `src/visualize/components/` パッケージに分割
  - `clone_metrics.py` (297行), `summary.py` (1480行), `layout.py` (876行), `clone_detail.py` (380行), `explorer.py` (148行)
- `src/visualize/callbacks.py` (1696行) → `src/visualize/callbacks/` パッケージに分割
  - `scatter_callbacks.py` (624行), `explorer_callbacks.py` (260行), `nav_callbacks.py` (125行), `filter_callbacks.py` (542行)
  - デッドコード約200行を削除 (旧on_dashboard_click, update_network_graph_callback)
- `src/visualize/data_loader.py` (1568行) → `src/visualize/data_loader/` パッケージに分割
  - `project_discovery.py` (548行), `csv_loader.py` (991行), `file_tree.py` (59行)
- `src/web/app.py` (496行→109行) — パイプライン実行とバリデーションを分離
  - `src/web/pipeline_runner.py` (319行): 分析パイプライン実行ロジック
  - `src/web/validation.py` (115行): パラメータ検証・型変換
- 各パッケージの `__init__.py` で後方互換性のためシンボルを再エクスポート

### テスト結果

- `pytest src/visualize/test_ui_logic.py -q` — 2 passed (各ステップ後に確認)
- インポートテスト: `src.visualize.scatter.create_dash_app`, `src.visualize.callbacks`, `src.visualize.data_loader`, `src.web.pipeline_runner` 全てOK

### 判断メモ

- web と visualize は統合しない判断: FastAPI (REST/WebSocket) と Dash (可視化) で責務が異なるため維持
- 分割しない方針の例: csv_loader.py (991行) はデータ読み込みチェーンが密結合しているため細分化せず
- callbacks分割時,デッドコード (return文の後のコメントアウト済みコードブロック) を発見・削除
- pipeline_runner.py は外部モジュール (modules.*) を遅延インポートに変更し依存チェーンを軽減

### 残課題

- TODO(gen): csv_loader.py (991行) の一部関数が50行超 — load_from_no_imports_json (161行), load_from_project_csv (189行) の内部リファクタリングは将来課題
- TODO(gen): summary.py の build_project_summary (730行) も巨大 — 段階的な分割を検討

## 02-20-04:30 UIバグ修正4件: CSS/ボタン配置/散布図表示/ラベル改善

### 変更ファイル

- src/web/static/index.html — CSS変数 (`--sidebar-width` 等) が `:root` ブロック外に配置されていたバグを修正 (サイドバーが上部に表示される問題). 折りたたみボタンをブランドエリアへ, ヘルプボタンをフッターへ移動
- visualize/components.py — `_build_nav_sidebar()`: 折りたたみボタン (`sidebar-toggle`) をブランドエリアに配置, ヘルプボタン (`help-btn`) を言語セレクタ横のフッターに移動. Dataset ドロップダウン幅を 520px に拡大, `optionHeight=50` 追加
- visualize/assets/ide_theme.css — `.sidebar-collapse-btn` を `position: absolute` からインラインフレックスアイテムに変更
- visualize/data_loader.py — `_build_descriptive_label()` ヘルパー追加. `normal` → `CCFinderSW (Normal)`, `filtered` → `Import Filtered` 等の人間可読マッピング. `get_csv_options_for_project()` と `_gather_scatter_projects()` で使用
- visualize/plotting.py — `create_scatter_plot()` の `customdata` 構築で `clone_type` をハードコードしていた4箇所を `method_col` 変数に修正 (KeyError: 'clone_type' 解消)

### テスト結果

- `pytest tests/ -q` — 33 passed in 0.09s
- Docker コンテナでの `create_scatter_plot()` 実行: 460点, 2トレース正常生成
- `ast.parse` — plotting.py 構文チェック OK

### 判断メモ

- 散布図の KeyError 原因: `plotting.py` が `customdata` で `clone_type` 列を直接参照していたが, scatter CSV フォーマットにはこの列が存在しない. 168行目で既に `method_col` として `detection_method` or `clone_type` を選択していたため, それを使うよう統一
- Dataset ラベル: パイプ区切りの生値 (`Python|normal|50|filtered|...`) から説明的ラベル (`Language: Python, Detection: CCFinderSW (Normal), ...`) に変更. ドロップダウン幅も拡大
- CSS変数バグ: `:root {}` の閉じ括弧の後に変数定義が追加されていたため, CSS全体のパースが壊れていた

### 残課題

- TODO(gen): ブラウザでの散布図表示の最終動作確認

## 02-20-02:00 UIリデザイン: BALES CLOUD型サイドバーナビゲーション導入

### 変更ファイル

- visualize/components.py — `create_ide_layout()` を全面書き換え. 左サイドバーナビゲーション (`_build_nav_sidebar()`) + ヘルプモーダル (`_build_help_modal()`) を新規追加. レイアウトを `app-container` グリッド (sidebar + main) に変更. ビュー切替ボタンをサイドバー `nav-link` に移行
- visualize/assets/ide_theme.css — 全面書き換え (~480行). 旧ヘッダー/ビュースイッチャー削除, `.app-container`, `.app-sidebar`, `.nav-link`, `.content-header`, `.content-body`, `.view-panel` 等のサイドバーレイアウト CSS を追加. CSS変数: `--sidebar-width: 220px`, `--sidebar-collapsed-width: 56px`
- visualize/callbacks.py — `toggle_view_mode` に7番目の Output (`page-title`) 追加. クラス名を `nav-link`/`view-panel` に変更. ヘルプモーダルトグル・サイドバー折りたたみ (clientside callback) を追加
- visualize/assets/i18n.js — 旧キー (`headerTitle`, `btnScatter` 等) 削除, サイドバー用キー (`navSettings`, `navScatter`, `navListView`, `navStats`) 追加
- visualize/scatter.py — Bootstrap Icons CDN を `external_stylesheets` に追加
- src/web/static/index.html — サイドバーナビゲーション追加 (検出設定ページ統一). `page-layout` グリッド構造, Bootstrap Icons CDN, インラインCSS (~100行) 追加. "可視化ツールを開く" ボタン削除
- src/web/static/app.js — 削除された要素 (`lang-label`, `btn-visualize`) への `setText` 呼び出しを除去. サイドバーナビの `data-i18n-key` 属性による動的翻訳を追加. I18N辞書に `navSettings`/`navScatter`/`navListView`/`navStats` キー追加

### テスト結果

- `pytest tests/ -q` — 33 passed in 0.08s
- `python -c "ast.parse(...)"` — components.py, callbacks.py 構文チェック OK

### 判断メモ

- BALES CLOUD (CRM SaaS) のスクリーンショットを参考デザインとして採用. 左サイドバー + メインコンテンツエリアの構成
- サイドバーは折りたたみ可能 (ClientSide Callback でパフォーマンス最適化)
- ヘルプボタンは dbc.Modal によるモーダルダイアログ方式を採用
- 検出設定ページ (index.html) も同一サイドバーレイアウトに統一. インラインCSSで実装 (静的HTMLのため)
- Explorer → List View (リスト表示) にリネーム
- 旧 nav ボタン ID (`btn-view-scatter`, `btn-view-explorer`, `btn-view-stats`) はコールバック互換性のため維持

### 残課題

- TODO(gen): ブラウザでの動作確認 (Docker build + run)
- TODO(gen): サイドバーのレスポンシブ対応の微調整が必要な可能性あり

## 02-20-00:30 マイクロサービス検出の高速化: スナップショットモード導入

### 変更ファイル

- src/modules/identify_microservice.py — `analyze_repo_snapshot()` を新規追加. CLAIMの `claim()` (単一スナップショット) を使い, コミット履歴走査なしで現在のワークツリーからマイクロサービスを検出. `Microservice` → `ServiceContext` の変換ロジック含む (context 優先, なければ Dockerfile パスから推定).
- src/web/app.py — `_generate_visualization_csv()` のマイクロサービス検出呼び出しを `analyze_repo()` (フル履歴走査) から `analyze_repo_snapshot()` (スナップショット) に変更. 不要になった ms_detection CSV 存在チェックを services_json 存在チェックに簡素化.

### テスト結果

- `pytest tests/ -q` — 33 passed in 0.11s

### 判断メモ

- ボトルネック: `dc_choice.analyze_repo()` + `ms_detection.analyze_repo()` が全コミット履歴を2回走査 (各コミットで `git checkout` + `rglob` + YAML/Dockerfile パース). 4340コミットで20時間以上.
- CLAIMライブラリには `claim(name, workdir)` が元から存在し, 現在のワークツリーのみを解析して `set[Microservice]` を返す (数秒).
- 可視化CSVに必要なのは「最新スナップショットでのサービス境界」のみであり, コミット履歴の変遷は不要. よってスナップショットモードで十分.
- `analyze_repo()` (フル走査) は `analyze_dataset()` バッチ処理用にそのまま残存.

### 残課題

- TODO(gen): スナップショットモードの統合テスト (実リポジトリでの動作確認)
- TODO(gen): `analyze_repo()` のフル走査も将来的にスナップショットに置き換えるか検討

## 02-19-04:00 UI改善: フィルタパネル簡素化・日本語テキスト英語化・ヘッダー整理・マイグレーションスクリプト

### 変更ファイル

- scripts/migrate_ms_detection_to_json.py — 新規: 既存 ms_detection CSV → services_json JSON 一括変換 CLI スクリプト (--force, --dry-run, --ms-detection-dir, --services-json-dir 対応)
- visualize/components.py — Detection Method フィルタを非表示化 (hidden, value="all" 固定). フィルタパネルを CSS クラスベースの2行レイアウトに簡素化 (filter-panel/filter-row/filter-group). ヘッダーを2行構造に変更 (上段: タイトル+ナビ, 下段: プロジェクト選択+ビュースイッチ). 全ユーザー向け日本語テキスト (60箇所以上) を英語に置換
- visualize/callbacks.py — 全ユーザー向け日本語テキストを英語に置換 ("所有"→"All", "条件に一致するクローンはありません"→"No matching clones", "クローンのみ"→"clones only" 等)
- visualize/assets/ide_theme.css — filter-panel/filter-row/filter-group/filter-label/filter-input/filter-dropdown/filter-radio/code-type-buttons の CSS 追加. ヘッダーを76px 2行レイアウトに変更 (header-top-row/header-bottom-row). scatter/stats コンテナの top を76pxに更新
- visualize/assets/i18n.js — filterDetection キー削除. filterComod/filterScope/filterCodeType/filterCloneId/filterManyServices のラベルからコロン除去. Multi-Service Clones ラベルに統一

### テスト結果

- `pytest tests/ -q` — 33 passed in 0.06s
- `python -c "import ast; ast.parse(...)"` — components.py, callbacks.py 構文チェックOK

### 判断メモ

- Detection Method は UI から非表示にするが, コールバック互換性のため hidden div として残した (3つのコールバックが Input として参照しているため, 完全削除するとDashエラーになる)
- ヘッダー2行化: 上段にタイトル+Back/Language, 下段にProject/Dataset+ViewSwitcher の分離で視認性向上
- 日本語テキスト置換: docstring/コメント内の日本語は維持. "日本語" ラベル (言語切替オプション) も意図的に維持

### 残課題

- TODO(gen): visualize/test_ui_logic.py は pandas 未インストールで collect error (前回からの継続)
- TODO(gen): CSV list dropdown (old tab layout, lines 900-1000) にもまだ日本語ラベルあり ("プロジェクトを選択:", "全言語" 等を修正済み)
- TODO(gen): ブラウザでの動作確認が必要 (dash 環境が必要)

## 02-19-01:00 services_json キャッシュ・2段階プロジェクト選択

### 変更ファイル

- src/modules/visualization/service_mapping.py — `save_service_contexts_to_json()` / `load_service_contexts_from_json()` を追加. JSON キャッシュの保存・読み込みをサポート. codebases_inter-service.json 互換の languages ラッパー形式にも対応
- src/modules/identify_microservice.py — ms_detection 完了後に `dest/services_json/<name>.json` へ自動保存する `_save_services_json_cache()` を追加. print→logging変換, 例外メッセージにコンテキスト追加
- src/modules/visualization/build_scatter_dataset.py — `dest/services_json/<name>.json` を優先読み込みし, 存在しなければ従来の ms_detection CSV にフォールバック
- src/web/app.py — `dest/services_json/<name>.json` が既に存在する場合に ms_detection の再実行をスキップ
- visualize/data_loader.py — `get_project_names()` / `get_csv_options_for_project()` を追加 (2段階選択 API)
- visualize/components.py — `create_ide_layout` にプロジェクト名セレクタ (`project-name-selector`) を追加し, CSVファイルセレクタ (`project-selector`) と2段階で選択する UI に変更
- visualize/callbacks.py — `project-name-selector` 変更時に `project-selector` のオプションを動的更新するコールバックを追加
- visualize/assets/i18n.js — `labelProject` / `labelDataset` の英語・日本語ラベルを追加
- visualize/scatter.py — `get_project_names()` をインポートし, `create_ide_layout` に `project_names` を渡すよう変更
- tests/test_service_mapping_json.py — 新規: JSON キャッシュの保存/読み込み/ラウンドトリップ/重複排除/互換形式のテスト (5テスト)

### テスト結果

- `pytest tests/ -q` — 33 passed in 0.12s (既存28 + 新規5)

### 判断メモ

- services_json の保存形式: `{"services": {"<context>/": ["<svc_name>"]}, "URL": "..."}`. CLAIM の ms_detection は言語を区別しないため languages ラッパーなしにした. ただし読み込み側は languages ラッパー形式にも対応
- 2段階選択: 既存コールバックの `project-selector` ID を維持し, その前に `project-name-selector` を追加するアプローチを採用. 既存の全コールバックを変更せずに済む
- `claim_parser.py` の `eval()` 使用は安全性の懸念があり, JSON キャッシュ導入により将来的に `eval()` を完全に排除できる基盤ができた

### 残課題

- TODO(gen): visualize/test_ui_logic.py はpandas未インストールで collect errorになる (前回からの継続)
- TODO(gen): 既存の ms_detection CSV から一括で services_json を生成するマイグレーションスクリプトがあると便利
- TODO(gen): claim_parser.py の eval() を完全排除する安全化リファクタリング

## 02-18-21:30 ログ削減・可視化UIのCSS修正・言語切替・デザイン統一

### 変更ファイル

- src/modules/analyze_modification.py — print()をlogging変換, コミットごとのログを10件間隔の進捗表示に変更
- src/modules/collect_datas.py — コミットごとのcheckout/skipログを10件間隔の進捗表示に変更
- visualize/scatter.py — assets_folderパスを `visualize/assets/` に修正 (CSS読み込み不具合の根本原因)
- visualize/assets/ide_theme.css — CSS変数をindex.html風の `--primary: #f5a623` に統一, ヘッダーのアクセントカラー変更
- visualize/assets/components.css — h1/h4の装飾色を `--primary` に統一
- visualize/assets/i18n.js — 新規: 英語/日本語切替のクライアントサイドロジック
- visualize/components.py — create_ide_layout に言語セレクタ(en/ja)と `data-i18n` 属性を追加, 設定画面への戻りリンク追加
- visualize/callbacks.py — 言語切替用のclientside callbackを登録

### テスト結果

- `pytest tests/ -q` — 28 passed in 0.04s

### 判断メモ

- CSSが当たらない原因: `scatter.py` の `assets_folder` がリポジトリルートの `assets/` を指していたが, 実ファイルは `visualize/assets/` にあった
- i18nはDashのclientside_callbackで実装し, サーバー往復を回避して高速に切り替わるようにした
- デザイントークン (--primary等) をindex.htmlのクローン検出設定画面と共通化した
- ログの間引き: 1件ごと→10件ごとにすることでWebSocket配信量を大幅に削減

### 残課題

- TODO(gen): visualize/test_ui_logic.py はpandas未インストールで collect errorになる (今回の変更とは無関係)

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
