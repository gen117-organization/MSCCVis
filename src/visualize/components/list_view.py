"""ドリルダウン方式クローンメトリクスリストビュー — レイアウトコンポーネント.

3 つの起点タブ (MSベース / ファイルベース / CSベース) から
階層的に詳細を掘り下げる DataTable ベースのビューを提供する.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

FILE_TYPE_OPTIONS = [
    {"label": "All Types", "value": "all"},
    {"label": "Logic",     "value": "logic"},
    {"label": "Test",      "value": "test"},
    {"label": "Data",      "value": "data"},
    {"label": "Config",    "value": "config"},
]

# DataTable 共通スタイル
_TABLE_STYLE_HEADER = {
    "backgroundColor": "#f0f3f7",
    "fontWeight": "600",
    "fontSize": "12px",
    "border": "1px solid #dee2e6",
    "textAlign": "center",
    "whiteSpace": "normal",
    "height": "auto",
}
_TABLE_STYLE_CELL = {
    "fontSize": "12px",
    "padding": "6px 10px",
    "border": "1px solid #e9ecef",
    "textAlign": "left",
    "whiteSpace": "normal",
    "height": "auto",
    "overflow": "hidden",
    "textOverflow": "ellipsis",
    "maxWidth": "280px",
}
_TABLE_STYLE_DATA_CONDITIONAL = [
    {
        "if": {"row_index": "odd"},
        "backgroundColor": "#f8f9fa",
    },
    {
        "if": {"state": "selected"},
        "backgroundColor": "#d0e8ff",
        "border": "1px solid #4a90d9",
    },
    {
        "if": {"state": "active"},
        "backgroundColor": "#e6f2ff",
        "border": "1px solid #4a90d9",
    },
]

# ---------------------------------------------------------------------------
# 初期ナビゲーション状態
# ---------------------------------------------------------------------------


def _initial_nav() -> dict:
    return {
        "origin": "ms",   # "ms" | "file" | "cs"
        "ms_name": None,  # str — 選択された MS 名 (MS Level 2 以降)
        "l2_tab": "file", # "file" | "cs" — MS Level 2 内のサブタブ
        "level": 1,       # 1 | 2 | 3
        "detail_id": None,# str — Level 3 の detail 識別子
    }


# ---------------------------------------------------------------------------
# DataTable スタブ（常に DOM に存在させる）
# ---------------------------------------------------------------------------


def _make_stub_table() -> dash_table.DataTable:
    """初期表示用の空 DataTable."""
    return dash_table.DataTable(
        id="list-main-table",
        columns=[],
        data=[],
        page_size=25,
        page_action="native",
        sort_action="native",
        sort_mode="single",
        row_selectable=False,
        style_table={"overflowX": "auto", "minWidth": "100%"},
        style_header=_TABLE_STYLE_HEADER,
        style_cell=_TABLE_STYLE_CELL,
        style_data_conditional=_TABLE_STYLE_DATA_CONDITIONAL,
        active_cell=None,
        tooltip_delay=0,
        tooltip_duration=None,
    )


# ---------------------------------------------------------------------------
# メインレイアウト
# ---------------------------------------------------------------------------


def create_list_view_layout() -> html.Div:
    """ドリルダウンリストビューの全体レイアウトを返す."""
    return html.Div(
        id="list-view-container",
        className="list-view-container",
        style={
            "height": "100%",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "backgroundColor": "#fff",
        },
        children=[
            # ── 起点タブ (MS / File / CS) ──────────────────────────────────
            dbc.Tabs(
                id="list-origin-tabs",
                active_tab="ms",
                children=[
                    dbc.Tab(label="MS Base",   tab_id="ms",   className="list-origin-tab"),
                    dbc.Tab(label="File Base", tab_id="file", className="list-origin-tab"),
                    dbc.Tab(label="CS Base",   tab_id="cs",   className="list-origin-tab"),
                ],
                style={
                    "borderBottom": "2px solid #dee2e6",
                    "paddingLeft": "8px",
                    "backgroundColor": "#f8f9fa",
                    "flexShrink": "0",
                },
            ),

            # ── ツールバー（パンくず + フィルタ）──────────────────────────
            html.Div(
                id="list-toolbar",
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "16px",
                    "padding": "6px 12px",
                    "borderBottom": "1px solid #e9ecef",
                    "backgroundColor": "#fafbfc",
                    "flexShrink": "0",
                    "flexWrap": "wrap",
                },
                children=[
                    # パンくず
                    html.Div(
                        id="list-breadcrumb",
                        style={"flex": "1", "minWidth": "200px"},
                        children=[_breadcrumb_root("ms")],
                    ),
                    # File Type ドロップダウン
                    html.Div(
                        [
                            html.Span(
                                "File Type:",
                                style={
                                    "fontSize": "12px",
                                    "fontWeight": "600",
                                    "marginRight": "6px",
                                    "whiteSpace": "nowrap",
                                },
                            ),
                            dcc.Dropdown(
                                id="list-filetype-filter",
                                options=FILE_TYPE_OPTIONS,
                                value="all",
                                clearable=False,
                                searchable=False,
                                style={"width": "130px", "fontSize": "12px"},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                ],
            ),

            # ── Level 2 サブタブ（MS Level 2 のみ表示） ───────────────────
            html.Div(
                id="list-l2-subtabs-container",
                style={"flexShrink": "0", "display": "none"},
                children=[
                    dbc.Tabs(
                        id="list-l2-tabs",
                        active_tab="file",
                        children=[
                            dbc.Tab(label="Files",       tab_id="file"),
                            dbc.Tab(label="Clone Sets",  tab_id="cs"),
                        ],
                        style={"padding": "0 12px", "backgroundColor": "#fff"},
                    )
                ],
            ),

            # ── データが無い時のメッセージ ─────────────────────────────────
            html.Div(
                id="list-no-data-msg",
                style={"display": "none", "padding": "20px", "color": "#888", "textAlign": "center"},
                children="Select a project to view clone metrics.",
            ),

            # ── テーブルコンテナ ───────────────────────────────────────────
            dcc.Loading(
                id="loading-list",
                type="dot",
                color="#4a90d9",
                children=[
                    html.Div(
                        id="list-table-wrapper",
                        style={"flex": "1", "overflowY": "auto", "padding": "8px 12px"},
                        children=[_make_stub_table()],
                    ),
                ],
                style={"flex": "1", "overflow": "hidden", "display": "flex", "flexDirection": "column"},
            ),

            # ── Level 3: 詳細カード ────────────────────────────────────────
            html.Div(
                id="list-detail-panel",
                style={"display": "none", "borderTop": "2px solid #dee2e6", "padding": "12px", "maxHeight": "40%", "overflowY": "auto", "flexShrink": "0"},
            ),

            # ── ストア ────────────────────────────────────────────────────
            dcc.Store(id="list-nav-store", data=_initial_nav()),
        ],
    )


# ---------------------------------------------------------------------------
# パンくずリスト生成
# ---------------------------------------------------------------------------


def _breadcrumb_root(origin: str) -> html.Span:
    labels = {"ms": "MS Base", "file": "File Base", "cs": "CS Base"}
    return html.Span(
        labels.get(origin, origin),
        id={"type": "list-bc-btn", "index": "root"},
        n_clicks=0,
        style={
            "cursor": "pointer",
            "color": "#0366d6",
            "fontSize": "12px",
            "fontWeight": "600",
        },
    )


def build_breadcrumb(
    origin: str,
    ms_name: str | None,
    level: int,
    l2_tab: str,
    detail_id: str | None,
) -> list:
    """ナビゲーション状態からパンくずリスト要素を生成する."""
    sep = html.Span(" › ", style={"color": "#999", "margin": "0 4px", "fontSize": "12px"})
    bc: list = []

    # Root
    labels = {"ms": "MS Base", "file": "File Base", "cs": "CS Base"}
    root_label = labels.get(origin, origin)
    bc.append(
        html.Span(
            root_label,
            id={"type": "list-bc-btn", "index": "root"},
            n_clicks=0,
            style={
                "cursor": "pointer" if level > 1 else "default",
                "color": "#0366d6" if level > 1 else "#495057",
                "fontSize": "12px",
                "fontWeight": "600",
            },
        )
    )

    if origin == "ms" and level >= 2 and ms_name:
        bc.append(sep)
        bc.append(
            html.Span(
                ms_name,
                id={"type": "list-bc-btn", "index": "ms"},
                n_clicks=0,
                style={
                    "cursor": "pointer" if level > 2 else "default",
                    "color": "#0366d6" if level > 2 else "#495057",
                    "fontSize": "12px",
                },
            )
        )
        if level >= 2:
            bc.append(sep)
            tab_label = "Files" if l2_tab == "file" else "Clone Sets"
            bc.append(
                html.Span(
                    tab_label,
                    style={"fontSize": "12px", "color": "#495057"},
                )
            )

    if level >= 3 and detail_id:
        bc.append(sep)
        short = detail_id if len(detail_id) <= 40 else f"…{detail_id[-38:]}"
        bc.append(
            html.Span(
                short,
                style={"fontSize": "12px", "color": "#495057", "fontStyle": "italic"},
            )
        )

    return bc


# ---------------------------------------------------------------------------
# Level 3 詳細カード
# ---------------------------------------------------------------------------


def build_detail_panel(
    origin: str,
    l2_tab: str,
    detail_id: str,
    metrics: dict,
) -> list:
    """Level 3 詳細パネルの内容を生成する."""
    if origin in ("file", ) or (origin == "ms" and l2_tab == "file"):
        return _file_detail_panel(detail_id, metrics)
    else:
        return _cs_detail_panel(detail_id, metrics)


def _file_detail_panel(file_path: str, metrics: dict) -> list:
    file_df = metrics.get("file")
    if file_df is None or file_df.empty:
        return [html.P(f"No detail for: {file_path}", style={"color": "#888"})]

    row = file_df[file_df["file_path"] == file_path]
    if row.empty:
        return [html.P(f"File not found: {file_path}", style={"color": "#888"})]
    row = row.iloc[0]

    items = [
        ("File", file_path),
        ("Service",              row.get("service", "—")),
        ("File Type",            row.get("file_type", "—")),
        ("Shared MS Count",      row.get("sharing_service_count", "—")),
        ("Total MS Count",       row.get("total_service_count", "—")),
        ("Sharing MS Ratio",     f"{row.get('sharing_service_ratio', 0) * 100:.1f}%"),
        ("Inter-Service CS Count",    row.get("cross_service_clone_set_count", "—")),
        ("Inter-Service CS Ratio",    f"{row.get('cross_service_clone_set_ratio', 0) * 100:.1f}%"),
        ("Inter-Service Clone LOC",   row.get("cross_service_line_count", "—")),
        ("Inter-Service Comod Count", row.get("cross_service_comod_count", "—")),
        ("Comod Shared MS Count",     row.get("comod_shared_service_count", "—")),
    ]
    return _detail_card("File Detail", items)


def _cs_detail_panel(clone_id: str, metrics: dict) -> list:
    cs_df = metrics.get("clone_set")
    if cs_df is None or cs_df.empty:
        return [html.P(f"No detail for clone set: {clone_id}", style={"color": "#888"})]

    row = cs_df[cs_df["clone_id"].astype(str) == str(clone_id)]
    if row.empty:
        return [html.P(f"Clone set not found: {clone_id}", style={"color": "#888"})]
    row = row.iloc[0]

    items = [
        ("Clone ID",               clone_id),
        ("Involved Services",      row.get("involved_services", "—")),
        ("# Involved MS",          row.get("service_count", "—")),
        ("File Types",             row.get("file_types", "—")),
        ("Inter-Service Frag Count",   row.get("cross_service_fragment_count", "—")),
        ("Inter-Service Frag Ratio",   f"{row.get('cross_service_fragment_ratio', 0) * 100:.1f}%"),
        ("Inter-Service Clone LOC",    row.get("cross_service_line_count", "—")),
        ("Inter-Service Scale",        row.get("cross_service_scale", "—")),
        ("Simultaneous Mod Count",     row.get("comod_count", "—")),
        ("Comod Fragment Count",       row.get("comod_fragment_count", "—")),
        ("Comod Fragment Ratio",   f"{row.get('comod_fragment_ratio', 0) * 100:.1f}%"),
    ]
    return _detail_card("Clone Set Detail", items)


def _detail_card(title: str, items: list[tuple[str, object]]) -> list:
    rows = [
        html.Tr([
            html.Td(label, style={"fontWeight": "600", "padding": "3px 12px", "fontSize": "12px", "whiteSpace": "nowrap", "color": "#555"}),
            html.Td(str(value), style={"padding": "3px 12px", "fontSize": "12px"}),
        ])
        for label, value in items
    ]
    return [
        html.H6(title, style={"marginBottom": "8px", "color": "#333", "fontWeight": "700"}),
        dbc.Table(
            html.Tbody(rows),
            bordered=False,
            striped=True,
            size="sm",
            style={"marginBottom": "0"},
        ),
    ]
