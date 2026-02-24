# visualize パッケージ — 概要・データ読込 (data_loader)

## パッケージ全体像

MSCCVis の可視化レイヤーを担うパッケージ.
Dash + Plotly + dash-bootstrap-components で構築されたシングルページアプリケーション (SPA) を提供する.

```
src/visualize/
├── scatter.py           # Dash アプリ エントリポイント
├── constants.py         # DetectionMethod 定数
├── utils.py             # ファイル読込・スニペット取得
├── clone_analytics.py   # クローン比率計算 (プレースホルダー)
├── network.py           # ネットワークグラフ
├── plotting.py          # 散布図生成
├── test_ui_logic.py     # unittest
├── project_summary.json # 事前計算済みサマリー (50件)
├── callbacks/           # Dashコールバック (4分割)
├── components/          # UIコンポーネント (5分割)
└── data_loader/         # データ読込 (3分割)
```

---

### 1. 設計方針

- **目的**: クローン検出結果 (CSV/JSON) をインタラクティブに探索・分析するための Web UI を提供する.
- **アプローチ**: Dash フレームワークを使い,サーバーサイドコールバックで散布図・ファイルエクスプローラー・統計ビューの3画面を構成する. データ読込は複数フォーマットに対応するフォールバックチェーン方式.
- **制約・トレードオフ**: 大規模データ (2000MB超) は読込拒否. キャッシュはインメモリ辞書のため,プロセス再起動で消失する.

---

### 2. 入出力

**入力**:
- `dest/scatter/{project}/csv/*.csv` — 散布図用前処理済みCSV (最優先)
- `dest/codeclones/{project}/latest/{lang}_no_imports.json` — no_imports JSON
- `data/csv/{project}/ccfsw_{lang}.csv`, `tks_{lang}.csv`, `rnr_{lang}.csv` — 検出手法別CSV
- `dest/services_json/{project}.json` — マイクロサービス構成定義
- `src/visualize/project_summary.json` — 50プロジェクトの事前計算済みサマリー

**出力**:
- ブラウザ上のインタラクティブ可視化 (散布図, ネットワーク図, 統計テーブル)

---

### 3. 処理フロー

1. **Step 1**: `scatter.py` — `create_dash_app()` で Dash アプリを初期化
2. **Step 2**: `data_loader/project_discovery.py` — 利用可能プロジェクト・言語を列挙
3. **Step 3**: `components/layout.py` — `create_ide_layout()` でサイドバー付きレイアウト構築
4. **Step 4**: `callbacks/__init__.py` — `register_callbacks()` で全コールバック登録
5. **Step 5**: ユーザーがプロジェクトを選択 → `data_loader/csv_loader.py` — `load_and_process_data()` でデータ読込
6. **Step 6**: `plotting.py` — `create_scatter_plot()` で散布図描画
7. **Step 7**: コールバックがクリック/フィルタ操作に応答

---

### 4. コード解説

#### scatter.py — エントリポイント

```python
def create_dash_app(url_base_pathname: str = "/") -> Dash:
    assets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    dash_app = Dash(
        __name__,
        assets_folder=assets_path,
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
        ],
        requests_pathname_prefix=normalized_prefix,
        routes_pathname_prefix="/",
    )
    dash_app.title = "MSCCVis – コードクローン可視化"
    dash_app.config.suppress_callback_exceptions = True

    available_projects = get_available_projects_enhanced()
    dash_app.layout = create_ide_layout(
        available_projects, available_languages,
        default_value, initial_fig, initial_summary,
        project_names=project_names,
    )
    register_callbacks(dash_app)
    return dash_app
```

- **何をしているか**: Bootstrap テーマと Bootstrap Icons を読み込み,IDE風レイアウトの Dash アプリを生成する.
- **なぜそうしているか**: FastAPI の `/visualize` マウントと整合させるため `requests_pathname_prefix` と `routes_pathname_prefix` を分離している. Starlette の `WSGIMiddleware` がプレフィックスを剥がすため,内部ルーティングは常に `/`.

---

#### constants.py — 検出手法定数

```python
class DetectionMethod:
    NO_IMPORT = 'no-import'
    TKS = 'tks'
    CCFSW = 'ccfsw'

    LABELS = {
        NO_IMPORT: 'Normal',
        TKS: 'TKS',
        CCFSW: 'Legacy (Raw)'
    }

    PREFIX_MAP = {
        'import': NO_IMPORT,
        'tks': TKS,
        '': CCFSW
    }

    @classmethod
    def from_prefix(cls, prefix):
        clean_prefix = prefix.lower().rstrip('_')
        return cls.PREFIX_MAP.get(clean_prefix, cls.CCFSW)
```

- **何をしているか**: CSV ファイル名のプレフィックス (`import_`, `tks_` 等) を検出手法識別子にマッピングする.
- **なぜそうしているか**: UIラベル,フィルタリング,散布図のマーカー形状区別に統一的な識別子が必要. ファイル名規約からの逆引きを `from_prefix` で実現.

---

## data_loader パッケージ

### 1. 設計方針

- **目的**: 複数フォーマットのクローン検出結果を統一的な `pd.DataFrame` + `file_ranges` 辞書に変換する.
- **アプローチ**: フォールバックチェーン方式. 5段階の優先順位でデータソースを探索し,最初に見つかったものを使用する.
- **制約・トレードオフ**: CSVファイルサイズ上限 2000MB. キャッシュキーは `{project}_{commit}_{language}` で,同一セッション中はリロード不要.

---

### 2. 入出力

**入力** (優先順):
1. `dest/scatter/{project}/csv/*.csv` — 散布図用前処理済みCSV
2. `core.unified_data_loader` — 統一ローダー (利用可能な場合)
3. `dest/codeclones/{project}/latest/{lang}_no_imports.json` — JSON形式クローンセット
4. `data/csv/{project}/ccfsw_{lang}.csv` + `tks_{lang}.csv` — 検出手法別CSV
5. `src/visualize/csv/{project}_{commit}_{lang}_all.csv` — レガシーCSV

**出力**:
- `tuple[pd.DataFrame | None, dict | None, str | None]` — (DataFrame, file_ranges辞書, エラーメッセージ)

DataFrame の主要カラム:

| カラム | 型 | 説明 |
|---|---|---|
| `clone_id` | int | クローンID |
| `file_id_x`, `file_id_y` | int | ファイルID (X/Y軸) |
| `file_path_x`, `file_path_y` | str | ファイルパス |
| `start_line_x`, `end_line_x` | int | クローン範囲 |
| `service_x`, `service_y` | str | 所属サービス名 |
| `relation` | str | `"intra"` または `"inter"` |
| `method` | str | 検出手法 (`no-import`, `tks`) |
| `coord_pair` | str | 座標ペアの一意キー |
| `clone_key` | str | クローンの一意キー (重複除去用) |

---

### 3. 処理フロー

1. **Step 1**: `load_and_process_data(project, commit, language)` — メインエントリポイント
2. **Step 2**: キャッシュ確認 (`_data_cache`)
3. **Step 3**: `_scatter_sources()` → `_unified_sources_exist()` → `_no_imports_sources()` → `_project_csv_sources()` → `_legacy_csv_path()` の順にデータソース探索
4. **Step 4**: 見つかったソースに対応するローダー関数を呼び出し
5. **Step 5**: 共通後処理: `service_x`/`service_y` マッピング, `relation` 計算, `coord_pair` 生成

---

### 4. コード解説

#### csv_loader.py — フォールバックチェーン

```python
def load_and_process_data(project_name, commit_hash, language):
    cache_key = f"{project_name}_{commit_hash}_{language}"
    if cache_key in _data_cache:
        return _data_cache[cache_key]["df"], _data_cache[cache_key]["file_ranges"], None

    # 1. dest/scatter (前処理済み, 最優先)
    sources = _scatter_sources(project_name, language)
    if sources:
        return load_from_scatter_csv(sources, services_json_path, cache_key, language)

    # 2. unified data loader
    if _unified_sources_exist(project_name, language):
        return load_from_unified_loader(project_name, language, cache_key)

    # 3. no_imports JSON
    # ... (省略)
    # 4. project CSV (CCFSW + TKS + RNR)
    # 5. レガシー CSV
```

- **何をしているか**: 5段階のフォールバックでデータソースを探索し,最初に成功したローダーの結果を返す.
- **なぜそうしているか**: プロジェクトのデータ形式はパイプラインの実行状態に依存し,統一されていない. 複数形式に対応することで,どの段階の出力でも可視化可能にする.

---

#### csv_loader.py — サービスマッピング

```python
def vectorized_file_id_to_service(file_ids, file_ranges):
    """ファイルIDの配列をサービス名の配列にベクトル化変換."""
    service_map = {}
    for service, ranges in file_ranges.items():
        for start, end in ranges:
            for fid in range(start, end + 1):
                service_map[fid] = service
    return [service_map.get(fid, 'unknown') for fid in file_ids]
```

- **何をしているか**: `services.json` の `file_ranges` 辞書を展開し,ファイルID→サービス名の逆引きマップを構築して一括変換する.
- **なぜそうしているか**: DataFrame の各行でループする非効率を避け,事前にマップを構築してリスト内包表記で高速変換する.

---

#### project_discovery.py — プロジェクト探索

```python
def get_csv_options_for_project(project_name):
    """指定プロジェクトの散布図CSVファイル一覧を取得する.

    戻り値の value 形式: "project|||scatter_file:<filename>|||language"
    """
    scatter_dir = Path("dest/scatter") / project_name / "csv"
    if not scatter_dir.exists():
        return []
    for csv_file in sorted(scatter_dir.glob("*.csv")):
        info = _parse_scatter_csv_filename(csv_file.name)
        # ... ラベル構築, オプション生成
```

- **何をしているか**: 2段階プロジェクト選択の Step 2. 選択されたプロジェクト配下の CSV を列挙し,パース結果からUIラベル (例: `Java · Normal min50 · clone_set · merge_commit`) を構築.
- **なぜそうしているか**: 1プロジェクトに複数の検出条件 × 言語の組み合わせがあるため,ユーザーが直感的に選択できるラベルが必要.

---

#### file_tree.py — ファイルツリー構築

```python
def build_file_tree_data(file_paths):
    """パスリストからネスト辞書形式のツリーを構築.
    葉ノードは "__FILE__" マーカー."""
    tree = {}
    for path in file_paths:
        parts = path.strip("/").split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = "__FILE__"
    return tree
```

- **何をしているか**: フラットなファイルパスリストを再帰的な辞書構造に変換する.
- **なぜそうしているか**: エクスプローラービューの `html.Details` / `html.Summary` による折りたたみ可能なツリー表示に必要.

---

### 5. 課題・TODO

- `TODO: Implement safe clone ratio calculation using available data (e.g. dest/clones_json) without modifying the git repository state.` — [clone_analytics.py](../src/visualize/clone_analytics.py) の `calculate_project_average_clone_ratio` は常に `0.0` を返すプレースホルダー.
