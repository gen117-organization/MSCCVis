import logging
from dash import Input, Output, State, no_update, html, dcc, ALL, callback_context
import dash
import json
import pandas as pd
import plotly.graph_objects as go
from .data_loader import load_and_process_data, get_available_projects_enhanced
from .plotting import create_scatter_plot
from .components import (
    build_project_summary, 
    build_clone_details_view, 
    find_overlapping_clones, 
    build_clone_selector, 
    create_stats_header,
    generate_cross_service_filter_options
)
from modules.util import get_file_type
from .constants import DetectionMethod

logger = logging.getLogger(__name__)

# データキャッシュ用のグローバル変数
app_data = {
    'df': pd.DataFrame(),
    'file_ranges': {},
    'project': '',
    'commit': '',
    'language': '',
    'current_clone': {}
}

# Button Colors
CODE_TYPE_COLORS = {
    'all': {'bg': '#f8f9fa', 'border': '#d1d5da', 'text': '#24292e', 'active_bg': '#e1e4e8', 'active_border': '#586069'},
    'logic': {'bg': '#f1f8ff', 'border': '#c8e1ff', 'text': '#0366d6', 'active_bg': '#dbedff', 'active_border': '#0366d6'},
    'data': {'bg': '#ffeef0', 'border': '#f9d0c4', 'text': '#d73a49', 'active_bg': '#ffdce0', 'active_border': '#d73a49'},
    'test': {'bg': '#e6ffed', 'border': '#cdfeb8', 'text': '#28a745', 'active_bg': '#ccffd8', 'active_border': '#28a745'},
    'config': {'bg': '#fafbfc', 'border': '#e1e4e8', 'text': '#6a737d', 'active_bg': '#f6f8fa', 'active_border': '#6a737d'},
    'mixed': {'bg': '#f3f0ff', 'border': '#e0d8ff', 'text': '#6f42c1', 'active_bg': '#e5dbff', 'active_border': '#6f42c1'},
}

def create_code_type_button(label, count, value, active_value):
    isActive = value == active_value
    colors = CODE_TYPE_COLORS.get(value, CODE_TYPE_COLORS['all'])
    
    style = {
        'padding': '4px 10px',
        'border': f'1px solid {colors["active_border"] if isActive else colors["border"]}',
        'borderRadius': '20px',
        'backgroundColor': colors['active_bg'] if isActive else colors['bg'],
        'color': colors['text'],
        'fontSize': '12px',
        'fontWeight': '600' if isActive else 'normal',
        'cursor': 'pointer',
        'boxShadow': '0 1px 2px rgba(0,0,0,0.05)' if not isActive else 'inset 0 1px 2px rgba(0,0,0,0.1)',
        'transition': 'all 0.2s ease',
        'opacity': '1.0' if isActive or count > 0 else '0.5', # Fade if 0 counts but not active,
        'marginRight': '5px' # Inline spacing
    }
    
    return html.Button(
        f"{label} ({count})",
        id={'type': 'code-type-btn', 'index': value},
        n_clicks=0,
        style=style
    )

def register_callbacks(app):
    """Dashアプリにコールバックを登録する"""
    
    # --- i18n: 言語セレクタ → lang-store → clientside で DOM テキスト差し替え ---
    @app.callback(
        Output('lang-store', 'data'),
        Input('vis-lang-select', 'value'),
        prevent_initial_call=False,
    )
    def _sync_lang_store(lang):
        return lang or 'en'

    app.clientside_callback(
        """
        function(lang) {
            if (window.dash_clientside && window.dash_clientside.i18n) {
                return window.dash_clientside.i18n.applyLang(lang);
            }
            return "";
        }
        """,
        Output('i18n-dummy', 'children'),
        Input('lang-store', 'data'),
    )
    
    # --- REMOVED: update_filter_options (UI removed) ---
    
    @app.callback(
        [Output('scatter-plot', 'figure'),
         Output('project-summary-container', 'children', allow_duplicate=True),
         Output('scatter-stats-header', 'children')], # Added Header Output
         # Output('filter-status', 'children') # Removed from Layout
        [Input('project-selector', 'value'), # Renamed
         Input('detection-method-radio', 'value'), # Renamed
         Input('clone-id-filter', 'value'), # Restored as Dropdown
         Input('comodification-filter', 'value'), # Renamed
         Input('code-type-store', 'data'), # Changed from Dropdown to Store
         Input('service-scope-filter', 'value'), # Added service scope filter
         Input('cross-service-filter', 'value')], # Added cross-service filter (Multi-service)
         # Input('scope-filter', 'value')], # Removed
        prevent_initial_call=True
    )
    def update_graph_and_summary(selected_value, detection_method_filter, clone_id_filter, comodified_filter_val, code_type_filter, service_scope_filter, cross_service_filter):
        """選択されたプロジェクトとフィルターに基づいて散布図とサマリーを更新"""
        # Default removed filters
        # clone_id_filter = 'all' # Passed as arg
        scope_filter = 'all'
        
        # Map comodification filter (yes/no/all -> true/false/all)
        comodified_filter = 'all'
        if comodified_filter_val == 'yes':
             comodified_filter = 'true'
        elif comodified_filter_val == 'no':
             comodified_filter = 'false'
        
        if not selected_value or selected_value.startswith('HEADER_'):
            return no_update, no_update, no_update
        
        try:
             project, commit, language = selected_value.split('|||', 2)
        except:
             # Handle simple project name case if needed
             return no_update, no_update, no_update
        
        # プロジェクト変更時にキャッシュをクリア
        current_project_key = f"{project}_{commit}_{language}"
        cached_project_key = f"{app_data.get('project', '')}_{app_data.get('commit', '')}_{app_data.get('language', '')}"
        
        if current_project_key != cached_project_key:
            logger.info("Project changed from %s to %s, clearing cache...", cached_project_key, current_project_key)
            from .data_loader import clear_data_cache
            clear_data_cache()
        
        df_raw, file_ranges, error = load_and_process_data(project, commit, language)

        if df_raw is None:
            fig = go.Figure().update_layout(title=f"Error: {error}")
            return fig, build_project_summary(None, {}, project, commit, language), html.Div("Error loading data")

        # フィルタリング処理：no_importsデータ（import文除去済み）をそのまま使用
        df_filtered = df_raw
        df_display = df_filtered.copy()
        filter_status = ""
        
        # Scope Filter (Unknown)
        if scope_filter == 'resolved':
            df_display = df_display[(df_display['service_x'] != 'unknown') & (df_display['service_y'] != 'unknown')]
        elif scope_filter == 'unknown':
            df_display = df_display[(df_display['service_x'] == 'unknown') | (df_display['service_y'] == 'unknown')]
        # 'all' の場合は何もしない

        # Service Scope Filter (Within / Cross) - Implementation
        if service_scope_filter and service_scope_filter != 'all':
            # Use 'relation' column if available for better performance (intra/inter)
            if 'relation' in df_display.columns:
                if service_scope_filter == 'within':
                    df_display = df_display[df_display['relation'] == 'intra']
                    filter_status += " | 🏠 Within Service"
                elif service_scope_filter == 'cross':
                    df_display = df_display[df_display['relation'] == 'inter']
                    filter_status += " | 🌐 Cross Services"
            else:
                # Fallback to string comparison
                if service_scope_filter == 'within':
                    df_display = df_display[df_display['service_x'] == df_display['service_y']]
                    filter_status += " | 🏠 Within Service"
                elif service_scope_filter == 'cross':
                    df_display = df_display[df_display['service_x'] != df_display['service_y']]
                    filter_status += " | 🌐 Cross Services"

        # Cross Service Filter (Many Services / Specific ID)
        if cross_service_filter and cross_service_filter != 'all':
            try:
                # Value matches Clone ID directly (int)
                selected_clone_id = int(str(cross_service_filter))
                
                if 'clone_id' in df_display.columns:
                    df_display = df_display[df_display['clone_id'] == selected_clone_id]
                    filter_status += f" | 🌐 ID: {selected_clone_id}"
            except Exception as e:
                # Fallback or silent fail
                logger.warning("Cross service filtering error: %s", e)

        # 最適化された検出方法フィルタを適用（T046）
        method_filter_applied = False
        original_count = len(df_display)
        method_column = 'detection_method' if 'detection_method' in df_display.columns else None
        if not method_column and 'clone_type' in df_display.columns:
            method_column = 'clone_type'
        
        logger.debug("Filtering - Method: %s, Column: %s", detection_method_filter, method_column)
        if method_column:
            logger.debug("Available methods in data: %s", df_display[method_column].unique())

        if detection_method_filter and detection_method_filter != 'all' and method_column:
            method_filter_applied = True
            
            # Map 'import' to 'no-import' for legacy compatibility
            target_method = detection_method_filter
            if target_method == 'import':
                # Use both 'import' and 'no-import' to be safe
                filtered_data = df_display[df_display[method_column].str.lower().isin(['import', 'no-import'])]
            else:
                filtered_data = df_display[df_display[method_column].str.lower() == target_method]
            
            logger.debug("Filtered count: %d (Original: %d)", len(filtered_data), original_count)
            filter_label = f"{DetectionMethod.LABELS.get(detection_method_filter, detection_method_filter)} クローンのみ"

            if len(filtered_data) > 0:
                df_display = filtered_data
            else:
                df_display = filtered_data
                label_upper = DetectionMethod.LABELS.get(detection_method_filter, detection_method_filter)
                fig = go.Figure().update_layout(
                    title=f"選択したプロジェクトに{label_upper}クローンデータがありません",
                    annotations=[{
                        'text': f'このプロジェクトには{label_upper}検出結果がないか、<br>データ変換が実行されていない可能性があります。',
                        'xref': 'paper', 'yref': 'paper',
                        'x': 0.5, 'y': 0.5, 'xanchor': 'center', 'yanchor': 'middle',
                        'showarrow': False, 'font': {'size': 14, 'color': 'gray'}
                    }]
                )
                filter_status = f"🔍 {filter_label} (0 行)"
                filters = {
                    'method': detection_method_filter,
                    'clone_id': clone_id_filter,
                    'comodified': comodified_filter,
                    'code_type': code_type_filter,
                    'scope': service_scope_filter
                }
                stats_header = create_stats_header(df_raw, df_display, filters)
                return fig, build_project_summary(df_display, file_ranges, project, commit, language), stats_header
        
        # クローンIDフィルタを適用（TKSフィルタが適用されている場合はその結果を使用）
        if clone_id_filter and clone_id_filter != 'all':
             # clone_id_filter e.g. "ID001" or numeric
            try:
                import re
                # 文字列から数値を抽出 (Legacy format: clone_123, New: 123)
                digit_str = re.sub(r'\D', '', str(clone_id_filter))
                if digit_str:
                    selected_clone_id = int(digit_str)
                    
                    source_df = df_display
                    df_display = source_df[source_df['clone_id'] == selected_clone_id]
                    
                    from .components import calculate_cross_service_metrics
                    # フィルタリングされたデータフレームを使ってメトリクスを計算
                    clone_metrics, _, _ = calculate_cross_service_metrics(df_display)
                    if selected_clone_id in clone_metrics:
                        metrics = clone_metrics[selected_clone_id]
                        
                        filter_status_parts = []
                        if method_filter_applied:
                            method_label = f"🔍 {DetectionMethod.LABELS.get(detection_method_filter, 'Unknown')}"
                            filter_status_parts.append(method_label)
                        filter_status_parts.append(f"🎯 ID {selected_clone_id:03d}: {metrics['pair_count']}ペア")
                        filter_status = " | ".join(filter_status_parts)
            except Exception as e:
                logger.warning("Clone ID filtering error: %s", e)
                pass
        
        # 同時修正フィルタ
        if comodified_filter and comodified_filter != 'all':
            # 既にフィルタリングされたdf_displayを使用
            source_df = df_display
            if comodified_filter == 'true':
                # True, 1, 'True', 'true' などを許容
                df_display = source_df[source_df['comodified'].isin([True, 1, 'True', 'true'])]
                filter_status += " | 🔄 Co-modified Only"
            elif comodified_filter == 'false':
                # False, 0, 'False', 'false' などを許容
                df_display = source_df[source_df['comodified'].isin([False, 0, 'False', 'false'])]
                filter_status += " | 🔄 Not Co-modified"
        
        # コードタイプフィルタ
        if code_type_filter and code_type_filter != 'all':
            # フィルタ適用順序を考慮してソースを選択
            source_df = df_display
            # ... (filtering logic kept same) ...
            if 'file_type_x' in source_df.columns:
                if code_type_filter == 'data':
                    df_display = source_df[(source_df['file_type_x'] == 'data') & (source_df['file_type_y'] == 'data')]

                    filter_status += " | 💾 Data Code"
                elif code_type_filter == 'logic':
                    # Logic = (Logic or Config or Data) vs (Logic or Config or Data) MINUS (Data-Data) MINUS (Config-Config)
                    # つまり、Productコード同士のペアで、純粋なDataペアとConfigペアを除いたもの（Logic-Config等を含む）
                    product_types = ['logic', 'data', 'config']
                    is_product_x = source_df['file_type_x'].isin(product_types)
                    is_product_y = source_df['file_type_y'].isin(product_types)
                    is_data_pair = (source_df['file_type_x'] == 'data') & (source_df['file_type_y'] == 'data')
                    is_config_pair = (source_df['file_type_x'] == 'config') & (source_df['file_type_y'] == 'config')
                    
                    df_display = source_df[is_product_x & is_product_y & ~is_data_pair & ~is_config_pair]
                    filter_status += " | 🧠 Logic Code"
                elif code_type_filter == 'test':
                    df_display = source_df[(source_df['file_type_x'] == 'test') & (source_df['file_type_y'] == 'test')]
                    filter_status += " | 🧪 Test Code"
                elif code_type_filter == 'config':
                    df_display = source_df[(source_df['file_type_x'] == 'config') & (source_df['file_type_y'] == 'config')]
                    filter_status += " | ⚙️ Config Code"
                elif code_type_filter == 'mixed':
                    # Mixed = Test vs Product (Test vs Non-Test)
                    is_test_x = source_df['file_type_x'] == 'test'
                    is_test_y = source_df['file_type_y'] == 'test'
                    df_display = source_df[is_test_x != is_test_y]
                    filter_status += " | 🔀 Mixed Code"
            else:
                # 古いデータ形式、または file_type カラムがない場合
                # ファイルパスから判定する (get_file_type を使用)
                df_display = source_df.copy()
                
                # apply を使う (少し遅いが確実)
                df_display['temp_type_x'] = df_display['file_path_x'].apply(lambda x: get_file_type(str(x)))
                df_display['temp_type_y'] = df_display['file_path_y'].apply(lambda x: get_file_type(str(x)))
                
                if code_type_filter == 'data':
                    df_display = df_display[(df_display['temp_type_x'] == 'data') & (df_display['temp_type_y'] == 'data')]
                    filter_status += " | 💾 Data Code"
                elif code_type_filter == 'logic':
                    # Logic = Product-Product (excluding pure Data/Config)
                    product_types = ['logic', 'data', 'config']
                    is_product_x = df_display['temp_type_x'].isin(product_types)
                    is_product_y = df_display['temp_type_y'].isin(product_types)
                    is_data_pair = (df_display['temp_type_x'] == 'data') & (df_display['temp_type_y'] == 'data')
                    is_config_pair = (df_display['temp_type_x'] == 'config') & (df_display['temp_type_y'] == 'config')
                    
                    df_display = df_display[is_product_x & is_product_y & ~is_data_pair & ~is_config_pair]
                    filter_status += " | 🧠 Logic Code"
                elif code_type_filter == 'test':
                    df_display = df_display[(df_display['temp_type_x'] == 'test') & (df_display['temp_type_y'] == 'test')]
                    filter_status += " | 🧪 Test Code"
                elif code_type_filter == 'config':
                    df_display = df_display[(df_display['temp_type_x'] == 'config') & (df_display['temp_type_y'] == 'config')]
                    filter_status += " | ⚙️ Config Code"
                elif code_type_filter == 'mixed':
                    # Mixed = Test vs Product
                    is_test_x = df_display['temp_type_x'] == 'test'
                    is_test_y = df_display['temp_type_y'] == 'test'
                    df_display = df_display[is_test_x != is_test_y]
                    filter_status += " | 🔀 Mixed Code"
                
                # 一時カラムを削除
                df_display = df_display.drop(columns=['temp_type_x', 'temp_type_y'])


        # フィルター状態を表示（軽量な通常ペア数で高速表示）
        if not filter_status:  # フィルタ状態がまだ設定されていない場合
            original_pairs = len(df_raw)
            filtered_pairs = len(df_display)
            filter_parts = []
            
            # サービススコープフィルタの表示
            if service_scope_filter and service_scope_filter != 'all':
                scope_icon = "🏠" if service_scope_filter == 'within' else "🌐"
                scope_label = "Within" if service_scope_filter == 'within' else "Cross"
                filter_parts.append(f"{scope_icon} {scope_label}")
            
            # 検出方法フィルタの表示
            if method_filter_applied and detection_method_filter and detection_method_filter != 'all':
                label = DetectionMethod.LABELS.get(detection_method_filter, detection_method_filter)
                method_label = f"🔍 {label}"
                filter_parts.append(method_label)
            
            if clone_id_filter and clone_id_filter != 'all' and clone_id_filter.startswith('clone_'):
                # クローンIDフィルタの場合
                selected_clone_id = clone_id_filter.replace('clone_', '')
                filter_parts.append(f"🎯 ID {selected_clone_id}")
            
            # 同時修正フィルタの表示
            if comodified_filter and comodified_filter != 'all':
                if comodified_filter == 'true':
                    filter_parts.append("🔄 同時修正あり")
                elif comodified_filter == 'false':
                    filter_parts.append("🔄 同時修正なし")
            
            # コードタイプフィルタの表示
            if code_type_filter and code_type_filter != 'all':
                if code_type_filter == 'production':
                    filter_parts.append("🏭 プロダクトコード")
                elif code_type_filter == 'test':
                    filter_parts.append("🧪 テストコード")
                elif code_type_filter == 'mixed':
                    filter_parts.append("🔀 Mixed")
            
            # フィルタ状態のメッセージを組み立て
            if filter_parts:
                filter_status = " | ".join(filter_parts) + f": {filtered_pairs:,} / {original_pairs:,} ペア"
                if filtered_pairs != original_pairs:
                    reduction_percent = (original_pairs - filtered_pairs) / original_pairs * 100
                    filter_status += f" ({reduction_percent:.1f}% 削減)"
            else:
                # フィルタなしの場合
                filter_status = f"表示中: {filtered_pairs:,} / {original_pairs:,} クローンペア"

        # データをキャッシュ
        app_data.update({
            'df': df_display,
            'file_ranges': file_ranges,
            'project': project,
            'commit': commit,
            'language': language
        })

        # データ点数が多い場合は静的モード（WebGL + ホバーなし）を有効化
        # 閾値は20,000点とする（ブラウザのパフォーマンスに応じて調整）
        static_mode = len(df_display) > 20000
        if static_mode:
            filter_status += " | ⚠️ データ量が多いため静的表示モード（ホバー無効）"

        fig = create_scatter_plot(df_display, file_ranges, project, language, static_mode=static_mode)
        summary = build_project_summary(df_display, file_ranges, project, commit, language)
        
        filters = {
            'method': detection_method_filter,
            'clone_id': clone_id_filter,
            'comodified': comodified_filter,
            'code_type': code_type_filter,
            'scope': service_scope_filter
        }
        stats_header = create_stats_header(df_raw, df_display, filters)
        
        return fig, summary, stats_header

    @app.callback(
        Output('clone-selector-container', 'children'),
        Input('scatter-plot', 'clickData'),
        prevent_initial_call=True
    )
    def update_clone_selector(clickData):
        """散布図のクリックに基づいてクローン選択用DropDownを更新"""
        if not clickData or app_data['df'].empty:
            return no_update
        
        # 散布図クリックの場合
        click_x = clickData['points'][0]['x']
        click_y = clickData['points'][0]['y']
        
        overlapping_clones = find_overlapping_clones(
            app_data['df'], click_x, click_y
        )
        
        if len(overlapping_clones) <= 1:
            # 1個以下の場合はDropDownを表示しない
            return html.Div()
        
        return build_clone_selector(overlapping_clones, app_data['df'])

    @app.callback(
        Output('clone-details-table', 'children'),
        Input('scatter-plot', 'clickData'),
        prevent_initial_call=True
    )
    def update_details_from_plot(clickData):
        """散布図のクリックに基づいてクローン詳細テーブルを更新"""
        if not clickData or app_data['df'].empty:
            return no_update
        
        # 散布図クリックの場合
        click_x = clickData['points'][0]['x']
        click_y = clickData['points'][0]['y']
        
        overlapping_clones = find_overlapping_clones(
            app_data['df'], click_x, click_y
        )
        
        if overlapping_clones:
            # 最初のクローンを表示
            row = app_data['df'].loc[overlapping_clones[0]]
            
            # 現在選択されているクローン情報をapp_dataに保存
            app_data['current_clone'] = {
                'index': overlapping_clones[0],
                'clone_id': row.get('clone_id', ''),
                'file_id_x': row.get('file_id_x', ''),
                'file_id_y': row.get('file_id_y', ''),
                'file_path_x': row.get('file_path_x', ''),
                'file_path_y': row.get('file_path_y', ''),
                'start_line_x': row.get('start_line_x', ''),
                'end_line_x': row.get('end_line_x', ''),
                'start_line_y': row.get('start_line_y', ''),
                'end_line_y': row.get('end_line_y', ''),
                'click_x': click_x,
                'click_y': click_y
            }
            
            return build_clone_details_view(row, app_data['project'], app_data['df'], app_data['file_ranges'])
        
        return html.P(f"座標({click_x}, {click_y})にクローンが見つかりません。")

    @app.callback(
        Output('clone-details-table', 'children', allow_duplicate=True),
        Input('clone-dropdown', 'value'),
        prevent_initial_call=True
    )
    def update_details_from_dropdown(selected_clone_idx):
        """ドロップダウン選択に基づいてクローン詳細テーブルを更新"""
        if selected_clone_idx is None or app_data['df'].empty:
            return no_update
            
        try:
            if selected_clone_idx in app_data['df'].index:
                row = app_data['df'].loc[selected_clone_idx]
                
                # 現在選択されているクローン情報をapp_dataに保存
                app_data['current_clone'] = {
                    'index': selected_clone_idx,
                    'clone_id': row.get('clone_id', ''),
                    'file_id_x': row.get('file_id_x', ''),
                    'file_id_y': row.get('file_id_y', ''),
                    'file_path_x': row.get('file_path_x', ''),
                    'file_path_y': row.get('file_path_y', ''),
                    'start_line_x': row.get('start_line_x', ''),
                    'end_line_x': row.get('end_line_x', ''),
                    'start_line_y': row.get('start_line_y', ''),
                    'end_line_y': row.get('end_line_y', ''),
                    'click_x': row.get('file_id_y', ''), # 座標系注意
                    'click_y': row.get('file_id_x', '')
                }
                
                return build_clone_details_view(row, app_data['project'], app_data['df'], app_data['file_ranges'])
        except Exception:
            # ドロップダウンが存在しない場合やエラーの場合
            pass
        
        return no_update

    # --- REMOVED: on_dashboard_click (Dashboard table not used) ---
    # @app.callback(
    #     [Output('main-tabs', 'value'),
    #      Output('project-selector', 'value')],
    #     [Input('dashboard-table', 'active_cell')],
    #     [State('dashboard-table', 'data')]
    # )
    # def on_dashboard_click(active_cell, table_data):
    #    pass
        if not active_cell or not table_data:
            return no_update, no_update
        
        try:
            row = table_data[active_cell['row']]
            project = row.get('Project')
            language = row.get('Language')
            
            if project and language:
                options = get_available_projects_enhanced()
                target_value = None
                for opt in options:
                    if isinstance(opt, dict) and 'value' in opt:
                        val = opt['value']
                        if val.startswith('HEADER_'): continue
                        try:
                            p, c, l = val.split('|||', 2)
                            if p == project and l == language:
                                target_value = val
                                break
                        except ValueError:
                            continue
                
                if target_value:
                    return 'tab-scatter', target_value
        except Exception as e:
            logger.error("Error in dashboard click: %s", e)
        
        return no_update, no_update

    # --- REMOVED: update_network_graph_callback (Not used in IDE theme) ---
    # @app.callback(
    #     Output('network-graph', 'figure'),
    #     [Input('project-selector', 'value'),
    #      Input('detection-method-radio', 'value'),
    #      Input('comodification-filter', 'value'),
    #      Input('code-type-filter', 'value')]
    # )
    # def update_network_graph_callback(selected_value, detection_method_filter, comodified_filter, code_type_filter):
    #     pass
        
        try:
            project, commit, language = selected_value.split('|||', 2)
            
            # services.json を読み込む
            from .data_loader import load_full_services_json
            services_json_path = f"dest/scatter/{project}/services.json"
            services_data = load_full_services_json(services_json_path)
            
            # フィルタリングのためにDataFrameを読み込む
            df_raw, _, _ = load_and_process_data(project, commit, language)
            
            df_filtered = None
            if df_raw is not None:
                df_filtered = df_raw.copy()
                
                # Scope Filter (Unknown)
                if scope_filter == 'resolved':
                    df_filtered = df_filtered[(df_filtered['service_x'] != 'unknown') & (df_filtered['service_y'] != 'unknown')]
                elif scope_filter == 'unknown':
                    df_filtered = df_filtered[(df_filtered['service_x'] == 'unknown') | (df_filtered['service_y'] == 'unknown')]
                # 'all' の場合は何もしない

                # Detection Method Filter
                method_column = 'detection_method' if 'detection_method' in df_filtered.columns else None
                if not method_column and 'clone_type' in df_filtered.columns:
                    method_column = 'clone_type'
                
                if detection_method_filter and detection_method_filter != 'all' and method_column:
                    df_filtered = df_filtered[df_filtered[method_column].str.lower() == detection_method_filter]
                
                # Co-modification Filter
                if comodified_filter and comodified_filter != 'all' and 'comodified' in df_filtered.columns:
                    if comodified_filter == 'true':
                        df_filtered = df_filtered[df_filtered['comodified'].isin([True, 1])]
                    else:
                        df_filtered = df_filtered[~df_filtered['comodified'].isin([True, 1])]
                
                # Code Type Filter
                if code_type_filter and code_type_filter != 'all':
                    # file_type カラムが存在し、かつ新しいタイプが含まれているか確認
                    has_new_types = False
                    if 'file_type_x' in df_filtered.columns:
                        unique_types = df_filtered['file_type_x'].unique()
                        if 'data' in unique_types or 'logic' in unique_types:
                            has_new_types = True
                    
                    if has_new_types:
                        if code_type_filter == 'data':
                            df_filtered = df_filtered[(df_filtered['file_type_x'] == 'data') & (df_filtered['file_type_y'] == 'data')]
                        elif code_type_filter == 'logic':
                            df_filtered = df_filtered[(df_filtered['file_type_x'] == 'logic') & (df_filtered['file_type_y'] == 'logic')]
                        elif code_type_filter == 'test':
                            df_filtered = df_filtered[(df_filtered['file_type_x'] == 'test') & (df_filtered['file_type_y'] == 'test')]
                        elif code_type_filter == 'config':
                            df_filtered = df_filtered[(df_filtered['file_type_x'] == 'config') & (df_filtered['file_type_y'] == 'config')]
                        elif code_type_filter == 'mixed':
                            df_filtered = df_filtered[df_filtered['file_type_x'] != df_filtered['file_type_y']]
                    else:
                        # 古いデータ形式、または file_type カラムがない場合
                        # ファイルパスから判定する (get_file_type を使用)
                        
                        # apply を使う
                        df_filtered['temp_type_x'] = df_filtered['file_path_x'].apply(lambda x: get_file_type(str(x)))
                        df_filtered['temp_type_y'] = df_filtered['file_path_y'].apply(lambda x: get_file_type(str(x)))
                        
                        if code_type_filter == 'data':
                            df_filtered = df_filtered[(df_filtered['temp_type_x'] == 'data') & (df_filtered['temp_type_y'] == 'data')]
                        elif code_type_filter == 'logic':
                            df_filtered = df_filtered[(df_filtered['temp_type_x'] == 'logic') & (df_filtered['temp_type_y'] == 'logic')]
                        elif code_type_filter == 'test':
                            df_filtered = df_filtered[(df_filtered['temp_type_x'] == 'test') & (df_filtered['temp_type_y'] == 'test')]
                        elif code_type_filter == 'config':
                            df_filtered = df_filtered[(df_filtered['temp_type_x'] == 'config') & (df_filtered['temp_type_y'] == 'config')]
                        elif code_type_filter == 'mixed':
                            df_filtered = df_filtered[df_filtered['temp_type_x'] != df_filtered['temp_type_y']]
                        
                        # 一時カラムを削除
                        df_filtered = df_filtered.drop(columns=['temp_type_x', 'temp_type_y'])

            from .network import create_network_graph
            return create_network_graph(services_data, project, language, df=df_filtered)
        except Exception as e:
            logger.error("Error updating network graph: %s", e)
            return go.Figure().update_layout(title=f"Error: {e}")

    # --- New IDE Theme Callbacks ---
    
    @app.callback(
        [Output('file-tree-container', 'children'),
         Output('file-tree-data-store', 'data'),
         Output('clone-data-store', 'data'),
         Output('project-summary-container', 'children')],
        [Input('project-selector', 'value')],
        [State('project-selector', 'options')]
    )
    def update_project_data(project_value, project_options):
        """プロジェクト選択時にデータをロードし、ツリーとクローンストアを更新"""
        if not project_value:
             return [], {}, [], "Please select a project."
             
        # Extract selected project info (simple implementation assuming value is just project name or combined string)
        # Assuming project_value is 'project_name|||commit|||language' format based on existing logic
        # But if the user selects from the new dropdown, it might be simpler.
        # Let's adapt to existing format: project|||commit|||default_lang
        
        try:
             project, commit, lang_from_val = project_value.split('|||', 2)
        except ValueError:
             # If value is just project name (e.g. from URL or clean select)
             project = project_value
             commit = "HEAD" # fallback
             lang_from_val = None
        
        target_lang = lang_from_val
        
        # Load Data
        df, file_ranges, error = load_and_process_data(project, commit, target_lang)
        
        if df is None:
             return [], {}, [], f"Error loading data: {error}"
             
        # Generate summary
        summary_view = build_project_summary(df, file_ranges, project, commit, target_lang)
        
        # Build Tree
        from .data_loader import build_file_tree_data, get_clone_related_files
        from .components import create_file_tree_component
        
        related_files = get_clone_related_files(df)
        tree_structure = build_file_tree_data(related_files)
        tree_component = create_file_tree_component(tree_structure)
        
        # Prepare clone data store (minimized)
        # Convert df to dict records for Client-side filtering
        clone_records = df.to_dict('records')
        
        # Removed generate_clone_id_filter_options logic as we use direct input now
        
        return tree_component, tree_structure, clone_records, summary_view
        
    @app.callback(
        [Output('editor-content', 'children'),
         Output('editor-header', 'children'),
         Output('clone-list-container', 'children'),
         Output('selected-file-store', 'data')],
        [Input({'type': 'file-node', 'index': ALL}, 'n_clicks'),
         Input({'type': 'clone-item', 'index': ALL}, 'n_clicks'),
         Input('scatter-plot', 'clickData')],
        [State('clone-data-store', 'data'),
         State('project-selector', 'value'),
         State('selected-file-store', 'data')]
    )
    def handle_explorer_interaction(file_clicks, clone_clicks, scatter_click, clone_data, project_value, current_file):
        """ファイルクリックまたはクローンクリック時の処理"""
        ctx = dash.callback_context
        if not ctx.triggered:
            return no_update
            
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        from .components import create_code_editor_view, create_clone_list_component, build_clone_details_view_single
        from .utils import get_file_content
        
        # Project info
        try:
             project, commit, _ = project_value.split('|||', 2)
        except:
             project = project_value

        if trigger_id == 'scatter-plot':
             if not scatter_click or not clone_data: return no_update
             
             try:
                 # customdata[1] is clone_id based on plotting.py
                 clone_id = scatter_click['points'][0]['customdata'][1]
                 target_clone = next((c for c in clone_data if str(c['clone_id']) == str(clone_id)), None)
                 
                 if target_clone:
                     split_view = build_clone_details_view_single(target_clone, project)
                     view_container = html.Div(split_view, style={'padding': '20px', 'height': '100%', 'overflow': 'auto'})
                     return view_container, f"Comparing Clone #{clone_id}", no_update, no_update
             except Exception as e:
                 logger.error("Error handling scatter click: %s", e)
            
             return no_update

        try:
            trigger_info = json.loads(trigger_id)
        except:
            return no_update

        if trigger_info['type'] == 'file-node':
            # File Clicked -> Show Code & Clone List
            file_name_short = trigger_info['index']
            # Reconstruct full path? This is tricky with flat ID.
            # Ideally we traverse the tree or lookup.
            # For now, let's search in clone_data for matching file name (imperfect but works for demo)
            # Better: Store full path in ID or use client-side callback to pass data.
            # Assuming 'index' carries enough info or we scan clone_data
            
            # Simple scan
            target_file = None
            if not clone_data:
                return no_update
                
            # Find a clone that has this file name at end of path
            # TODO: Improve this path resolution
            samples = [c['file_path_x'] for c in clone_data if c['file_path_x'].endswith(file_name_short)]
            if not samples:
                samples = [c['file_path_y'] for c in clone_data if c['file_path_y'].endswith(file_name_short)]
            
            if samples:
                target_file = samples[0] # Pick first match
            else:
                target_file = f"src/{file_name_short}" # Guess
            
            # Filter clones for this file
            related_clones = []
            for c in clone_data:
                if c['file_path_x'] == target_file:
                    related_clones.append({
                        'clone_id': c['clone_id'],
                        'start_line': int(c['start_line_x']),
                        'end_line': int(c['end_line_x']),
                        'partner_path': c['file_path_y'],
                        'partner_start': int(c['start_line_y']),
                        'partner_end': int(c['end_line_y']),
                        'similarity': 1.0 # placeholder
                    })
                elif c['file_path_y'] == target_file:
                     related_clones.append({
                        'clone_id': c['clone_id'],
                        'start_line': int(c['start_line_y']),
                        'end_line': int(c['end_line_y']),
                        'partner_path': c['file_path_x'],
                        'partner_start': int(c['start_line_x']),
                        'partner_end': int(c['end_line_x']),
                        'similarity': 1.0 # placeholder
                    })
            
            # Get Code Content
            content = get_file_content(project, target_file)
            
            editor_view = create_code_editor_view(content, target_file, related_clones)
            clone_list_view = create_clone_list_component(related_clones)
            
            return editor_view, f"Editing: {target_file}", clone_list_view, target_file
            
        elif trigger_info['type'] == 'clone-item':
            # Clone Clicked -> Show Split View
            clone_id = trigger_info['index'] # ID is str
            
            # Find original row data
            target_clone = next((c for c in clone_data if str(c['clone_id']) == clone_id), None)
            
            if target_clone:
                split_view = build_clone_details_view_single(target_clone, project)
                # Wrap in container to fit editor area style
                view_container = html.Div(split_view, style={'padding': '20px', 'height': '100%', 'overflow': 'auto'})
                
                return view_container, f"Comparing Clone #{clone_id}", no_update, no_update
                
        return no_update

    @app.callback(
        [Output('scatter-container', 'className'),
         Output('ide-main-container', 'style'),
         Output('stats-container', 'className'),
         Output('btn-view-scatter', 'className'),
         Output('btn-view-explorer', 'className'),
         Output('btn-view-stats', 'className')],
        [Input('btn-view-scatter', 'n_clicks'),
         Input('btn-view-explorer', 'n_clicks'),
         Input('btn-view-stats', 'n_clicks')],
        [State('scatter-container', 'className')]
    )
    def toggle_view_mode(btn_scatter, btn_explorer, btn_stats, current_class):
        ctx = dash.callback_context
        
        # Default state (initial load): Scatter active
        if not ctx.triggered:
            return "scatter-container-fullscreen active", {'display': 'none'}, "stats-container-fullscreen", "view-btn active", "view-btn", "view-btn"
            
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'btn-view-scatter':
            return "scatter-container-fullscreen active", {'display': 'none'}, "stats-container-fullscreen", "view-btn active", "view-btn", "view-btn"
        elif button_id == 'btn-view-explorer':
            return "scatter-container-fullscreen", {'display': 'flex'}, "stats-container-fullscreen", "view-btn", "view-btn active", "view-btn"
        elif button_id == 'btn-view-stats':
            return "scatter-container-fullscreen", {'display': 'none'}, "stats-container-fullscreen active", "view-btn", "view-btn", "view-btn active"
            
        return "scatter-container-fullscreen active", {'display': 'none'}, "stats-container-fullscreen", "view-btn active", "view-btn", "view-btn"

    # Update store via client-side or server-side when button clicked
    @app.callback(
        Output('code-type-store', 'data'),
        [Input({'type': 'code-type-btn', 'index': ALL}, 'n_clicks')],
        [State('code-type-store', 'data')],
        prevent_initial_call=True
    )
    def update_selected_code_type(n_clicks, current_value):
        ctx = dash.callback_context
        if not ctx.triggered:
            return no_update
            
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        try:
            val = json.loads(button_id)['index']
            return val
        except:
            return no_update

    # Dynamic generation of Code Type buttons with counts
    @app.callback(
        Output('code-type-buttons-container', 'children'),
        [Input('project-selector', 'value'),
         Input('detection-method-radio', 'value'),
         Input('comodification-filter', 'value'),
         Input('service-scope-filter', 'value'),
         Input('cross-service-filter', 'value'),
         Input('code-type-store', 'data')]
    )
    def update_code_type_counts(project_value, detection_method, comodified_val, service_scope, cross_service, active_code_type):
        if not project_value:
            return []
            
        # Parse project info similar to main callback
        try:
             project, commit, language = project_value.split('|||', 2)
        except:
             return []
             
        # Load data (should be cached)
        df, _, _ = load_and_process_data(project, commit, language)
        if df is None or df.empty:
            return []
            
        # Apply base filters (Method & Comodification & Scope) to count code types
        # 1. Method Filter
        df_filtered = df
        method_column = 'detection_method' if 'detection_method' in df.columns else 'clone_type'
        if not method_column and 'clone_type' in df.columns:
            method_column = 'clone_type'

        if detection_method and detection_method != 'all':
             target_method = detection_method
             
             # Map 'import' to 'no-import'
             if 'detection_method' in df.columns or method_column: 
                 if target_method == 'import':
                     df_filtered = df_filtered[df_filtered[method_column].str.lower().isin(['import', 'no-import'])]
                 else:
                     df_filtered = df_filtered[df_filtered[method_column].str.lower() == target_method]

        # 2. Comodification Filter
        comodified_filter = 'all'
        if comodified_val == 'yes': comodified_filter = 'true'
        elif comodified_val == 'no': comodified_filter = 'false'
        
        if comodified_filter != 'all' and 'comodified' in df_filtered.columns:
            if comodified_filter == 'true':
                df_filtered = df_filtered[df_filtered['comodified'].isin([True, 1])]
            else:
                df_filtered = df_filtered[~df_filtered['comodified'].isin([True, 1])]

        # 3. Service Scope Filter
        if service_scope and service_scope != 'all':
            if 'relation' in df_filtered.columns:
                 if service_scope == 'within':
                     df_filtered = df_filtered[df_filtered['relation'] == 'intra']
                 elif service_scope == 'cross':
                     df_filtered = df_filtered[df_filtered['relation'] == 'inter']
            else:
                 # Fallback
                 if service_scope == 'within':
                     df_filtered = df_filtered[df_filtered['service_x'] == df_filtered['service_y']]
                 elif service_scope == 'cross':
                     df_filtered = df_filtered[df_filtered['service_x'] != df_filtered['service_y']]

        # 4. Cross Service Filter
        if cross_service and cross_service != 'all' and 'clone_id' in df_filtered.columns:
            try:
                selected_clone_id = int(str(cross_service))
                df_filtered = df_filtered[df_filtered['clone_id'] == selected_clone_id]
            except:
                pass

        # Count Code Types
        counts = {'all': len(df_filtered), 'logic': 0, 'data': 0, 'test': 0, 'config': 0, 'mixed': 0}
        
        # Prepare file type series
        if 'file_type_x' in df_filtered.columns:
            series_x = df_filtered['file_type_x']
            series_y = df_filtered['file_type_y']
        else:
            # Fallback (resolve types manually)
            series_x = df_filtered['file_path_x'].apply(lambda x: get_file_type(str(x)))
            series_y = df_filtered['file_path_y'].apply(lambda x: get_file_type(str(x)))

        # 1. Test Pairs
        is_test_x = series_x == 'test'
        is_test_y = series_y == 'test'
        counts['test'] = ((is_test_x) & (is_test_y)).sum()

        # 2. Data Pairs
        is_data_pair = (series_x == 'data') & (series_y == 'data')
        counts['data'] = is_data_pair.sum()

        # 3. Config Pairs
        is_config_pair = (series_x == 'config') & (series_y == 'config')
        counts['config'] = is_config_pair.sum()

        # 4. Mixed Pairs (Test vs Non-Test)
        # Note: Logic in main filter is: `is_test_x != is_test_y`
        counts['mixed'] = (is_test_x != is_test_y).sum()

        # 5. Logic Pairs
        # Logic = Product-Product (logic/data/config) excluding pure Data and pure Config
        product_types = ['logic', 'data', 'config']
        is_product_x = series_x.isin(product_types)
        is_product_y = series_y.isin(product_types)
        is_product_pair = is_product_x & is_product_y
        
        # Ensure we don't double count Data or Config pairs in Logic
        # Logic includes Logic-Logic, Logic-Data, Logic-Config, Data-Config etc.
        # But excludes Data-Data and Config-Config
        is_logic_pair = is_product_pair & ~is_data_pair & ~is_config_pair
        counts['logic'] = is_logic_pair.sum()
                     
        # Generate Buttons
        buttons = []
        # Order: All, Logic, Data, Mixed, Test, Config
        order = ['all', 'logic', 'data', 'mixed', 'test', 'config']
        
        for type_key in order:
            btn = create_code_type_button(
                type_key.capitalize(), 
                counts.get(type_key, 0), 
                type_key, 
                active_code_type or 'all'
            )
            buttons.append(btn)
            
        return buttons

    # Update cross-service filter options based on project data (Filtered)
    @app.callback(
        Output('cross-service-filter', 'options'),
        [Input('project-selector', 'value'),
         Input('detection-method-radio', 'value'),
         Input('comodification-filter', 'value'),
         Input('service-scope-filter', 'value'),
         Input('code-type-store', 'data')]
    )
    def update_cross_service_options(project_value, detection_method, comodified_val, service_scope, code_type_filter):
        if not project_value:
             return [{'label': '所有 (All)', 'value': 'all'}]
        try:
             if '|||' in project_value:
                 project, commit, language = project_value.split('|||', 2)
             else:
                 return [{'label': '所有 (All)', 'value': 'all'}]

             # Reuse load_and_process_data (it is cached)
             df, _, _ = load_and_process_data(project, commit, language)
             
             if df is None or df.empty:
                 return [{'label': '所有 (All)', 'value': 'all'}]
             
             # --- 1. Base Filtering (Method) ---
             # Apply Method filter first to get the universe of clones for this detection method.
             df_method = df

             # Method Filter
             method_column = 'detection_method' if 'detection_method' in df.columns else 'clone_type'
             if not method_column and 'clone_type' in df.columns:
                 method_column = 'clone_type'

             if detection_method and detection_method != 'all':
                  if 'detection_method' in df.columns or method_column:
                      # Robust string conversion for filtering
                      dtype_name = df_method[method_column].dtype.name
                      if dtype_name == 'object' or dtype_name == 'category':
                            try:
                                col_str = df_method[method_column].astype(str).str.lower()
                                if detection_method == 'import':
                                    df_method = df_method[col_str.isin(['import', 'no-import'])]
                                else:
                                    df_method = df_method[col_str == detection_method.lower()]
                            except Exception:
                                pass # Skip filter on error

             if df_method.empty:
                 return [{'label': '条件に一致するクローンはありません (No Match)', 'value': 'all'}]

             # --- 1.5 Code Type Filter ---
             if code_type_filter and code_type_filter != 'all' and 'file_type_x' in df_method.columns:
                 if code_type_filter == 'data':
                     df_method = df_method[(df_method['file_type_x'] == 'data') & (df_method['file_type_y'] == 'data')]
                 elif code_type_filter == 'logic':
                     product_types = ['logic', 'data', 'config']
                     is_product_x = df_method['file_type_x'].isin(product_types)
                     is_product_y = df_method['file_type_y'].isin(product_types)
                     is_data_pair = (df_method['file_type_x'] == 'data') & (df_method['file_type_y'] == 'data')
                     is_config_pair = (df_method['file_type_x'] == 'config') & (df_method['file_type_y'] == 'config')
                     df_method = df_method[is_product_x & is_product_y & ~is_data_pair & ~is_config_pair]
                 elif code_type_filter == 'test':
                     df_method = df_method[(df_method['file_type_x'] == 'test') & (df_method['file_type_y'] == 'test')]
                 elif code_type_filter == 'config':
                     df_method = df_method[(df_method['file_type_x'] == 'config') & (df_method['file_type_y'] == 'config')]
                 elif code_type_filter == 'mixed':
                     is_test_x = df_method['file_type_x'] == 'test'
                     is_test_y = df_method['file_type_y'] == 'test'
                     df_method = df_method[is_test_x != is_test_y]

             if df_method.empty:
                 return [{'label': '条件に一致するクローンはありません (No Match)', 'value': 'all'}]

             # --- 2. Comodification Filter (Selection Phase) ---
             # We select IDs that *contain* at least one pair satisfying the comodification condition.
             # This implements "Plan B": Filter at the clone level, not the pair level.
             
             comodified_filter = 'all'
             if comodified_val == 'yes': comodified_filter = 'true'
             elif comodified_val == 'no': comodified_filter = 'false'
             
             valid_clone_ids = df_method['clone_id'].unique()
             
             if comodified_filter != 'all' and 'comodified' in df_method.columns:
                 if comodified_filter == 'true':
                     # Valid clones must have at least one comodified pair
                     valid_ids_series = df_method.loc[df_method['comodified'].isin([True, 1]), 'clone_id']
                     valid_clone_ids = valid_ids_series.unique()
                 else:
                     # Valid clones must have at least one non-comodified pair (or ONLY non-comodified? Use strict "NO" logic?)
                     # Usually "No" means "Show things that are NOT comodified". 
                     # If a clone has mixed (some yes, some no), usually it's considered "Has Comodification".
                     # If the user wants "No Co-modification", they probably want to see clones that are completely clean or just the pairs that aren't.
                     # However, to be consistent with "Yes" logic (Existence), let's assume strict filtering for "No" might be too harsh if we do "Only No".
                     # Let's simple filter the pairs first, then get IDs. 
                     # Actually, to align with the user request "Interlock with Simultaneous Modification", 
                     # if I choose "YES", I want clones that are being modified together.
                     # If I choose "NO", I want clones that are NOT being modified together.
                     ids_with_comod = df_method.loc[df_method['comodified'].isin([True, 1]), 'clone_id'].unique()
                     if comodified_filter == 'true':
                         valid_clone_ids = ids_with_comod
                     else:
                         # Exclude clones that have ANY comodification? Or just include IDs present in the 'false' set?
                         # Let's stick to the previous simple logic:
                         # Filter rows matching condition -> Get IDs.
                         # This means if I pick "NO", I look for pairs with NO comodification. 
                         # If a clone has 5 pairs, 1 Yes, 4 No. 
                         # "Yes" filter -> finds the 1 pair -> ID matches -> Show Clone (3 services).
                         # "No" filter -> finds the 4 pairs -> ID matches -> Show Clone (3 services).
                         # This seems acceptable. It effectively says "Show me clones involving this type of behavior".
                         valid_ids_series = df_method.loc[~df_method['comodified'].isin([True, 1]), 'clone_id']
                         valid_clone_ids = valid_ids_series.unique()

             if len(valid_clone_ids) == 0:
                 return [{'label': '条件に一致するクローンはありません (No Match)', 'value': 'all'}]

             # --- 3. Calculate "Many Services" Status (Global Context) ---
             # We use ALL pairs derived from the valid IDs (from df_method) to count services.
             # This ensures that even if the "Comodified" pairs are all within Service A, 
             # if the clone also has pairs in Service B (which were not comodified), 
             # the clone counts as satisfying "Many Services".
             
             df_candidates = df_method[df_method['clone_id'].isin(valid_clone_ids)]
             
             if 'clone_id' not in df_candidates.columns:
                 return [{'label': '所有 (All)', 'value': 'all'}]

             s1_df = df_candidates[['clone_id', 'service_x']].rename(columns={'service_x': 'service'})
             s2_df = df_candidates[['clone_id', 'service_y']].rename(columns={'service_y': 'service'})
             services_df = pd.concat([s1_df, s2_df])
             
             # Count unique services per clone_id
             service_counts = services_df.groupby('clone_id')['service'].nunique()
             
             # Identify "Many Service" Clones (>= 2)
             # We DO NOT filter by Scope here, as per user request. 
             # "Many Services" clones should be visible even if Scope is "Within".
             many_service_clones_series = service_counts[service_counts >= 2].sort_values(ascending=False)
             
             # Limit to top 200
             final_target = many_service_clones_series.head(200)
             top_ids = final_target.index.tolist()

             if not top_ids:
                  return [{'label': '条件に一致するクローンはありません (No Match)', 'value': 'all'}]
                  
             # Retrieve Code Types for these IDs (Using df_candidates or df_method)
             df_stats_source = df_method[df_method['clone_id'].isin(top_ids)]
             
             clone_stats = []
             
             if 'file_type_x' in df_stats_source.columns:
                 # Group by clone_id and determine type
                 for cid in top_ids:
                     subset = df_stats_source[df_stats_source['clone_id'] == cid]
                     if subset.empty:
                         continue
                     
                     types_x = subset['file_type_x'].astype(str)
                     types_y = subset['file_type_y'].astype(str)
                     all_types = set(types_x) | set(types_y)
                     
                     if 'test' in all_types and len(all_types - {'test'}) > 0:
                         ctype = 'Mixed'
                     elif len(all_types) == 1:
                         ctype = list(all_types)[0].capitalize()
                     elif 'logic' in all_types:
                         ctype = 'Logic'
                     else:
                         ctype = 'Mixed'
                         
                     clone_stats.append({
                         'clone_id': int(cid),
                         'service_count': final_target[cid],
                         'code_type': ctype
                     })
             else:
                 # Fallback for old data without file types
                 for cid in top_ids:
                     clone_stats.append({
                         'clone_id': int(cid),
                         'service_count': final_target[cid],
                         'code_type': 'Unknown'
                     })
                 
             options = generate_cross_service_filter_options(clone_stats)
             return options
        except Exception as e:
             logger.error("Error updating cross service options: %s", e)
             return [{'label': '所有 (All)', 'value': 'all'}]
