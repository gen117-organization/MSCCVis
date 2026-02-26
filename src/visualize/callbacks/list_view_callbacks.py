"""ドリルダウンリストビューのコールバック.

ナビゲーション状態管理 + テーブルレンダリング.
"""

from __future__ import annotations

import logging
from typing import Any

import dash
import pandas as pd
from dash import Input, Output, State, ALL, no_update

from ..components.list_view import build_breadcrumb, build_detail_panel
from ..data_loader.metrics_loader import (
    clear_metrics_cache,
    get_cs_table_df,
    get_file_table_df,
    get_service_table_df,
    load_metrics_dataframes,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# カラム定義
# ---------------------------------------------------------------------------


def _service_columns() -> list[dict]:
    return [
        {"id": "service",                   "name": "Service",          "type": "text"},
        {"id": "clone_set_count",           "name": "# Clone Sets",     "type": "numeric"},
        {"id": "inter_clone_set_count",     "name": "# Inter CS",       "type": "numeric"},
        {"id": "total_clone_line_count",    "name": "Clone LOC",        "type": "numeric"},
        {"id": "roc_pct",                   "name": "ROC (%)",          "type": "numeric"},
        {"id": "comod_count",               "name": "Comod Count",      "type": "numeric"},
        {"id": "comod_other_service_count", "name": "Related MS",       "type": "numeric"},
    ]


def _file_columns(include_service: bool = True) -> list[dict]:
    cols: list[dict] = [{"id": "file_name", "name": "File", "type": "text"}]
    if include_service:
        cols.append({"id": "service", "name": "Service", "type": "text"})
    cols += [
        {"id": "file_type",                     "name": "Type",         "type": "text"},
        {"id": "sharing_service_count",         "name": "Shared MS",    "type": "numeric"},
        {"id": "cross_service_clone_set_count", "name": "# Shared CS",  "type": "numeric"},
        {"id": "cross_cs_ratio_pct",            "name": "Shared CS%",   "type": "numeric"},
        {"id": "cross_service_comod_count",     "name": "Comod",        "type": "numeric"},
    ]
    return cols


def _cs_columns() -> list[dict]:
    return [
        {"id": "clone_id",                 "name": "Clone ID",    "type": "text"},
        {"id": "service_count",            "name": "# MS",        "type": "numeric"},
        {"id": "comod_count",              "name": "Comod",       "type": "numeric"},
        {"id": "inter_frag_ratio_pct",     "name": "Inter%",      "type": "numeric"},
        {"id": "cross_service_line_count", "name": "Inter LOC",   "type": "numeric"},
        {"id": "file_types",               "name": "File Types",  "type": "text"},
    ]


# デフォルトソート定義 (column_id, direction)
_DEFAULT_SORT: dict[str, list[dict]] = {
    "service":  [{"column_id": "clone_set_count",       "direction": "desc"}],
    "file":     [{"column_id": "sharing_service_count", "direction": "desc"}],
    "cs":       [{"column_id": "comod_count",           "direction": "desc"}],
}


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _parse_project(project_value: str | None) -> tuple[str | None, str | None, str | None]:
    """project_selector value から (project, commit, language) を取り出す."""
    if not project_value:
        return None, None, None
    try:
        project, commit, language = project_value.split("|||", 2)
        return project, commit, language
    except (ValueError, AttributeError):
        return None, None, None


def _initial_nav() -> dict:
    return {
        "origin": "ms",
        "ms_name": None,
        "l2_tab": "file",
        "level": 1,
        "detail_id": None,
        "_last_cell": None,   # 最後に処理した active_cell（二重処理防止）
    }


def _empty_table_outputs() -> tuple:
    """テーブルを空にする出力タプル."""
    return (
        [],       # columns
        [],       # data
        [],       # sort_by
        0,        # page_current
        [],       # breadcrumb children
        {"flexShrink": "0", "display": "none"},   # l2-subtabs-container style
        [],       # detail-panel children
        {"display": "none"},                       # detail-panel style
        {"display": "block", "padding": "20px", "color": "#888", "textAlign": "center"},  # no-data-msg
    )


def _df_to_records(df: pd.DataFrame, cols: list[dict]) -> list[dict]:
    """列定義に基づいて DataFrame を records リストに変換する."""
    if df is None or df.empty:
        return []
    col_ids = [c["id"] for c in cols]
    existing = [c for c in col_ids if c in df.columns]
    sub = df[existing].copy()
    # 不足列を None で補完
    for c in col_ids:
        if c not in sub.columns:
            sub[c] = None
    # NaN を None に変換（JSON シリアライズ対応）
    records = sub[col_ids].where(pd.notna(sub[col_ids]), None).to_dict("records")
    return records


def _apply_sort(df: pd.DataFrame, sort_by: list[dict]) -> pd.DataFrame:
    """sort_by リストに従って DataFrame をソートする."""
    if df.empty or not sort_by:
        return df
    by = []
    ascending = []
    for s in sort_by:
        col = s.get("column_id")
        if col and col in df.columns:
            by.append(col)
            ascending.append(s.get("direction", "asc") == "asc")
    if by:
        df = df.sort_values(by=by, ascending=ascending, na_position="last")
    return df


# ---------------------------------------------------------------------------
# ドリルダウン / ナビゲーション
# ---------------------------------------------------------------------------


def _drill_down(nav: dict, row: dict, l2_tab: str) -> dict:
    """行クリックに基づいてナビゲーション状態を更新する."""
    origin = nav.get("origin", "ms")
    level = nav.get("level", 1)

    if origin == "ms":
        if level == 1:
            ms_name = row.get("service", "")
            return {**nav, "ms_name": ms_name, "l2_tab": l2_tab, "level": 2}
        elif level == 2:
            detail_id = row.get("file_path") or row.get("clone_id") or ""
            return {**nav, "detail_id": str(detail_id), "level": 3}
    else:
        # file / cs origin: level 1 → detail (level 2)
        detail_id = row.get("file_path") or row.get("clone_id") or ""
        return {**nav, "detail_id": str(detail_id), "level": 2}

    return nav


def _navigate_back(nav: dict, target: str) -> dict:
    """パンくずクリックに基づいてナビゲーション状態を巻き戻す."""
    if target == "root":
        return {**_initial_nav(), "origin": nav.get("origin", "ms")}
    if target == "ms":
        return {**nav, "level": 2, "detail_id": None, "_last_cell": None}
    return nav


# ---------------------------------------------------------------------------
# コールバック登録
# ---------------------------------------------------------------------------


def register_list_view_callbacks(app: dash.Dash, app_data: dict) -> None:
    """リストビュー関連のコールバックをすべて登録する."""

    # ── A: ナビゲーション状態更新 ──────────────────────────────────────────

    @app.callback(
        Output("list-nav-store", "data"),
        [
            Input("list-origin-tabs", "active_tab"),
            Input("list-main-table", "active_cell"),
            Input("list-l2-tabs", "active_tab"),
            Input({"type": "list-bc-btn", "index": ALL}, "n_clicks"),
        ],
        [
            State("list-nav-store", "data"),
            State("list-main-table", "data"),
        ],
        prevent_initial_call=True,
    )
    def update_nav_store(
        origin_tab: str,
        active_cell: dict | None,
        l2_tab: str,
        bc_clicks: list,
        nav: dict,
        table_data: list[dict],
    ) -> dict:
        ctx = dash.callback_context
        if not ctx.triggered:
            return no_update

        triggered_id = ctx.triggered_id

        # 起点タブ切り替え → Level 1 にリセット
        if triggered_id == "list-origin-tabs":
            return {**_initial_nav(), "origin": origin_tab or "ms"}

        # L2 サブタブ切り替え
        if triggered_id == "list-l2-tabs":
            return {**nav, "l2_tab": l2_tab or "file", "_last_cell": None}

        # パンくずクリック
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "list-bc-btn":
            # どのボタンが実際にクリックされたか確認
            triggered_prop = ctx.triggered[0]["prop_id"]
            import json as _json
            try:
                btn_id = _json.loads(triggered_prop.split(".")[0])
            except Exception:
                return no_update
            # n_clicks が 0 なら初期化トリガー → 無視
            if not ctx.triggered[0]["value"]:
                return no_update
            return _navigate_back(nav, btn_id.get("index", "root"))

        # 行クリック (DataTable active_cell)
        if triggered_id == "list-main-table":
            if active_cell is None or not table_data:
                return no_update
            # 同じセルの二重処理防止
            last_cell = nav.get("_last_cell")
            if last_cell is not None and last_cell == active_cell:
                return no_update
            row_idx = active_cell.get("row", 0)
            if row_idx >= len(table_data):
                return no_update
            row = table_data[row_idx]
            new_nav = _drill_down(nav, row, nav.get("l2_tab", "file"))
            new_nav["_last_cell"] = active_cell
            return new_nav

        return no_update

    # ── B: テーブル・パンくず・詳細パネルのレンダリング ────────────────────

    @app.callback(
        [
            Output("list-main-table", "columns"),
            Output("list-main-table", "data"),
            Output("list-main-table", "sort_by"),
            Output("list-main-table", "page_current"),
            Output("list-breadcrumb", "children"),
            Output("list-l2-subtabs-container", "style"),
            Output("list-detail-panel", "children"),
            Output("list-detail-panel", "style"),
            Output("list-no-data-msg", "style"),
        ],
        [
            Input("list-nav-store", "data"),
            Input("project-selector", "value"),
            Input("list-filetype-filter", "value"),
        ],
        prevent_initial_call=False,
    )
    def render_list_view(
        nav: dict,
        project_value: str | None,
        file_type: str | None,
    ) -> tuple:
        no_data_visible   = {"display": "block", "padding": "20px", "color": "#888", "textAlign": "center"}
        data_hidden        = {"display": "none"}
        l2_hidden          = {"flexShrink": "0", "display": "none"}
        l2_visible         = {"flexShrink": "0", "display": "block", "borderBottom": "1px solid #dee2e6"}
        detail_hidden      = {"display": "none"}
        detail_visible     = {
            "display": "block",
            "borderTop": "2px solid #dee2e6",
            "padding": "12px",
            "maxHeight": "300px",
            "overflowY": "auto",
            "flexShrink": "0",
        }

        if not project_value or not nav:
            return _empty_table_outputs()

        project, commit, language = _parse_project(project_value)
        if not project or not language:
            return _empty_table_outputs()

        # メトリクス読み込み
        try:
            metrics = load_metrics_dataframes(project, language)
        except Exception as exc:
            logger.error("Error loading metrics for %s/%s: %s", project, language, exc)
            return _empty_table_outputs()

        if all(v.empty for k, v in metrics.items() if k != "fragments"):
            return _empty_table_outputs()

        origin = nav.get("origin", "ms")
        level  = nav.get("level", 1)
        ms_name = nav.get("ms_name")
        l2_tab = nav.get("l2_tab", "file")
        detail_id = nav.get("detail_id")
        ft = file_type or "all"

        # パンくず
        bc_children = build_breadcrumb(origin, ms_name, level, l2_tab, detail_id)

        # ── Level 3: 詳細パネル表示 ─────────────────────────────────────
        if level == 3 and detail_id:
            # Level 2 テーブルを継続表示しつつ詳細パネルも出す
            cols, data, sort_by = _build_level2_ms_table(metrics, ms_name, l2_tab, ft)
            detail_content = build_detail_panel(origin, l2_tab, detail_id, metrics)
            return (
                cols, data, sort_by, 0,
                bc_children,
                l2_visible,
                detail_content,
                detail_visible,
                data_hidden,
            )

        # ── Level 2: MS → ファイル / CS ─────────────────────────────────
        if origin == "ms" and level == 2:
            cols, data, sort_by = _build_level2_ms_table(metrics, ms_name, l2_tab, ft)
            return (
                cols, data, sort_by, 0,
                bc_children,
                l2_visible,
                [], detail_hidden,
                data_hidden,
            )

        # ── Level 1 ─────────────────────────────────────────────────────
        if origin == "ms":
            cols, data, sort_by = _build_service_table(metrics)
        elif origin == "file":
            cols, data, sort_by = _build_file_table(metrics, ms_name=None, file_type=ft)
        else:  # "cs"
            cols, data, sort_by = _build_cs_table(metrics, ms_name=None, file_type=ft)

        detail_content: list = []
        # file/cs origin Level 2 → detail
        if origin in ("file", "cs") and level == 2 and detail_id:
            detail_content = build_detail_panel(origin, l2_tab, detail_id, metrics)

        return (
            cols, data, sort_by, 0,
            bc_children,
            l2_hidden,
            detail_content,
            detail_visible if detail_content else detail_hidden,
            data_hidden,
        )

    # ── C: project 変更時にメトリクスキャッシュをパージ ────────────────────

    @app.callback(
        Output("list-nav-store", "data", allow_duplicate=True),
        Input("project-selector", "value"),
        State("list-nav-store", "data"),
        prevent_initial_call=True,
    )
    def reset_nav_on_project_change(project_value: str | None, nav: dict) -> dict:
        """プロジェクトが変わったらキャッシュをクリアして Level 1 に戻す."""
        clear_metrics_cache()
        return {**_initial_nav(), "origin": nav.get("origin", "ms")}


# ---------------------------------------------------------------------------
# テーブルビルダー
# ---------------------------------------------------------------------------


def _build_service_table(
    metrics: dict[str, pd.DataFrame],
) -> tuple[list, list, list]:
    df = get_service_table_df(metrics)
    cols = _service_columns()
    sort_by = _DEFAULT_SORT["service"]
    df = _apply_sort(df, sort_by)
    data = _df_to_records(df, cols)
    return cols, data, sort_by


def _build_file_table(
    metrics: dict[str, pd.DataFrame],
    ms_name: str | None,
    file_type: str,
) -> tuple[list, list, list]:
    df = get_file_table_df(metrics, ms_name=ms_name, file_type=file_type)
    include_svc = ms_name is None  # Level 1 はサービス列あり
    cols = _file_columns(include_service=include_svc)
    sort_by = _DEFAULT_SORT["file"]
    df = _apply_sort(df, sort_by)
    data = _df_to_records(df, cols)
    return cols, data, sort_by


def _build_cs_table(
    metrics: dict[str, pd.DataFrame],
    ms_name: str | None,
    file_type: str,
) -> tuple[list, list, list]:
    df = get_cs_table_df(metrics, ms_name=ms_name, file_type=file_type)
    cols = _cs_columns()
    sort_by = _DEFAULT_SORT["cs"]
    df = _apply_sort(df, sort_by)
    data = _df_to_records(df, cols)
    return cols, data, sort_by


def _build_level2_ms_table(
    metrics: dict[str, pd.DataFrame],
    ms_name: str | None,
    l2_tab: str,
    file_type: str,
) -> tuple[list, list, list]:
    if l2_tab == "file":
        return _build_file_table(metrics, ms_name=ms_name, file_type=file_type)
    else:
        return _build_cs_table(metrics, ms_name=ms_name, file_type=file_type)
