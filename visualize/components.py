import logging

logger = logging.getLogger(__name__)
from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import difflib
import re
import pandas as pd
import os
from .utils import get_local_snippet
from modules.util import get_file_type
from .constants import DetectionMethod
from collections import Counter

def calculate_unique_pair_count_for_clone(clone_df):
    """クローンデータフレームに対してユニークペア数を計算する"""
    if clone_df is None or clone_df.empty:
        return 0
    
    # 重複除去のためのキーを作成
    df_temp = clone_df.copy()
    df_temp['clone_key'] = (df_temp['clone_id'].astype(str) + '|' + 
                           df_temp['file_path_x'].str.split('/').str[-1] + '|' +
                           df_temp['start_line_x'].astype(str) + '-' + df_temp['end_line_x'].astype(str) + '|' +
                           df_temp['file_path_y'].str.split('/').str[-1] + '|' +
                           df_temp['start_line_y'].astype(str) + '-' + df_temp['end_line_y'].astype(str))
    
    # coord_pair列が存在しない場合は作成
    if 'coord_pair' not in df_temp.columns:
        df_temp['coord_pair'] = df_temp['file_id_y'].astype(str) + '_' + df_temp['file_id_x'].astype(str)
    
    # 重複除去して数をカウント
    return len(df_temp.drop_duplicates(subset=['coord_pair', 'clone_key']))

def calculate_cross_service_metrics(df):
    """クローンの多サービス跨り度を分析する"""
    if df is None or df.empty:
        return {}, 0, {}
    
    # 全サービス数を計算
    services_x = set(df['service_x'].unique())
    services_y = set(df['service_y'].unique())
    total_services = len(services_x.union(services_y))
    
    # 各クローンIDが跨るサービス数を計算
    clone_metrics = {}
    for clone_id in df['clone_id'].unique():
        clone_rows = df[df['clone_id'] == clone_id]
        services_x = set(clone_rows['service_x'].unique())
        services_y = set(clone_rows['service_y'].unique())
        all_clone_services = services_x.union(services_y)
        
        # ユニークペア数を計算
        unique_pair_count = calculate_unique_pair_count_for_clone(clone_rows)
        
        # Co-modifiedペア数を計算
        comodified_count = 0
        if 'comodified' in clone_rows.columns:
            comodified_count = len(clone_rows[clone_rows['comodified'].isin([1, True, '1', 'True'])])
            
        # Code Typeの内訳を計算
        code_types = Counter()
        is_mixed = False
        if 'file_type_x' in clone_rows.columns and 'file_type_y' in clone_rows.columns:
            # Mixed判定: Test vs Product (Test vs Non-Test)
            is_test_x = clone_rows['file_type_x'] == 'test'
            is_test_y = clone_rows['file_type_y'] == 'test'
            mixed_rows = clone_rows[is_test_x != is_test_y]
            
            if not mixed_rows.empty:
                is_mixed = True
            
            # 集計はx側をベースにする（代表値）
            code_types.update(clone_rows['file_type_x'])
        elif 'file_type_x' in clone_rows.columns:
            code_types.update(clone_rows['file_type_x'])
            
        # Detection Method (もし混在している場合)
        methods = set()
        if 'detection_method' in clone_rows.columns:
            methods.update(clone_rows['detection_method'].unique())
        elif 'clone_type' in clone_rows.columns: # fallback
             methods.update(clone_rows['clone_type'].unique())

        clone_metrics[clone_id] = {
            'service_count': len(all_clone_services),
            'services': list(all_clone_services),
            'pair_count': unique_pair_count,  # ユニークペア数を使用
            'total_pair_count': len(clone_rows),  # 元の重複含む数も保持
            'comodified_count': comodified_count,
            'code_types': dict(code_types),
            'is_mixed': is_mixed,
            'methods': list(methods),
            'inter_service_pairs': len(clone_rows[clone_rows['clone_type'] == 'inter']),
            'file_paths': list(set(clone_rows['file_path_x'].tolist() + clone_rows['file_path_y'].tolist()))
        }
    
    # サービス跨り度の分布
    service_count_distribution = Counter([metrics['service_count'] for metrics in clone_metrics.values()])
    
    return clone_metrics, total_services, service_count_distribution



def generate_cross_service_filter_options(clone_stats):
    """
    クローンIDごとの統計情報リストからフィルタリングオプションを生成
    clone_stats: list of dict {'clone_id': id, 'service_count': count, 'code_type': type}
    Sorted by service_count DESC
    """
    options = [{'label': 'すべてのクローンを表示 (All)', 'value': 'all'}]
    
    for stat in clone_stats:
        # Improved formatting using symbols for readability and spacing
        label = f"🆔 {stat['clone_id']}   🌐 {stat['service_count']} Services   🏷️ {stat['code_type']}"
        options.append({
            'label': label,
            'value': stat['clone_id']
        })
    
    return options

def get_github_base_url(project):
    """プロジェクト概要と同じ方法でGitHubベースURLを取得する"""
    from .data_loader import load_project_summary
    
    summary_data = load_project_summary()
    if summary_data and project in summary_data.get('projects', {}):
        project_info = summary_data['projects'][project]
        if 'metadata' in project_info:
            metadata = project_info['metadata']
            return metadata.get('url', f"https://github.com/{project}")
    
    # fallback: プロジェクト名からURLを構築
    return f"https://github.com/{project}"

def generate_github_file_url(project, file_path, start_line=None, end_line=None):
    """プロジェクト概要と整合性のあるGitHubファイルURLを生成する"""
    if not project or not file_path:
        return None
    
    # プロジェクト概要と同じ方法でベースURLを取得
    github_base = get_github_base_url(project)
    
    # ファイルパスの先頭の/を削除
    clean_file_path = file_path.lstrip('/')
    
    # デフォルトブランチを使用（通常は main または master）
    # プロジェクトサマリーJSONに branch 情報があればそれを使用
    from .data_loader import load_project_summary
    branch = "main"  # デフォルト
    
    summary_data = load_project_summary()
    if summary_data and project in summary_data.get('projects', {}):
        project_info = summary_data['projects'][project]
        if 'metadata' in project_info:
            metadata = project_info['metadata']
            branch = metadata.get('default_branch', 'master')
    
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
    if 'coord_pair' not in df.columns:
        df['coord_pair'] = df['file_id_y'].astype(str) + '_' + df['file_id_x'].astype(str)
    
    # 該当する座標のクローンを検索
    overlapping_indices = df[df['coord_pair'] == coord_pair].index.tolist()
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
        file_x = row.get('file_path_x', 'Unknown').split('/')[-1]
        file_y = row.get('file_path_y', 'Unknown').split('/')[-1] 
        lines_x = f"{row.get('start_line_x', 0)}-{row.get('end_line_x', 0)}"
        lines_y = f"{row.get('start_line_y', 0)}-{row.get('end_line_y', 0)}"
        clone_id = row.get('clone_id', idx)
        
        # 重複チェック用のキーを作成（clone_id + ファイル + 行範囲）
        clone_key = f"{clone_id}|{file_x}|{lines_x}|{file_y}|{lines_y}"
        
        if clone_key not in seen_clones:
            seen_clones.add(clone_key)
            clone_data.append({
                'clone_id': clone_id,
                'idx': idx,
                'file_x': file_x,
                'file_y': file_y,
                'lines_x': lines_x,
                'lines_y': lines_y,
                'clone_key': clone_key
            })
    
    # 重複除去後の数が1以下の場合は何も表示しない
    if len(clone_data) <= 1:
        return html.Div()
    
    # clone_idごとの個数をカウント（重複除去後）
    from collections import Counter
    clone_id_counts = Counter(data['clone_id'] for data in clone_data)
    
    # ペア数でソート（多い順、同じペア数の場合はclone_idでソート）
    clone_data.sort(key=lambda x: (-clone_id_counts[x['clone_id']], x['clone_id']))
    
    # ソート後にオプションを作成（clone_idの個数情報を追加）
    for data in clone_data:
        clone_id = data['clone_id']
        count = clone_id_counts[clone_id]
        count_info = f" ({count}ペア)" if count > 1 else ""
        label = f"Clone ID {clone_id}: {data['file_x']}[{data['lines_x']}] ↔ {data['file_y']}[{data['lines_y']}]{count_info}"
        options.append({'label': label, 'value': data['idx']})
    
    # 重複除去の情報を表示
    removed_count = clone_count - len(clone_data)
    header_text = f"{len(clone_data)}個のクローンが重複しています。表示するクローンを選択してください："
    if removed_count > 0:
        header_text += f" (重複{removed_count}個を除去)"
    
    return html.Div([
        html.H6(header_text, style={'margin-bottom': '10px'}),
        dcc.Dropdown(
            id='clone-dropdown',
            options=options,
            value=clone_data[0]['idx'],  # ソート後の最初のクローンを選択
            clearable=False,
            style={'width': '100%', 'minWidth': '600px', 'maxWidth': '900px', 'margin-bottom': '15px'}  # 幅を調整
        )
    ], style={'background': 'white', 'padding': '15px', 'border-radius': '8px', 'margin-bottom': '5px'})

def create_help_section():
    """散布図の見方のセクションを作成する"""
    return html.Details([
        html.Summary("📊 散布図の見方", style={'cursor': 'pointer', 'fontWeight': 'bold', 'fontSize': '16px', 'color': '#495057'}),
        html.Div([
            html.P("この散布図は、ファイル間のクローン関係をヒートマップ風に可視化します。", 
                   className='help-text', style={'marginBottom': '15px', 'fontStyle': 'italic'}),
            
            # 基本概念
            html.Div([
                html.H6("🔍 基本概念", style={'color': '#6c757d', 'marginBottom': '10px'}),
                html.Ul([
                    html.Li([html.Strong("軸: "), "各ファイルに割り当てられたファイル番号（X軸・Y軸共通）"]),
                    html.Li([html.Strong("点（プロット）: "), "2つのファイル間でコードクローンが検出されたことを示す"]),
                    html.Li([html.Strong("点線: "), "各マイクロサービスの境界線（ファイル範囲）"]),
                ], style={'marginBottom': '15px'})
            ]),
            
            # マーカー形状
            html.Div([
                html.H6("🔸 マーカー形状", style={'color': '#6c757d', 'marginBottom': '10px'}),
                html.Ul([
                    html.Li([html.Span("● 円形: ", style={'color': '#495057', 'fontWeight': 'bold'}), 
                            "サービス内クローン（同じマイクロサービス内）"]),
                    html.Li([html.Span("■ 四角: ", style={'color': '#495057', 'fontWeight': 'bold'}), 
                            "サービス間クローン（異なるマイクロサービス間）"]),
                ], style={'marginBottom': '15px'})
            ]),
            
            # ヒートマップ色分け
            html.Div([
                html.H6("🌡️ ヒートマップ（クローン集中度）", style={'color': '#6c757d', 'marginBottom': '10px'}),
                html.P("同一座標での重複クローン数に基づく5段階カラーマップ：", style={'marginBottom': '8px'}),
                html.Ul([
                    html.Li([html.Span("● 青: ", style={'color': '#0066CC', 'fontWeight': 'bold'}), "低密度（重複数: 少）"]),
                    html.Li([html.Span("● 緑: ", style={'color': '#00CC66', 'fontWeight': 'bold'}), "中密度"]),
                    html.Li([html.Span("● 黄: ", style={'color': '#CCCC00', 'fontWeight': 'bold'}), "高密度"]),
                    html.Li([html.Span("● オレンジ: ", style={'color': '#FF6600', 'fontWeight': 'bold'}), "超高密度"]),
                    html.Li([html.Span("● 赤: ", style={'color': '#CC0000', 'fontWeight': 'bold'}), "最高密度（重複数: 多）"]),
                ], style={'marginBottom': '15px'})
            ]),
            
            # 操作方法
            html.Div([
                html.H6("🖱️ 操作方法", style={'color': '#6c757d', 'marginBottom': '10px'}),
                html.Ul([
                    html.Li([html.Strong("単一クリック: "), "該当座標のクローン詳細を画面下部に表示"]),
                    html.Li([html.Strong("複数クローン時: "), "DropDownメニューが表示され、表示するクローンを選択可能"]),
                    html.Li([html.Strong("ファイル表示: "), "詳細画面の「File」ボタンで、クローンを含むファイル全体を確認可能"]),
                ], style={'marginBottom': '10px'})
            ]),
            
        ], style={'marginTop': '15px', 'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px'})
    ], className='help-section')

def build_dashboard_view(dashboard_data):
    """ダッシュボードビューを構築する"""
    if not dashboard_data or 'metrics' not in dashboard_data:
        return html.Div([
            html.H3("Dashboard Data Not Found"),
            html.P("Please run 'python commands/generate_services_json.py' to generate dashboard data.")
        ], className="alert alert-warning")
    
    metrics = dashboard_data['metrics']
    detailed_stats = dashboard_data.get('detailed_stats', {})
    
    # --- データ集計 ---
    total_projects = 0
    languages = set()
    total_clones = 0
    clone_ratios = []
    project_lang_list = []
    scatter_points = [] # (file_count, clone_ratio, project_name)

    # テーブル用データ
    table_data = []
    
    # 円グラフ用集計
    total_types = {'logic': 0, 'data': 0, 'config': 0, 'test': 0, 'mixed': 0}
    comod_types = {'logic': 0, 'data': 0, 'config': 0, 'test': 0, 'mixed': 0}
    
    for project, langs in metrics.items():
        total_projects += 1
        for lang, data in langs.items():
            languages.add(lang)
            project_lang_list.append(lang)
            
            clone_ratio = data.get('clone_ratio', {})
            comodification = data.get('comodification_rate', {})
            file_count = data.get('file_count', 0) # Added field
            
            # クローン率 (within-production)
            cr_prod = clone_ratio.get('within-production', 0)
            cr_test = clone_ratio.get('within-testing', 0)
            
            clone_ratios.append(cr_prod)
            scatter_points.append({'x': file_count, 'y': cr_prod, 'text': f"{project} ({lang})"})
            
            # 同時修正率
            co_prod = comodification.get('within-production', {})
            co_prod_rate = 0
            if co_prod.get('count', 0) > 0:
                co_prod_rate = co_prod.get('comodification_count', 0) / co_prod['count']
                
            table_data.append({
                'Project': project,
                'Language': lang,
                'Files': f"{file_count:,}" if file_count > 0 else "N/A",
                'Clone Ratio (Prod)': f"{cr_prod:.2%}",
                'Clone Ratio (Test)': f"{cr_test:.2%}",
                'Co-mod Rate (Prod)': f"{co_prod_rate:.2%}"
            })
            
            # 詳細統計からクローン数とタイプを集計
            if project in detailed_stats and lang in detailed_stats[project]:
                stats = detailed_stats[project][lang]
                if 'methods' in stats:
                    methods = stats['methods']
                    target_method = 'ccfsw' if 'ccfsw' in methods else (list(methods.keys())[0] if methods else None)
                    
                    if target_method:
                        m_stats = methods[target_method]
                        total_clones += m_stats.get('count', 0)
                        
                        code_type = m_stats.get('code_type', {})
                        comod_st = m_stats.get('comodified_code_type', {})
                        
                        for k in total_types.keys():
                            total_types[k] += code_type.get(k, 0)
                            comod_types[k] += comod_st.get(k, 0)

    # 平均値計算
    avg_clone_ratio = sum(clone_ratios) / len(clone_ratios) if clone_ratios else 0
    
    # --- コンポーネント作成 ---
    
    # 1. Overview Cards
    def create_kpi_card(title, value, color):
        return dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(value, className="card-title", style={'fontWeight': 'bold', 'color': color, 'marginBottom': '0'}),
                html.Small(title, className="card-text", style={'color': '#6c757d', 'fontSize': '0.85rem'})
            ], className="text-center p-3")
        ], className="shadow-sm border-0"), width=3)

    overview_row = dbc.Row([
        create_kpi_card("Total Projects", str(total_projects), "#0d6efd"),
        create_kpi_card("Total Languages", str(len(languages)), "#198754"),
        create_kpi_card("Total Clones", f"{total_clones:,}", "#dc3545"),
        create_kpi_card("Avg. Clone Ratio", f"{avg_clone_ratio:.2%}", "#ffc107"),
    ], className="mb-4 g-3")

    # 2. Charts
    
    # Pie Charts (Existing)
    labels_all = [k.capitalize() for k in total_types.keys()]
    values_all = list(total_types.values())
    fig_pie1 = go.Figure(data=[go.Pie(labels=labels_all, values=values_all, hole=.4)])
    fig_pie1.update_layout(title_text="Clones by Code Type (All)", margin=dict(t=40, b=10, l=10, r=10), height=300)

    labels_comod = [k.capitalize() for k in comod_types.keys()]
    values_comod = list(comod_types.values())
    fig_pie2 = go.Figure(data=[go.Pie(labels=labels_comod, values=values_comod, hole=.4)])
    fig_pie2.update_layout(title_text="Co-modified Clones by Code Type", margin=dict(t=40, b=10, l=10, r=10), height=300)
    
    # Histogram: Clone Ratio
    fig_hist = go.Figure(data=[go.Histogram(x=clone_ratios, nbinsx=10, marker_color='#6c757d')])
    fig_hist.update_layout(
        title_text="Clone Ratio Distribution", 
        margin=dict(t=40, b=10, l=10, r=10), 
        height=300,
        xaxis_tickformat='.0%'
    )
    
    # Bar: Projects by Language
    from collections import Counter
    lang_counts = Counter(project_lang_list)
    fig_bar = go.Figure(data=[go.Bar(
        x=list(lang_counts.keys()), 
        y=list(lang_counts.values()),
        marker_color='#20c997'
    )])
    fig_bar.update_layout(title_text="Projects by Language", margin=dict(t=40, b=10, l=10, r=10), height=300)
    
    # Scatter: File Scale vs Clone Ratio
    scatter_x = [p['x'] for p in scatter_points]
    scatter_y = [p['y'] for p in scatter_points]
    scatter_text = [p['text'] for p in scatter_points]
    
    fig_scatter = go.Figure(data=[go.Scatter(
        x=scatter_x, 
        y=scatter_y, 
        mode='markers',
        text=scatter_text,
        marker=dict(size=10, color='#6610f2')
    )])
    fig_scatter.update_layout(
        title_text="File Scale vs Clone Ratio",
        xaxis_title="Number of Files",
        yaxis_title="Clone Ratio",
        yaxis_tickformat='.0%',
        margin=dict(t=40, b=10, l=10, r=10), 
        height=300
    )

    # Layout Construction
    return html.Div([
        html.H2("Project Dashboard", className="mb-4"),
        
        overview_row,
        
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_pie1), width=4),
            dbc.Col(dcc.Graph(figure=fig_pie2), width=4),
            dbc.Col(dcc.Graph(figure=fig_hist), width=4),
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_bar), width=6),
            dbc.Col(dcc.Graph(figure=fig_scatter), width=6),
        ], className="mb-4"),

        html.H4("Project List", className="mb-3"),
        dash_table.DataTable(
            id='dashboard-table',
            data=table_data,
            columns=[{'name': i, 'id': i} for i in ['Project', 'Language', 'Files', 'Clone Ratio (Prod)', 'Clone Ratio (Test)', 'Co-mod Rate (Prod)']],
            sort_action='native',
            filter_action='native',
            style_table={'overflowX': 'auto'},
            cell_selectable=False,
            style_cell={'textAlign': 'left', 'padding': '10px'},
            style_header={
                'backgroundColor': 'rgb(230, 230, 230)',
                'fontWeight': 'bold'
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': 'rgb(248, 248, 248)'
                }
            ]
        )
    ], className="p-4")

def create_layout(available_projects, available_languages, default_value, initial_fig, initial_summary):
    """Dashアプリの全体レイアウトを生成する"""
    
    # ダッシュボードデータの読み込み
    from .data_loader import load_dashboard_data
    dashboard_data = load_dashboard_data()
    dashboard_view = build_dashboard_view(dashboard_data)

    # 言語フィルターのオプションを作成
    language_options = [{'label': '全言語', 'value': 'all'}]
    language_options.extend([{'label': lang, 'value': lang} for lang in available_languages])
    
    # 既存の散布図ビューのコンテンツ
    # プロジェクト選択はタブの外に出すため、ここではフィルタから開始
    scatter_view_content = html.Div(className='container', children=[
        # 上部カード：コントロールパネルとプロジェクト概要
        html.Div(className='card', children=[
            
            html.Div(className='control-row', children=[
                html.Label("クローンIDフィルタ:", className='control-label', style={'width': '120px'}),
                dcc.Dropdown(
                    id='clone-id-filter',
                    options=[{'label': 'すべてのクローンを表示', 'value': 'all'}],
                    value='all',
                    placeholder="クローンIDでフィルタリング...",
                    style={'width': '400px', 'fontFamily': 'monospace', 'fontSize': '13px'},
                    optionHeight=35,
                    maxHeight=300
                )
            ]),
            html.Div(className='control-row', children=[
                html.Div(id='filter-status', style={'fontSize': '13px', 'color': '#333', 'fontWeight': 'bold'})
            ]),
            html.Hr(), # 区切り線
            html.Div(id='project-summary', children=initial_summary)
        ]),
        
        # 中央カード：散布図
        html.Div(className='card', children=[
            create_help_section(), # ヘルプセクションを追加
            dcc.Graph(id='scatter-plot', figure=initial_fig)
        ]),
        
        # 下部カード：クローン詳細
        html.Div(className='card', children=[
            html.Div(id='clone-selector-container'),  # クローン選択UI用のコンテナ
            html.Div(id='clone-details-table', children=[html.P("グラフ上の点をクリックすると、クローンの詳細情報が表示されます。")])
        ])
    ])
    
    # ネットワークグラフビューのコンテンツ
    network_view_content = html.Div(className='container', children=[
        html.Div(className='card', children=[
            html.H4("Service Dependency Network", className="card-title"),
            html.P("マイクロサービス間のクローン共有関係を可視化します。エッジはクローン共有を表し、ノードサイズはファイル数を表します。", className="text-muted"),
            dcc.Graph(id='network-graph', style={'height': '800px'})
        ])
    ])

    # 共通のプロジェクト選択行とフィルタ
    project_selector = html.Div(className='container mb-3', children=[
        html.Div(className='card', children=[
            html.Div(className='control-row', children=[
                html.Label("プロジェクトを選択:", className='control-label', style={'width': '120px'}),
                dcc.Dropdown(
                    id='project-dropdown', 
                    options=available_projects, 
                    value=default_value, 
                    style={'flex': 1, 'minWidth': '500px', 'maxWidth': '800px'},
                    optionHeight=70,
                    maxHeight=400
                )
            ]),
            
            # フィルタ群をRow/Colで整理 (共通化)
            dbc.Row([
                dbc.Col([
                    html.Label("Detection Method:", className='fw-bold'),
                    dbc.RadioItems(
                        id='detection-method-filter',
                        options=DetectionMethod.get_options(),
                        value=DetectionMethod.NO_IMPORT,
                        inline=True,
                        className="mb-2"
                    ),
                ], width=3),
                
                dbc.Col([
                    html.Label("Co-modification:", className='fw-bold'),
                    dbc.RadioItems(
                        id='comodified-filter',
                        options=[
                            {'label': 'All', 'value': 'all'},
                            {'label': 'Yes', 'value': 'true'},
                            {'label': 'No', 'value': 'false'}
                        ],
                        value='all',
                        inline=True,
                        className="mb-2"
                    ),
                ], width=3),
                
                dbc.Col([
                    html.Label("Code Type:", className='fw-bold'),
                    dbc.RadioItems(
                        id='code-type-filter',
                        options=[
                            {'label': 'All', 'value': 'all'},
                            {'label': 'Data', 'value': 'data'},
                            {'label': 'Logic', 'value': 'logic'},
                            {'label': 'Test', 'value': 'test'},
                            {'label': 'Config', 'value': 'config'},
                            {'label': 'Mixed', 'value': 'mixed'}
                        ],
                        value='all',
                        inline=True,
                        className="mb-2"
                    ),
                ], width=3),

                dbc.Col([
                    html.Label("Scope:", className='fw-bold'),
                    dbc.RadioItems(
                        id='scope-filter',
                        options=[
                            {'label': 'Resolved', 'value': 'resolved'},
                            {'label': 'All', 'value': 'all'},
                            {'label': 'Unknown', 'value': 'unknown'}
                        ],
                        value='resolved',
                        inline=True,
                        className="mb-2"
                    ),
                ], width=3),
            ], className="mb-3 p-2 border rounded bg-light"),
        ])
    ])

    # タブ構成
    return dbc.Container([
        html.H1("Microservice Code Clone Analysis", className="my-4 text-center"),
        project_selector,
        dcc.Tabs(id="main-tabs", value='tab-dashboard', children=[
            dcc.Tab(label='Dashboard', value='tab-dashboard', children=[dashboard_view]),
            dcc.Tab(label='Scatter Plot', value='tab-scatter', children=[scatter_view_content]),
            dcc.Tab(label='Dependency Network', value='tab-network', children=[network_view_content]),
        ]),
    ], fluid=True)

def build_project_summary(df, file_ranges, project, commit, language):
    """プロジェクトの統計情報サマリーを生成する（services.jsonの事前計算データを優先）"""
    from .data_loader import load_project_summary, load_full_services_json
    
    # services.json から詳細統計を読み込む
    services_json_path = f"dest/scatter/{project}/services.json"
    services_data = load_full_services_json(services_json_path)
    
    detailed_stats = {}
    
    if services_data and 'detailed_stats' in services_data:
        # 言語ごとの統計を取得（大文字小文字を吸収）
        target_lang = language.lower()
        for lang_key, stats in services_data['detailed_stats'].items():
            if lang_key.lower() == target_lang:
                detailed_stats = stats
                break
    
    # プロジェクトサマリーJSONからの追加情報
    summary_data = load_project_summary()
    project_info = None
    language_info = None
    
    if summary_data and project in summary_data.get('projects', {}):
        project_info = summary_data['projects'][project]
        if language in project_info.get('languages', {}):
            language_info = project_info['languages'][language]
    
    # --- 1. プロジェクト情報カード ---
    basic_info = [
        ("プロジェクト名:", project.split('.')[-1]),
        ("コミット/参照:", commit[:7] if len(commit) > 7 else commit),
        ("対象言語:", language)
    ]
    
    # GitHubリンク
    if project_info and 'metadata' in project_info:
        metadata = project_info['metadata']
        github_url = metadata.get('url', f"https://github.com/{project}")
        basic_info.append(("GitHubリンク:", html.A(github_url, href=github_url, target="_blank", style={'color': '#007bff', 'textDecoration': 'underline'})))
    elif project:
        github_url = f"https://github.com/{project}"
        basic_info.append(("GitHubリンク:", html.A(github_url, href=github_url, target="_blank", style={'color': '#007bff', 'textDecoration': 'underline'})))
    
    # プロジェクト全体統計
    if language_info and 'stats' in language_info:
        stats = language_info['stats']
        if stats.get('total_files', 0) > 0:
            basic_info.append(("総ファイル数:", f"{stats['total_files']:,}"))
            if 'code_lines' in stats:
                basic_info.append(("総コード行数:", f"{stats['code_lines']:,}"))
    
    project_info_card = html.Div([
        html.H5("📋 プロジェクト情報", style={'color': '#495057', 'marginBottom': '10px'}),
        create_info_table(basic_info)
    ], className='summary-card', style={'height': '100%'})
    
    # --- 2. サービス情報カード ---
    service_content = html.P("サービス情報がありません")
    if file_ranges:
        # サービスごとの統計情報を構築
        svc_file_counts = {}
        if services_data and 'languages' in services_data:
            for lang_key, lang_data in services_data['languages'].items():
                if lang_key.lower() == language.lower():
                    svc_file_counts = lang_data.get('file_counts', {})
                    break
        
        header = html.Tr([
            html.Th("Service"),
            html.Th("Files"),
        ])
        
        rows = []
        for svc in sorted(file_ranges.keys()):
            files = svc_file_counts.get(svc, 0)
            rows.append(html.Tr([
                html.Td(svc, style={'wordBreak': 'break-all'}),
                html.Td(f"{files:,}"),
            ]))
            
        # dbc.Tableを使用
        service_table = dbc.Table([html.Thead(header), html.Tbody(rows)], bordered=True, hover=True, striped=True, size="sm", style={'fontSize': '12px'})
        service_content = html.Div(service_table, style={'maxHeight': '300px', 'overflowY': 'auto'})

    service_info_card = html.Div([
        html.H5("🏢 サービス情報", style={'color': '#495057', 'marginBottom': '10px'}),
        service_content
    ], className='summary-card', style={'height': '100%'})

    # --- 3. クローン統計カード (詳細版 - マトリクス表示) ---
    stats_card_content = None
    
    if detailed_stats and 'methods' in detailed_stats:
        methods_data = detailed_stats['methods']
        
        header = html.Tr([
            html.Th("Method"),
            html.Th("Total"),
            html.Th("Co-modified"),
            html.Th("Logic"),
            html.Th("Data"),
            html.Th("Config"),
            html.Th("Test"),
            html.Th("Mixed")
        ])
        
        rows = []
        method_order = ['ccfsw', 'tks']
        available_methods = sorted(methods_data.keys(), key=lambda x: method_order.index(x) if x in method_order else 99)
        
        for m in available_methods:
            m_stats = methods_data[m]
            count = m_stats.get('count', 0)
            
            comod = m_stats.get('comodified', {})
            comod_true = comod.get('true', 0)
            comod_pct = (comod_true / count * 100) if count > 0 else 0
            
            ctype = m_stats.get('code_type', {})
            logic = ctype.get('logic', 0) + ctype.get('production', 0) # Fallback for legacy 'production'
            data = ctype.get('data', 0)
            config = ctype.get('config', 0)
            test = ctype.get('test', 0)
            mixed = ctype.get('mixed', 0)

            # Comodified Code Type
            comod_ctype = m_stats.get('comodified_code_type', {})
            comod_logic = comod_ctype.get('logic', 0)
            comod_data = comod_ctype.get('data', 0)
            comod_config = comod_ctype.get('config', 0)
            comod_test = comod_ctype.get('test', 0)
            comod_mixed = comod_ctype.get('mixed', 0)
            
            label = "Normal" if m == 'ccfsw' else m.upper()
            
            rows.append(html.Tr([
                html.Td(html.B(label)),
                html.Td(f"{count:,}"),
                html.Td(f"{comod_true:,} ({comod_pct:.1f}%)"),
                html.Td(f"{logic:,} ({comod_logic:,})", title="Total (Co-modified)"),
                html.Td(f"{data:,} ({comod_data:,})", title="Total (Co-modified)"),
                html.Td(f"{config:,} ({comod_config:,})", title="Total (Co-modified)"),
                html.Td(f"{test:,} ({comod_test:,})", title="Total (Co-modified)"),
                html.Td(f"{mixed:,} ({comod_mixed:,})", title="Total (Co-modified)")
            ]))

        # dbc.Tableを使用
        stats_table = dbc.Table([html.Thead(header), html.Tbody(rows)], bordered=True, hover=True, striped=True, size="sm", style={'fontSize': '12px', 'textAlign': 'center'})
        
        stats_card_content = html.Div([
            html.H5("📊 クローン統計詳細", style={'color': '#495057', 'marginBottom': '10px'}),
            html.Div(stats_table, style={'overflowX': 'auto', 'marginBottom': '15px'})
        ], className='summary-card')
    
    # --- 4. Charts Section ---
    # --- 4. Charts Section ---
    charts_section = html.Div()
    
    # データ準備 (Aggregating or Loading)
    counts_by_type = {}
    counts_by_method = {}
    counts_by_comod_type = {}
    
    # 既存の統計情報があれば使用
    if detailed_stats and 'count_by_type' in detailed_stats and 'count_by_method' in detailed_stats:
         counts_by_type = detailed_stats['count_by_type']
         counts_by_method = detailed_stats['count_by_method']
         if 'count_by_comod_type' in detailed_stats:
             counts_by_comod_type = detailed_stats['count_by_comod_type']

    # なければ methods から集計 (新形式)
    elif detailed_stats and 'methods' in detailed_stats:
         c_type_agg = Counter()
         m_agg = Counter()
         comod_type_agg = Counter()
         
         for m, m_stats in detailed_stats['methods'].items():
            count = m_stats.get('count', 0)
            if count > 0:
                label = "No Import" if m == "no-import" else m.upper()
                m_agg[label] += count
            
            if 'code_type' in m_stats:
                for ct, cc in m_stats['code_type'].items():
                     if cc > 0:
                         c_type_agg[ct.capitalize()] += cc
                         
            if 'comodified_code_type' in m_stats:
                for ct, cc in m_stats['comodified_code_type'].items():
                     if cc > 0:
                         comod_type_agg[ct.capitalize()] += cc
                         
         counts_by_type = dict(c_type_agg)
         counts_by_method = dict(m_agg)
         counts_by_comod_type = dict(comod_type_agg)

    # チャートの生成
    chart_components = []
    
    # 1. Overall Method Breakdown (Main Chart)
    if counts_by_method:
        fig_method = _create_pie_chart(counts_by_method, "Overall Detection Method Breakdown")
        chart_components.append(dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_method, config={'displayModeBar': False}), width=12),
        ], className="mb-4"))

    # 2. Charts per Method
    if detailed_stats and 'methods' in detailed_stats:
        method_order = ['tks', 'no-import', 'ccfsw']
        sorted_methods = sorted(detailed_stats['methods'].keys(), key=lambda x: method_order.index(x) if x in method_order else 99)
        
        for m in sorted_methods:
            m_stats = detailed_stats['methods'][m]
            count = m_stats.get('count', 0)
            if count == 0: continue

            label = "No Import" if m == 'no-import' else m.upper()
            
            # Sub-charts data
            c_type = {k.capitalize(): v for k, v in m_stats.get('code_type', {}).items() if v > 0}
            comod_type = {k.capitalize(): v for k, v in m_stats.get('comodified_code_type', {}).items() if v > 0}
            
            if not c_type and not comod_type:
                continue

            # Section Header
            chart_components.append(html.H5(f"📊 {label} Statistics", className="mt-4 mb-3", style={'borderBottom': '1px solid #dee2e6', 'paddingBottom': '5px', 'color': '#6c757d'}))
            
            row_cols = []
            if c_type:
                fig1 = _create_pie_chart(c_type, f"Code Type ({label})")
                row_cols.append(dbc.Col(dcc.Graph(figure=fig1, config={'displayModeBar': False}), width=6))
            
            if comod_type:
                fig2 = _create_pie_chart(comod_type, f"Co-modified Type ({label})")
                row_cols.append(dbc.Col(dcc.Graph(figure=fig2, config={'displayModeBar': False}), width=6))
            
            if row_cols:
                chart_components.append(dbc.Row(row_cols, className="mb-4"))

    if chart_components:
        charts_section = html.Div(chart_components)

    # Stats Card Content のフォールバック (methodsテーブルが生成されなかった場合のみ)
    if stats_card_content is None:
        if detailed_stats and 'detection_methods' in detailed_stats: # 旧形式のデータがある場合 (後方互換性)
            # Detection Method
            methods = detailed_stats.get('detection_methods', {})
            method_rows = []
            for m, count in methods.items():
                label = "No Import" if m == 'no-import' else m.upper()
                method_rows.append((f"{label}:", f"{count:,}"))
            
            old_cards = []
            if method_rows:
                old_cards.append(html.Div([
                    html.H5("🔍 Detection Method", style={'color': '#495057', 'marginBottom': '10px'}),
                    create_info_table(method_rows)
                ], className='summary-card'))
                
            # Co-modification
            comod = detailed_stats.get('comodification', {})
            comod_rows = [
                ("あり (True):", f"{comod.get('true', 0):,}"),
                ("なし (False):", f"{comod.get('false', 0):,}")
            ]
            old_cards.append(html.Div([
                html.H5("🔄 Co-modification", style={'color': '#495057', 'marginBottom': '10px'}),
                create_info_table(comod_rows)
            ], className='summary-card'))
            
            # Code Type
            ctype = detailed_stats.get('code_type', {})
            logic_count = ctype.get('logic', 0) + ctype.get('production', 0)
            ctype_rows = [
                ("Logic:", f"{logic_count:,}"),
                ("Data:", f"{ctype.get('data', 0):,}"),
                ("Config:", f"{ctype.get('config', 0):,}"),
                ("Test:", f"{ctype.get('test', 0):,}"),
                ("Mixed:", f"{ctype.get('mixed', 0):,}")
            ]
            old_cards.append(html.Div([
                html.H5("📦 Code Type", style={'color': '#495057', 'marginBottom': '10px'}),
                create_info_table(ctype_rows)
            ], className='summary-card'))
            
            stats_card_content = html.Div(old_cards, style={'display': 'grid', 'gridTemplateColumns': 'repeat(auto-fit, minmax(200px, 1fr))', 'gap': '15px'})
            
        else:
            # フォールバック: 従来の簡易表示 (dfから計算)
            if df is not None and not df.empty:
                total_pairs = len(df)
                stats_card_content = html.Div([
                    html.H5("📊 クローン統計 (簡易)", style={'color': '#495057', 'marginBottom': '10px'}),
                    create_info_table([("総クローンペア数:", f"{total_pairs:,}")])
                ], className='summary-card')
            else:
                stats_card_content = html.Div()

    return dbc.Container([
        dbc.Row([
            dbc.Col(project_info_card, width=12, lg=6, className="mb-3"),
            dbc.Col(service_info_card, width=12, lg=6, className="mb-3"),
        ]),
        dbc.Row([
            dbc.Col(stats_card_content, width=12, className="mb-3")
        ]),
        charts_section
    ], fluid=True)


    
    try:
        if project and language:
            # staticデータ（import行含む）の取得
            static_csv_file = f"visualize/csv/{project}_{commit}_{language}_all.csv"
            if os.path.exists(static_csv_file):
                static_df = pd.read_csv(static_csv_file)
                # staticデータで重複除去
                static_df['clone_key'] = (static_df['clone_id'].astype(str) + '|' + 
                                        static_df['file_path_x'].str.split('/').str[-1] + '|' +
                                        static_df['start_line_x'].astype(str) + '-' + static_df['end_line_x'].astype(str) + '|' +
                                        static_df['file_path_y'].str.split('/').str[-1] + '|' +
                                        static_df['start_line_y'].astype(str) + '-' + static_df['end_line_y'].astype(str))
                
                if 'coord_pair' not in static_df.columns:
                    static_df['coord_pair'] = static_df['file_id_y'].astype(str) + '_' + static_df['file_id_x'].astype(str)
                
                static_df_unique = static_df.drop_duplicates(subset=['coord_pair', 'clone_key'])
                static_clone_count = len(static_df_unique)
            
            # no_importsデータ（import行含まない）は現在の表示データ（既に重複除去済み）
            no_imports_clone_count = total_pairs
    except Exception as e:
        logger.error("Error loading comparison data: %s", e)
    
    # クローンタイプ別統計（T046最適化+RNR対応）
    if 'clone_type' in df_unique.columns:
        type_counts = df_unique['clone_type'].value_counts()
        ccfsw_cnt = type_counts.get('CCFSW', 0)
        tks_cnt = type_counts.get('TKS', 0)
        rnr_cnt = type_counts.get('RNR', 0)
        
        # 存在するタイプに応じて統計表示
        type_stats = []
        if ccfsw_cnt > 0:
            type_stats.append(("CCFSW クローン:", f"{ccfsw_cnt:,} ({ccfsw_cnt/total_pairs*100:.1f}%)"))
        if tks_cnt > 0:
            type_stats.append(("TKS クローン:", f"{tks_cnt:,} ({tks_cnt/total_pairs*100:.1f}%)"))
        if rnr_cnt > 0:
            type_stats.append(("RNR クローン:", f"{rnr_cnt:,} ({rnr_cnt/total_pairs*100:.1f}%)"))
        
        if type_stats:
            clone_stats.extend(type_stats)
        else:
            clone_stats.append(("レガシーデータ:", f"{total_pairs:,} (100.0%)"))
    else:
        # 旧形式データ
        clone_stats.append(("レガシーデータ:", f"{total_pairs:,} (100.0%)"))
    
    # サービス間・サービス内クローンの統計（重複除去後の正確な値）
    clone_stats.extend([
        ("サービス間クローン:", f"{inter_cnt:,} ({inter_cnt/total_pairs*100:.1f}%)"),
        ("サービス内クローン:", f"{intra_cnt:,} ({intra_cnt/total_pairs*100:.1f}%)"),
        ("最大重複数:", f"{top_overlap}")
    ])
    
    if language_info and 'stats' in language_info:
        stats = language_info['stats']
        clone_stats.extend([
            ("平均クローンサイズ:", f"{stats.get('avg_clone_size', 'N/A')} 行"),
            ("クローン対象ファイル数:", f"{stats.get('unique_files', 'N/A'):,}")
        ])
        
        # プロジェクト全体のクローン率を表示
        try:
            from visualize.clone_analytics import calculate_project_average_clone_ratio
            project_clone_ratio = calculate_project_average_clone_ratio(project)
            clone_stats.extend([
                ("クローン率:", f"{project_clone_ratio:.2f}%")
            ])
        except Exception as e:
            logger.error("Error calculating project clone ratio: %s", e)
            clone_stats.extend([
                ("プロジェクト全体クローン率:", "計算できませんでした")
            ])
        
        # Import preprocessing statistics (if available from project summary)
        # This replaces the old import_heavy detection with preprocessed comparison data
    
    cards.append(html.Div([
        html.H5("📊 クローン統計", style={'color': '#495057', 'marginBottom': '10px'}),
        create_info_table(clone_stats)
    ], className='summary-card'))
    
    # サービス情報カード（実際のfile_rangesから生成）
    service_data = []
    if file_ranges:
        # 実際のfile_rangesから正確なサービス一覧を生成
        for svc in file_ranges.keys():
            # project_summaryから統計情報を取得（あれば）
            svc_stats = {}
            if (language_info and 'stats' in language_info and 
                'services' in language_info['stats'] and 
                isinstance(language_info['stats']['services'], dict) and 
                svc in language_info['stats']['services']):
                svc_stats = language_info['stats']['services'][svc]
            
            service_data.append({
                'name': svc,
                'files': svc_stats.get('files', 0),
                'lines': svc_stats.get('total_lines', 0),
                'code_lines': svc_stats.get('code_lines', 0),
                'clone_ratio': clone_ratios.get(svc, 0.0)
            })
    
    if service_data:
        project_stats_info = []
        if language_info and 'stats' in language_info:
            stats = language_info['stats']
            if stats.get('total_files', 0) > 0:
                project_stats_info.append(("プロジェクト全ファイル数:", f"{stats['total_files']:,}"))
                
                if 'total_lines' in stats:
                    project_stats_info.append(("プロジェクト全行数:", f"{stats['total_lines']:,}"))
                
                if 'code_lines' in stats:
                    project_stats_info.append(("プロジェクトコード行数:", f"{stats['code_lines']:,}"))
        
        service_content = []
        if project_stats_info:
            service_content.append(html.Div([
                html.H6("� プロジェクト全体", style={'color': '#6c757d', 'fontSize': '12px', 'marginBottom': '8px'}),
                create_info_table(project_stats_info)
            ], style={'marginBottom': '15px', 'padding': '8px', 'background': '#f8f9fa', 'borderRadius': '4px'}))
        
        service_content.append(html.Div([
            html.H6("🔧 サービス一覧", style={'color': '#6c757d', 'fontSize': '12px', 'marginBottom': '8px'}),
            create_service_table(service_data) if len(service_data) <= 8 else html.Details([
                html.Summary(f"{len(service_data)} サービス (クリックで展開)"),
                create_service_table(service_data)
            ])
        ]))
        
        cards.append(html.Div([
            html.H5(f"🏗️ マイクロサービス ({len(service_data)})", style={'color': '#495057', 'marginBottom': '10px'}),
            create_service_table(service_data) if len(service_data) <= 8 else html.Details([
                html.Summary(f"{len(service_data)} サービス (クリックで展開)"),
                create_service_table(service_data)
            ])
        ], className='summary-card'))

    return html.Div([
        html.H4("📈 プロジェクト概要", style={
            'marginBottom': '20px', 
            'color': '#343a40',
            'border': 'none'  # 下線を削除
        }),
        html.Div(cards, className='summary-cards-container')
    ])

def create_info_table(rows):
    """情報テーブルを作成するヘルパー関数"""
    return html.Table([
        html.Tr([
            html.Td(label, className='info-label'), 
            html.Td(value, className='info-value')
        ]) for label, value in rows
    ], className='info-table')

def create_service_table(service_data):
    """サービス統計テーブルを作成するヘルパー関数（シンプル版）"""
    if not service_data:
        return html.P("サービス情報がありません")
    
    # 総行数を計算
    total_files = sum(svc['files'] for svc in service_data)
    total_lines = sum(svc['lines'] for svc in service_data)
    total_code_lines = sum(svc['code_lines'] for svc in service_data)
    
    header = html.Tr([
        html.Th("サービス名"),
        html.Th("ファイル数"),
        html.Th("総行数"),
        html.Th("コード行数"),
        html.Th("クローン率")
    ])
    
    rows = []
    for svc in service_data:
        rows.append(html.Tr([
            html.Td(svc['name']),
            html.Td(f"{svc['files']:,}"),
            html.Td(f"{svc['lines']:,}"),
            html.Td(f"{svc['code_lines']:,}"),
            html.Td(f"{svc['clone_ratio']:.1f}%")
        ]))
    
    # 合計行を追加
    rows.append(html.Tr([
        html.Td("合計", style={'fontWeight': 'bold'}),
        html.Td(f"{total_files:,}", style={'fontWeight': 'bold'}),
        html.Td(f"{total_lines:,}", style={'fontWeight': 'bold'}),
        html.Td(f"{total_code_lines:,}", style={'fontWeight': 'bold'}),
        html.Td("-", style={'fontWeight': 'bold'})
    ], style={'borderTop': '2px solid #ddd'}))
    
    return html.Table([header] + rows, style={
        'width': '100%',
        'borderCollapse': 'collapse',
        'fontSize': '14px'
    }, className='simple-service-table')


def create_project_clone_ratio_display(project_name: str) -> html.Div:
    """
    プロジェクト全体のクローン率を表示するコンポーネントを作成する。
    """
    try:
        from visualize.clone_analytics import calculate_project_average_clone_ratio
        
        clone_ratio = calculate_project_average_clone_ratio(project_name)
        
        return html.Div([
            html.H3("プロジェクト全体のクローン率", className='clone-ratio-title'),
            html.Div([
                html.Span(f"{clone_ratio:.2f}%", className='clone-ratio-value'),
                html.Span("のコードがクローンです", className='clone-ratio-description')
            ], className='clone-ratio-container')
        ], className='project-clone-ratio-section')
        
    except Exception as e:
        logger.error("Error calculating project clone ratio: %s", e)
        return html.Div([
            html.H3("プロジェクト全体のクローン率", className='clone-ratio-title'),
            html.Div([
                html.Span("計算できませんでした", className='clone-ratio-error')
            ], className='clone-ratio-container')
        ], className='project-clone-ratio-section')

def build_clone_details_view(row, project, df, file_ranges):
    """クリックされたクローンの詳細な比較ビューを生成する"""
    # この関数は単一クローン表示に特化
    return build_clone_details_view_single(row, project)

def build_clone_details_view_single(row, project):
    """単一クローンの詳細ビューを生成する"""
    file_x, file_y = row.get('file_path_x'), row.get('file_path_y')
    sx, ex = int(row.get('start_line_x', 0)), int(row.get('end_line_x', 0))
    sy, ey = int(row.get('start_line_y', 0)), int(row.get('end_line_y', 0))

    snippet_x_lines = get_local_snippet(project, file_x, sx, ex, context=0).splitlines()
    snippet_y_lines = get_local_snippet(project, file_y, sy, ey, context=0).splitlines()
    
    code_x_for_copy = "\n".join([re.sub(r'^[ >]\s*\d+:\s*', '', line) for line in snippet_x_lines])
    code_y_for_copy = "\n".join([re.sub(r'^[ >]\s*\d+:\s*', '', line) for line in snippet_y_lines])

    # 行番号を除いた純粋なコード内容で比較
    code_x_lines = [re.sub(r'^[ >]\s*\d+:\s*', '', line) for line in snippet_x_lines]
    code_y_lines = [re.sub(r'^[ >]\s*\d+:\s*', '', line) for line in snippet_y_lines]
    sm = difflib.SequenceMatcher(None, code_x_lines, code_y_lines)
    rows_x, rows_y = [], []
    
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        # 表示用には元の行番号付きの行を使用
        block_x, block_y = snippet_x_lines[i1:i2], snippet_y_lines[j1:j2]
        
        is_diff = tag == 'equal'  # 完全一致の場合に背景色を付ける
        
        for line in block_x:
            rows_x.append(_diff_pane(line, is_diff))
            
        for line in block_y:
            rows_y.append(_diff_pane(line, is_diff))

    return html.Div([
        # ヘッダーやメタ情報は各ペイン内に移動させるため、トップレベルはシンプルに
        html.Div([
            # Left Pane (Pane X)
            html.Div([
                _file_header(file_x, row.get('service_x', ''), project, sx, ex, row.get('file_id_x', 'N/A')),
                html.Div(_code_pane(rows_x, code_x_for_copy, "X", file_x, project, sx, ex), style={'flex': '1', 'overflow': 'hidden'})
            ], className='split-pane', style={'flex': '0 0 50%'}), # Initial 50% width
            
            # Gutter (Splitter)
            html.Div(className='split-gutter', title="Drag to resize"),
            
            # Right Pane (Pane Y)
            html.Div([
                _file_header(file_y, row.get('service_y', ''), project, sy, ey, row.get('file_id_y', 'N/A')),
                html.Div(_code_pane(rows_y, code_y_for_copy, "Y", file_y, project, sy, ey), style={'flex': '1', 'overflow': 'hidden'})
            ], className='split-pane', style={'flex': '1'}) # Takes remaining space
            
        ], className='split-container')
    ])


def _file_header(file_path, service, project, start_line, end_line, file_id):
    """ファイルヘッダーコンポーネント (VS Code Tab風)"""
    # ファイルタイプ判定
    ftype = get_file_type(file_path)
    
    # タイプごとのスタイル定義（テキスト色のみ）
    type_styles = {
        'logic': {'color': '#0366d6', 'borderColor': '#0366d6'}, # Blue
        'test': {'color': '#28a745', 'borderColor': '#28a745'},  # Green
        'data': {'color': '#d73a49', 'borderColor': '#d73a49'},  # Red
        'config': {'color': '#6a737d', 'borderColor': '#6a737d'}, # Gray
    }
    t_style = type_styles.get(ftype, {'color': '#586069', 'borderColor': '#e1e4e8'})
    
    # ファイル名だけ抽出
    filename = file_path.split('/')[-1] if file_path else 'Unknown'
    # ディレクトリパス
    dir_path = os.path.dirname(file_path) if file_path else ''

    # GitHub URL
    github_url = generate_github_file_url(project, file_path, start_line, end_line)

    return html.Div([
        # 左側: タイプバッジ(テキスト), ファイル名, パス
        html.Div([
            html.Span(ftype.upper(), style={
                'color': t_style['color'], 
                'fontSize': '10px', 
                'fontWeight': 'bold',
                'border': f"1px solid {t_style['borderColor']}", 
                'padding': '1px 4px', 
                'borderRadius': '3px',
                'marginRight': '8px'
            }),
            html.Span(filename, title=file_path, style={'fontWeight': '600', 'fontSize': '13px', 'marginRight': '8px', 'color': '#24292e'}),
            html.Span(dir_path, title=file_path, style={'color': '#6a737d', 'fontSize': '11px', 'fontFamily': 'monospace', 'overflow': 'hidden', 'textOverflow': 'ellipsis'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'overflow': 'hidden', 'whiteSpace': 'nowrap', 'flex': '1'}),
        
        # 右側: サービス名, File ID, Actions
        html.Div([
            html.Span([html.B("Svc: "), service], style={'fontSize': '11px', 'color': '#586069', 'marginRight': '10px'}),
            html.Span([html.B("ID: "), str(file_id)], style={'fontSize': '11px', 'color': '#586069', 'marginRight': '10px'}),
             html.A("GitHub ↗", href=github_url, target="_blank", style={'fontSize': '11px', 'color': '#0366d6', 'textDecoration': 'none'}) if github_url else None
        ], style={'display': 'flex', 'alignItems': 'center', 'flexShrink': '0'})
    ], style={
        'display': 'flex',
        'justifyContent': 'space-between',
        'alignItems': 'center',
        'padding': '8px 12px',
        'borderBottom': '1px solid #e1e4e8',
        'backgroundColor': '#f6f8fa',
        'height': '36px',
        'boxSizing': 'border-box',
        'borderTopLeftRadius': '6px',
        'borderTopRightRadius': '6px'
    })


def _code_pane(rows, code_for_copy, suffix, file_path, project, start_line, end_line):
    # ファイル全体の内容を読み込み
    from .utils import get_file_content
    full_content = get_file_content(project, file_path, start_line, end_line)
    
    # コード片部分 (dcc.Clipboardはヘッダーに移動してもいいが、一旦ここ)
    # オーバーレイコピーボタンのデザイン調整
    code_snippet = html.Div([
        dcc.Clipboard(content=code_for_copy, className="copy-button", title=f"Copy code {suffix}", style={'position':'absolute', 'top':'5px', 'right':'5px', 'zIndex':'10'}),
        html.Div(rows, className='code-pane-content', style={'padding': '15px'})
    ], className='code-pane', style={'position': 'relative', 'backgroundColor': '#fff', 'borderBottom': '1px solid #eee'})
    
    # ファイル全体部分 (高さ制限を撤廃し、自然に展開)
    full_file_section = html.Div([
        html.Div([
             html.Span("📄 Full Source Code", style={'fontWeight':'600', 'color':'#444', 'fontSize': '13px'}),
        ], style={
            'padding':'10px 15px', 
            'background':'#f8f9fa', 
            'borderBottom':'1px solid #e1e4e8',
            'display': 'flex',
            'alignItems': 'center',
            'justifyContent': 'space-between'
        }),
        
        dcc.Markdown(full_content, className="full-code-markdown", style={
            'padding':'15px', 
            'fontSize':'12px', 
            'lineHeight': '1.5',
            'fontFamily': "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"
        })
    ], className='full-file-content', style={'borderTop': 'none', 'height': '70vh', 'overflowY': 'auto', 'display': 'block'}) 
    
    return html.Div([
        html.Div("🔍 Matched Snippet", style={'fontSize': '11px', 'fontWeight': 'bold', 'color': '#888', 'textTransform': 'uppercase', 'padding': '10px 15px 5px', 'letterSpacing': '0.5px'}),
        code_snippet,
        full_file_section
    ], style={'backgroundColor': 'white', 'display': 'flex', 'flexDirection': 'column'})

def _diff_pane(line, is_diff):
    # utils.py generates: f"{prefix}{i+1:5d}: {lines[i]}"
    # old regex: r'([ >])\s*(\d+):\s*(.*)' <- \s* ate leading spaces of code
    # new regex preserves the content after the single space separator
    match = re.match(r'([ >])\s*(\d+): (.*)', line)
    if not match:
        # Fallback for empty lines or unexpected format (try matching without trailing content)
        match = re.match(r'([ >])\s*(\d+):(.*)', line)
        
    if not match:
        # Completely failed to match format, return as simple line
        return html.Div(line, className='diff-line', style={'whiteSpace': 'pre'})
    
    prefix, ln, text = match.groups()
    return html.Div([
        html.Span(ln, className='line-num', **({'data-prefix': prefix} if prefix != ' ' else {})),
        html.Span(text)
    ], className=f"diff-line {'diff' if is_diff else ''}")

def _legend_chip(label, color):
    return html.Div(label, style={'background':color, 'border':'1px solid #ddd', 'padding':'2px 6px', 'borderRadius':'3px', 'fontSize':'11px'})

def create_ide_layout(available_projects, available_languages, default_project, initial_fig, initial_summary):
    """IDE風レイアウトを作成する (index.html 風デザイン + 英語/日本語切替対応)"""
    
    # Project Selector
    project_selector = dcc.Dropdown(
        id='project-selector',
        options=available_projects,
        value=default_project,
        placeholder="Select Project",
        style={'width': '400px'},
        clearable=False
    )
    
    # View Switcher (Tabs)
    view_switcher = html.Div([
        html.Button("Scatter Plot", id="btn-view-scatter", className="view-btn active", n_clicks=0,
                     **{"data-i18n": "btnScatter"}),
        html.Button("Explorer", id="btn-view-explorer", className="view-btn", n_clicks=0,
                     **{"data-i18n": "btnExplorer"}),
        html.Button("Statistics", id="btn-view-stats", className="view-btn", n_clicks=0,
                     **{"data-i18n": "btnStats"}),
    ], className="view-switcher", style={'marginLeft': '20px'})

    # Language Selector (index.html 風)
    lang_selector = html.Div([
        html.Span("Language", id="vis-lang-label", style={
            'fontSize': '0.85rem', 'color': '#777',
        }, **{"data-i18n": "langLabel"}),
        dcc.Dropdown(
            id='vis-lang-select',
            options=[
                {'label': 'English', 'value': 'en'},
                {'label': '日本語', 'value': 'ja'},
            ],
            value='en',
            clearable=False,
            searchable=False,
            style={'width': '110px', 'fontSize': '0.85rem'},
        ),
    ], className="lang-bar", style={
        'display': 'flex', 'alignItems': 'center', 'gap': '8px',
        'marginLeft': 'auto', 'flexShrink': '0',
    })

    # Back to Settings link
    back_link = html.A(
        "Back to Settings",
        href="/",
        id="back-to-settings-link",
        className="btn-back",
        **{"data-i18n": "backToSettings"},
        style={
            'fontSize': '0.85rem', 'color': 'var(--primary, #f5a623)',
            'textDecoration': 'none', 'fontWeight': '600',
            'marginRight': '16px', 'whiteSpace': 'nowrap',
        },
    )

    # Header
    header = html.Div([
        html.Div("MSCCA Tools - Clone Explorer", style={
            'fontWeight': 'bold', 'color': 'var(--primary, #f5a623)',
            'fontSize': '1rem', 'whiteSpace': 'nowrap',
        }, **{"data-i18n": "headerTitle"}),
        html.Div([
            project_selector,
            view_switcher,
            back_link,
            lang_selector,
        ], className="header-controls")
    ], className="ide-header")

    # Sidebar
    sidebar = html.Div([
        html.Div([
            html.Div("EXPLORER", className="sidebar-header",
                      **{"data-i18n": "sidebarExplorer"}),
            html.Div(id="file-tree-container", className="sidebar-tree")
        ], className="sidebar-section", style={'flex': '2', 'borderBottom': '1px solid #e0e0e0'}),
        html.Div([
            html.Div(id="drag-handle", className="sidebar-resizer"),
            html.Div("CLONE OUTLINE", className="sidebar-header",
                      **{"data-i18n": "sidebarCloneOutline"}),
            html.Div(id="clone-list-container", className="sidebar-tree", style={'flex': '1'})
        ], className="sidebar-section", style={'flex': '1', 'display': 'flex', 'flexDirection': 'column'})
    ], className="ide-sidebar")

    # Main Area
    main_content = html.Div([
        # Editor Header (Breadcrumbs etc)
        html.Div(id="editor-header", className="editor-header",
                 children=html.Span("Select a file to view",
                                    **{"data-i18n": "editorPlaceholder"})),
        
        # Editor Content
        html.Div(id="editor-content", className="editor-content", children=[
            html.Div(
                html.Span("Select a file from the explorer to view its content.",
                           **{"data-i18n": "emptyState"}),
                id="empty-state-message",
                style={'padding': '20px', 'color': '#777', 'textAlign': 'center', 'marginTop': '50px'},
            )
        ], style={'padding': '0', 'height': '100%', 'overflow': 'hidden'})
    ], className="ide-content")

    # Scatter Plot Overlay (Initially Hidden)
    scatter_overlay = html.Div([
        # Filter Section
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.Label("Detection Method:", style={'fontSize': '12px', 'fontWeight': 'bold', 'color': '#555'},
                               **{"data-i18n": "filterDetection"}),
                    dbc.RadioItems(
                        id='detection-method-radio',
                        options=[
                            {'label': 'No-Import', 'value': 'import'},
                            {'label': 'All', 'value': 'all'},
                            {'label': 'TKS', 'value': 'tks'},
                            {'label': 'RNR', 'value': 'rnr'}
                        ],
                        value='import',
                        inline=True,
                        style={'fontSize': '13px'},
                        labelStyle={'marginRight': '15px'}
                    ),
                ], width="auto", style={'marginRight': '30px'}),

                dbc.Col([
                    html.Label("Co-modification:", style={'fontSize': '12px', 'fontWeight': 'bold', 'color': '#555'},
                               **{"data-i18n": "filterComod"}),
                    dbc.RadioItems(
                        id='comodification-filter',
                        options=[
                            {'label': 'All', 'value': 'all'},
                            {'label': 'Yes', 'value': 'yes'},
                            {'label': 'No', 'value': 'no'}
                        ],
                        value='all',
                        inline=True,
                        style={'fontSize': '13px'},
                        labelStyle={'marginRight': '15px'}
                    ),
                ], width="auto", style={'marginRight': '30px'}),

                dbc.Col([
                    html.Label("Scope:", style={'fontSize': '12px', 'fontWeight': 'bold', 'color': '#555'},
                               **{"data-i18n": "filterScope"}),
                    dbc.RadioItems(
                        id='service-scope-filter',
                        options=[
                            {'label': 'All', 'value': 'all'},
                            {'label': 'Within', 'value': 'within'},
                            {'label': 'Cross', 'value': 'cross'}
                        ],
                        value='all',
                        inline=True,
                        style={'fontSize': '13px'},
                        labelStyle={'marginRight': '15px'}
                    ),
                ], width="auto"),
            ], className="mb-2"),

            # Code Type Buttons Row
            html.Div([
                html.Label("Code Type:", style={'fontSize': '12px', 'fontWeight': 'bold', 'color': '#555', 'marginBottom': '4px', 'display': 'block'},
                           **{"data-i18n": "filterCodeType"}),
                html.Div(id='code-type-buttons-container', className='code-type-buttons', style={'display': 'flex', 'gap': '8px', 'flexWrap': 'wrap'}),
                dcc.Store(id='code-type-store', data='all'), # Logic/Data/Test etc.
            ], style={'marginTop': '10px'}),

            # Clone ID Row (collapsed if not needed, or right aligned)
            html.Div([
                 html.Label("Clone ID search:", style={'fontSize': '12px', 'fontWeight': 'bold', 'color': '#555', 'marginRight': '8px'},
                            **{"data-i18n": "filterCloneId"}),
                 dcc.Input(
                    id='clone-id-filter',
                    type='text',
                    placeholder="Input Clone ID",
                    debounce=True, # Search on Enter or loss of focus
                    style={
                        'width': '220px', 
                        'height': '36px', # Match standard dropdown height
                        'display': 'inline-block', 
                        'fontSize': '13px', 
                        'fontFamily': 'inherit', # Use standard font
                        'padding': '0 10px',
                        'marginRight': '20px',
                        'border': '1px solid #ccc',
                        'borderRadius': '4px',
                        'verticalAlign': 'middle', # Align with label
                        'boxSizing': 'border-box'
                    }
                ),
                
                # Cross Service Filter
                html.Label("Many Services:", style={'fontSize': '12px', 'fontWeight': 'bold', 'color': '#555', 'marginRight': '8px'},
                           **{"data-i18n": "filterManyServices"}),
                dcc.Dropdown(
                    id='cross-service-filter',
                    options=[{'label': 'All', 'value': 'all'}],
                    value='all',
                    placeholder="Select Clone ID (Many Services)",
                    clearable=True,
                    style={'width': '450px', 'display': 'inline-block', 'verticalAlign': 'middle', 'fontSize': '13px'}
                ),
            ], style={'marginTop': '10px', 'borderTop': '1px solid #eee', 'paddingTop': '8px', 'display': 'flex', 'alignItems': 'center'}),

        ], style={'padding': '15px', 'borderBottom': '1px solid #ddd', 'background': '#f8f9fa'}),
        
        # Main Content Scrollable Area
        html.Div([
            # Stats Header
            html.Div(id='scatter-stats-header', style={'padding': '5px 15px', 'borderBottom': '1px solid #eee', 'backgroundColor': '#fff', 'minHeight': '30px'}),
            
            # Graph
            html.Div([
                dcc.Loading(
                    id="loading-scatter",
                    type="circle",
                    children=[
                        dcc.Graph(
                            id='scatter-plot',
                            figure=initial_fig,
                            style={'height': '125vh', 'minHeight': '500px'}, # Fixed minimum height
                            config={'responsive': True} 
                        )
                    ]
                )
            ], style={'padding': '10px'}),

            # Clone Details Panel (Below Scatter Plot, Natural Flow)
            html.Div([
                html.Div(id='clone-selector-container', style={'marginBottom': '10px'}),
                html.Div(id='clone-details-table', children=[
                    html.P("Click a point on the graph to view clone details and code comparison here.",
                           **{"data-i18n": "scatterClickHint"})
                ])
            ], style={'padding': '20px', 'borderTop': '2px solid #ddd', 'backgroundColor': '#fff'})
            
         ], className="graph-container"),
         
    ], id="scatter-container", className="scatter-container-fullscreen active", style={'padding': '0', 'overflowY': 'auto'})

    # Statistics View Container (Initially Hidden)
    stats_container = html.Div([
        html.Div(initial_summary, id="project-summary-container", style={'padding':'20px'})
    ], id="stats-container", className="stats-container-fullscreen", style={'padding': '0', 'overflowY': 'auto'})

    # Stores
    stores = html.Div([
         dcc.Store(id='file-tree-data-store'),  # Tree structure data
         dcc.Store(id='selected-file-store'),    # Currently selected file path
         dcc.Store(id='clone-data-store'),       # Clone data for current project
         dcc.Store(id='lang-store', data='en'),  # UI language (en / ja)
         html.Div(id='i18n-dummy', style={'display': 'none'}),  # clientside callback output
    ])

    return html.Div([
        header,
        html.Div([
            sidebar,
            main_content
        ], id="ide-main-container", className="ide-main"),
        scatter_overlay,
        stats_container,
        stores
    ], className="ide-container")

def create_file_tree_component(tree_data, level=0):
    """
    再帰的にファイルツリーコンポーネントを生成する
    tree_data: build_file_tree_dataで生成された辞書
    """
    items = []
    # フォルダとファイルを分離してソート
    folders = sorted([k for k, v in tree_data.items() if v != '__FILE__'])
    files = sorted([k for k, v in tree_data.items() if v == '__FILE__'])
    
    # フォルダ
    for name in folders:
        # 子要素の生成
        children = create_file_tree_component(tree_data[name], level + 1)
        
        # Details/Summaryでフォルダ表現
        item = html.Details([
            html.Summary([
                html.Span("📂", className="tree-item-icon"),
                html.Span(name, className="tree-item-label")
            ], className="tree-item"),
            html.Div(children, style={'paddingLeft': '10px'})
        ])
        items.append(item)
        
    # ファイル
    for name in files:
        # パスの構築はコールバック側でやるのが難しいので、IDに埋め込むなどの工夫が必要だが
        # ここでは簡易的にファイル名を表示し、パスの特定は親コンポーネントの構造に依存するか
        # クライアントサイドコールバックでパスを再構築する
        # とりあえずdata属性にパスを持たせることは標準ではできないので、
        # IDを工夫する: "file-node-{path}" (パス中の/はエスケープが必要かも)
        # 簡易実装として、ここでのパス構築は省略し、callbackで解決する前提とする
        
        item = html.Div([
            html.Span("📄", className="tree-item-icon"),
            html.Span(name, className="tree-item-label")
        ], className="tree-item file-node", id={'type': 'file-node', 'index': name}) 
        # IDだけではパスが一意にならないので実運用ではフルパスが必要
        items.append(item)
        
    return items

def create_clone_list_component(clones):
    """
    クローンリストコンポーネントを生成する
    clones: 辞書またはDfのリスト format [{'id': 1, 'partner': 'xxx', 'similarity': 0.8}, ...]
    """
    if not clones:
        return html.Div("No clones found in this file.", style={'padding': '10px', 'color': '#999'})
        
    items = []
    for clone in clones:
        item = html.Div([
            html.Div([
                html.Span(f"Clone #{clone['clone_id']}", className="clone-id"),
                html.Span(f"Line {clone['start_line']}-{clone['end_line']}", style={'fontSize': '11px', 'color': '#888'})
            ], className="clone-list-info"),
            html.Div(f"vs {clone['partner_path']}", className="clone-file"),
            html.Div(f"Lines {clone['partner_start']}-{clone['partner_end']}", style={'fontSize': '11px', 'color': '#888', 'textAlign': 'right'})
        ], className="clone-list-item", id={'type': 'clone-item', 'index': str(clone['clone_id'])})
        items.append(item)
        
    return items

def create_code_editor_view(code_content, file_path, clones=None, start_line=1):
    """
    コードエディタビューを生成する
    code_content: ファイルの中身
    clones: ハイライトすべきクローン情報のリスト
    """
    lines = code_content.splitlines()
    line_elements = []
    code_elements = []
    
    # マーカーの生成（ハイライト）
    markers = []
    if clones:
        for clone in clones:
            # 1-based index to 0-based index and relative pixel calculation is hard in pure CSS
            # ここでは単純に行背景色を変えるためのクラスを付与する方式はHTML構造上難しいので
            # 行ごとに要素を生成する
            pass 

    for i, line in enumerate(lines):
        ln = i + start_line
        
        # 行に関連するクローンがあるかチェック
        is_cloned = False
        if clones:
            for clone in clones:
                 if clone['start_line'] <= ln <= clone['end_line']:
                     is_cloned = True
                     break
        
        # Line Number
        line_elements.append(html.Div(str(ln), className="code-line"))
        
        # Code Line
        style = {}
        if is_cloned:
            style['backgroundColor'] = 'rgba(144, 238, 144, 0.1)'
            
        code_elements.append(html.Div(line if line else ' ', className="code-line", style=style))

    return html.Div([
        html.Div(line_elements, className="line-numbers"),
        html.Div(code_elements, className="code-lines")
    ], className="code-container")

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
    method = filters.get('method')
    if method and method != 'all':
        label = DetectionMethod.LABELS.get(method, method)
        badges.append(_header_badge("Method", label, "#e1f5fe", "#0277bd"))
        
    # Code Type
    ctype = filters.get('code_type')
    if ctype and ctype != 'all':
        label = ctype.title() # e.g. Logic, Data
        badges.append(_header_badge("Type", label, "#e8f5e9", "#2e7d32"))

    # Co-modification
    comod = filters.get('comodified')
    if comod and comod != 'all':
        label = "Yes" if comod == 'true' else "No"
        badge_bg = "#fff3e0" if comod == 'true' else "#ffebee"
        badge_col = "#ef6c00" if comod == 'true' else "#c62828"
        badges.append(_header_badge("Co-mod", label, badge_bg, badge_col))

    # Service Scope
    scope = filters.get('scope')
    if scope and scope != 'all':
        label = "Within Svc" if scope == 'within' else "Cross Svc"
        badges.append(_header_badge("Scope", label, "#e0f7fa", "#006064"))

    # Clone ID
    cid = filters.get('clone_id')
    if cid and cid != 'all':
        # Clean up clone id display
        label = str(cid).replace('clone_', '')
        badges.append(_header_badge("ID", label, "#f3e5f5", "#7b1fa2"))
        
    # Statistics
    stats_text = [
        html.Span([html.B(f"{current:,}"), f" / {total:,} pairs ({ratio:.1f}%)"], style={'marginRight': '15px'}),
    ]
    
    # Add Similarity Stats if available
    if 'similarity' in df_display.columns and not df_display.empty:
        avg_sim = df_display['similarity'].mean()
        stats_text.append(html.Span([html.B("Avg Sim: "), f"{avg_sim:.2f}"]))

    return html.Div([
        html.Div(badges if badges else [html.Span("All Data", style={'fontSize':'12px', 'color':'#777'})], style={'display': 'flex', 'gap': '8px', 'alignItems': 'center'}),
        html.Div(stats_text, style={'fontSize': '13px', 'color': '#555'})
    ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'width': '100%'})

def _header_badge(key, value, bg_color, text_color):
    return html.Span([
        html.Span(f"{key}: ", style={'fontWeight': 'bold', 'opacity': '0.7'}),
        html.Span(value)
    ], style={
        'backgroundColor': bg_color,
        'color': text_color,
        'padding': '2px 8px',
        'borderRadius': '12px',
        'fontSize': '11px',
        'border': f'1px solid {text_color}40'
    })

def _create_pie_chart(data, title):
    if not data:
        return go.Figure().update_layout(title=title, annotations=[dict(text="No Data", showarrow=False)])
    
    labels = [k.capitalize() for k in data.keys()]
    values = list(data.values())
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, textinfo='label+percent', showlegend=False)])
    fig.update_layout(title_text=title, margin=dict(t=40, b=10, l=10, r=10), height=250)
    return fig

def _create_histogram(data, title):
    if not data:
        return go.Figure().update_layout(title=title, annotations=[dict(text="No Data", showarrow=False)])
    
    fig = go.Figure(data=[go.Histogram(x=data, nbinsx=20, marker_color='#6c757d')])
    fig.update_layout(
        title_text=title, 
        margin=dict(t=40, b=10, l=10, r=10), 
        height=250
    )
    return fig
