# クローンメトリクス計算モジュール設計ドキュメント

## 1. 設計方針

- **目的**: enriched_fragments.csv を入力として, マイクロサービス・クローンセット・ファイルの 3 粒度でクローンメトリクスを計算する. 散布図用の O(n²) ペア CSV に依存せず, O(n) のフラグメント粒度データから効率的にメトリクスを導出する.
- **アプローチ**: pandas の `groupby` を中心に, clone_id / service / file_path の各軸で集計する純粋関数群として実装. I/O (CSV 読み込み・JSON 読み込み) と計算ロジックを分離し, テスト容易性を確保.
- **制約・トレードオフ**:
  - `modified_commits` が JSON 配列文字列のため, 行ごとのパースが必要 (ベクトル化不可). 大規模データではボトルネックになり得る.
  - token_count は enriched_fragments.csv に含まれていないため (clones_json のパース問題により未実装), トークンベースのメトリクスは計算できない. 行数ベースで代替.
  - ROC の分母は `services.json` の `language_stats` から取得. enriched_fragments が生成されていても `language_stats` が未付与の場合, ROC = 0.0 になる.

---

## 2. 入出力

### 入力

| データソース | パス | 用途 |
|---|---|---|
| enriched_fragments.csv | `dest/enriched_fragments/<project>/<language>.csv` | フラグメント粒度のクローンデータ. 全メトリクスの計算基盤 |
| services.json | `dest/services_json/<project>.json` | `language_stats` セクション: サービス別 `total_loc` (ROC の分母) |

**enriched_fragments.csv カラム**:

```
clone_id, fragment_index, file_path, file_id, service,
start_line, end_line, line_count, file_type,
modified_commits (JSON array), modified_count
```

**services.json の language_stats 例**:

```json
{
  "language_stats": {
    "Python": {
      "services": {
        "worker": {"file_count": 5, "total_loc": 500},
        "vote": {"file_count": 3, "total_loc": 200}
      },
      "total_files": 20,
      "total_loc": 5000
    }
  }
}
```

### 出力

3 つの dataclass リストを辞書にまとめて返す:

```python
{
    "service": [ServiceMetrics, ...],
    "clone_set": [CloneSetMetrics, ...],
    "file": [FileMetrics, ...],
}
```

CSV/JSON への書き出しは呼び出し側に委ねる. `metrics_to_dataframes()` で DataFrame に変換可能.

---

## 3. 処理フロー

1. **Step 1: `load_enriched_fragments()`** — enriched_fragments.csv を DataFrame に読み込み, `service` と `modified_commits` の NaN を補完
2. **Step 2: `load_language_stats()`** — services.json から指定言語の `language_stats` を取得
3. **Step 3: `compute_service_metrics()`** — `service` 列で groupby し, サービスごとのクローンセット数・行数・ROC・同時修正を計算
4. **Step 4: `compute_clone_set_metrics()`** — `clone_id` 列で groupby し, クロスサービス判定・同時修正コミット抽出
5. **Step 5: `compute_file_metrics()`** — `file_path` 列で groupby し, 共有サービス・クロスサービスクローンセット・同時修正を計算
6. **Step 6: `compute_all_metrics()`** — Step 1-5 を統合し, 辞書形式で返す

---

## 4. コード解説

### データクラス

```python
@dataclass(frozen=True)
class ServiceMetrics:
    """マイクロサービス粒度のメトリクス."""
    service: str
    clone_set_count: int           # 含まれるクローンセット数
    total_clone_line_count: int    # クローンの合計行数
    clone_avg_line_count: float    # クローンフラグメントの平均行数
    clone_file_count: int          # クローンセットに含まれるファイル数
    roc: float                     # クローン行数 / サービス総LOC
    comod_count: int               # 同時修正コミット数
    comod_other_service_count: int # 同時修正に関わる他サービス数
```

- **何をしているか**: マイクロサービス 1 つ分の統計を保持する不変データクラス.
- **なぜそうしているか**: `frozen=True` で不変性を保証し, 集計結果を安全に受け渡す. `asdict()` で辞書・DataFrame に変換可能.

```python
@dataclass(frozen=True)
class CloneSetMetrics:
    """クローンセット粒度のメトリクス."""
    clone_id: str
    service_count: int                  # 跨っているサービス数
    cross_service_fragment_count: int   # 他サービスと共有しているコード片数
    cross_service_fragment_ratio: float # ↑ / 全フラグメント数
    cross_service_line_count: int       # 共有コード片の行数
    cross_service_scale: int            # 共有コード片数 × 行数
    cross_service_element_count: int    # サービスを跨っている要素数
    comod_count: int                    # 同時修正回数
    comod_fragment_count: int           # 同時修正されたフラグメント数
    comod_fragment_ratio: float         # ↑ / 全フラグメント数
```

```python
@dataclass(frozen=True)
class FileMetrics:
    """ファイル粒度のメトリクス."""
    file_path: str
    service: str
    sharing_service_count: int          # 共有しているサービス数
    total_service_count: int            # 全サービス数
    cross_service_clone_set_count: int  # 他サービスと共有しているクローンセット数
    cross_service_clone_set_ratio: float
    sharing_service_ratio: float        # 共有サービス数 / 全サービス数
    cross_service_line_count: int       # 共有クローンの行数
    cross_service_comod_count: int      # 共有クローンの同時修正数
    comod_shared_service_count: int     # 同時修正を共有したサービス数
```

### 同時修正 (co-modification) の判定

```python
def _compute_comod_commits_for_clone_set(
    fragments_df: pd.DataFrame,
) -> set[str]:
    commit_to_fragments: dict[str, set[int]] = {}
    for _, row in fragments_df.iterrows():
        frag_idx = int(row["fragment_index"])
        for commit in _parse_commits(str(row["modified_commits"])):
            commit_to_fragments.setdefault(commit, set()).add(frag_idx)
    return {c for c, frags in commit_to_fragments.items() if len(frags) >= 2}
```

- **何をしているか**: クローンセット内の全フラグメントの `modified_commits` を展開し, 同一コミットで 2 つ以上のフラグメントが修正されている場合に「同時修正コミット」として抽出する.
- **なぜそうしているか**: 既存の `calculate_comodification_rate.py` の定義を踏襲. ペアベースではなくフラグメント集合ベースで判定するため, enriched_fragments.csv の構造に適合する.

### クロスサービス判定

```python
def _build_clone_set_service_map(
    df: pd.DataFrame,
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for clone_id, group in df.groupby("clone_id"):
        services = {s for s in group["service"].unique() if s}
        result[str(clone_id)] = services
    return result
```

- **何をしているか**: 全 DataFrame を 1 回走査して clone_id → サービス集合 のマップを構築する. 空文字 (未解決サービス) は除外.
- **なぜそうしているか**: サービス・ファイル両粒度の計算で共通して使うため, 事前に 1 回だけ構築してキャッシュする.

### サービス粒度の ROC 計算

```python
def _compute_single_service(
    service: str,
    svc_df: pd.DataFrame,
    full_df: pd.DataFrame,
    services_loc: dict[str, int],
    clone_set_svc_map: dict[str, set[str]],
) -> ServiceMetrics:
    clone_ids = set(svc_df["clone_id"].unique())
    clone_set_count = len(clone_ids)

    total_clone_line = int(svc_df["line_count"].sum())
    frag_count = len(svc_df)
    avg_line = total_clone_line / frag_count if frag_count > 0 else 0.0

    clone_file_count = int(svc_df["file_path"].nunique())

    svc_total_loc = services_loc.get(service, 0)
    roc = total_clone_line / svc_total_loc if svc_total_loc > 0 else 0.0

    # ... (同時修正の計算は省略)
    return ServiceMetrics(...)
```

- **何をしているか**: サービスに属するフラグメントを集計して各メトリクスを算出. ROC は `sum(line_count) / language_stats の total_loc`.
- **なぜそうしているか**: ROC の分母にはクローン対象外のファイルも含む全 LOC が必要であり, `language_stats` から取得. enriched_fragments.csv にはクローン断片しか含まれないため分母にはならない.

### ファイル粒度の共有サービス計算

```python
def _compute_single_file(
    file_path: str,
    file_df: pd.DataFrame,
    full_df: pd.DataFrame,
    clone_set_svc_map: dict[str, set[str]],
    total_service_count: int,
) -> FileMetrics:
    file_service = _majority_service(file_df)
    file_clone_ids = set(file_df["clone_id"].unique())

    sharing_services: set[str] = set()
    cross_clone_sets: set[str] = set()
    cross_line = 0

    for cid in file_clone_ids:
        cs_services = clone_set_svc_map.get(cid, set())
        other_services = cs_services - {file_service} if file_service else cs_services
        if other_services:
            sharing_services |= other_services
            cross_clone_sets.add(cid)
            cid_file_frags = file_df[file_df["clone_id"] == cid]
            cross_line += int(cid_file_frags["line_count"].sum())
    # ... (省略)
    return FileMetrics(...)
```

- **何をしているか**: ファイルが属するクローンセットごとに, 自サービス以外にフラグメントを持つサービスを「共有サービス」としてカウントする.
- **なぜそうしているか**: ファイル視点のクロスサービス依存度を測るため. `_majority_service()` でファイルのサービスを決定し, それ以外を「他サービス」として集計する.

### 統合エントリポイント

```python
def compute_all_metrics(
    enriched_csv_path: Path,
    services_json_path: Path,
    language: str,
) -> dict[str, list[dict[str, Any]]]:
    df = load_enriched_fragments(enriched_csv_path)
    lang_stats = load_language_stats(services_json_path, language)

    service_metrics = compute_service_metrics(df, lang_stats)
    clone_set_metrics = compute_clone_set_metrics(df)

    services_section = lang_stats.get("services", {})
    total_svc = len(services_section) if services_section else len(
        {s for s in df["service"].unique() if s}
    )
    file_metrics = compute_file_metrics(df, total_svc)

    return {
        "service": [asdict(m) for m in service_metrics],
        "clone_set": [asdict(m) for m in clone_set_metrics],
        "file": [asdict(m) for m in file_metrics],
    }
```

- **何をしているか**: 3 粒度のメトリクスをまとめて計算し, `asdict()` で辞書リストに変換して返す.
- **なぜそうしているか**: 呼び出し側 (パイプライン・可視化・CLI) が出力形式 (CSV/JSON/DataFrame) を選択できるよう, 中間表現として辞書リストを返す. `metrics_to_dataframes()` で DataFrame 変換も可能.

### clone_analytics.py (プレースホルダー更新)

```python
def calculate_project_average_clone_ratio(project_name: str) -> float:
    dest = _PROJECT_ROOT / "dest"
    enriched_dir = dest / "enriched_fragments" / project_name
    services_json = dest / "services_json" / f"{project_name}.json"

    if not enriched_dir.exists() or not services_json.exists():
        return 0.0

    csv_files = sorted(enriched_dir.glob("*.csv"))
    all_rocs: list[float] = []
    for csv_path in csv_files:
        language = csv_path.stem
        # ... (filter prefix 除去)
        df = load_enriched_fragments(csv_path)
        lang_stats = load_language_stats(services_json, language)
        metrics = compute_service_metrics(df, lang_stats)
        for m in metrics:
            if m.roc > 0:
                all_rocs.append(m.roc)
    return sum(all_rocs) / len(all_rocs) if all_rocs else 0.0
```

- **何をしているか**: 既存のプレースホルダー (`return 0.0`) を置き換え, enriched_fragments.csv から全サービスの ROC 平均を計算する.
- **なぜそうしているか**: `summary.py` から呼ばれている既存の API 互換を維持しつつ, 実データに基づく値を返すようにする.

---

## 5. 課題・TODO

- `TODO(gen): clones_json の clone_sets がリスト形式の場合の token_count パース修正` — token_count が enriched_fragments.csv に含まれないため, トークンベースのメトリクスは未実装
- `TODO(gen): 大規模データでの modified_commits パース性能` — 現在 `iterrows()` + `json.loads()` で行ごとにパースしている. 数万行規模では `apply()` + バッチ処理への最適化を検討
- `TODO(gen): compute_all_metrics の出力を CSV/JSON に保存するパイプライン統合` — 現在は戻り値を返すのみ. Web UI パイプラインや CLI での保存ステップは未接続
- `TODO(gen): 可視化 UI (Stats ビュー) でのメトリクス表示` — `summary.py` の Stats パネルから `compute_all_metrics()` を呼び出してダッシュボード表示する機能は未実装
