"""enriched_fragments.csv からクローンメトリクスを計算する.

3 つの粒度でメトリクスを算出する:

1. **サービス粒度** (ServiceMetrics): マイクロサービスごとのクローン統計
2. **クローンセット粒度** (CloneSetMetrics): クローンセット単位のクロスサービス・同時修正統計
3. **ファイル粒度** (FileMetrics): ファイル単位のクロスサービス共有・同時修正統計

入力:
- ``enriched_fragments.csv``
  (clone_id, fragment_index, file_path, file_id, service,
   start_line, end_line, line_count, file_type,
   modified_commits (JSON), modified_count)
- ``services.json`` の ``language_stats`` セクション
  (サービス別 total_loc を ROC の分母に使用)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceMetrics:
    """マイクロサービス粒度のメトリクス."""

    service: str
    clone_set_count: int
    total_clone_line_count: int
    clone_avg_line_count: float
    clone_file_count: int
    roc: float
    comod_count: int
    comod_other_service_count: int


@dataclass(frozen=True)
class CloneSetMetrics:
    """クローンセット粒度のメトリクス."""

    clone_id: str
    service_count: int
    cross_service_fragment_count: int
    cross_service_fragment_ratio: float
    cross_service_line_count: int
    cross_service_scale: int
    cross_service_element_count: int
    comod_count: int
    comod_fragment_count: int
    comod_fragment_ratio: float


@dataclass(frozen=True)
class FileMetrics:
    """ファイル粒度のメトリクス."""

    file_path: str
    service: str
    sharing_service_count: int
    total_service_count: int
    cross_service_clone_set_count: int
    cross_service_clone_set_ratio: float
    sharing_service_ratio: float
    cross_service_line_count: int
    cross_service_comod_count: int
    comod_shared_service_count: int


# ---------------------------------------------------------------------------
# 読み込み
# ---------------------------------------------------------------------------


def load_enriched_fragments(csv_path: Path) -> pd.DataFrame:
    """enriched_fragments.csv を DataFrame に読み込む.

    Args:
        csv_path: CSV ファイルパス.

    Returns:
        DataFrame.

    Raises:
        FileNotFoundError: ファイルが存在しない場合.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"enriched fragments csv not found: {csv_path}")
    df = pd.read_csv(
        csv_path,
        dtype={
            "clone_id": str,
            "fragment_index": int,
            "file_path": str,
            "file_id": int,
            "service": str,
            "start_line": int,
            "end_line": int,
            "line_count": int,
            "file_type": str,
            "modified_commits": str,
            "modified_count": int,
        },
    )
    # service が NaN の場合は空文字に統一
    df["service"] = df["service"].fillna("")
    df["modified_commits"] = df["modified_commits"].fillna("[]")
    return df


def load_language_stats(services_json_path: Path, language: str) -> dict[str, Any]:
    """services.json から指定言語の language_stats を読み込む.

    Args:
        services_json_path: services.json パス.
        language: 言語名 (e.g. ``"Python"``).

    Returns:
        language_stats[language] の辞書. 存在しない場合は空辞書.
    """
    if not services_json_path.exists():
        logger.warning("services json not found: %s", services_json_path)
        return {}
    with services_json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("language_stats", {}).get(language, {})


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _parse_commits(commits_json: str) -> set[str]:
    """JSON 配列文字列からコミットハッシュの集合を返す."""
    if not commits_json or commits_json == "[]":
        return set()
    try:
        result = json.loads(commits_json)
        if isinstance(result, list):
            return {str(c) for c in result if c}
        return set()
    except (json.JSONDecodeError, TypeError):
        return set()


def _compute_comod_commits_for_clone_set(
    fragments_df: pd.DataFrame,
) -> set[str]:
    """クローンセット内の同時修正コミットを抽出する.

    「同時修正」= 同一コミットで 2 つ以上のフラグメントが修正されているもの.

    Args:
        fragments_df: 1 クローンセット分の DataFrame.

    Returns:
        同時修正コミットのセット.
    """
    commit_to_fragments: dict[str, set[int]] = {}
    for _, row in fragments_df.iterrows():
        frag_idx = int(row["fragment_index"])
        for commit in _parse_commits(str(row["modified_commits"])):
            commit_to_fragments.setdefault(commit, set()).add(frag_idx)
    return {c for c, frags in commit_to_fragments.items() if len(frags) >= 2}


def _get_comod_fragment_indices(
    fragments_df: pd.DataFrame,
    comod_commits: set[str],
) -> set[int]:
    """同時修正コミットに関与したフラグメントの index 集合を返す."""
    indices: set[int] = set()
    for _, row in fragments_df.iterrows():
        frag_commits = _parse_commits(str(row["modified_commits"]))
        if frag_commits & comod_commits:
            indices.add(int(row["fragment_index"]))
    return indices


def _build_clone_set_service_map(
    df: pd.DataFrame,
) -> dict[str, set[str]]:
    """clone_id -> サービス集合 のマップを構築する.

    空文字サービス (未解決) は除外する.
    """
    result: dict[str, set[str]] = {}
    for clone_id, group in df.groupby("clone_id"):
        services = {s for s in group["service"].unique() if s}
        result[str(clone_id)] = services
    return result


# ---------------------------------------------------------------------------
# サービス粒度メトリクス
# ---------------------------------------------------------------------------


def compute_service_metrics(
    df: pd.DataFrame,
    language_stats: dict[str, Any],
) -> list[ServiceMetrics]:
    """サービス粒度のメトリクスを計算する.

    Args:
        df: enriched_fragments DataFrame.
        language_stats: services.json の language_stats[language].

    Returns:
        サービスごとの ServiceMetrics リスト.
    """
    if df.empty:
        return []

    # サービスが空 (未解決) のフラグメントは除外
    df_resolved = df[df["service"] != ""]
    if df_resolved.empty:
        return []

    services_loc = _extract_service_loc(language_stats)
    clone_set_svc_map = _build_clone_set_service_map(df)

    results: list[ServiceMetrics] = []
    for service, svc_df in df_resolved.groupby("service"):
        service = str(service)
        metrics = _compute_single_service(
            service, svc_df, df, services_loc, clone_set_svc_map
        )
        results.append(metrics)

    return sorted(results, key=lambda m: m.service)


def _extract_service_loc(
    language_stats: dict[str, Any],
) -> dict[str, int]:
    """language_stats からサービス名 -> total_loc マップを抽出する."""
    services_section = language_stats.get("services", {})
    return {
        svc: int(info.get("total_loc", 0))
        for svc, info in services_section.items()
        if isinstance(info, dict)
    }


def _compute_single_service(
    service: str,
    svc_df: pd.DataFrame,
    full_df: pd.DataFrame,
    services_loc: dict[str, int],
    clone_set_svc_map: dict[str, set[str]],
) -> ServiceMetrics:
    """1 サービスの ServiceMetrics を計算する."""
    # 含まれるクローンセット数
    clone_ids = set(svc_df["clone_id"].unique())
    clone_set_count = len(clone_ids)

    # 合計クローン行数 & 平均行数
    total_clone_line = int(svc_df["line_count"].sum())
    frag_count = len(svc_df)
    avg_line = total_clone_line / frag_count if frag_count > 0 else 0.0

    # クローンセットに含まれるユニークファイル数
    clone_file_count = int(svc_df["file_path"].nunique())

    # ROC = クローン行数 / サービス総 LOC
    svc_total_loc = services_loc.get(service, 0)
    roc = total_clone_line / svc_total_loc if svc_total_loc > 0 else 0.0

    # 同時修正数 (全クローンセットの comod 合計)
    comod_count = 0
    comod_other_services: set[str] = set()
    for cid in clone_ids:
        cs_df = full_df[full_df["clone_id"] == cid]
        comod_commits = _compute_comod_commits_for_clone_set(cs_df)
        comod_count += len(comod_commits)
        if comod_commits:
            other_svcs = clone_set_svc_map.get(cid, set()) - {service}
            comod_other_services |= other_svcs

    return ServiceMetrics(
        service=service,
        clone_set_count=clone_set_count,
        total_clone_line_count=total_clone_line,
        clone_avg_line_count=round(avg_line, 2),
        clone_file_count=clone_file_count,
        roc=round(roc, 6),
        comod_count=comod_count,
        comod_other_service_count=len(comod_other_services),
    )


# ---------------------------------------------------------------------------
# クローンセット粒度メトリクス
# ---------------------------------------------------------------------------


def compute_clone_set_metrics(
    df: pd.DataFrame,
) -> list[CloneSetMetrics]:
    """クローンセット粒度のメトリクスを計算する.

    Args:
        df: enriched_fragments DataFrame.

    Returns:
        クローンセットごとの CloneSetMetrics リスト.
    """
    if df.empty:
        return []

    results: list[CloneSetMetrics] = []
    for clone_id, cs_df in df.groupby("clone_id"):
        metrics = _compute_single_clone_set(str(clone_id), cs_df)
        results.append(metrics)

    return sorted(results, key=lambda m: m.clone_id)


def _compute_single_clone_set(
    clone_id: str,
    cs_df: pd.DataFrame,
) -> CloneSetMetrics:
    """1 クローンセットの CloneSetMetrics を計算する."""
    services = {s for s in cs_df["service"].unique() if s}
    service_count = len(services)
    total_frags = len(cs_df)
    is_cross = service_count >= 2

    # クロスサービス系
    if is_cross:
        cross_frags = cs_df[cs_df["service"] != ""]
        cross_count = len(cross_frags)
        cross_line = int(cross_frags["line_count"].sum())
    else:
        cross_count = 0
        cross_line = 0

    cross_ratio = cross_count / total_frags if total_frags > 0 else 0.0
    cross_scale = cross_count * cross_line

    # サービスを跨っている要素数 = 全フラグメント数 (is_cross の場合)
    cross_element_count = total_frags if is_cross else 0

    # 同時修正
    comod_commits = _compute_comod_commits_for_clone_set(cs_df)
    comod_count = len(comod_commits)
    comod_frag_indices = _get_comod_fragment_indices(cs_df, comod_commits)
    comod_frag_count = len(comod_frag_indices)
    comod_frag_ratio = comod_frag_count / total_frags if total_frags > 0 else 0.0

    return CloneSetMetrics(
        clone_id=clone_id,
        service_count=service_count,
        cross_service_fragment_count=cross_count,
        cross_service_fragment_ratio=round(cross_ratio, 6),
        cross_service_line_count=cross_line,
        cross_service_scale=cross_scale,
        cross_service_element_count=cross_element_count,
        comod_count=comod_count,
        comod_fragment_count=comod_frag_count,
        comod_fragment_ratio=round(comod_frag_ratio, 6),
    )


# ---------------------------------------------------------------------------
# ファイル粒度メトリクス
# ---------------------------------------------------------------------------


def compute_file_metrics(
    df: pd.DataFrame,
    total_service_count: int,
) -> list[FileMetrics]:
    """ファイル粒度のメトリクスを計算する.

    Args:
        df: enriched_fragments DataFrame.
        total_service_count: プロジェクト内の全サービス数.

    Returns:
        ファイルごとの FileMetrics リスト.
    """
    if df.empty:
        return []

    clone_set_svc_map = _build_clone_set_service_map(df)

    results: list[FileMetrics] = []
    for file_path, file_df in df.groupby("file_path"):
        metrics = _compute_single_file(
            str(file_path),
            file_df,
            df,
            clone_set_svc_map,
            total_service_count,
        )
        results.append(metrics)

    return sorted(results, key=lambda m: m.file_path)


def _compute_single_file(
    file_path: str,
    file_df: pd.DataFrame,
    full_df: pd.DataFrame,
    clone_set_svc_map: dict[str, set[str]],
    total_service_count: int,
) -> FileMetrics:
    """1 ファイルの FileMetrics を計算する."""
    file_service = _majority_service(file_df)
    file_clone_ids = set(file_df["clone_id"].unique())
    total_clone_sets = len(file_clone_ids)

    # クローンセットを共有しているサービス (自分以外)
    sharing_services: set[str] = set()
    cross_clone_sets: set[str] = set()
    cross_line = 0

    for cid in file_clone_ids:
        cs_services = clone_set_svc_map.get(cid, set())
        other_services = cs_services - {file_service} if file_service else cs_services
        if other_services:
            sharing_services |= other_services
            cross_clone_sets.add(cid)
            # このファイル内の当該クローンセットの行数
            cid_file_frags = file_df[file_df["clone_id"] == cid]
            cross_line += int(cid_file_frags["line_count"].sum())

    sharing_count = len(sharing_services)
    cross_cs_count = len(cross_clone_sets)
    cross_cs_ratio = cross_cs_count / total_clone_sets if total_clone_sets > 0 else 0.0
    sharing_ratio = (
        sharing_count / total_service_count if total_service_count > 0 else 0.0
    )

    # 同時修正 (クロスサービスのクローンセットに限定)
    cross_comod_count = 0
    comod_shared_services: set[str] = set()

    for cid in cross_clone_sets:
        cs_df = full_df[full_df["clone_id"] == cid]
        comod_commits = _compute_comod_commits_for_clone_set(cs_df)
        cross_comod_count += len(comod_commits)
        if comod_commits:
            other_svcs = clone_set_svc_map.get(cid, set()) - {file_service}
            comod_shared_services |= other_svcs

    return FileMetrics(
        file_path=file_path,
        service=file_service,
        sharing_service_count=sharing_count,
        total_service_count=total_service_count,
        cross_service_clone_set_count=cross_cs_count,
        cross_service_clone_set_ratio=round(cross_cs_ratio, 6),
        sharing_service_ratio=round(sharing_ratio, 6),
        cross_service_line_count=cross_line,
        cross_service_comod_count=cross_comod_count,
        comod_shared_service_count=len(comod_shared_services),
    )


def _majority_service(file_df: pd.DataFrame) -> str:
    """ファイル内で最も多いサービス名を返す. 空文字は除外."""
    resolved = file_df[file_df["service"] != ""]
    if resolved.empty:
        return ""
    return str(resolved["service"].mode().iloc[0])


# ---------------------------------------------------------------------------
# 統合エントリポイント
# ---------------------------------------------------------------------------


def compute_all_metrics(
    enriched_csv_path: Path,
    services_json_path: Path,
    language: str,
) -> dict[str, list[dict[str, Any]]]:
    """3 粒度のメトリクスをまとめて計算し, 辞書形式で返す.

    Args:
        enriched_csv_path: enriched_fragments.csv パス.
        services_json_path: services.json パス.
        language: 言語名.

    Returns:
        ``{"service": [...], "clone_set": [...], "file": [...]}``
        各値は dataclass を辞書化したリスト.
    """
    df = load_enriched_fragments(enriched_csv_path)
    lang_stats = load_language_stats(services_json_path, language)

    service_metrics = compute_service_metrics(df, lang_stats)
    clone_set_metrics = compute_clone_set_metrics(df)

    # total_service_count: language_stats の services 数,
    # なければ DataFrame 内のユニークサービス数で代替
    services_section = lang_stats.get("services", {})
    total_svc = (
        len(services_section)
        if services_section
        else len({s for s in df["service"].unique() if s})
    )
    file_metrics = compute_file_metrics(df, total_svc)

    return {
        "service": [asdict(m) for m in service_metrics],
        "clone_set": [asdict(m) for m in clone_set_metrics],
        "file": [asdict(m) for m in file_metrics],
    }


def metrics_to_dataframes(
    metrics: dict[str, list[dict[str, Any]]],
) -> dict[str, pd.DataFrame]:
    """compute_all_metrics の結果を DataFrame に変換する.

    Args:
        metrics: ``compute_all_metrics()`` の戻り値.

    Returns:
        ``{"service": DataFrame, "clone_set": DataFrame, "file": DataFrame}``.
    """
    return {key: pd.DataFrame(rows) for key, rows in metrics.items()}
