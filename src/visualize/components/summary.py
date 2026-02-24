import logging

from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import os
from collections import Counter

from ..constants import DetectionMethod

logger = logging.getLogger(__name__)


def create_help_section():
    """散布図の見方のセクションを作成する"""
    return html.Details(
        [
            html.Summary(
                "📊 How to Read the Scatter Plot",
                style={
                    "cursor": "pointer",
                    "fontWeight": "bold",
                    "fontSize": "16px",
                    "color": "#495057",
                },
            ),
            html.Div(
                [
                    html.P(
                        "This scatter plot visualizes clone relationships between files as a heatmap.",
                        className="help-text",
                        style={"marginBottom": "15px", "fontStyle": "italic"},
                    ),
                    # 基本概念
                    html.Div(
                        [
                            html.H6(
                                "🔍 Basic Concepts",
                                style={"color": "#6c757d", "marginBottom": "10px"},
                            ),
                            html.Ul(
                                [
                                    html.Li(
                                        [
                                            html.Strong("Axes: "),
                                            "File numbers assigned to each file (shared on both X and Y axes)",
                                        ]
                                    ),
                                    html.Li(
                                        [
                                            html.Strong("Point: "),
                                            "Indicates a code clone detected between two files",
                                        ]
                                    ),
                                    html.Li(
                                        [
                                            html.Strong("Dashed line: "),
                                            "Service boundaries (file ranges for each microservice)",
                                        ]
                                    ),
                                ],
                                style={"marginBottom": "15px"},
                            ),
                        ]
                    ),
                    # マーカー形状
                    html.Div(
                        [
                            html.H6(
                                "🔸 Marker Shapes",
                                style={"color": "#6c757d", "marginBottom": "10px"},
                            ),
                            html.Ul(
                                [
                                    html.Li(
                                        [
                                            html.Span(
                                                "● Circle: ",
                                                style={
                                                    "color": "#495057",
                                                    "fontWeight": "bold",
                                                },
                                            ),
                                            "Intra-service clone (within the same microservice)",
                                        ]
                                    ),
                                    html.Li(
                                        [
                                            html.Span(
                                                "■ Square: ",
                                                style={
                                                    "color": "#495057",
                                                    "fontWeight": "bold",
                                                },
                                            ),
                                            "Inter-service clone (across different microservices)",
                                        ]
                                    ),
                                ],
                                style={"marginBottom": "15px"},
                            ),
                        ]
                    ),
                    # ヒートマップ色分け
                    html.Div(
                        [
                            html.H6(
                                "🌡️ Heatmap (Clone Density)",
                                style={"color": "#6c757d", "marginBottom": "10px"},
                            ),
                            html.P(
                                "5-level color map based on overlapping clone count at same coordinates:",
                                style={"marginBottom": "8px"},
                            ),
                            html.Ul(
                                [
                                    html.Li(
                                        [
                                            html.Span(
                                                "● Blue: ",
                                                style={
                                                    "color": "#0066CC",
                                                    "fontWeight": "bold",
                                                },
                                            ),
                                            "Low density",
                                        ]
                                    ),
                                    html.Li(
                                        [
                                            html.Span(
                                                "● Green: ",
                                                style={
                                                    "color": "#00CC66",
                                                    "fontWeight": "bold",
                                                },
                                            ),
                                            "Medium density",
                                        ]
                                    ),
                                    html.Li(
                                        [
                                            html.Span(
                                                "● Yellow: ",
                                                style={
                                                    "color": "#CCCC00",
                                                    "fontWeight": "bold",
                                                },
                                            ),
                                            "High density",
                                        ]
                                    ),
                                    html.Li(
                                        [
                                            html.Span(
                                                "● Orange: ",
                                                style={
                                                    "color": "#FF6600",
                                                    "fontWeight": "bold",
                                                },
                                            ),
                                            "Very high density",
                                        ]
                                    ),
                                    html.Li(
                                        [
                                            html.Span(
                                                "● Red: ",
                                                style={
                                                    "color": "#CC0000",
                                                    "fontWeight": "bold",
                                                },
                                            ),
                                            "Maximum density",
                                        ]
                                    ),
                                ],
                                style={"marginBottom": "15px"},
                            ),
                        ]
                    ),
                    # 操作方法
                    html.Div(
                        [
                            html.H6(
                                "🖱️ Interactions",
                                style={"color": "#6c757d", "marginBottom": "10px"},
                            ),
                            html.Ul(
                                [
                                    html.Li(
                                        [
                                            html.Strong("Click: "),
                                            "Shows clone details below the graph",
                                        ]
                                    ),
                                    html.Li(
                                        [
                                            html.Strong("Multiple clones: "),
                                            "A dropdown menu appears to select which clone to display",
                                        ]
                                    ),
                                    html.Li(
                                        [
                                            html.Strong("File view: "),
                                            "Use the 'File' button in the detail panel to view the full file containing the clone",
                                        ]
                                    ),
                                ],
                                style={"marginBottom": "10px"},
                            ),
                        ]
                    ),
                ],
                style={
                    "marginTop": "15px",
                    "padding": "15px",
                    "backgroundColor": "#f8f9fa",
                    "borderRadius": "8px",
                },
            ),
        ],
        className="help-section",
    )


def build_dashboard_view(dashboard_data):
    """ダッシュボードビューを構築する"""
    if not dashboard_data or "metrics" not in dashboard_data:
        return html.Div(
            [
                html.H3("Dashboard Data Not Found"),
                html.P(
                    "Please run 'python commands/generate_services_json.py' to generate dashboard data."
                ),
            ],
            className="alert alert-warning",
        )

    metrics = dashboard_data["metrics"]
    detailed_stats = dashboard_data.get("detailed_stats", {})

    # --- データ集計 ---
    total_projects = 0
    languages = set()
    total_clones = 0
    clone_ratios = []
    project_lang_list = []
    scatter_points = []  # (file_count, clone_ratio, project_name)

    # テーブル用データ
    table_data = []

    # 円グラフ用集計
    total_types = {"logic": 0, "data": 0, "config": 0, "test": 0, "mixed": 0}
    comod_types = {"logic": 0, "data": 0, "config": 0, "test": 0, "mixed": 0}

    for project, langs in metrics.items():
        total_projects += 1
        for lang, data in langs.items():
            languages.add(lang)
            project_lang_list.append(lang)

            clone_ratio = data.get("clone_ratio", {})
            comodification = data.get("comodification_rate", {})
            file_count = data.get("file_count", 0)  # Added field

            # クローン率 (within-production)
            cr_prod = clone_ratio.get("within-production", 0)
            cr_test = clone_ratio.get("within-testing", 0)

            clone_ratios.append(cr_prod)
            scatter_points.append(
                {"x": file_count, "y": cr_prod, "text": f"{project} ({lang})"}
            )

            # 同時修正率
            co_prod = comodification.get("within-production", {})
            co_prod_rate = 0
            if co_prod.get("count", 0) > 0:
                co_prod_rate = co_prod.get("comodification_count", 0) / co_prod["count"]

            table_data.append(
                {
                    "Project": project,
                    "Language": lang,
                    "Files": f"{file_count:,}" if file_count > 0 else "N/A",
                    "Clone Ratio (Prod)": f"{cr_prod:.2%}",
                    "Clone Ratio (Test)": f"{cr_test:.2%}",
                    "Co-mod Rate (Prod)": f"{co_prod_rate:.2%}",
                }
            )

            # 詳細統計からクローン数とタイプを集計
            if project in detailed_stats and lang in detailed_stats[project]:
                stats = detailed_stats[project][lang]
                if "methods" in stats:
                    methods = stats["methods"]
                    target_method = (
                        "ccfsw"
                        if "ccfsw" in methods
                        else (list(methods.keys())[0] if methods else None)
                    )

                    if target_method:
                        m_stats = methods[target_method]
                        total_clones += m_stats.get("count", 0)

                        code_type = m_stats.get("code_type", {})
                        comod_st = m_stats.get("comodified_code_type", {})

                        for k in total_types.keys():
                            total_types[k] += code_type.get(k, 0)
                            comod_types[k] += comod_st.get(k, 0)

    # 平均値計算
    avg_clone_ratio = sum(clone_ratios) / len(clone_ratios) if clone_ratios else 0

    # --- コンポーネント作成 ---

    # 1. Overview Cards
    def create_kpi_card(title, value, color):
        return dbc.Col(
            dbc.Card(
                [
                    dbc.CardBody(
                        [
                            html.H4(
                                value,
                                className="card-title",
                                style={
                                    "fontWeight": "bold",
                                    "color": color,
                                    "marginBottom": "0",
                                },
                            ),
                            html.Small(
                                title,
                                className="card-text",
                                style={"color": "#6c757d", "fontSize": "0.85rem"},
                            ),
                        ],
                        className="text-center p-3",
                    )
                ],
                className="shadow-sm border-0",
            ),
            width=3,
        )

    overview_row = dbc.Row(
        [
            create_kpi_card("Total Projects", str(total_projects), "#0d6efd"),
            create_kpi_card("Total Languages", str(len(languages)), "#198754"),
            create_kpi_card("Total Clones", f"{total_clones:,}", "#dc3545"),
            create_kpi_card("Avg. Clone Ratio", f"{avg_clone_ratio:.2%}", "#ffc107"),
        ],
        className="mb-4 g-3",
    )

    # 2. Charts

    # Pie Charts (Existing)
    labels_all = [k.capitalize() for k in total_types.keys()]
    values_all = list(total_types.values())
    fig_pie1 = go.Figure(data=[go.Pie(labels=labels_all, values=values_all, hole=0.4)])
    fig_pie1.update_layout(
        title_text="Clones by Code Type (All)",
        margin=dict(t=40, b=10, l=10, r=10),
        height=300,
    )

    labels_comod = [k.capitalize() for k in comod_types.keys()]
    values_comod = list(comod_types.values())
    fig_pie2 = go.Figure(
        data=[go.Pie(labels=labels_comod, values=values_comod, hole=0.4)]
    )
    fig_pie2.update_layout(
        title_text="Co-modified Clones by Code Type",
        margin=dict(t=40, b=10, l=10, r=10),
        height=300,
    )

    # Histogram: Clone Ratio
    fig_hist = go.Figure(
        data=[go.Histogram(x=clone_ratios, nbinsx=10, marker_color="#6c757d")]
    )
    fig_hist.update_layout(
        title_text="Clone Ratio Distribution",
        margin=dict(t=40, b=10, l=10, r=10),
        height=300,
        xaxis_tickformat=".0%",
    )

    # Bar: Projects by Language
    from collections import Counter

    lang_counts = Counter(project_lang_list)
    fig_bar = go.Figure(
        data=[
            go.Bar(
                x=list(lang_counts.keys()),
                y=list(lang_counts.values()),
                marker_color="#20c997",
            )
        ]
    )
    fig_bar.update_layout(
        title_text="Projects by Language",
        margin=dict(t=40, b=10, l=10, r=10),
        height=300,
    )

    # Scatter: File Scale vs Clone Ratio
    scatter_x = [p["x"] for p in scatter_points]
    scatter_y = [p["y"] for p in scatter_points]
    scatter_text = [p["text"] for p in scatter_points]

    fig_scatter = go.Figure(
        data=[
            go.Scatter(
                x=scatter_x,
                y=scatter_y,
                mode="markers",
                text=scatter_text,
                marker=dict(size=10, color="#6610f2"),
            )
        ]
    )
    fig_scatter.update_layout(
        title_text="File Scale vs Clone Ratio",
        xaxis_title="Number of Files",
        yaxis_title="Clone Ratio",
        yaxis_tickformat=".0%",
        margin=dict(t=40, b=10, l=10, r=10),
        height=300,
    )

    # Layout Construction
    return html.Div(
        [
            html.H2("Project Dashboard", className="mb-4"),
            overview_row,
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(figure=fig_pie1), width=4),
                    dbc.Col(dcc.Graph(figure=fig_pie2), width=4),
                    dbc.Col(dcc.Graph(figure=fig_hist), width=4),
                ],
                className="mb-4",
            ),
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(figure=fig_bar), width=6),
                    dbc.Col(dcc.Graph(figure=fig_scatter), width=6),
                ],
                className="mb-4",
            ),
            html.H4("Project List", className="mb-3"),
            dash_table.DataTable(
                id="dashboard-table",
                data=table_data,
                columns=[
                    {"name": i, "id": i}
                    for i in [
                        "Project",
                        "Language",
                        "Files",
                        "Clone Ratio (Prod)",
                        "Clone Ratio (Test)",
                        "Co-mod Rate (Prod)",
                    ]
                ],
                sort_action="native",
                filter_action="native",
                style_table={"overflowX": "auto"},
                cell_selectable=False,
                style_cell={"textAlign": "left", "padding": "10px"},
                style_header={
                    "backgroundColor": "rgb(230, 230, 230)",
                    "fontWeight": "bold",
                },
                style_data_conditional=[
                    {
                        "if": {"row_index": "odd"},
                        "backgroundColor": "rgb(248, 248, 248)",
                    }
                ],
            ),
        ],
        className="p-4",
    )


# ---------------------------------------------------------------------------
# Clone Metrics (compute_clone_metrics) セクション
# ---------------------------------------------------------------------------

_SERVICE_COLUMNS = [
    {"name": "Service", "id": "service"},
    {"name": "Clone Sets", "id": "clone_set_count", "type": "numeric"},
    {"name": "Total Lines", "id": "total_clone_line_count", "type": "numeric"},
    {"name": "Avg Lines", "id": "clone_avg_line_count", "type": "numeric"},
    {"name": "Files", "id": "clone_file_count", "type": "numeric"},
    {"name": "ROC", "id": "roc", "type": "numeric"},
    {"name": "Comod", "id": "comod_count", "type": "numeric"},
    {"name": "Comod (Other)", "id": "comod_other_service_count", "type": "numeric"},
]

_CLONE_SET_COLUMNS = [
    {"name": "Clone ID", "id": "clone_id"},
    {"name": "Services", "id": "service_count", "type": "numeric"},
    {"name": "XS Frags", "id": "cross_service_fragment_count", "type": "numeric"},
    {"name": "XS Ratio", "id": "cross_service_fragment_ratio", "type": "numeric"},
    {"name": "XS Lines", "id": "cross_service_line_count", "type": "numeric"},
    {"name": "XS Scale", "id": "cross_service_scale", "type": "numeric"},
    {"name": "XS Elems", "id": "cross_service_element_count", "type": "numeric"},
    {"name": "Comod", "id": "comod_count", "type": "numeric"},
    {"name": "Comod Frags", "id": "comod_fragment_count", "type": "numeric"},
    {"name": "Comod Ratio", "id": "comod_fragment_ratio", "type": "numeric"},
]

_FILE_COLUMNS = [
    {"name": "File", "id": "file_path"},
    {"name": "Service", "id": "service"},
    {"name": "Sharing Svcs", "id": "sharing_service_count", "type": "numeric"},
    {"name": "Total Svcs", "id": "total_service_count", "type": "numeric"},
    {"name": "XS Clone Sets", "id": "cross_service_clone_set_count", "type": "numeric"},
    {"name": "XS CS Ratio", "id": "cross_service_clone_set_ratio", "type": "numeric"},
    {"name": "Share Ratio", "id": "sharing_service_ratio", "type": "numeric"},
    {"name": "XS Lines", "id": "cross_service_line_count", "type": "numeric"},
    {"name": "XS Comod", "id": "cross_service_comod_count", "type": "numeric"},
    {"name": "Comod Svcs", "id": "comod_shared_service_count", "type": "numeric"},
]


def _metrics_datatable(
    table_id: str, columns: list, data: list
) -> dash_table.DataTable:
    """メトリクスを Dash DataTable として描画する."""
    return dash_table.DataTable(
        id=table_id,
        columns=columns,
        data=data,
        page_size=10,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f8f9fa",
            "fontWeight": "bold",
            "border": "1px solid #dee2e6",
        },
        style_cell={
            "textAlign": "left",
            "padding": "8px 12px",
            "border": "1px solid #dee2e6",
            "fontSize": "13px",
            "maxWidth": "250px",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "#f8f9fa",
            }
        ],
    )


def _build_clone_metrics_section(metrics: dict) -> html.Div:
    """事前計算済みクローンメトリクス (3 粒度) のアコーディオン UI を構築する.

    Args:
        metrics: ``compute_all_metrics()`` の JSON 出力.
            ``{"service": [...], "clone_set": [...], "file": [...]}``.

    Returns:
        3 つのアコーディオンアイテムを含む Div.
    """
    service_data = metrics.get("service", [])
    clone_set_data = metrics.get("clone_set", [])
    file_data = metrics.get("file", [])

    items = []

    if service_data:
        items.append(
            dbc.AccordionItem(
                _metrics_datatable(
                    "metrics-service-table", _SERVICE_COLUMNS, service_data
                ),
                title=f"📊 Service Metrics ({len(service_data)} services)",
            )
        )

    if clone_set_data:
        items.append(
            dbc.AccordionItem(
                _metrics_datatable(
                    "metrics-cloneset-table", _CLONE_SET_COLUMNS, clone_set_data
                ),
                title=f"🔗 Clone Set Metrics ({len(clone_set_data)} sets)",
            )
        )

    if file_data:
        items.append(
            dbc.AccordionItem(
                _metrics_datatable("metrics-file-table", _FILE_COLUMNS, file_data),
                title=f"📄 File Metrics ({len(file_data)} files)",
            )
        )

    if not items:
        return html.Div()

    return dbc.Row(
        [
            dbc.Col(
                html.Div(
                    [
                        html.H5(
                            "📏 Clone Metrics (Detailed)",
                            style={"color": "#495057", "marginBottom": "10px"},
                        ),
                        dbc.Accordion(items, start_collapsed=True),
                    ],
                    className="summary-card",
                ),
                width=12,
                className="mb-3",
            )
        ]
    )


def build_project_summary(df, file_ranges, project, commit, language):
    """プロジェクトの統計情報サマリーを生成する（services.jsonの事前計算データを優先）"""
    from ..data_loader import (
        load_project_summary,
        load_full_services_json,
        load_clone_metrics,
    )

    # services.json から詳細統計を読み込む
    services_json_path = f"dest/scatter/{project}/services.json"
    services_data = load_full_services_json(services_json_path)

    detailed_stats = {}

    if services_data and "detailed_stats" in services_data:
        # 言語ごとの統計を取得（大文字小文字を吸収）
        target_lang = language.lower()
        for lang_key, stats in services_data["detailed_stats"].items():
            if lang_key.lower() == target_lang:
                detailed_stats = stats
                break

    # プロジェクトサマリーJSONからの追加情報
    summary_data = load_project_summary()
    project_info = None
    language_info = None

    if summary_data and project in summary_data.get("projects", {}):
        project_info = summary_data["projects"][project]
        if language in project_info.get("languages", {}):
            language_info = project_info["languages"][language]

    # --- 1. プロジェクト情報カード ---
    basic_info = [
        ("Project:", project.split(".")[-1]),
        ("Commit/Ref:", commit[:7] if len(commit) > 7 else commit),
        ("Language:", language),
    ]

    # GitHubリンク
    if project_info and "metadata" in project_info:
        metadata = project_info["metadata"]
        github_url = metadata.get("url", f"https://github.com/{project}")
        basic_info.append(
            (
                "GitHub Link:",
                html.A(
                    github_url,
                    href=github_url,
                    target="_blank",
                    style={"color": "#007bff", "textDecoration": "underline"},
                ),
            )
        )
    elif project:
        github_url = f"https://github.com/{project}"
        basic_info.append(
            (
                "GitHub Link:",
                html.A(
                    github_url,
                    href=github_url,
                    target="_blank",
                    style={"color": "#007bff", "textDecoration": "underline"},
                ),
            )
        )

    # プロジェクト全体統計
    if language_info and "stats" in language_info:
        stats = language_info["stats"]
        if stats.get("total_files", 0) > 0:
            basic_info.append(("Total Files:", f"{stats['total_files']:,}"))
            if "code_lines" in stats:
                basic_info.append(("Total Code Lines:", f"{stats['code_lines']:,}"))

    project_info_card = html.Div(
        [
            html.H5(
                "📋 Project Info",
                style={"color": "#495057", "marginBottom": "10px"},
            ),
            create_info_table(basic_info),
        ],
        className="summary-card",
        style={"height": "100%"},
    )

    # --- 2. サービス情報カード ---
    service_content = html.P("No service information available")
    if file_ranges:
        # サービスごとの統計情報を構築
        svc_file_counts = {}
        if services_data and "languages" in services_data:
            for lang_key, lang_data in services_data["languages"].items():
                if lang_key.lower() == language.lower():
                    svc_file_counts = lang_data.get("file_counts", {})
                    break

        header = html.Tr(
            [
                html.Th("Service"),
                html.Th("Files"),
            ]
        )

        rows = []
        for svc in sorted(file_ranges.keys()):
            files = svc_file_counts.get(svc, 0)
            rows.append(
                html.Tr(
                    [
                        html.Td(svc, style={"wordBreak": "break-all"}),
                        html.Td(f"{files:,}"),
                    ]
                )
            )

        # dbc.Tableを使用
        service_table = dbc.Table(
            [html.Thead(header), html.Tbody(rows)],
            bordered=True,
            hover=True,
            striped=True,
            size="sm",
            style={"fontSize": "12px"},
        )
        service_content = html.Div(
            service_table, style={"maxHeight": "300px", "overflowY": "auto"}
        )

    service_info_card = html.Div(
        [
            html.H5(
                "🏢 Service Info", style={"color": "#495057", "marginBottom": "10px"}
            ),
            service_content,
        ],
        className="summary-card",
        style={"height": "100%"},
    )

    # --- 3. クローン統計カード (詳細版 - マトリクス表示) ---
    stats_card_content = None

    if detailed_stats and "methods" in detailed_stats:
        methods_data = detailed_stats["methods"]

        header = html.Tr(
            [
                html.Th("Method"),
                html.Th("Total"),
                html.Th("Co-modified"),
                html.Th("Logic"),
                html.Th("Data"),
                html.Th("Config"),
                html.Th("Test"),
                html.Th("Mixed"),
            ]
        )

        rows = []
        method_order = ["ccfsw", "tks"]
        available_methods = sorted(
            methods_data.keys(),
            key=lambda x: method_order.index(x) if x in method_order else 99,
        )

        for m in available_methods:
            m_stats = methods_data[m]
            count = m_stats.get("count", 0)

            comod = m_stats.get("comodified", {})
            comod_true = comod.get("true", 0)
            comod_pct = (comod_true / count * 100) if count > 0 else 0

            ctype = m_stats.get("code_type", {})
            logic = ctype.get("logic", 0) + ctype.get(
                "production", 0
            )  # Fallback for legacy 'production'
            data = ctype.get("data", 0)
            config = ctype.get("config", 0)
            test = ctype.get("test", 0)
            mixed = ctype.get("mixed", 0)

            # Comodified Code Type
            comod_ctype = m_stats.get("comodified_code_type", {})
            comod_logic = comod_ctype.get("logic", 0)
            comod_data = comod_ctype.get("data", 0)
            comod_config = comod_ctype.get("config", 0)
            comod_test = comod_ctype.get("test", 0)
            comod_mixed = comod_ctype.get("mixed", 0)

            label = "Normal" if m == "ccfsw" else m.upper()

            rows.append(
                html.Tr(
                    [
                        html.Td(html.B(label)),
                        html.Td(f"{count:,}"),
                        html.Td(f"{comod_true:,} ({comod_pct:.1f}%)"),
                        html.Td(
                            f"{logic:,} ({comod_logic:,})", title="Total (Co-modified)"
                        ),
                        html.Td(
                            f"{data:,} ({comod_data:,})", title="Total (Co-modified)"
                        ),
                        html.Td(
                            f"{config:,} ({comod_config:,})",
                            title="Total (Co-modified)",
                        ),
                        html.Td(
                            f"{test:,} ({comod_test:,})", title="Total (Co-modified)"
                        ),
                        html.Td(
                            f"{mixed:,} ({comod_mixed:,})", title="Total (Co-modified)"
                        ),
                    ]
                )
            )

        # dbc.Tableを使用
        stats_table = dbc.Table(
            [html.Thead(header), html.Tbody(rows)],
            bordered=True,
            hover=True,
            striped=True,
            size="sm",
            style={"fontSize": "12px", "textAlign": "center"},
        )

        stats_card_content = html.Div(
            [
                html.H5(
                    "📊 Clone Statistics (Detailed)",
                    style={"color": "#495057", "marginBottom": "10px"},
                ),
                html.Div(
                    stats_table, style={"overflowX": "auto", "marginBottom": "15px"}
                ),
            ],
            className="summary-card",
        )

    # --- 4. Charts Section ---
    # --- 4. Charts Section ---
    charts_section = html.Div()

    # データ準備 (Aggregating or Loading)
    counts_by_type = {}
    counts_by_method = {}
    counts_by_comod_type = {}

    # 既存の統計情報があれば使用
    if (
        detailed_stats
        and "count_by_type" in detailed_stats
        and "count_by_method" in detailed_stats
    ):
        counts_by_type = detailed_stats["count_by_type"]
        counts_by_method = detailed_stats["count_by_method"]
        if "count_by_comod_type" in detailed_stats:
            counts_by_comod_type = detailed_stats["count_by_comod_type"]

    # なければ methods から集計 (新形式)
    elif detailed_stats and "methods" in detailed_stats:
        c_type_agg = Counter()
        m_agg = Counter()
        comod_type_agg = Counter()

        for m, m_stats in detailed_stats["methods"].items():
            count = m_stats.get("count", 0)
            if count > 0:
                label = "No Import" if m == "no-import" else m.upper()
                m_agg[label] += count

            if "code_type" in m_stats:
                for ct, cc in m_stats["code_type"].items():
                    if cc > 0:
                        c_type_agg[ct.capitalize()] += cc

            if "comodified_code_type" in m_stats:
                for ct, cc in m_stats["comodified_code_type"].items():
                    if cc > 0:
                        comod_type_agg[ct.capitalize()] += cc

        counts_by_type = dict(c_type_agg)
        counts_by_method = dict(m_agg)
        counts_by_comod_type = dict(comod_type_agg)

    # チャートの生成
    chart_components = []

    # 1. Overall Method Breakdown (Main Chart)
    if counts_by_method:
        fig_method = _create_pie_chart(
            counts_by_method, "Overall Detection Method Breakdown"
        )
        chart_components.append(
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Graph(figure=fig_method, config={"displayModeBar": False}),
                        width=12,
                    ),
                ],
                className="mb-4",
            )
        )

    # 2. Charts per Method
    if detailed_stats and "methods" in detailed_stats:
        method_order = ["tks", "no-import", "ccfsw"]
        sorted_methods = sorted(
            detailed_stats["methods"].keys(),
            key=lambda x: method_order.index(x) if x in method_order else 99,
        )

        for m in sorted_methods:
            m_stats = detailed_stats["methods"][m]
            count = m_stats.get("count", 0)
            if count == 0:
                continue

            label = "No Import" if m == "no-import" else m.upper()

            # Sub-charts data
            c_type = {
                k.capitalize(): v
                for k, v in m_stats.get("code_type", {}).items()
                if v > 0
            }
            comod_type = {
                k.capitalize(): v
                for k, v in m_stats.get("comodified_code_type", {}).items()
                if v > 0
            }

            if not c_type and not comod_type:
                continue

            # Section Header
            chart_components.append(
                html.H5(
                    f"📊 {label} Statistics",
                    className="mt-4 mb-3",
                    style={
                        "borderBottom": "1px solid #dee2e6",
                        "paddingBottom": "5px",
                        "color": "#6c757d",
                    },
                )
            )

            row_cols = []
            if c_type:
                fig1 = _create_pie_chart(c_type, f"Code Type ({label})")
                row_cols.append(
                    dbc.Col(
                        dcc.Graph(figure=fig1, config={"displayModeBar": False}),
                        width=6,
                    )
                )

            if comod_type:
                fig2 = _create_pie_chart(comod_type, f"Co-modified Type ({label})")
                row_cols.append(
                    dbc.Col(
                        dcc.Graph(figure=fig2, config={"displayModeBar": False}),
                        width=6,
                    )
                )

            if row_cols:
                chart_components.append(dbc.Row(row_cols, className="mb-4"))

    if chart_components:
        charts_section = html.Div(chart_components)

    # Stats Card Content のフォールバック (methodsテーブルが生成されなかった場合のみ)
    if stats_card_content is None:
        if (
            detailed_stats and "detection_methods" in detailed_stats
        ):  # 旧形式のデータがある場合 (後方互換性)
            # Detection Method
            methods = detailed_stats.get("detection_methods", {})
            method_rows = []
            for m, count in methods.items():
                label = "No Import" if m == "no-import" else m.upper()
                method_rows.append((f"{label}:", f"{count:,}"))

            old_cards = []
            if method_rows:
                old_cards.append(
                    html.Div(
                        [
                            html.H5(
                                "🔍 Detection Method",
                                style={"color": "#495057", "marginBottom": "10px"},
                            ),
                            create_info_table(method_rows),
                        ],
                        className="summary-card",
                    )
                )

            # Co-modification
            comod = detailed_stats.get("comodification", {})
            comod_rows = [
                ("Yes (True):", f"{comod.get('true', 0):,}"),
                ("No (False):", f"{comod.get('false', 0):,}"),
            ]
            old_cards.append(
                html.Div(
                    [
                        html.H5(
                            "🔄 Co-modification",
                            style={"color": "#495057", "marginBottom": "10px"},
                        ),
                        create_info_table(comod_rows),
                    ],
                    className="summary-card",
                )
            )

            # Code Type
            ctype = detailed_stats.get("code_type", {})
            logic_count = ctype.get("logic", 0) + ctype.get("production", 0)
            ctype_rows = [
                ("Logic:", f"{logic_count:,}"),
                ("Data:", f"{ctype.get('data', 0):,}"),
                ("Config:", f"{ctype.get('config', 0):,}"),
                ("Test:", f"{ctype.get('test', 0):,}"),
                ("Mixed:", f"{ctype.get('mixed', 0):,}"),
            ]
            old_cards.append(
                html.Div(
                    [
                        html.H5(
                            "📦 Code Type",
                            style={"color": "#495057", "marginBottom": "10px"},
                        ),
                        create_info_table(ctype_rows),
                    ],
                    className="summary-card",
                )
            )

            stats_card_content = html.Div(
                old_cards,
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))",
                    "gap": "15px",
                },
            )

        else:
            # フォールバック: 従来の簡易表示 (dfから計算)
            if df is not None and not df.empty:
                total_pairs = len(df)
                stats_card_content = html.Div(
                    [
                        html.H5(
                            "📊 Clone Statistics (Simple)",
                            style={"color": "#495057", "marginBottom": "10px"},
                        ),
                        create_info_table([("Total Clone Pairs:", f"{total_pairs:,}")]),
                    ],
                    className="summary-card",
                )
            else:
                stats_card_content = html.Div()

    # --- クローンメトリクス (compute_clone_metrics) セクション ---
    metrics_section = html.Div()
    clone_metrics = load_clone_metrics(project, language)
    if clone_metrics:
        metrics_section = _build_clone_metrics_section(clone_metrics)

    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(project_info_card, width=12, lg=6, className="mb-3"),
                    dbc.Col(service_info_card, width=12, lg=6, className="mb-3"),
                ]
            ),
            dbc.Row([dbc.Col(stats_card_content, width=12, className="mb-3")]),
            metrics_section,
            charts_section,
        ],
        fluid=True,
    )

    try:
        if project and language:
            # staticデータ（import行含む）の取得
            static_csv_file = f"src/visualize/csv/{project}_{commit}_{language}_all.csv"
            if os.path.exists(static_csv_file):
                static_df = pd.read_csv(static_csv_file)
                # staticデータで重複除去
                static_df["clone_key"] = (
                    static_df["clone_id"].astype(str)
                    + "|"
                    + static_df["file_path_x"].str.split("/").str[-1]
                    + "|"
                    + static_df["start_line_x"].astype(str)
                    + "-"
                    + static_df["end_line_x"].astype(str)
                    + "|"
                    + static_df["file_path_y"].str.split("/").str[-1]
                    + "|"
                    + static_df["start_line_y"].astype(str)
                    + "-"
                    + static_df["end_line_y"].astype(str)
                )

                if "coord_pair" not in static_df.columns:
                    static_df["coord_pair"] = (
                        static_df["file_id_y"].astype(str)
                        + "_"
                        + static_df["file_id_x"].astype(str)
                    )

                static_df_unique = static_df.drop_duplicates(
                    subset=["coord_pair", "clone_key"]
                )
                static_clone_count = len(static_df_unique)

            # no_importsデータ（import行含まない）は現在の表示データ（既に重複除去済み）
            no_imports_clone_count = total_pairs
    except Exception as e:
        logger.error("Error loading comparison data: %s", e)

    # クローンタイプ別統計（T046最適化+RNR対応）
    if "clone_type" in df_unique.columns:
        type_counts = df_unique["clone_type"].value_counts()
        ccfsw_cnt = type_counts.get("CCFSW", 0)
        tks_cnt = type_counts.get("TKS", 0)
        rnr_cnt = type_counts.get("RNR", 0)

        # 存在するタイプに応じて統計表示
        type_stats = []
        if ccfsw_cnt > 0:
            type_stats.append(
                ("CCFSW Clones:", f"{ccfsw_cnt:,} ({ccfsw_cnt/total_pairs*100:.1f}%)")
            )
        if tks_cnt > 0:
            type_stats.append(
                ("TKS Clones:", f"{tks_cnt:,} ({tks_cnt/total_pairs*100:.1f}%)")
            )
        if rnr_cnt > 0:
            type_stats.append(
                ("RNR Clones:", f"{rnr_cnt:,} ({rnr_cnt/total_pairs*100:.1f}%)")
            )

        if type_stats:
            clone_stats.extend(type_stats)
        else:
            clone_stats.append(("Legacy Data:", f"{total_pairs:,} (100.0%)"))
    else:
        # 旧形式データ
        clone_stats.append(("Legacy Data:", f"{total_pairs:,} (100.0%)"))

    # サービス間・サービス内クローンの統計（重複除去後の正確な値）
    clone_stats.extend(
        [
            (
                "Inter-service Clones:",
                f"{inter_cnt:,} ({inter_cnt/total_pairs*100:.1f}%)",
            ),
            (
                "Intra-service Clones:",
                f"{intra_cnt:,} ({intra_cnt/total_pairs*100:.1f}%)",
            ),
            ("Max Overlap:", f"{top_overlap}"),
        ]
    )

    if language_info and "stats" in language_info:
        stats = language_info["stats"]
        clone_stats.extend(
            [
                ("Avg Clone Size:", f"{stats.get('avg_clone_size', 'N/A')} lines"),
                ("Files with Clones:", f"{stats.get('unique_files', 'N/A'):,}"),
            ]
        )

        # プロジェクト全体のクローン率を表示
        try:
            from ..clone_analytics import calculate_project_average_clone_ratio

            project_clone_ratio = calculate_project_average_clone_ratio(project)
            clone_stats.extend([("Clone Ratio:", f"{project_clone_ratio:.2f}%")])
        except Exception as e:
            logger.error("Error calculating project clone ratio: %s", e)
            clone_stats.extend([("Project Clone Ratio:", "Could not be calculated")])

        # Import preprocessing statistics (if available from project summary)
        # This replaces the old import_heavy detection with preprocessed comparison data

    cards.append(
        html.Div(
            [
                html.H5(
                    "📊 Clone Statistics",
                    style={"color": "#495057", "marginBottom": "10px"},
                ),
                create_info_table(clone_stats),
            ],
            className="summary-card",
        )
    )

    # サービス情報カード（実際のfile_rangesから生成）
    service_data = []
    if file_ranges:
        # 実際のfile_rangesから正確なサービス一覧を生成
        for svc in file_ranges.keys():
            # project_summaryから統計情報を取得（あれば）
            svc_stats = {}
            if (
                language_info
                and "stats" in language_info
                and "services" in language_info["stats"]
                and isinstance(language_info["stats"]["services"], dict)
                and svc in language_info["stats"]["services"]
            ):
                svc_stats = language_info["stats"]["services"][svc]

            service_data.append(
                {
                    "name": svc,
                    "files": svc_stats.get("files", 0),
                    "lines": svc_stats.get("total_lines", 0),
                    "code_lines": svc_stats.get("code_lines", 0),
                    "clone_ratio": clone_ratios.get(svc, 0.0),
                }
            )

    if service_data:
        project_stats_info = []
        if language_info and "stats" in language_info:
            stats = language_info["stats"]
            if stats.get("total_files", 0) > 0:
                project_stats_info.append(("Total Files:", f"{stats['total_files']:,}"))

                if "total_lines" in stats:
                    project_stats_info.append(
                        ("Total Lines:", f"{stats['total_lines']:,}")
                    )

                if "code_lines" in stats:
                    project_stats_info.append(
                        ("Code Lines:", f"{stats['code_lines']:,}")
                    )

        service_content = []
        if project_stats_info:
            service_content.append(
                html.Div(
                    [
                        html.H6(
                            "📁 Project Overview",
                            style={
                                "color": "#6c757d",
                                "fontSize": "12px",
                                "marginBottom": "8px",
                            },
                        ),
                        create_info_table(project_stats_info),
                    ],
                    style={
                        "marginBottom": "15px",
                        "padding": "8px",
                        "background": "#f8f9fa",
                        "borderRadius": "4px",
                    },
                )
            )

        service_content.append(
            html.Div(
                [
                    html.H6(
                        "🔧 Service List",
                        style={
                            "color": "#6c757d",
                            "fontSize": "12px",
                            "marginBottom": "8px",
                        },
                    ),
                    (
                        create_service_table(service_data)
                        if len(service_data) <= 8
                        else html.Details(
                            [
                                html.Summary(
                                    f"{len(service_data)} services (click to expand)"
                                ),
                                create_service_table(service_data),
                            ]
                        )
                    ),
                ]
            )
        )

        cards.append(
            html.Div(
                [
                    html.H5(
                        f"🏗️ Microservices ({len(service_data)})",
                        style={"color": "#495057", "marginBottom": "10px"},
                    ),
                    (
                        create_service_table(service_data)
                        if len(service_data) <= 8
                        else html.Details(
                            [
                                html.Summary(
                                    f"{len(service_data)} services (click to expand)"
                                ),
                                create_service_table(service_data),
                            ]
                        )
                    ),
                ],
                className="summary-card",
            )
        )

    return html.Div(
        [
            html.H4(
                "📈 Project Overview",
                style={
                    "marginBottom": "20px",
                    "color": "#343a40",
                    "border": "none",  # 下線を削除
                },
            ),
            html.Div(cards, className="summary-cards-container"),
        ]
    )


def create_info_table(rows):
    """情報テーブルを作成するヘルパー関数"""
    return html.Table(
        [
            html.Tr(
                [
                    html.Td(label, className="info-label"),
                    html.Td(value, className="info-value"),
                ]
            )
            for label, value in rows
        ],
        className="info-table",
    )


def create_service_table(service_data):
    """サービス統計テーブルを作成するヘルパー関数（シンプル版）"""
    if not service_data:
        return html.P("No service information available")

    # 総行数を計算
    total_files = sum(svc["files"] for svc in service_data)
    total_lines = sum(svc["lines"] for svc in service_data)
    total_code_lines = sum(svc["code_lines"] for svc in service_data)

    header = html.Tr(
        [
            html.Th("Service"),
            html.Th("Files"),
            html.Th("Total Lines"),
            html.Th("Code Lines"),
            html.Th("Clone Ratio"),
        ]
    )

    rows = []
    for svc in service_data:
        rows.append(
            html.Tr(
                [
                    html.Td(svc["name"]),
                    html.Td(f"{svc['files']:,}"),
                    html.Td(f"{svc['lines']:,}"),
                    html.Td(f"{svc['code_lines']:,}"),
                    html.Td(f"{svc['clone_ratio']:.1f}%"),
                ]
            )
        )

    # 合計行を追加
    rows.append(
        html.Tr(
            [
                html.Td("Total", style={"fontWeight": "bold"}),
                html.Td(f"{total_files:,}", style={"fontWeight": "bold"}),
                html.Td(f"{total_lines:,}", style={"fontWeight": "bold"}),
                html.Td(f"{total_code_lines:,}", style={"fontWeight": "bold"}),
                html.Td("-", style={"fontWeight": "bold"}),
            ],
            style={"borderTop": "2px solid #ddd"},
        )
    )

    return html.Table(
        [header] + rows,
        style={"width": "100%", "borderCollapse": "collapse", "fontSize": "14px"},
        className="simple-service-table",
    )


def create_project_clone_ratio_display(project_name: str) -> html.Div:
    """
    プロジェクト全体のクローン率を表示するコンポーネントを作成する。
    """
    try:
        from ..clone_analytics import calculate_project_average_clone_ratio

        clone_ratio = calculate_project_average_clone_ratio(project_name)

        return html.Div(
            [
                html.H3("Project Clone Ratio", className="clone-ratio-title"),
                html.Div(
                    [
                        html.Span(f"{clone_ratio:.2f}%", className="clone-ratio-value"),
                        html.Span(
                            "of code is cloned",
                            className="clone-ratio-description",
                        ),
                    ],
                    className="clone-ratio-container",
                ),
            ],
            className="project-clone-ratio-section",
        )

    except Exception as e:
        logger.error("Error calculating project clone ratio: %s", e)
        return html.Div(
            [
                html.H3("Project Clone Ratio", className="clone-ratio-title"),
                html.Div(
                    [
                        html.Span(
                            "Could not be calculated", className="clone-ratio-error"
                        )
                    ],
                    className="clone-ratio-container",
                ),
            ],
            className="project-clone-ratio-section",
        )


def create_stats_header(df_raw, df_display, filters):
    """散布図上部の統計ヘッダーを生成する"""
    if df_display is None:
        return html.Div()

    total = len(df_raw) if df_raw is not None else 0
    current = len(df_display)
    ratio = (current / total * 100) if total > 0 else 0

    # Filter Badges
    badges = []

    # Method
    method = filters.get("method")
    if method and method != "all":
        label = DetectionMethod.LABELS.get(method, method)
        badges.append(_header_badge("Method", label, "#e1f5fe", "#0277bd"))

    # Code Type
    ctype = filters.get("code_type")
    if ctype and ctype != "all":
        label = ctype.title()  # e.g. Logic, Data
        badges.append(_header_badge("Type", label, "#e8f5e9", "#2e7d32"))

    # Co-modification
    comod = filters.get("comodified")
    if comod and comod != "all":
        label = "Yes" if comod == "true" else "No"
        badge_bg = "#fff3e0" if comod == "true" else "#ffebee"
        badge_col = "#ef6c00" if comod == "true" else "#c62828"
        badges.append(_header_badge("Co-mod", label, badge_bg, badge_col))

    # Service Scope
    scope = filters.get("scope")
    if scope and scope != "all":
        label = "Within Svc" if scope == "within" else "Cross Svc"
        badges.append(_header_badge("Scope", label, "#e0f7fa", "#006064"))

    # Clone ID
    cid = filters.get("clone_id")
    if cid and cid != "all":
        # Clean up clone id display
        label = str(cid).replace("clone_", "")
        badges.append(_header_badge("ID", label, "#f3e5f5", "#7b1fa2"))

    # Statistics
    stats_text = [
        html.Span(
            [html.B(f"{current:,}"), f" / {total:,} pairs ({ratio:.1f}%)"],
            style={"marginRight": "15px"},
        ),
    ]

    # Add Similarity Stats if available
    if "similarity" in df_display.columns and not df_display.empty:
        avg_sim = df_display["similarity"].mean()
        stats_text.append(html.Span([html.B("Avg Sim: "), f"{avg_sim:.2f}"]))

    return html.Div(
        [
            html.Div(
                (
                    badges
                    if badges
                    else [
                        html.Span(
                            "All Data", style={"fontSize": "12px", "color": "#777"}
                        )
                    ]
                ),
                style={"display": "flex", "gap": "8px", "alignItems": "center"},
            ),
            html.Div(stats_text, style={"fontSize": "13px", "color": "#555"}),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "width": "100%",
        },
    )


def _header_badge(key, value, bg_color, text_color):
    return html.Span(
        [
            html.Span(f"{key}: ", style={"fontWeight": "bold", "opacity": "0.7"}),
            html.Span(value),
        ],
        style={
            "backgroundColor": bg_color,
            "color": text_color,
            "padding": "2px 8px",
            "borderRadius": "12px",
            "fontSize": "11px",
            "border": f"1px solid {text_color}40",
        },
    )


def _create_pie_chart(data, title):
    if not data:
        return go.Figure().update_layout(
            title=title, annotations=[dict(text="No Data", showarrow=False)]
        )

    labels = [k.capitalize() for k in data.keys()]
    values = list(data.values())
    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                textinfo="label+percent",
                showlegend=False,
            )
        ]
    )
    fig.update_layout(title_text=title, margin=dict(t=40, b=10, l=10, r=10), height=250)
    return fig


def _create_histogram(data, title):
    if not data:
        return go.Figure().update_layout(
            title=title, annotations=[dict(text="No Data", showarrow=False)]
        )

    fig = go.Figure(data=[go.Histogram(x=data, nbinsx=20, marker_color="#6c757d")])
    fig.update_layout(title_text=title, margin=dict(t=40, b=10, l=10, r=10), height=250)
    return fig
