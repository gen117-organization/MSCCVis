# visualize ユーティリティ (utils, plotting, network, clone_analytics)

## ファイル構成

```
src/visualize/
├── utils.py             # ファイル読込・スニペット取得
├── plotting.py          # 散布図 (ヒートマップ風カラーマップ)
├── network.py           # サービス間ネットワークグラフ
└── clone_analytics.py   # クローン比率計算 (プレースホルダー)
```

---

## utils.py — ファイル読込・スニペットユーティリティ

### 1. 設計方針

- **目的**: ローカルファイルシステム上のソースコードを読み込み,行番号付きスニペットやファイルツリーを生成する.
- **アプローチ**: `functools.lru_cache` で最大200ファイル分の行データをキャッシュし,同一ファイルへの重複I/Oを排除. パストラバーサル攻撃を `resolve()` + 前方一致チェックで防止.
- **制約・トレードオフ**: LRUキャッシュは `Path` オブジェクトをキーとするため,同一ファイルの異なるパス表現 (相対/絶対) でキャッシュミスが起きうる.

---

### 2. 入出力

**入力**:
- `project: str` — プロジェクト名 (例: `"owner.repo"`)
- `file_path: str` — ファイルパス (相対 or 絶対)
- `start_line, end_line: int` — クローン行範囲

**出力**:
- `str` — 行番号付きコードスニペット (`>` マークでクローン行を示す)
- `str` — Markdown形式のファイルコンテンツ
- `str` — ディレクトリツリー文字列

---

### 3. 処理フロー

1. **Step 1**: `get_local_project_root(project)` — プロジェクトルート特定 (4か所を優先順で探索)
2. **Step 2**: `read_file_lines_cached(path)` — LRUキャッシュ付きファイル読込
3. **Step 3**: `get_local_snippet(project, file_path, start, end)` — 行範囲切り出し + コンテキスト行付加

---

### 4. コード解説

#### プロジェクトルート探索

```python
def get_local_project_root(project: str) -> Path:
    """4か所を優先順で探索してプロジェクトルートを返す."""
    # 1. dest/temp/no_imports/{project} (import除去済みソース)
    no_imports_base = LOCAL_NO_IMPORTS_BASE / project
    if no_imports_base.exists():
        return no_imports_base
    # 2. dest/temp/static/{project} (従来の静的コピー)
    static_base = LOCAL_STATIC_BASE / project
    if static_base.exists():
        return static_base
    # 3. dest/clone_analysis/{project}/repo (分析ワークツリー)
    # 4. dest/projects/{project} (現在の標準)
    # ... フォールバック
```

- **何をしているか**: プロジェクトのソースコードが格納されている可能性のある4ディレクトリを順に確認する.
- **なぜそうしているか**: パイプラインの実行段階によってソースの格納場所が異なる. no_imports (import行除去済み) を最優先にすることで,クローン検出と整合するコードを表示する.

---

#### パストラバーサル防止

```python
def get_local_snippet(project, file_path, start_line, end_line, context=2):
    if file_path.startswith('/'):
        abs_path = Path(file_path).resolve()
    else:
        root = get_local_project_root(project)
        abs_path = (root / file_path.lstrip('/')).resolve()
        if not str(abs_path).startswith(str(root.resolve())):
            raise ValueError('Path escape detected')
    # ...
```

- **何をしているか**: 相対パスの場合にプロジェクトルート外へのアクセスを検知して拒否する.
- **なぜそうしているか**: ユーザー入力 (クローンデータの `file_path`) に `../` が含まれる可能性があり,任意ファイルの読取を防止する必要がある.

---

## plotting.py — 散布図生成

### 1. 設計方針

- **目的**: クローンペアをファイルID座標上のヒートマップ風散布図として描画する.
- **アプローチ**: 関係 (intra/inter) × 検出手法 (Normal/TKS) の4トレースを重ね合わせ,マーカー形状で関係を,色で同時修正回数を表現する 5段階ヒートマップ.
- **制約・トレードオフ**: 大規模データは `go.Scattergl` (WebGL) で描画するが,ブラウザのGPUメモリに依存するため,数万点を超えると動作が重くなる.

---

### 2. 入出力

**入力**:
- `df: pd.DataFrame` — クローンデータ (file_id_x, file_id_y, relation, comodified 等)
- `file_ranges: dict` — サービス → ファイルID範囲
- `static_mode: bool` — True なら WebGL + マーカー縮小

**出力**:
- `go.Figure` — Plotly 散布図

---

### 3. 処理フロー

1. **Step 1**: `coord_pair`, `clone_key` 補完 (`create_scatter_plot`)
2. **Step 2**: `clone_key` ベースの重複除去
3. **Step 3**: 関係別 × 手法別で4グループに分割
4. **Step 4**: 同時修正回数 → 5段階色マッピング
5. **Step 5**: `add_service_boundaries(fig, file_ranges)` — サービス境界の点線

---

### 4. コード解説

#### 5段階ヒートマップ

```python
def create_scatter_plot(df, file_ranges, project_name, language, static_mode=False):
    # 色の定義: 同時修正回数に応じた5段階
    color_scale = [
        (0, "rgb(68, 119, 170)"),     # 青: comod=0
        (0.25, "rgb(68, 170, 119)"),  # 緑: comod=1
        (0.5, "rgb(255, 221, 51)"),   # 黄: comod=2-3
        (0.75, "rgb(255, 153, 51)"),  # 橙: comod=4-7
        (1, "rgb(204, 51, 17)"),      # 赤: comod>=8
    ]

    # マーカー形状: intra=circle, inter=square
    for relation, marker_symbol in [("intra", "circle"), ("inter", "square")]:
        fig.add_trace(go.Scattergl(
            x=group["file_id_x"], y=group["file_id_y"],
            mode="markers",
            marker=dict(
                color=group["comod_normalized"],
                colorscale=color_scale,
                symbol=marker_symbol,
                size=6 if static_mode else 8,
            ),
            customdata=custom_cols,
        ))
```

- **何をしているか**: 同時修正回数を正規化して5段階色に変換し,intra/interでマーカー形状を変える散布図を生成する.
- **なぜそうしているか**: 同時修正は保守コストの指標であり,色の濃淡で頻度を直感的に把握できる. マーカー形状はサービス内/間の区別に使い,色と形状の2次元でクローンの性質を表現する.

---

#### サービス境界線

```python
def add_service_boundaries(fig, file_ranges):
    boundaries = set()
    for ranges in file_ranges.values():
        for start, end in ranges:
            if start > 0:
                boundaries.add(start - 0.5)
            boundaries.add(end + 0.5)
    for boundary in sorted(boundaries):
        fig.add_vline(x=boundary, line_dash="dash", line_color="gray", opacity=0.8)
        fig.add_hline(y=boundary, line_dash="dash", line_color="gray", opacity=0.8)
```

- **何をしているか**: ファイルID範囲の境界にグレーの点線を追加し,サービスの区切りを視覚化する.
- **なぜそうしているか**: 散布図上でサービス間クローン (対角線外の点) とサービス内クローン (対角線上の点) の区別を明確にする.

---

## network.py — ネットワークグラフ

### 1. 設計方針

- **目的**: サービス間のクローン共有関係をネットワークグラフ (ノード=サービス, エッジ=inter-serviceクローン) で描画する.
- **アプローチ**: 円形レイアウト. ノードサイズはファイル数の対数スケール. `df` 指定時は DataFrame からエッジを再計算.
- **制約・トレードオフ**: エッジの太さの動的変更は Plotly の Line trace では困難なため,一定太さで描画している.

---

### 2. 入出力

**入力**:
- `services_data: dict` — `services.json` の内容
- `df: pd.DataFrame | None` — フィルタ済みデータ (指定時はエッジを再計算)

**出力**:
- `go.Figure` — ネットワークグラフ

---

### 4. コード解説

```python
def create_network_graph(services_data, project_name, language, df=None):
    # 円形レイアウト
    for i, service in enumerate(sorted_services):
        angle = 2 * math.pi * i / N
        x, y = R * math.cos(angle), R * math.sin(angle)
        size = 10 + (math.log(file_count + 1) * 5)  # 対数スケール

    # エッジ: df指定時はinterペアを再カウント
    if df is not None:
        inter_df = df[df['relation'] == 'inter']
        for _, row in inter_df.iterrows():
            key = f"{min(s1, s2)}--{max(s1, s2)}"
            inter_counts[key] = inter_counts.get(key, 0) + 1
    else:
        inter_counts = services_data.get('counts', {}).get('inter', {})
```

- **何をしているか**: サービスを円周上に配置し,inter-service クローン数に基づくエッジを接続する.
- **なぜそうしているか**: マイクロサービス間の依存度を俯瞰的に把握するため. フィルタ適用時はエッジを再計算し,フィルタ後の依存構造を反映する.

---

## clone_analytics.py — クローン比率計算

### 1. 設計方針

- **目的**: プロジェクトの平均クローン比率を計算する (**現在はプレースホルダー**).
- **アプローチ**: 将来的には `dest/clones_json` のデータを使用して計算する予定.
- **制約・トレードオフ**: Git リポジトリの状態を変更せずに計算する必要があり,現時点では安全な実装方法が確立されていない.

---

### 4. コード解説

```python
def calculate_project_average_clone_ratio(project_name: str) -> float:
    """プロジェクトの平均クローン比率を計算する (未実装)."""
    return 0.0
```

- **何をしているか**: 常に `0.0` を返す.
- **なぜそうしているか**: 実際の計算にはリポジトリのチェックアウトやファイル解析が必要だが,可視化ツールからリポジトリ状態を変更するのは安全でない. 事前計算済みデータからの読取方式に移行予定.

---

### 5. 課題・TODO

- `TODO: Implement safe clone ratio calculation using available data (e.g. dest/clones_json) without modifying the git repository state.` — [clone_analytics.py](../src/visualize/clone_analytics.py)
