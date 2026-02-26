"""List View 用メトリクスローダー.

precomputed clone_metrics JSON を優先して読み込み，
存在しなければ enriched_fragments CSV から動的計算でフォールバックする．
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/visualize/data_loader → repo root


def _dest() -> Path:
    return _PROJECT_ROOT / "dest"


# ---------------------------------------------------------------------------
# キャッシュキー
# ---------------------------------------------------------------------------

_metrics_cache: dict[tuple[str, str], dict[str, pd.DataFrame]] = {}


def _cache_key(project: str, language: str) -> tuple[str, str]:
    return (project, language.lower())


def clear_metrics_cache() -> None:
    _metrics_cache.clear()


# ---------------------------------------------------------------------------
# メインエントリポイント
# ---------------------------------------------------------------------------


def load_metrics_dataframes(
    project: str,
    language: str,
) -> dict[str, pd.DataFrame]:
    """3 粒度 + enriched fragments の DataFrame を返す.

    Returns:
        ``{"service": df, "clone_set": df, "file": df, "fragments": df}``
        各 df は空でも常に返す．
    """
    key = _cache_key(project, language)
    if key in _metrics_cache:
        return _metrics_cache[key]

    result = _load_and_enrich(project, language)
    _metrics_cache[key] = result
    return result


def _empty_result() -> dict[str, pd.DataFrame]:
    return {
        "service": pd.DataFrame(),
        "clone_set": pd.DataFrame(),
        "file": pd.DataFrame(),
        "fragments": pd.DataFrame(),
    }


def _load_and_enrich(project: str, language: str) -> dict[str, pd.DataFrame]:
    # 1. precomputed JSON
    raw = _load_precomputed(project, language)

    # 2. fallback: compute from enriched_fragments
    if raw is None:
        raw = _compute_from_enriched(project, language)

    if raw is None:
        logger.warning("No metrics available for %s / %s", project, language)
        return _empty_result()

    svc_df = pd.DataFrame(raw.get("service", []))
    cs_df = pd.DataFrame(raw.get("clone_set", []))
    file_df = pd.DataFrame(raw.get("file", []))

    # 3. enriched fragments（file_type・MS 所属の補完に使う）
    frags = _load_enriched_fragments(project, language)

    if not frags.empty:
        file_df = _enrich_file_df(file_df, frags)
        cs_df = _enrich_cs_df(cs_df, frags)

    return {
        "service": svc_df,
        "clone_set": cs_df,
        "file": file_df,
        "fragments": frags,
    }


# ---------------------------------------------------------------------------
# 読み込みヘルパー
# ---------------------------------------------------------------------------


def _load_precomputed(project: str, language: str) -> dict[str, list] | None:
    # 大文字小文字を無視してファイルを検索（言語名は Java / JAVA / java など揺れる）
    metrics_dir = _dest() / "clone_metrics"
    if not metrics_dir.exists():
        logger.debug("clone_metrics dir not found: %s", metrics_dir)
        return None
    lang_lower = language.lower()
    path: Path | None = None
    for candidate in metrics_dir.glob(f"{project}_*.json"):
        # ファイル名から言語部分を取り出して比較
        suffix = candidate.stem[len(project) + 1:]
        if suffix.lower() == lang_lower:
            path = candidate
            break
    if path is None:
        logger.debug("Precomputed metrics not found for %s/%s in %s", project, language, metrics_dir)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read precomputed metrics %s: %s", path, exc)
        return None


def _compute_from_enriched(project: str, language: str) -> dict[str, list] | None:
    enriched_csv = _find_enriched_csv(project, language)
    services_json = _dest() / "services_json" / f"{project}.json"

    if enriched_csv is None or not services_json.exists():
        logger.debug("Cannot compute metrics for %s/%s: missing files", project, language)
        return None

    try:
        from modules.visualization.compute_clone_metrics import (
            compute_all_metrics,
        )

        return compute_all_metrics(enriched_csv, services_json, language)
    except Exception as exc:
        logger.error("Error computing metrics for %s/%s: %s", project, language, exc)
        return None


def _find_enriched_csv(project: str, language: str) -> Path | None:
    enriched_dir = _dest() / "enriched_fragments" / project
    if not enriched_dir.exists():
        return None
    for candidate in sorted(enriched_dir.glob("*.csv")):
        stem = candidate.stem
        for prefix in ("import_", "tks_"):
            if stem.startswith(prefix):
                stem = stem[len(prefix):]
                break
        if stem.lower() == language.lower():
            return candidate
    return None


def _load_enriched_fragments(project: str, language: str) -> pd.DataFrame:
    csv_path = _find_enriched_csv(project, language)
    if csv_path is None:
        return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path)
        df["service"] = df["service"].fillna("") if "service" in df.columns else ""
        if "file_type" in df.columns:
            df["file_type"] = df["file_type"].fillna("unknown")
        return df
    except Exception as exc:
        logger.warning("Failed to read enriched fragments %s: %s", csv_path, exc)
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# 補完（enrich）ヘルパー
# ---------------------------------------------------------------------------


def _enrich_file_df(file_df: pd.DataFrame, frags: pd.DataFrame) -> pd.DataFrame:
    """ファイルメトリクスに file_type 列を付与する."""
    if file_df.empty or "file_type" in file_df.columns:
        return file_df
    if "file_path" not in frags.columns or "file_type" not in frags.columns:
        return file_df
    # ファイルパスごとに最頻 file_type を選ぶ
    type_map = (
        frags[frags["service"] != ""]
        .groupby("file_path")["file_type"]
        .agg(lambda s: s.mode().iloc[0] if not s.empty else "unknown")
        .to_dict()
    )
    file_df = file_df.copy()
    file_df["file_type"] = file_df["file_path"].map(type_map).fillna("unknown")
    return file_df


def _enrich_cs_df(cs_df: pd.DataFrame, frags: pd.DataFrame) -> pd.DataFrame:
    """クローンセットメトリクスに file_types (comma-separated) と
    involved_services (comma-separated) 列を付与する."""
    if cs_df.empty:
        return cs_df
    if "clone_id" not in frags.columns:
        return cs_df

    needed_cols = {"file_types", "involved_services"}
    if needed_cols.issubset(cs_df.columns):
        return cs_df

    cs_df = cs_df.copy()

    # file_type タグ集合
    if "file_type" in frags.columns and "file_types" not in cs_df.columns:
        ft_map = (
            frags.groupby("clone_id")["file_type"]
            .agg(lambda s: ", ".join(sorted(s.dropna().unique())))
            .to_dict()
        )
        cs_df["file_types"] = cs_df["clone_id"].map(ft_map).fillna("")

    # involved services
    if "service" in frags.columns and "involved_services" not in cs_df.columns:
        svc_map = (
            frags[frags["service"] != ""]
            .groupby("clone_id")["service"]
            .agg(lambda s: ", ".join(sorted(s.dropna().unique())))
            .to_dict()
        )
        cs_df["involved_services"] = cs_df["clone_id"].map(svc_map).fillna("")

    return cs_df


# ---------------------------------------------------------------------------
# ビュー用フィルタ / 変換
# ---------------------------------------------------------------------------


def get_service_table_df(metrics: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """MS Level 1 表示用 DataFrame を返す."""
    df = metrics.get("service", pd.DataFrame()).copy()
    if df.empty:
        return df
    if "roc" in df.columns:
        df["roc_pct"] = (df["roc"] * 100).round(2)
    return df


def get_file_table_df(
    metrics: dict[str, pd.DataFrame],
    ms_name: str | None = None,
    file_type: str = "all",
) -> pd.DataFrame:
    """ファイル Level 1 / MS Level 2 ファイルタブ用 DataFrame を返す."""
    df = metrics.get("file", pd.DataFrame()).copy()
    if df.empty:
        return df

    # MS フィルタ
    if ms_name and "service" in df.columns:
        df = df[df["service"] == ms_name]

    # file_type フィルタ
    if file_type and file_type != "all" and "file_type" in df.columns:
        df = df[df["file_type"].str.lower() == file_type.lower()]

    # ファイル名（パスの最終要素）を追加
    if "file_path" in df.columns:
        df["file_name"] = df["file_path"].apply(lambda p: Path(p).name)

    # パーセンテージ列
    if "cross_service_clone_set_ratio" in df.columns:
        df["cross_cs_ratio_pct"] = (df["cross_service_clone_set_ratio"] * 100).round(1)
    if "sharing_service_ratio" in df.columns:
        df["sharing_service_ratio_pct"] = (df["sharing_service_ratio"] * 100).round(1)

    return df


def get_cs_table_df(
    metrics: dict[str, pd.DataFrame],
    ms_name: str | None = None,
    file_type: str = "all",
) -> pd.DataFrame:
    """CS Level 1 / MS Level 2 クローンセットタブ用 DataFrame を返す."""
    cs_df = metrics.get("clone_set", pd.DataFrame()).copy()
    frags = metrics.get("fragments", pd.DataFrame())

    if cs_df.empty:
        return cs_df

    # MS フィルタ: frags でそのサービスに属するクローンセットに絞る
    if ms_name and not frags.empty and "service" in frags.columns:
        ms_ids = set(frags[frags["service"] == ms_name]["clone_id"].astype(str).unique())
        if "clone_id" in cs_df.columns:
            cs_df = cs_df[cs_df["clone_id"].astype(str).isin(ms_ids)]

    # file_type フィルタ（file_types 列に含む場合）
    if file_type and file_type != "all" and "file_types" in cs_df.columns:
        cs_df = cs_df[
            cs_df["file_types"].str.lower().str.contains(file_type.lower(), na=False)
        ]

    # パーセンテージ列
    if "cross_service_fragment_ratio" in cs_df.columns:
        cs_df["inter_frag_ratio_pct"] = (cs_df["cross_service_fragment_ratio"] * 100).round(1)
    if "comod_fragment_ratio" in cs_df.columns:
        cs_df["comod_frag_ratio_pct"] = (cs_df["comod_fragment_ratio"] * 100).round(1)

    return cs_df
