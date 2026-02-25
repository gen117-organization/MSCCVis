# visualize コールバック (callbacks)

## callbacks パッケージ構成

```
src/visualize/callbacks/
├── __init__.py              # 登録ハブ + グローバルデータキャッシュ
├── nav_callbacks.py         # ナビゲーション・i18n・サイドバー
├── scatter_callbacks.py     # 散布図更新・クリック・フィルタ
├── explorer_callbacks.py    # ファイルツリー・コードエディタ
└── filter_callbacks.py      # コードタイプ・クロスサービスフィルタ
```

---

### 1. 設計方針

- **目的**: Dash コールバックを機能別に分割し,各画面のユーザー操作に応答するロジックを管理する.
- **アプローチ**: 共有データキャッシュ (`app_data`) を `__init__.py` で定義し,各サブモジュールの `register_*` 関数に注入する. DOM 操作が頻繁な処理 (サイドバー折畳, i18n) は `clientside_callback` で高速化.
- **制約・トレードオフ**: `app_data` はモジュールレベル辞書のため,マルチワーカー環境では共有不可. `suppress_callback_exceptions = True` を前提に動的コンポーネントの Output を許容.

---

### 2. 入出力

**入力** (Dash Input/State):
- `project-name-selector.value` — プロジェクト名 (Step 1)
- `project-selector.value` — CSVファイル選択 (`project|||commit|||language` 形式)
- `scatter-plot.clickData` — 散布図クリックデータ
- `detection-method-radio.value` — 検出手法フィルタ
- `vis-lang-select.value` — 言語切替セレクタ
- `url-location.search` — URL クエリパラメータ
- `code-type-store.data` — コードタイプフィルタ値

**出力** (Dash Output):
- `scatter-plot.figure` — Plotly 散布図
- `project-summary-container.children` — プロジェクトサマリーUI
- `editor-content.children` — コードエディタ内容
- `file-tree-container.children` — ファイルツリーUI
- `lang-store.data` — 言語設定ストア

---

### 3. 処理フロー

#### 散布図更新フロー

1. **Step 1**: `update_csv_options_for_project(project_name)` — プロジェクト名 → CSV一覧
2. **Step 2**: `update_graph_and_summary(...)` — CSV選択 → データ読込 → フィルタチェーン → 散布図生成
3. **Step 3**: `update_clone_selector(clickData)` — クリック座標 → 重複クローン一覧
4. **Step 4**: `update_details_from_plot(clickData)` — クリック → クローン詳細テーブル

#### フィルタチェーン (Step 2 内部)

```
df_raw (全データ)
  ↓ scope_filter (unknown / resolved / all)
  ↓ service_scope_filter (within / cross / all)
  ↓ cross_service_filter (clone_id 指定)
  ↓ detection_method_filter (no-import / tks / all)
  ↓ clone_id_filter (特定 clone_id)
  ↓ comodification_filter (true / false / all)
  ↓ code_type_filter (logic / data / test / config / mixed / all)
df_display (フィルタ済み)
```

---

### 4. コード解説

#### __init__.py — データキャッシュと登録ハブ

```python
app_data = {
    "df": pd.DataFrame(),
    "file_ranges": {},
    "project": "",
    "commit": "",
    "language": "",
    "current_clone": {},
}

def register_callbacks(app):
    register_nav_callbacks(app, app_data)
    register_scatter_callbacks(app, app_data)
    register_explorer_callbacks(app, app_data)
    register_filter_callbacks(app, app_data)
```

- **何をしているか**: 全コールバック間で共有するデータキャッシュを定義し,4つのサブモジュールを順に登録する.
- **なぜそうしているか**: コールバック間でデータフレームやプロジェクト情報を受け渡す共有メモリが必要. `dcc.Store` だけでは大規模DataFrameの受け渡しが非効率なため,サーバーサイドの辞書を使用.

---

#### nav_callbacks.py — ビュー切替

```python
@app.callback(
    [Output("scatter-container", "className"),
     Output("ide-main-container", "style"),
     Output("stats-container", "className"),
     # ... nav-link classes, page-title
    ],
    [Input("btn-view-scatter", "n_clicks"),
     Input("btn-view-explorer", "n_clicks"),
     Input("btn-view-stats", "n_clicks"),
     Input("url-location", "search")],
    [State("scatter-container", "className")],
)
def toggle_view_mode(btn_scatter, btn_explorer, btn_stats, url_search, current_class):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""

    # URL ?view= パラメータによる初期ビュー選択
    if not ctx.triggered or triggered_id == "url-location":
        if url_search:
            params = parse_qs(url_search.lstrip("?"))
            view = params.get("view", [""])[0]
            if view == "explorer":
                return explorer_state
            # ...
```

- **何をしているか**: サイドバーのナビリンクまたは URL パラメータ (`?view=scatter|explorer|stats`) に応じて3画面を切り替える.
- **なぜそうしているか**: 設定画面 (index.html) から直接特定ビューにジャンプするために URL パラメータ対応が必要. CSS クラスの切替で `display: none` / `flex` を制御.

---

#### nav_callbacks.py — i18n (国際化)

```python
@app.callback(
    Output("lang-store", "data"),
    Input("vis-lang-select", "value"),
)
def _sync_lang_store(lang):
    return lang or "en"

# clientside: window.dash_clientside.i18n.applyLang(lang)
```

- **何をしているか**: 言語セレクタの値をストアに同期し,クライアントサイドの `i18n.js` で DOM テキストを一括差替えする.
- **なぜそうしているか**: テキスト差替えはサーバー往復不要なためクライアントサイドで処理. 言語設定はストアに保持し,他コールバックからも参照可能にする.

---

#### scatter_callbacks.py — フィルタリング

```python
def update_graph_and_summary(
    selected_value, detection_method_filter, clone_id_filter,
    comodified_filter_val, code_type_filter,
    service_scope_filter, cross_service_filter,
):
    project, commit, language = selected_value.split("|||", 2)
    df_raw, file_ranges, error = load_and_process_data(project, commit, language)

    # フィルタチェーン適用
    df_display = df_raw.copy()
    if service_scope_filter == "within":
        df_display = df_display[df_display["relation"] == "intra"]
    # ... (各フィルタ順次適用)

    # 散布図生成
    fig = create_scatter_plot(df_display, file_ranges, project, language)

    # サマリー・ヘッダー生成
    summary = build_project_summary(df_raw, file_ranges, project, commit, language)
    stats_header = create_stats_header(df_raw, df_display, filters)
    return fig, summary, stats_header
```

- **何をしているか**: 7つの Input に応じてフィルタを段階的に適用し,散布図・サマリー・統計ヘッダーを更新する.
- **なぜそうしているか**: フィルタの適用順が結果に影響するため,scope → service → cross_service → method → clone_id → comodification → code_type の固定順で適用. `df_raw` は統計ヘッダーの「全件中 n 件」表示に使用するため保持.

---

#### scatter_callbacks.py — クリックイベント

```python
@app.callback(
    Output("clone-selector-container", "children"),
    Input("scatter-plot", "clickData"),
    State("project-selector", "value"),
)
def update_clone_selector(clickData):
    # クリック座標から重複クローンを検出
    overlapping = find_overlapping_clones(app_data['df'], click_x, click_y)
    return build_clone_selector(overlapping, app_data['df'])
```

- **何をしているか**: 散布図のクリック座標にある全クローンペアを検出し,選択用ドロップダウンを生成する.
- **なぜそうしているか**: 同一座標に複数のクローンペアが重なることがあるため,ユーザーが選択できるUI を提供する.

---

#### explorer_callbacks.py — ファイルツリー・コード表示

```python
@app.callback(
    [Output("file-tree-container", "children"),
     Output("file-tree-data-store", "data"),
     Output("clone-data-store", "data"),
     Output("project-summary-container", "children")],
    [Input("project-selector", "value")],
)
def update_project_data(project_value, project_options):
    df, file_ranges, error = load_and_process_data(project, commit, target_lang)
    related_files = get_clone_related_files(df)
    tree_structure = build_file_tree_data(related_files)
    tree_component = create_file_tree_component(tree_structure)
    clone_records = df.to_dict("records")
    return tree_component, tree_structure, clone_records, summary_view
```

- **何をしているか**: プロジェクト選択時にデータをロードし,ファイルツリー UI と `clone-data-store` (クライアントサイド用辞書) を構築する.
- **なぜそうしているか**: エクスプローラービューではファイルクリック → クローン一覧 → コード表示の連鎖が必要. `clone-data-store` にレコードを格納することで,ファイルクリック時のサーバー往復を減らす.

---

#### filter_callbacks.py — コードタイプフィルタ

```python
CODE_TYPE_COLORS = {
    "all":    {"bg": "#f8f9fa", "text": "#24292e", ...},
    "logic":  {"bg": "#f1f8ff", "text": "#0366d6", ...},
    "data":   {"bg": "#ffeef0", "text": "#d73a49", ...},
    "test":   {"bg": "#e6ffed", "text": "#28a745", ...},
    "config": {"bg": "#fafbfc", "text": "#6a737d", ...},
    "mixed":  {"bg": "#f3f0ff", "text": "#6f42c1", ...},
}

def create_code_type_button(label, count, value, active_value):
    isActive = value == active_value
    colors = CODE_TYPE_COLORS.get(value, CODE_TYPE_COLORS["all"])
    return html.Button(
        f"{label} ({count})",
        id={"type": "code-type-btn", "index": value},
        style={"borderRadius": "20px", ...},
    )
```

- **何をしているか**: コードタイプ (logic, data, test, config, mixed) ごとにピルボタンを生成し,件数バッジを付与する.
- **なぜそうしているか**: `modules.util.get_file_type` でファイルを分類し,タイプ別のクローン分布を視覚的に確認できるようにする. ピル型ボタンは GitHub Issues のラベルUIを参考にしたデザイン.

---

#### filter_callbacks.py — クロスサービスフィルタ

```python
def update_cross_service_options(...):
    # メソッド → コードタイプ → 同時修正 の順にフィルタ適用
    # サービス数 >= 2 のクローンIDを抽出 (上位200件)
    clone_metrics, _, _ = calculate_cross_service_metrics(df_filtered)
    multi_service_clones = [
        m for m in clone_metrics.values() if m["service_count"] >= 2
    ]
    sorted_clones = sorted(multi_service_clones, key=lambda x: -x["pair_count"])[:200]
    return generate_cross_service_filter_options(sorted_clones)
```

- **何をしているか**: 複数サービスに跨るクローンを検出し,ペア数順でソートしたフィルタ選択肢を生成する.
- **なぜそうしているか**: Inter-service クローンの中でも特定のクローンID に絞り込んで分析するため. 上限200件はドロップダウンの描画パフォーマンスを考慮.

---

### 5. 課題・TODO

- `TODO: Improve this path resolution` — [explorer_callbacks.py](../src/visualize/callbacks/explorer_callbacks.py) のファイルパス解決. 現在はファイル名末尾一致で検索しており,同名ファイルが複数サービスにある場合に誤マッチする可能性がある.
