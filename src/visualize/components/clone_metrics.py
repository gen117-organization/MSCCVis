import logging
import os

from dash import html, dcc
import pandas as pd

from ..utils import get_local_snippet
from ..constants import DetectionMethod
from collections import Counter

logger = logging.getLogger(__name__)

def calculate_unique_pair_count_for_clone(clone_df):
    """クローンデータフレームに対してユニークペア数を計算する"""
    if clone_df is None or clone_df.empty:
        return 0

    # 重複除去のためのキーを作成
    df_temp = clone_df.copy()
    df_temp["clone_key"] = (
        df_temp["clone_id"].astype(str)
        + "|"
        + df_temp["file_path_x"].str.split("/").str[-1]
        + "|"
        + df_temp["start_line_x"].astype(str)
        + "-"
        + df_temp["end_line_x"].astype(str)
        + "|"
        + df_temp["file_path_y"].str.split("/").str[-1]
        + "|"
        + df_temp["start_line_y"].astype(str)
        + "-"
        + df_temp["end_line_y"].astype(str)
    )

    # coord_pair列が存在しない場合は作成
    if "coord_pair" not in df_temp.columns:
        df_temp["coord_pair"] = (
            df_temp["file_id_y"].astype(str) + "_" + df_temp["file_id_x"].astype(str)
        )

    # 重複除去して数をカウント
    return len(df_temp.drop_duplicates(subset=["coord_pair", "clone_key"]))


def calculate_cross_service_metrics(df):
    """クローンの多サービス跨り度を分析する"""
    if df is None or df.empty:
        return {}, 0, {}

    # 全サービス数を計算
    services_x = set(df["service_x"].unique())
    services_y = set(df["service_y"].unique())
    total_services = len(services_x.union(services_y))

    # 各クローンIDが跨るサービス数を計算
    clone_metrics = {}
    for clone_id in df["clone_id"].unique():
        clone_rows = df[df["clone_id"] == clone_id]
        services_x = set(clone_rows["service_x"].unique())
        services_y = set(clone_rows["service_y"].unique())
        all_clone_services = services_x.union(services_y)

        # ユニークペア数を計算
        unique_pair_count = calculate_unique_pair_count_for_clone(clone_rows)

        # Co-modifiedペア数を計算
        comodified_count = 0
        if "comodified" in clone_rows.columns:
            comodified_count = len(
                clone_rows[clone_rows["comodified"].isin([1, True, "1", "True"])]
            )

        # Code Typeの内訳を計算
        code_types = Counter()
        is_mixed = False
        if "file_type_x" in clone_rows.columns and "file_type_y" in clone_rows.columns:
            # Mixed判定: Test vs Product (Test vs Non-Test)
            is_test_x = clone_rows["file_type_x"] == "test"
            is_test_y = clone_rows["file_type_y"] == "test"
            mixed_rows = clone_rows[is_test_x != is_test_y]

            if not mixed_rows.empty:
                is_mixed = True

            # 集計はx側をベースにする（代表値）
            code_types.update(clone_rows["file_type_x"])
        elif "file_type_x" in clone_rows.columns:
            code_types.update(clone_rows["file_type_x"])

        # Detection Method (もし混在している場合)
        methods = set()
        if "detection_method" in clone_rows.columns:
            methods.update(clone_rows["detection_method"].unique())
        elif "clone_type" in clone_rows.columns:  # fallback
            methods.update(clone_rows["clone_type"].unique())

        clone_metrics[clone_id] = {
            "service_count": len(all_clone_services),
            "services": list(all_clone_services),
            "pair_count": unique_pair_count,  # ユニークペア数を使用
            "total_pair_count": len(clone_rows),  # 元の重複含む数も保持
            "comodified_count": comodified_count,
            "code_types": dict(code_types),
            "is_mixed": is_mixed,
            "methods": list(methods),
            "inter_service_pairs": len(clone_rows[clone_rows["clone_type"] == "inter"]),
            "file_paths": list(
                set(
                    clone_rows["file_path_x"].tolist()
                    + clone_rows["file_path_y"].tolist()
                )
            ),
        }

    # サービス跨り度の分布
    service_count_distribution = Counter(
        [metrics["service_count"] for metrics in clone_metrics.values()]
    )

    return clone_metrics, total_services, service_count_distribution


def generate_cross_service_filter_options(clone_stats):
    """
    クローンIDごとの統計情報リストからフィルタリングオプションを生成
    clone_stats: list of dict {'clone_id': id, 'service_count': count, 'code_type': type}
    Sorted by service_count DESC
    """
    options = [{"label": "Show All Clones", "value": "all"}]

    for stat in clone_stats:
        # Improved formatting using symbols for readability and spacing
        label = f"🆔 {stat['clone_id']}   🌐 {stat['service_count']} Services   🏷️ {stat['code_type']}"
        options.append({"label": label, "value": stat["clone_id"]})

    return options


def get_github_base_url(project):
    """プロジェクト概要と同じ方法でGitHubベースURLを取得する"""
    from ..data_loader import load_project_summary

    summary_data = load_project_summary()
    if summary_data and project in summary_data.get("projects", {}):
        project_info = summary_data["projects"][project]
        if "metadata" in project_info:
            metadata = project_info["metadata"]
            return metadata.get("url", f"https://github.com/{project}")

    # fallback: プロジェクト名からURLを構築
    return f"https://github.com/{project}"


def generate_github_file_url(project, file_path, start_line=None, end_line=None):
    """プロジェクト概要と整合性のあるGitHubファイルURLを生成する"""
    if not project or not file_path:
        return None

    # プロジェクト概要と同じ方法でベースURLを取得
    github_base = get_github_base_url(project)

    # ファイルパスの先頭の/を削除
    clean_file_path = file_path.lstrip("/")

    # デフォルトブランチを使用（通常は main または master）
    # プロジェクトサマリーJSONに branch 情報があればそれを使用
    from ..data_loader import load_project_summary

    branch = "main"  # デフォルト

    summary_data = load_project_summary()
    if summary_data and project in summary_data.get("projects", {}):
        project_info = summary_data["projects"][project]
        if "metadata" in project_info:
            metadata = project_info["metadata"]
            branch = metadata.get("default_branch", "master")

    # ファイルURLを構築
    file_url = f"{github_base}/blob/{branch}/{clean_file_path}"

    # 行番号が指定されている場合は行範囲を追加
    if start_line is not None:
        if end_line is not None and end_line != start_line:
            file_url += f"#L{start_line}-L{end_line}"
        else:
            file_url += f"#L{start_line}"

    return file_url


def find_overlapping_clones(df, click_x, click_y):
    """指定された座標にあるクローンを検索する"""
    # 散布図は x=file_id_y, y=file_id_x で描画されているため、
    # coord_pair (file_id_y_file_id_x) と一致させるには click_x_click_y の順にする必要がある
    coord_pair = f"{int(click_x)}_{int(click_y)}"

    # coord_pair列が存在しない場合は作成
    if "coord_pair" not in df.columns:
        df["coord_pair"] = (
            df["file_id_y"].astype(str) + "_" + df["file_id_x"].astype(str)
        )

    # 該当する座標のクローンを検索
    overlapping_indices = df[df["coord_pair"] == coord_pair].index.tolist()
    return overlapping_indices


def build_clone_selector(overlapping_indices, df):
    """重複クローン選択用のドロップダウンを生成する"""
    if len(overlapping_indices) <= 1:
        return html.Div()  # 重複がない場合は何も表示しない

    clone_count = len(overlapping_indices)
    options = []
    clone_data = []  # ソート用のデータを格納
    seen_clones = set()  # 重複除去用

    # まず全てのクローンデータを収集し、重複を除去
    for i, idx in enumerate(overlapping_indices):
        row = df.loc[idx]
        file_x = row.get("file_path_x", "Unknown").split("/")[-1]
        file_y = row.get("file_path_y", "Unknown").split("/")[-1]
        lines_x = f"{row.get('start_line_x', 0)}-{row.get('end_line_x', 0)}"
        lines_y = f"{row.get('start_line_y', 0)}-{row.get('end_line_y', 0)}"
        clone_id = row.get("clone_id", idx)

        # 重複チェック用のキーを作成（clone_id + ファイル + 行範囲）
        clone_key = f"{clone_id}|{file_x}|{lines_x}|{file_y}|{lines_y}"

        if clone_key not in seen_clones:
            seen_clones.add(clone_key)
            clone_data.append(
                {
                    "clone_id": clone_id,
                    "idx": idx,
                    "file_x": file_x,
                    "file_y": file_y,
                    "lines_x": lines_x,
                    "lines_y": lines_y,
                    "clone_key": clone_key,
                }
            )

    # 重複除去後の数が1以下の場合は何も表示しない
    if len(clone_data) <= 1:
        return html.Div()

    # clone_idごとの個数をカウント（重複除去後）
    from collections import Counter

    clone_id_counts = Counter(data["clone_id"] for data in clone_data)

    # ペア数でソート（多い順、同じペア数の場合はclone_idでソート）
    clone_data.sort(key=lambda x: (-clone_id_counts[x["clone_id"]], x["clone_id"]))

    # ソート後にオプションを作成（clone_idの個数情報を追加）
    for data in clone_data:
        clone_id = data["clone_id"]
        count = clone_id_counts[clone_id]
        count_info = f" ({count} pairs)" if count > 1 else ""
        label = f"Clone ID {clone_id}: {data['file_x']}[{data['lines_x']}] ↔ {data['file_y']}[{data['lines_y']}]{count_info}"
        options.append({"label": label, "value": data["idx"]})

    # 重複除去の情報を表示
    removed_count = clone_count - len(clone_data)
    header_text = (
        f"{len(clone_data)} overlapping clones found. Select a clone to display:"
    )
    if removed_count > 0:
        header_text += f" ({removed_count} duplicates removed)"

    return html.Div(
        [
            html.H6(header_text, style={"margin-bottom": "10px"}),
            dcc.Dropdown(
                id="clone-dropdown",
                options=options,
                value=clone_data[0]["idx"],  # ソート後の最初のクローンを選択
                clearable=False,
                style={
                    "width": "100%",
                    "minWidth": "600px",
                    "maxWidth": "900px",
                    "margin-bottom": "15px",
                },  # 幅を調整
            ),
        ],
        style={
            "background": "white",
            "padding": "15px",
            "border-radius": "8px",
            "margin-bottom": "5px",
        },
    )


