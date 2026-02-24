import logging

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from ..constants import DetectionMethod
from .summary import (
    create_help_section,
    build_dashboard_view,
    build_project_summary,
)

logger = logging.getLogger(__name__)

def create_layout(
    available_projects, available_languages, default_value, initial_fig, initial_summary
):
    """Dashアプリの全体レイアウトを生成する"""

    # ダッシュボードデータの読み込み
    from ..data_loader import load_dashboard_data

    dashboard_data = load_dashboard_data()
    dashboard_view = build_dashboard_view(dashboard_data)

    # 言語フィルターのオプションを作成
    language_options = [{"label": "All Languages", "value": "all"}]
    language_options.extend(
        [{"label": lang, "value": lang} for lang in available_languages]
    )

    # 既存の散布図ビューのコンテンツ
    # プロジェクト選択はタブの外に出すため、ここではフィルタから開始
    scatter_view_content = html.Div(
        className="container",
        children=[
            # 上部カード：コントロールパネルとプロジェクト概要
            html.Div(
                className="card",
                children=[
                    html.Div(
                        className="control-row",
                        children=[
                            html.Label(
                                "Clone ID Filter:",
                                className="control-label",
                                style={"width": "120px"},
                            ),
                            dcc.Dropdown(
                                id="clone-id-filter",
                                options=[{"label": "Show all clones", "value": "all"}],
                                value="all",
                                placeholder="Filter by Clone ID...",
                                style={
                                    "width": "400px",
                                    "fontFamily": "monospace",
                                    "fontSize": "13px",
                                },
                                optionHeight=35,
                                maxHeight=300,
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-row",
                        children=[
                            html.Div(
                                id="filter-status",
                                style={
                                    "fontSize": "13px",
                                    "color": "#333",
                                    "fontWeight": "bold",
                                },
                            )
                        ],
                    ),
                    html.Hr(),  # 区切り線
                    html.Div(id="project-summary", children=initial_summary),
                ],
            ),
            # 中央カード：散布図
            html.Div(
                className="card",
                children=[
                    create_help_section(),  # ヘルプセクションを追加
                    dcc.Graph(id="scatter-plot", figure=initial_fig),
                ],
            ),
            # 下部カード：クローン詳細
            html.Div(
                className="card",
                children=[
                    html.Div(
                        id="clone-selector-container"
                    ),  # クローン選択UI用のコンテナ
                    html.Div(
                        id="clone-details-table",
                        children=[
                            html.P("Click a point on the graph to view clone details.")
                        ],
                    ),
                ],
            ),
        ],
    )

    # ネットワークグラフビューのコンテンツ
    network_view_content = html.Div(
        className="container",
        children=[
            html.Div(
                className="card",
                children=[
                    html.H4("Service Dependency Network", className="card-title"),
                    html.P(
                        "Visualizes clone sharing relationships between microservices. Edges represent clone sharing, and node sizes represent file counts.",
                        className="text-muted",
                    ),
                    dcc.Graph(id="network-graph", style={"height": "800px"}),
                ],
            )
        ],
    )

    # 共通のプロジェクト選択行とフィルタ
    project_selector = html.Div(
        className="container mb-3",
        children=[
            html.Div(
                className="card",
                children=[
                    html.Div(
                        className="control-row",
                        children=[
                            html.Label(
                                "Select project:",
                                className="control-label",
                                style={"width": "120px"},
                            ),
                            dcc.Dropdown(
                                id="project-dropdown",
                                options=available_projects,
                                value=default_value,
                                style={
                                    "flex": 1,
                                    "minWidth": "500px",
                                    "maxWidth": "800px",
                                },
                                optionHeight=70,
                                maxHeight=400,
                            ),
                        ],
                    ),
                    # フィルタ群をRow/Colで整理 (共通化)
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label(
                                        "Detection Method:", className="fw-bold"
                                    ),
                                    dbc.RadioItems(
                                        id="detection-method-filter",
                                        options=DetectionMethod.get_options(),
                                        value=DetectionMethod.NO_IMPORT,
                                        inline=True,
                                        className="mb-2",
                                    ),
                                ],
                                width=3,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Co-modification:", className="fw-bold"),
                                    dbc.RadioItems(
                                        id="comodified-filter",
                                        options=[
                                            {"label": "All", "value": "all"},
                                            {"label": "Yes", "value": "true"},
                                            {"label": "No", "value": "false"},
                                        ],
                                        value="all",
                                        inline=True,
                                        className="mb-2",
                                    ),
                                ],
                                width=3,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Code Type:", className="fw-bold"),
                                    dbc.RadioItems(
                                        id="code-type-filter",
                                        options=[
                                            {"label": "All", "value": "all"},
                                            {"label": "Data", "value": "data"},
                                            {"label": "Logic", "value": "logic"},
                                            {"label": "Test", "value": "test"},
                                            {"label": "Config", "value": "config"},
                                            {"label": "Mixed", "value": "mixed"},
                                        ],
                                        value="all",
                                        inline=True,
                                        className="mb-2",
                                    ),
                                ],
                                width=3,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Scope:", className="fw-bold"),
                                    dbc.RadioItems(
                                        id="scope-filter",
                                        options=[
                                            {"label": "Resolved", "value": "resolved"},
                                            {"label": "All", "value": "all"},
                                            {"label": "Unknown", "value": "unknown"},
                                        ],
                                        value="resolved",
                                        inline=True,
                                        className="mb-2",
                                    ),
                                ],
                                width=3,
                            ),
                        ],
                        className="mb-3 p-2 border rounded bg-light",
                    ),
                ],
            )
        ],
    )

    # タブ構成
    return dbc.Container(
        [
            html.H1("Microservice Code Clone Analysis", className="my-4 text-center"),
            project_selector,
            dcc.Tabs(
                id="main-tabs",
                value="tab-dashboard",
                children=[
                    dcc.Tab(
                        label="Dashboard",
                        value="tab-dashboard",
                        children=[dashboard_view],
                    ),
                    dcc.Tab(
                        label="Scatter Plot",
                        value="tab-scatter",
                        children=[scatter_view_content],
                    ),
                    dcc.Tab(
                        label="Dependency Network",
                        value="tab-network",
                        children=[network_view_content],
                    ),
                ],
            ),
        ],
        fluid=True,
    )




def _build_nav_sidebar(lang_selector):
    """左側ナビゲーションサイドバーを構築する.

    Args:
        lang_selector: 言語選択用の Dropdown コンポーネント.

    Returns:
        html.Nav コンポーネント.
    """
    return html.Nav(
        id="app-sidebar",
        className="app-sidebar",
        children=[
            # Brand area (with collapse toggle)
            html.Div(
                className="sidebar-brand",
                children=[
                    html.Div(
                        [
                            html.Span("MSCCVis", className="sidebar-brand-text"),
                        ],
                        className="sidebar-brand-inner",
                    ),
                    html.Button(
                        html.I(
                            className="bi bi-chevron-left",
                            id="sidebar-toggle-icon",
                        ),
                        id="sidebar-toggle",
                        className="sidebar-collapse-btn",
                        n_clicks=0,
                        title="Toggle sidebar",
                    ),
                ],
            ),
            # Navigation items
            html.Ul(
                className="sidebar-nav-list",
                children=[
                    html.Li(
                        html.A(
                            [
                                html.I(className="bi bi-gear nav-icon"),
                                html.Span(
                                    "Detection Settings",
                                    className="nav-text",
                                    **{"data-i18n": "navSettings"},
                                ),
                            ],
                            href="/",
                            className="nav-link",
                        ),
                        className="nav-item",
                    ),
                    html.Li(
                        html.Button(
                            [
                                html.I(className="bi bi-graph-up nav-icon"),
                                html.Span(
                                    "Scatter Plot",
                                    className="nav-text",
                                    **{"data-i18n": "navScatter"},
                                ),
                            ],
                            id="btn-view-scatter",
                            className="nav-link active",
                            n_clicks=0,
                        ),
                        className="nav-item",
                    ),
                    html.Li(
                        html.Button(
                            [
                                html.I(className="bi bi-list-ul nav-icon"),
                                html.Span(
                                    "List View",
                                    className="nav-text",
                                    **{"data-i18n": "navListView"},
                                ),
                            ],
                            id="btn-view-explorer",
                            className="nav-link",
                            n_clicks=0,
                        ),
                        className="nav-item",
                    ),
                    html.Li(
                        html.Button(
                            [
                                html.I(className="bi bi-bar-chart-line nav-icon"),
                                html.Span(
                                    "Statistics",
                                    className="nav-text",
                                    **{"data-i18n": "navStats"},
                                ),
                            ],
                            id="btn-view-stats",
                            className="nav-link",
                            n_clicks=0,
                        ),
                        className="nav-item",
                    ),
                ],
            ),
            # Footer: language selector + help button
            html.Div(
                className="sidebar-footer",
                children=[
                    html.I(className="bi bi-globe2 nav-icon"),
                    lang_selector,
                    html.Button(
                        html.I(className="bi bi-question-circle"),
                        id="help-btn",
                        className="sidebar-help-btn",
                        n_clicks=0,
                        title="About this tool",
                    ),
                ],
            ),
        ],
    )


def _build_help_modal():
    """ヘルプモーダルダイアログを構築する.

    Returns:
        dbc.Modal コンポーネント.
    """
    return dbc.Modal(
        id="help-modal",
        is_open=False,
        size="lg",
        centered=True,
        children=[
            dbc.ModalHeader(
                dbc.ModalTitle("MSCCVis — Clone Explorer"),
                close_button=True,
            ),
            dbc.ModalBody(
                [
                    html.H5("About", className="mb-3"),
                    html.P(
                        "MSCCVis (Microservice Code Clone Visualizer) is a toolset "
                        "for detecting and visualizing code clones across microservice "
                        "repositories. It integrates CCFinderSW for clone detection "
                        "and CLAIM for microservice boundary identification.",
                    ),
                    html.Hr(),
                    html.H6("Views"),
                    html.Ul(
                        [
                            html.Li(
                                [
                                    html.Strong("Scatter Plot"),
                                    html.Span(
                                        " — Visualizes clone pairs as points. "
                                        "Filter by co-modification, scope, and code type."
                                    ),
                                ]
                            ),
                            html.Li(
                                [
                                    html.Strong("List View"),
                                    html.Span(
                                        " — Browse repository files and "
                                        "inspect clone fragments side-by-side."
                                    ),
                                ]
                            ),
                            html.Li(
                                [
                                    html.Strong("Statistics"),
                                    html.Span(
                                        " — Project summary with service mapping, "
                                        "clone ratio, and co-modification metrics."
                                    ),
                                ]
                            ),
                        ]
                    ),
                    html.Hr(),
                    html.H6("Tips"),
                    html.Ul(
                        [
                            html.Li(
                                "Click a point on the scatter plot to see clone details."
                            ),
                            html.Li("Use the sidebar to switch between views."),
                            html.Li(
                                "Collapse the sidebar with the toggle button "
                                "for more screen space."
                            ),
                        ]
                    ),
                ]
            ),
        ],
    )


def create_ide_layout(
    available_projects,
    available_languages,
    default_project,
    initial_fig,
    initial_summary,
    *,
    project_names=None,
):
    """サイドバーナビゲーション + メインコンテンツのレイアウトを作成する."""

    # Project Name Selector (Step 1)
    project_name_selector = dcc.Dropdown(
        id="project-name-selector",
        options=project_names or [],
        value=None,
        placeholder="Select Project",
        style={"width": "280px"},
        clearable=False,
        maxHeight=500,
        optionHeight=45,
    )

    # CSV File Selector (Step 2) — ID は既存コールバック互換のため維持
    project_selector = dcc.Dropdown(
        id="project-selector",
        options=available_projects,
        value=default_project,
        placeholder="Select Dataset",
        style={"width": "640px", "fontSize": "0.82rem"},
        clearable=False,
        disabled=True,
        optionHeight=55,
        maxHeight=500,
    )

    # Language Selector
    lang_dropdown = dcc.Dropdown(
        id="vis-lang-select",
        options=[
            {"label": "English", "value": "en"},
            {"label": "日本語", "value": "ja"},
        ],
        value="en",
        clearable=False,
        searchable=False,
        style={"width": "100px", "fontSize": "0.82rem"},
    )

    # ── Navigation Sidebar ──
    nav_sidebar = _build_nav_sidebar(lang_dropdown)

    # ── Content Header (project selectors) ──
    content_header = html.Div(
        className="content-header",
        children=[
            html.H2(
                "Scatter Plot",
                id="page-title",
                className="content-title",
                **{"data-i18n": "navScatter"},
            ),
            html.Div(
                className="header-selectors",
                children=[
                    html.Span(
                        "Project:",
                        className="selector-label",
                        **{"data-i18n": "labelProject"},
                    ),
                    project_name_selector,
                    html.Span("▸", className="selector-separator"),
                    html.Span(
                        "Dataset:",
                        className="selector-label",
                        **{"data-i18n": "labelDataset"},
                    ),
                    project_selector,
                ],
            ),
        ],
    )

    # ── Explorer (List View) ──
    explorer_sidebar = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        "EXPLORER",
                        className="sidebar-header",
                        **{"data-i18n": "sidebarExplorer"},
                    ),
                    html.Div(id="file-tree-container", className="sidebar-tree"),
                ],
                className="sidebar-section",
                style={"flex": "2", "borderBottom": "1px solid #e0e0e0"},
            ),
            html.Div(
                [
                    html.Div(id="drag-handle", className="sidebar-resizer"),
                    html.Div(
                        "CLONE OUTLINE",
                        className="sidebar-header",
                        **{"data-i18n": "sidebarCloneOutline"},
                    ),
                    html.Div(
                        id="clone-list-container",
                        className="sidebar-tree",
                        style={"flex": "1"},
                    ),
                ],
                className="sidebar-section",
                style={"flex": "1", "display": "flex", "flexDirection": "column"},
            ),
        ],
        className="ide-sidebar",
    )

    editor_content = html.Div(
        [
            html.Div(
                id="editor-header",
                className="editor-header",
                children=html.Span(
                    "Select a file to view", **{"data-i18n": "editorPlaceholder"}
                ),
            ),
            html.Div(
                id="editor-content",
                className="editor-content",
                children=[
                    html.Div(
                        html.Span(
                            "Select a file from the explorer to view its content.",
                            **{"data-i18n": "emptyState"},
                        ),
                        id="empty-state-message",
                        style={
                            "padding": "20px",
                            "color": "#777",
                            "textAlign": "center",
                            "marginTop": "50px",
                        },
                    )
                ],
                style={"padding": "0", "height": "100%", "overflow": "hidden"},
            ),
        ],
        className="ide-content",
    )

    # ── Scatter View ──
    scatter_view = html.Div(
        [
            # Hidden: Detection Method (callback 互換用)
            html.Div(
                dbc.RadioItems(
                    id="detection-method-radio",
                    options=[{"label": "All", "value": "all"}],
                    value="all",
                ),
                style={"display": "none"},
            ),
            # Filter Panel
            html.Div(
                [
                    # Row 1: Co-modification / Scope / Code Type
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label(
                                        "Co-modification",
                                        className="filter-label",
                                        **{"data-i18n": "filterComod"},
                                    ),
                                    dbc.RadioItems(
                                        id="comodification-filter",
                                        options=[
                                            {"label": "All", "value": "all"},
                                            {"label": "Yes", "value": "yes"},
                                            {"label": "No", "value": "no"},
                                        ],
                                        value="all",
                                        inline=True,
                                        className="filter-radio",
                                    ),
                                ],
                                className="filter-group",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Scope",
                                        className="filter-label",
                                        **{"data-i18n": "filterScope"},
                                    ),
                                    dbc.RadioItems(
                                        id="service-scope-filter",
                                        options=[
                                            {"label": "All", "value": "all"},
                                            {"label": "Within", "value": "within"},
                                            {"label": "Cross", "value": "cross"},
                                        ],
                                        value="all",
                                        inline=True,
                                        className="filter-radio",
                                    ),
                                ],
                                className="filter-group",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Code Type",
                                        className="filter-label",
                                        **{"data-i18n": "filterCodeType"},
                                    ),
                                    html.Div(
                                        id="code-type-buttons-container",
                                        className="code-type-buttons",
                                        style={
                                            "display": "flex",
                                            "gap": "6px",
                                            "flexWrap": "wrap",
                                        },
                                    ),
                                    dcc.Store(id="code-type-store", data="all"),
                                ],
                                className="filter-group",
                                style={"flex": "1"},
                            ),
                        ],
                        className="filter-row",
                    ),
                    # Row 2: Clone ID / Many Services
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label(
                                        "Clone ID",
                                        className="filter-label",
                                        **{"data-i18n": "filterCloneId"},
                                    ),
                                    dcc.Input(
                                        id="clone-id-filter",
                                        type="text",
                                        placeholder="Input Clone ID",
                                        debounce=True,
                                        className="filter-input",
                                    ),
                                ],
                                className="filter-group",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Multi-Service Clones",
                                        className="filter-label",
                                        **{"data-i18n": "filterManyServices"},
                                    ),
                                    dcc.Dropdown(
                                        id="cross-service-filter",
                                        options=[{"label": "All", "value": "all"}],
                                        value="all",
                                        placeholder="Select Clone ID",
                                        clearable=True,
                                        className="filter-dropdown",
                                        style={"minWidth": "360px"},
                                    ),
                                ],
                                className="filter-group",
                                style={"flex": "1"},
                            ),
                        ],
                        className="filter-row",
                        style={
                            "borderTop": "1px solid var(--border, #e0e0e0)",
                            "paddingTop": "8px",
                        },
                    ),
                ],
                className="filter-panel",
            ),
            # Graph + Clone Details
            html.Div(
                [
                    html.Div(
                        id="scatter-stats-header",
                        style={
                            "padding": "5px 15px",
                            "borderBottom": "1px solid #eee",
                            "backgroundColor": "#fff",
                            "minHeight": "30px",
                        },
                    ),
                    html.Div(
                        [
                            dcc.Loading(
                                id="loading-scatter",
                                type="circle",
                                children=[
                                    dcc.Graph(
                                        id="scatter-plot",
                                        figure=initial_fig,
                                        style={
                                            "height": "125vh",
                                            "minHeight": "500px",
                                        },
                                        config={"responsive": True},
                                    )
                                ],
                            )
                        ],
                        style={"padding": "10px"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                id="clone-selector-container",
                                style={"marginBottom": "10px"},
                            ),
                            html.Div(
                                id="clone-details-table",
                                children=[
                                    html.P(
                                        "Click a point on the graph to view clone "
                                        "details and code comparison here.",
                                        **{"data-i18n": "scatterClickHint"},
                                    )
                                ],
                            ),
                        ],
                        style={
                            "padding": "20px",
                            "borderTop": "2px solid #ddd",
                            "backgroundColor": "#fff",
                        },
                    ),
                ],
                className="graph-container",
            ),
        ],
        id="scatter-container",
        className="view-panel active",
        style={"padding": "0", "overflowY": "auto"},
    )

    # ── Statistics View ──
    stats_view = html.Div(
        [
            html.Div(
                initial_summary,
                id="project-summary-container",
                style={"padding": "20px"},
            )
        ],
        id="stats-container",
        className="view-panel",
        style={"padding": "0", "overflowY": "auto"},
    )

    # ── Help Modal ──
    help_modal = _build_help_modal()

    # ── Stores ──
    stores = html.Div(
        [
            dcc.Location(id="url-location", refresh=False),
            dcc.Store(id="file-tree-data-store"),
            dcc.Store(id="selected-file-store"),
            dcc.Store(id="clone-data-store"),
            dcc.Store(id="lang-store", data="en"),
            html.Div(id="i18n-dummy", style={"display": "none"}),
        ]
    )

    return html.Div(
        className="app-container",
        children=[
            nav_sidebar,
            html.Div(
                className="app-main",
                children=[
                    content_header,
                    html.Div(
                        className="content-body",
                        children=[
                            # Explorer view (natural flow, hidden by default)
                            html.Div(
                                [explorer_sidebar, editor_content],
                                id="ide-main-container",
                                className="ide-main",
                            ),
                            # Scatter overlay
                            scatter_view,
                            # Stats overlay
                            stats_view,
                        ],
                    ),
                ],
            ),
            help_modal,
            stores,
        ],
    )


