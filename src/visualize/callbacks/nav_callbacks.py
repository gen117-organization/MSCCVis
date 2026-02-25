"""ナビゲーション・i18n・ヘルプ関連のコールバック."""
import logging

import dash
from dash import Input, Output, State, no_update

logger = logging.getLogger(__name__)


def register_nav_callbacks(app, app_data):
    """ナビゲーション/i18n/ヘルプ/サイドバー関連のコールバックを登録する."""

    # --- i18n: 言語セレクタ → lang-store → clientside で DOM テキスト差し替え ---
    @app.callback(
        Output("lang-store", "data"),
        Input("vis-lang-select", "value"),
        prevent_initial_call=False,
    )
    def _sync_lang_store(lang):
        return lang or "en"

    app.clientside_callback(
        """
        function(lang) {
            if (window.dash_clientside && window.dash_clientside.i18n) {
                return window.dash_clientside.i18n.applyLang(lang);
            }
            return "";
        }
        """,
        Output("i18n-dummy", "children"),
        Input("lang-store", "data"),
    )


    @app.callback(
        [
            Output("scatter-container", "className"),
            Output("ide-main-container", "style"),
            Output("stats-container", "className"),
            Output("btn-view-scatter", "className"),
            Output("btn-view-explorer", "className"),
            Output("btn-view-stats", "className"),
            Output("page-title", "children"),
        ],
        [
            Input("btn-view-scatter", "n_clicks"),
            Input("btn-view-explorer", "n_clicks"),
            Input("btn-view-stats", "n_clicks"),
            Input("url-location", "search"),
        ],
        [State("scatter-container", "className")],
    )
    def toggle_view_mode(btn_scatter, btn_explorer, btn_stats, url_search, current_class):
        ctx = dash.callback_context

        # View definitions: (scatter_cls, ide_style, stats_cls, nav_scatter, nav_explorer, nav_stats, title)
        scatter_state = (
            "view-panel active",
            {"display": "none"},
            "view-panel",
            "nav-link active",
            "nav-link",
            "nav-link",
            "Scatter Plot",
        )
        explorer_state = (
            "view-panel",
            {"display": "flex"},
            "view-panel",
            "nav-link",
            "nav-link active",
            "nav-link",
            "List View",
        )
        stats_state = (
            "view-panel",
            {"display": "none"},
            "view-panel active",
            "nav-link",
            "nav-link",
            "nav-link active",
            "Statistics",
        )

        triggered_id = ""
        if ctx.triggered:
            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # URL ?view= パラメータによる初期ビュー選択
        if not ctx.triggered or triggered_id == "url-location":
            if url_search:
                from urllib.parse import parse_qs
                params = parse_qs(url_search.lstrip("?"))
                view = params.get("view", [""])[0]
                if view == "explorer":
                    return explorer_state
                elif view == "stats":
                    return stats_state
            return scatter_state

        if triggered_id == "btn-view-scatter":
            return scatter_state
        elif triggered_id == "btn-view-explorer":
            return explorer_state
        elif triggered_id == "btn-view-stats":
            return stats_state

        return scatter_state

    # Update store via client-side or server-side when button clicked

    @app.callback(
        Output("help-modal", "is_open"),
        [Input("help-btn", "n_clicks")],
        [State("help-modal", "is_open")],
        prevent_initial_call=True,
    )
    def toggle_help_modal(n_clicks, is_open):
        if n_clicks:
            return not is_open
        return is_open

    # ── Sidebar Collapse (clientside for performance) ──
    app.clientside_callback(
        """
        function(n_clicks) {
            var container = document.querySelector('.app-container');
            if (!container) return '';
            container.classList.toggle('sidebar-collapsed');
            return '';
        }
        """,
        Output("sidebar-toggle", "title"),
        Input("sidebar-toggle", "n_clicks"),
        prevent_initial_call=True,
    )
