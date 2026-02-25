# visualize コンポーネント (components)

## components パッケージ構成

```
src/visualize/components/
├── __init__.py        # 公開シンボル再エクスポート (19シンボル)
├── layout.py          # 全体レイアウト定義 (IDE型 + レガシータブ型)
├── summary.py         # プロジェクトサマリー・ダッシュボード・統計
├── clone_detail.py    # クローン差分比較ビュー (VS Code風)
├── clone_metrics.py   # メトリクス計算・GitHub URL・重複検出
└── explorer.py        # ファイルツリー・コードエディタ
```

---

### 1. 設計方針

- **目的**: Dash の HTML/dcc コンポーネントを関数単位で生成し,レイアウトとビジネスロジック (コールバック) を分離する.
- **アプローチ**: 各関数は状態を持たず,引数からコンポーネントを構築して返す純粋関数型の設計. 計算処理 (`calculate_*`) とUI生成 (`build_*`, `create_*`) を同パッケージ内に同居させるが,ファイルレベルでは分離.
- **制約・トレードオフ**: `summary.py` が1481行と大きく,ダッシュボード / プロジェクトサマリー / 統計ヘッダーの3責務を兼ねている. `clone_detail.py` は `difflib` を使用するため,大規模なコードブロックの差分計算はサーバー側で行われる.

---

### 2. 入出力

**入力**:
- `pd.DataFrame` — フィルタ済みクローンデータ
- `dict` — `file_ranges` (サービス → ファイルID範囲のマッピング)
- `str` — プロジェクト名, コミットハッシュ, 言語
- `dict` — クローン行の辞書 (散布図クリックデータ)

**出力**:
- `dash.html.Div`, `dbc.Container`, `dbc.Modal` — Dash コンポーネント

---

### 3. 処理フロー

#### レイアウト構築

1. **Step 1**: `create_ide_layout()` — 全体のコンテナ構築
2. **Step 2**: `_build_nav_sidebar()` — サイドバー (ブランド, ナビ, 言語切替, ヘルプ)
3. **Step 3**: 3ビュー (Scatter, Explorer, Statistics) のコンテナ生成
4. **Step 4**: `_build_help_modal()` — ヘルプモーダル

#### クローン詳細表示

1. **Step 1**: `build_clone_details_view_single(row, project)` — エントリポイント
2. **Step 2**: `get_local_snippet()` でローカルファイルからコード取得
3. **Step 3**: `difflib.SequenceMatcher` で差分検出
4. **Step 4**: `_code_pane()` + `_diff_pane()` で行単位のハイライト
5. **Step 5**: `_file_header()` で VS Code タブ風ヘッダー生成

---

### 4. コード解説

#### layout.py — IDE型レイアウト

```python
def create_ide_layout(
    available_projects, available_languages, default_project,
    initial_fig, initial_summary, *, project_names=None,
):
    sidebar = _build_nav_sidebar(lang_dropdown)
    return html.Div(
        id="app-container", className="app-container",
        children=[
            sidebar,
            html.Main(className="main-content", children=[
                # Content Header (プロジェクト選択, フィルタ)
                html.Div(className="content-header", children=[
                    # 2段階選択: project-name-selector → project-selector
                    dcc.Dropdown(id="project-name-selector", ...),
                    dcc.Dropdown(id="project-selector", ...),
                ]),
                # Scatter View
                html.Div(id="scatter-container", className="view-panel active"),
                # Explorer View (IDE風3カラム)
                html.Div(id="ide-main-container", style={"display": "none"}),
                # Statistics View
                html.Div(id="stats-container", className="view-panel"),
            ]),
            dcc.Location(id="url-location", refresh=False),
            # Stores
            dcc.Store(id="lang-store", data="en"),
            dcc.Store(id="code-type-store", data="all"),
        ],
    )
```

- **何をしているか**: サイドバー + メインコンテンツの CSS Grid レイアウトを構築. 3つのビュー (Scatter, Explorer, Statistics) は CSS クラスの切替で表示/非表示を制御.
- **なぜそうしているか**: SPA として画面遷移なしにビューを切替えるため. `dcc.Store` でクライアントサイドの状態 (言語, フィルタ) を保持し,コールバック間で共有する.

---

#### layout.py — 2段階プロジェクト選択

```python
# Step 1: プロジェクト名のみを選択
dcc.Dropdown(
    id="project-name-selector",
    options=project_names,  # [{"label": "owner.repo", "value": "owner.repo"}, ...]
    placeholder="Select Project...",
)

# Step 2: 選択されたプロジェクトの CSV 一覧
dcc.Dropdown(
    id="project-selector",
    options=[],  # コールバックで動的更新
    disabled=True,
)
```

- **何をしているか**: プロジェクト名で絞り込んでから,具体的な CSV ファイル (言語 × 検出設定の組み合わせ) を選択する2段階UI.
- **なぜそうしているか**: 50プロジェクト × 複数言語 × 複数設定で選択肢が膨大になるため,段階的に絞り込むことでユーザビリティを向上.

---

#### clone_detail.py — 差分比較ビュー

```python
def build_clone_details_view_single(row, project):
    snippet_x_lines = get_local_snippet(project, file_x, sx, ex, context=0).splitlines()
    snippet_y_lines = get_local_snippet(project, file_y, sy, ey, context=0).splitlines()

    # 行番号を除いた純粋なコード内容で比較
    code_x_lines = [re.sub(r"^[ >]\s*\d+:\s*", "", line) for line in snippet_x_lines]
    code_y_lines = [re.sub(r"^[ >]\s*\d+:\s*", "", line) for line in snippet_y_lines]
    sm = difflib.SequenceMatcher(None, code_x_lines, code_y_lines)

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        is_diff = tag == "equal"  # 一致箇所に背景色
        for line in snippet_x_lines[i1:i2]:
            rows_x.append(_diff_pane(line, is_diff))
    # ... 左右分割ビュー構築
```

- **何をしているか**: 2つのクローンフラグメントを `difflib.SequenceMatcher` で比較し,一致行に背景色を付けた左右分割ビューを生成する.
- **なぜそうしているか**: クローンペアの類似度を視覚的に確認するため. `is_diff = tag == "equal"` により,**一致している部分** (=クローン箇所) をハイライトする設計. VS Code の差分ビューに倣い,ガター付きのリサイズ可能な分割レイアウトを採用.

---

#### clone_detail.py — ファイルヘッダー

```python
def _file_header(file_path, service, project, start_line, end_line, file_id):
    file_type = get_file_type(file_path)
    type_colors = {
        "logic": "#0366d6", "data": "#d73a49",
        "test": "#28a745",  "config": "#6a737d",
    }
    github_url = generate_github_file_url(project, file_path, start_line, end_line)
    return html.Div([
        # ファイルタイプバッジ (色付き)
        html.Span(file_type.upper(), className="file-type-badge", ...),
        # ファイルパス + GitHub リンク
        html.A(file_path, href=github_url, target="_blank"),
    ], className="editor-tab-header")
```

- **何をしているか**: ファイルパス,サービス名,行範囲,ファイルタイプバッジ,GitHub へのリンクを含む VS Code タブ風ヘッダーを生成する.
- **なぜそうしているか**: コード片の文脈を即座に把握できるよう,メタデータを視覚的にまとめる. GitHub リンクにより原文の確認も容易にする.

---

#### clone_metrics.py — クロスサービス分析

```python
def calculate_cross_service_metrics(df):
    clone_metrics = {}
    for clone_id in df["clone_id"].unique():
        clone_rows = df[df["clone_id"] == clone_id]
        all_clone_services = set(clone_rows["service_x"]).union(set(clone_rows["service_y"]))
        unique_pair_count = calculate_unique_pair_count_for_clone(clone_rows)
        clone_metrics[clone_id] = {
            "service_count": len(all_clone_services),
            "pair_count": unique_pair_count,
            "comodified_count": comodified_count,
            "code_types": dict(code_types),
            "is_mixed": is_mixed,
            "methods": list(methods),
            "file_paths": list(set(...)),
        }
    return clone_metrics, total_services, service_count_distribution
```

- **何をしているか**: 各クローンIDについて,跨るサービス数・ユニークペア数・同時修正数・コードタイプ分布を計算する.
- **なぜそうしているか**: クロスサービスフィルタのオプション生成と,統計ビューでのサービス間依存度の定量化に使用.

---

#### explorer.py — ファイルツリー

```python
def create_file_tree_component(tree_data, level=0):
    folders = sorted([k for k, v in tree_data.items() if v != "__FILE__"])
    files = sorted([k for k, v in tree_data.items() if v == "__FILE__"])

    for name in folders:
        children = create_file_tree_component(tree_data[name], level + 1)
        item = html.Details([
            html.Summary([
                html.Span("📂", className="tree-item-icon"),
                html.Span(name, className="tree-item-label"),
            ]),
            html.Div(children, style={"paddingLeft": "10px"}),
        ])
        items.append(item)

    for name in files:
        item = html.Div([
            html.Span("📄", className="tree-item-icon"),
            html.Span(name, className="tree-item-label"),
        ], id={"type": "file-node", "index": name})
        items.append(item)
    return items
```

- **何をしているか**: ネスト辞書を再帰的に辿り,フォルダは `html.Details` (折りたたみ可能),ファイルは `html.Div` (パターンマッチングID付き) としてレンダリングする.
- **なぜそうしているか**: Dash の pattern-matching callback (`{"type": "file-node", "index": ALL}`) でファイルクリックをハンドリングするため. `html.Details` はネイティブHTMLの折りたたみ要素で,JavaScript不要で動作する.

---

#### explorer.py — コードエディタ

```python
def create_code_editor_view(code_content, file_path, clones=None, start_line=1):
    lines = code_content.split("\n")
    for i, line in enumerate(lines):
        line_num = start_line + i
        is_clone = any(c["start"] <= line_num <= c["end"] for c in (clones or []))
        line_components.append(html.Div([
            html.Span(str(line_num), className="line-number"),
            html.Span(line, className="line-content" + (" clone-highlight" if is_clone else "")),
        ], className="code-line"))
    return html.Div(line_components, className="code-editor")
```

- **何をしているか**: コード内容を行番号付きで表示し,クローン箇所に `clone-highlight` クラスを付与してハイライトする.
- **なぜそうしているか**: IDE のエディタ風UIで,クローンとして検出された行範囲を視覚的に識別可能にする.

---

### 5. 課題・TODO

- TODO(gen): `summary.py` が1481行と大きい. ダッシュボード / プロジェクトサマリー / 統計ヘッダーの3機能への分割を検討.
