"""散布図関連のコールバック."""
import logging
import re

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, no_update, html

from ..data_loader import (
    load_and_process_data,
    get_csv_options_for_project,
    clear_data_cache,
)
from ..plotting import create_scatter_plot
from ..components import (
    build_project_summary,
    build_clone_details_view,
    find_overlapping_clones,
    build_clone_selector,
    create_stats_header,
    calculate_cross_service_metrics,
)
from ..constants import DetectionMethod
from modules.util import get_file_type

logger = logging.getLogger(__name__)


def register_scatter_callbacks(app, app_data):
    """散布図・クリック・ドロップダウン関連のコールバックを登録する."""

    # --- 2段階プロジェクト選択: プロジェクト名 → CSVファイル一覧更新 ---
    @app.callback(
        [
            Output("project-selector", "options"),
            Output("project-selector", "value"),
            Output("project-selector", "disabled"),
        ],
        Input("project-name-selector", "value"),
        prevent_initial_call=True,
    )
    def update_csv_options_for_project(project_name):
        """プロジェクト名選択時にCSVファイルドロップダウンを更新する."""
        if not project_name:
            return [], None, True

        from ..data_loader import get_csv_options_for_project

        csv_options = get_csv_options_for_project(project_name)
        if not csv_options:
            return [], None, True

        # 最初のオプションをデフォルト選択
        default_value = csv_options[0]["value"]
        return csv_options, default_value, False

    @app.callback(
        [
            Output("scatter-plot", "figure"),
            Output("project-summary-container", "children", allow_duplicate=True),
            Output("scatter-stats-header", "children"),
        ],  # Added Header Output
        # Output('filter-status', 'children') # Removed from Layout
        [
            Input("project-selector", "value"),  # Renamed
            Input("detection-method-radio", "value"),  # Renamed
            Input("clone-id-filter", "value"),  # Restored as Dropdown
            Input("comodification-filter", "value"),  # Renamed
            Input("code-type-store", "data"),  # Changed from Dropdown to Store
            Input("service-scope-filter", "value"),  # Added service scope filter
            Input("cross-service-filter", "value"),
        ],  # Added cross-service filter (Multi-service)
        # Input('scope-filter', 'value')], # Removed
        prevent_initial_call=True,
    )
    def update_graph_and_summary(
        selected_value,
        detection_method_filter,
        clone_id_filter,
        comodified_filter_val,
        code_type_filter,
        service_scope_filter,
        cross_service_filter,
    ):
        """選択されたプロジェクトとフィルターに基づいて散布図とサマリーを更新"""
        # Default removed filters
        # clone_id_filter = 'all' # Passed as arg
        scope_filter = "all"

        # Map comodification filter (yes/no/all -> true/false/all)
        comodified_filter = "all"
        if comodified_filter_val == "yes":
            comodified_filter = "true"
        elif comodified_filter_val == "no":
            comodified_filter = "false"

        if not selected_value or selected_value.startswith("HEADER_"):
            return no_update, no_update, no_update

        try:
            project, commit, language = selected_value.split("|||", 2)
        except:
            # Handle simple project name case if needed
            return no_update, no_update, no_update

        # プロジェクト変更時にキャッシュをクリア
        current_project_key = f"{project}_{commit}_{language}"
        cached_project_key = f"{app_data.get('project', '')}_{app_data.get('commit', '')}_{app_data.get('language', '')}"

        if current_project_key != cached_project_key:
            logger.info(
                "Project changed from %s to %s, clearing cache...",
                cached_project_key,
                current_project_key,
            )
            from ..data_loader import clear_data_cache

            clear_data_cache()

        df_raw, file_ranges, error = load_and_process_data(project, commit, language)

        if df_raw is None:
            fig = go.Figure().update_layout(title=f"Error: {error}")
            return (
                fig,
                build_project_summary(None, {}, project, commit, language),
                html.Div("Error loading data"),
            )

        # フィルタリング処理：no_importsデータ（import文除去済み）をそのまま使用
        df_filtered = df_raw
        df_display = df_filtered.copy()
        filter_status = ""

        # Scope Filter (Unknown)
        if scope_filter == "resolved":
            df_display = df_display[
                (df_display["service_x"] != "unknown")
                & (df_display["service_y"] != "unknown")
            ]
        elif scope_filter == "unknown":
            df_display = df_display[
                (df_display["service_x"] == "unknown")
                | (df_display["service_y"] == "unknown")
            ]
        # 'all' の場合は何もしない

        # Service Scope Filter (Within / Cross) - Implementation
        if service_scope_filter and service_scope_filter != "all":
            # Use 'relation' column if available for better performance (intra/inter)
            if "relation" in df_display.columns:
                if service_scope_filter == "within":
                    df_display = df_display[df_display["relation"] == "intra"]
                    filter_status += " | 🏠 Within Service"
                elif service_scope_filter == "cross":
                    df_display = df_display[df_display["relation"] == "inter"]
                    filter_status += " | 🌐 Cross Services"
            else:
                # Fallback to string comparison
                if service_scope_filter == "within":
                    df_display = df_display[
                        df_display["service_x"] == df_display["service_y"]
                    ]
                    filter_status += " | 🏠 Within Service"
                elif service_scope_filter == "cross":
                    df_display = df_display[
                        df_display["service_x"] != df_display["service_y"]
                    ]
                    filter_status += " | 🌐 Cross Services"

        # Cross Service Filter (Many Services / Specific ID)
        if cross_service_filter and cross_service_filter != "all":
            try:
                # Value matches Clone ID directly (int)
                selected_clone_id = int(str(cross_service_filter))

                if "clone_id" in df_display.columns:
                    df_display = df_display[df_display["clone_id"] == selected_clone_id]
                    filter_status += f" | 🌐 ID: {selected_clone_id}"
            except Exception as e:
                # Fallback or silent fail
                logger.warning("Cross service filtering error: %s", e)

        # 最適化された検出方法フィルタを適用（T046）
        method_filter_applied = False
        original_count = len(df_display)
        method_column = (
            "detection_method" if "detection_method" in df_display.columns else None
        )
        if not method_column and "clone_type" in df_display.columns:
            method_column = "clone_type"

        logger.debug(
            "Filtering - Method: %s, Column: %s", detection_method_filter, method_column
        )
        if method_column:
            logger.debug(
                "Available methods in data: %s", df_display[method_column].unique()
            )

        if (
            detection_method_filter
            and detection_method_filter != "all"
            and method_column
        ):
            method_filter_applied = True

            # Map 'import' to 'no-import' for legacy compatibility
            target_method = detection_method_filter
            if target_method == "import":
                # Use both 'import' and 'no-import' to be safe
                filtered_data = df_display[
                    df_display[method_column].str.lower().isin(["import", "no-import"])
                ]
            else:
                filtered_data = df_display[
                    df_display[method_column].str.lower() == target_method
                ]

            logger.debug(
                "Filtered count: %d (Original: %d)", len(filtered_data), original_count
            )
            filter_label = f"{DetectionMethod.LABELS.get(detection_method_filter, detection_method_filter)} clones only"

            if len(filtered_data) > 0:
                df_display = filtered_data
            else:
                df_display = filtered_data
                label_upper = DetectionMethod.LABELS.get(
                    detection_method_filter, detection_method_filter
                )
                fig = go.Figure().update_layout(
                    title=f"No {label_upper} clone data found for this project",
                    annotations=[
                        {
                            "text": f"No {label_upper} detection results available,<br>or data conversion has not been performed.",
                            "xref": "paper",
                            "yref": "paper",
                            "x": 0.5,
                            "y": 0.5,
                            "xanchor": "center",
                            "yanchor": "middle",
                            "showarrow": False,
                            "font": {"size": 14, "color": "gray"},
                        }
                    ],
                )
                filter_status = f"🔍 {filter_label} (0 rows)"
                filters = {
                    "method": detection_method_filter,
                    "clone_id": clone_id_filter,
                    "comodified": comodified_filter,
                    "code_type": code_type_filter,
                    "scope": service_scope_filter,
                }
                stats_header = create_stats_header(df_raw, df_display, filters)
                return (
                    fig,
                    build_project_summary(
                        df_display, file_ranges, project, commit, language
                    ),
                    stats_header,
                )

        # クローンIDフィルタを適用（TKSフィルタが適用されている場合はその結果を使用）
        if clone_id_filter and clone_id_filter != "all":
            # clone_id_filter e.g. "ID001" or numeric
            try:
                import re

                # 文字列から数値を抽出 (Legacy format: clone_123, New: 123)
                digit_str = re.sub(r"\D", "", str(clone_id_filter))
                if digit_str:
                    selected_clone_id = int(digit_str)

                    source_df = df_display
                    df_display = source_df[source_df["clone_id"] == selected_clone_id]

                    from ..components import calculate_cross_service_metrics

                    # フィルタリングされたデータフレームを使ってメトリクスを計算
                    clone_metrics, _, _ = calculate_cross_service_metrics(df_display)
                    if selected_clone_id in clone_metrics:
                        metrics = clone_metrics[selected_clone_id]

                        filter_status_parts = []
                        if method_filter_applied:
                            method_label = f"🔍 {DetectionMethod.LABELS.get(detection_method_filter, 'Unknown')}"
                            filter_status_parts.append(method_label)
                        filter_status_parts.append(
                            f"🎯 ID {selected_clone_id:03d}: {metrics['pair_count']}ペア"
                        )
                        filter_status = " | ".join(filter_status_parts)
            except Exception as e:
                logger.warning("Clone ID filtering error: %s", e)
                pass

        # 同時修正フィルタ
        if comodified_filter and comodified_filter != "all":
            # 既にフィルタリングされたdf_displayを使用
            source_df = df_display
            if comodified_filter == "true":
                # True, 1, 'True', 'true' などを許容
                df_display = source_df[
                    source_df["comodified"].isin([True, 1, "True", "true"])
                ]
                filter_status += " | 🔄 Co-modified Only"
            elif comodified_filter == "false":
                # False, 0, 'False', 'false' などを許容
                df_display = source_df[
                    source_df["comodified"].isin([False, 0, "False", "false"])
                ]
                filter_status += " | 🔄 Not Co-modified"

        # コードタイプフィルタ
        if code_type_filter and code_type_filter != "all":
            # フィルタ適用順序を考慮してソースを選択
            source_df = df_display
            # ... (filtering logic kept same) ...
            if "file_type_x" in source_df.columns:
                if code_type_filter == "data":
                    df_display = source_df[
                        (source_df["file_type_x"] == "data")
                        & (source_df["file_type_y"] == "data")
                    ]

                    filter_status += " | 💾 Data Code"
                elif code_type_filter == "logic":
                    # Logic = (Logic or Config or Data) vs (Logic or Config or Data) MINUS (Data-Data) MINUS (Config-Config)
                    # つまり、Productコード同士のペアで、純粋なDataペアとConfigペアを除いたもの（Logic-Config等を含む）
                    product_types = ["logic", "data", "config"]
                    is_product_x = source_df["file_type_x"].isin(product_types)
                    is_product_y = source_df["file_type_y"].isin(product_types)
                    is_data_pair = (source_df["file_type_x"] == "data") & (
                        source_df["file_type_y"] == "data"
                    )
                    is_config_pair = (source_df["file_type_x"] == "config") & (
                        source_df["file_type_y"] == "config"
                    )

                    df_display = source_df[
                        is_product_x & is_product_y & ~is_data_pair & ~is_config_pair
                    ]
                    filter_status += " | 🧠 Logic Code"
                elif code_type_filter == "test":
                    df_display = source_df[
                        (source_df["file_type_x"] == "test")
                        & (source_df["file_type_y"] == "test")
                    ]
                    filter_status += " | 🧪 Test Code"
                elif code_type_filter == "config":
                    df_display = source_df[
                        (source_df["file_type_x"] == "config")
                        & (source_df["file_type_y"] == "config")
                    ]
                    filter_status += " | ⚙️ Config Code"
                elif code_type_filter == "mixed":
                    # Mixed = Test vs Product (Test vs Non-Test)
                    is_test_x = source_df["file_type_x"] == "test"
                    is_test_y = source_df["file_type_y"] == "test"
                    df_display = source_df[is_test_x != is_test_y]
                    filter_status += " | 🔀 Mixed Code"
            else:
                # 古いデータ形式、または file_type カラムがない場合
                # ファイルパスから判定する (get_file_type を使用)
                df_display = source_df.copy()

                # apply を使う (少し遅いが確実)
                df_display["temp_type_x"] = df_display["file_path_x"].apply(
                    lambda x: get_file_type(str(x))
                )
                df_display["temp_type_y"] = df_display["file_path_y"].apply(
                    lambda x: get_file_type(str(x))
                )

                if code_type_filter == "data":
                    df_display = df_display[
                        (df_display["temp_type_x"] == "data")
                        & (df_display["temp_type_y"] == "data")
                    ]
                    filter_status += " | 💾 Data Code"
                elif code_type_filter == "logic":
                    # Logic = Product-Product (excluding pure Data/Config)
                    product_types = ["logic", "data", "config"]
                    is_product_x = df_display["temp_type_x"].isin(product_types)
                    is_product_y = df_display["temp_type_y"].isin(product_types)
                    is_data_pair = (df_display["temp_type_x"] == "data") & (
                        df_display["temp_type_y"] == "data"
                    )
                    is_config_pair = (df_display["temp_type_x"] == "config") & (
                        df_display["temp_type_y"] == "config"
                    )

                    df_display = df_display[
                        is_product_x & is_product_y & ~is_data_pair & ~is_config_pair
                    ]
                    filter_status += " | 🧠 Logic Code"
                elif code_type_filter == "test":
                    df_display = df_display[
                        (df_display["temp_type_x"] == "test")
                        & (df_display["temp_type_y"] == "test")
                    ]
                    filter_status += " | 🧪 Test Code"
                elif code_type_filter == "config":
                    df_display = df_display[
                        (df_display["temp_type_x"] == "config")
                        & (df_display["temp_type_y"] == "config")
                    ]
                    filter_status += " | ⚙️ Config Code"
                elif code_type_filter == "mixed":
                    # Mixed = Test vs Product
                    is_test_x = df_display["temp_type_x"] == "test"
                    is_test_y = df_display["temp_type_y"] == "test"
                    df_display = df_display[is_test_x != is_test_y]
                    filter_status += " | 🔀 Mixed Code"

                # 一時カラムを削除
                df_display = df_display.drop(columns=["temp_type_x", "temp_type_y"])

        # フィルター状態を表示（軽量な通常ペア数で高速表示）
        if not filter_status:  # フィルタ状態がまだ設定されていない場合
            original_pairs = len(df_raw)
            filtered_pairs = len(df_display)
            filter_parts = []

            # サービススコープフィルタの表示
            if service_scope_filter and service_scope_filter != "all":
                scope_icon = "🏠" if service_scope_filter == "within" else "🌐"
                scope_label = "Within" if service_scope_filter == "within" else "Cross"
                filter_parts.append(f"{scope_icon} {scope_label}")

            # 検出方法フィルタの表示
            if (
                method_filter_applied
                and detection_method_filter
                and detection_method_filter != "all"
            ):
                label = DetectionMethod.LABELS.get(
                    detection_method_filter, detection_method_filter
                )
                method_label = f"🔍 {label}"
                filter_parts.append(method_label)

            if (
                clone_id_filter
                and clone_id_filter != "all"
                and clone_id_filter.startswith("clone_")
            ):
                # クローンIDフィルタの場合
                selected_clone_id = clone_id_filter.replace("clone_", "")
                filter_parts.append(f"🎯 ID {selected_clone_id}")

            # 同時修正フィルタの表示
            if comodified_filter and comodified_filter != "all":
                if comodified_filter == "true":
                    filter_parts.append("🔄 同時修正あり")
                elif comodified_filter == "false":
                    filter_parts.append("🔄 同時修正なし")

            # コードタイプフィルタの表示
            if code_type_filter and code_type_filter != "all":
                if code_type_filter == "production":
                    filter_parts.append("🏭 プロダクトコード")
                elif code_type_filter == "test":
                    filter_parts.append("🧪 テストコード")
                elif code_type_filter == "mixed":
                    filter_parts.append("🔀 Mixed")

            # フィルタ状態のメッセージを組み立て
            if filter_parts:
                filter_status = (
                    " | ".join(filter_parts)
                    + f": {filtered_pairs:,} / {original_pairs:,} ペア"
                )
                if filtered_pairs != original_pairs:
                    reduction_percent = (
                        (original_pairs - filtered_pairs) / original_pairs * 100
                    )
                    filter_status += f" ({reduction_percent:.1f}% 削減)"
            else:
                # フィルタなしの場合
                filter_status = (
                    f"表示中: {filtered_pairs:,} / {original_pairs:,} クローンペア"
                )

        # データをキャッシュ
        app_data.update(
            {
                "df": df_display,
                "file_ranges": file_ranges,
                "project": project,
                "commit": commit,
                "language": language,
            }
        )

        # データ点数が多い場合は静的モード（WebGL + ホバーなし）を有効化
        # 閾値は20,000点とする（ブラウザのパフォーマンスに応じて調整）
        static_mode = len(df_display) > 20000
        if static_mode:
            filter_status += " | ⚠️ データ量が多いため静的表示モード（ホバー無効）"

        fig = create_scatter_plot(
            df_display, file_ranges, project, language, static_mode=static_mode
        )
        summary = build_project_summary(
            df_display, file_ranges, project, commit, language
        )

        filters = {
            "method": detection_method_filter,
            "clone_id": clone_id_filter,
            "comodified": comodified_filter,
            "code_type": code_type_filter,
            "scope": service_scope_filter,
        }
        stats_header = create_stats_header(df_raw, df_display, filters)

        return fig, summary, stats_header

    @app.callback(
        Output("clone-selector-container", "children"),
        Input("scatter-plot", "clickData"),
        prevent_initial_call=True,
    )
    def update_clone_selector(clickData):
        """散布図のクリックに基づいてクローン選択用DropDownを更新"""
        if not clickData or app_data["df"].empty:
            return no_update

        # 散布図クリックの場合
        click_x = clickData["points"][0]["x"]
        click_y = clickData["points"][0]["y"]

        overlapping_clones = find_overlapping_clones(app_data["df"], click_x, click_y)

        if len(overlapping_clones) <= 1:
            # 1個以下の場合はDropDownを表示しない
            return html.Div()

        return build_clone_selector(overlapping_clones, app_data["df"])

    @app.callback(
        Output("clone-details-table", "children"),
        Input("scatter-plot", "clickData"),
        prevent_initial_call=True,
    )
    def update_details_from_plot(clickData):
        """散布図のクリックに基づいてクローン詳細テーブルを更新"""
        if not clickData or app_data["df"].empty:
            return no_update

        # 散布図クリックの場合
        click_x = clickData["points"][0]["x"]
        click_y = clickData["points"][0]["y"]

        overlapping_clones = find_overlapping_clones(app_data["df"], click_x, click_y)

        if overlapping_clones:
            # 最初のクローンを表示
            row = app_data["df"].loc[overlapping_clones[0]]

            # 現在選択されているクローン情報をapp_dataに保存
            app_data["current_clone"] = {
                "index": overlapping_clones[0],
                "clone_id": row.get("clone_id", ""),
                "file_id_x": row.get("file_id_x", ""),
                "file_id_y": row.get("file_id_y", ""),
                "file_path_x": row.get("file_path_x", ""),
                "file_path_y": row.get("file_path_y", ""),
                "start_line_x": row.get("start_line_x", ""),
                "end_line_x": row.get("end_line_x", ""),
                "start_line_y": row.get("start_line_y", ""),
                "end_line_y": row.get("end_line_y", ""),
                "click_x": click_x,
                "click_y": click_y,
            }

            return build_clone_details_view(
                row, app_data["project"], app_data["df"], app_data["file_ranges"]
            )

        return html.P(f"座標({click_x}, {click_y})にクローンが見つかりません。")

    @app.callback(
        Output("clone-details-table", "children", allow_duplicate=True),
        Input("clone-dropdown", "value"),
        prevent_initial_call=True,
    )
    def update_details_from_dropdown(selected_clone_idx):
        """ドロップダウン選択に基づいてクローン詳細テーブルを更新"""
        if selected_clone_idx is None or app_data["df"].empty:
            return no_update

        try:
            if selected_clone_idx in app_data["df"].index:
                row = app_data["df"].loc[selected_clone_idx]

                # 現在選択されているクローン情報をapp_dataに保存
                app_data["current_clone"] = {
                    "index": selected_clone_idx,
                    "clone_id": row.get("clone_id", ""),
                    "file_id_x": row.get("file_id_x", ""),
                    "file_id_y": row.get("file_id_y", ""),
                    "file_path_x": row.get("file_path_x", ""),
                    "file_path_y": row.get("file_path_y", ""),
                    "start_line_x": row.get("start_line_x", ""),
                    "end_line_x": row.get("end_line_x", ""),
                    "start_line_y": row.get("start_line_y", ""),
                    "end_line_y": row.get("end_line_y", ""),
                    "click_x": row.get("file_id_y", ""),  # 座標系注意
                    "click_y": row.get("file_id_x", ""),
                }

                return build_clone_details_view(
                    row, app_data["project"], app_data["df"], app_data["file_ranges"]
                )
        except Exception:
            # ドロップダウンが存在しない場合やエラーの場合
            pass

        return no_update

