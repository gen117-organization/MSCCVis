import logging

logger = logging.getLogger(__name__)
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import plotly.colors as pc

def extract_service_relative_path_vectorized(file_paths, service_names):
    """no_importsデータから相対パスを抽出（ベクトル化で高速化）"""
    result = []
    for file_path, service_name in zip(file_paths, service_names):
        if not file_path or not service_name:
            result.append(file_path or "")
            continue
        
        # サービス名でパスを分割し、サービス名以降の部分を取得
        # no_importsデータの場合、パスは /absolute/path/to/service-name/src/... の形式
        service_short_name = service_name.split('/')[-1]  # 例: "certificate-generator"
        if service_short_name in file_path:
            parts = file_path.split(service_short_name, 1)
            if len(parts) > 1:
                relative_path = parts[1].lstrip('/')
                # さらに短くするため、src以降のパスのみを取得
                if '/src/' in relative_path:
                    src_parts = relative_path.split('/src/', 1)
                    if len(src_parts) > 1:
                        result.append('src/' + src_parts[1])
                        continue
                result.append(relative_path if relative_path else "")
                continue
        
        # フォールバック: ファイル名のみ
        result.append(file_path.split('/')[-1])
    return result

def add_service_boundaries(fig, file_ranges):
    """サービス境界に点線を追加"""
    boundaries = set()
    for ranges in file_ranges.values():
        for start, end in ranges:
            if start > 0: boundaries.add(start - 0.5)
            boundaries.add(end + 0.5)
    
    for boundary in sorted(boundaries):
        fig.add_vline(x=boundary, line_dash="dash", line_color="gray", opacity=0.8)
        fig.add_hline(y=boundary, line_dash="dash", line_color="gray", opacity=0.8)

def add_service_labels(fig, file_ranges):
    """サービス名のラベルを追加（スタッガード配置対応）"""
    logger.debug("add_service_labels called with file_ranges: %s", file_ranges)
    
    # サービス数が一定以上の場合はスタッガード（千鳥）配置にする
    num_services = len(file_ranges)
    use_staggered = num_services >= 15
    
    # サービスを開始位置順にソートして処理（確実に隣接順にするため）
    # rangesはリストだが、サービスごとの最小開始位置でソート
    sorted_services = sorted(
        file_ranges.items(), 
        key=lambda item: min(r[0] for r in item[1]) if item[1] else float('inf')
    )
    
    for i, (service_name, ranges) in enumerate(sorted_services):
        # スタッガード配置用のオフセット計算
        if use_staggered:
            # 偶数/奇数でラベル位置を変える
            is_odd = i % 2 == 1
            x_label_y_pos = -0.20 if is_odd else -0.15
            y_label_x_pos = -0.08 if is_odd else -0.05
        else:
            x_label_y_pos = -0.15
            y_label_x_pos = -0.05

        logger.debug("Processing service %s with ranges %s", service_name, ranges)
        for start, end in ranges:
            center = (start + end) / 2
            text = f"{service_name.split('/')[-1]}<br>[{start}-{end}]"
            # X軸ラベル（下側）- 45度時計回りに回転、位置を下に移動
            fig.add_annotation(x=center, y=x_label_y_pos, xref="x", yref="paper", text=text, showarrow=False, font=dict(size=10), xanchor="center", textangle=90)
            # Y軸ラベル（左側）
            fig.add_annotation(x=y_label_x_pos, y=center, xref="paper", yref="y", text=text, showarrow=False, font=dict(size=10), textangle=0, xanchor="right", yanchor="middle")

def create_scatter_plot(df, file_ranges, project_name, language, static_mode=False):
    """データフレームから散布図を作成する（ヒートマップ風カラーマップ + マーカー形状区別）"""
    logger.debug("create_scatter_plot called with file_ranges: %s, static_mode=%s", file_ranges, static_mode)
    if df is None or df.empty:
        return go.Figure().update_layout(title="No data available")

    # データのコピーを作成（元データを変更しない）
    df = df.copy()

    # 必須列の補完（dest/scatter フォーマット対応）
    if 'coord_pair' not in df.columns and {'file_id_x', 'file_id_y'} <= set(df.columns):
        df['coord_pair'] = df['file_id_y'].astype(str) + '_' + df['file_id_x'].astype(str)

    if 'clone_key' not in df.columns:
        clone_key_parts = [
            df.get('clone_id', '').astype(str),
            df.get('file_path_x', '').astype(str).str.split('/').str[-1],
            df.get('start_line_x', '').astype(str) + '-' + df.get('end_line_x', '').astype(str),
            df.get('file_path_y', '').astype(str).str.split('/').str[-1],
            df.get('start_line_y', '').astype(str) + '-' + df.get('end_line_y', '').astype(str)
        ]
        df['clone_key'] = clone_key_parts[0] + '|' + clone_key_parts[1] + '|' + clone_key_parts[2] + '|' + clone_key_parts[3] + '|' + clone_key_parts[4]
    
    # 高速化：ベクトル化された処理
    logger.info("Processing data for visualization...")
    
    # 重複除去: 同じcoord_pair + clone_id + file情報の組み合わせを除去（高速化）
    clone_key_parts = [
        df['clone_id'].astype(str),
        df['file_path_x'].str.split('/').str[-1].fillna(''),
        df['start_line_x'].astype(str) + '-' + df['end_line_x'].astype(str),
        df['file_path_y'].str.split('/').str[-1].fillna(''),
        df['start_line_y'].astype(str) + '-' + df['end_line_y'].astype(str)
    ]
    df['clone_key'] = clone_key_parts[0] + '|' + clone_key_parts[1] + '|' + clone_key_parts[2] + '|' + clone_key_parts[3] + '|' + clone_key_parts[4]
    
    # 重複除去後のユニーククローンのみでoverlap_countを計算（高速化）
    df_unique = df.drop_duplicates(subset=['coord_pair', 'clone_key'])
    coord_counts = df_unique['coord_pair'].value_counts()
    df['filtered_overlap_count'] = df['coord_pair'].map(coord_counts)
    
    # サービス相対パスを計算（ベクトル化で高速化）
    logger.debug("Before extracting relative paths - sample file_path_x: %s", df['file_path_x'].iloc[0] if not df.empty else 'No data')
    logger.debug("Before extracting relative paths - sample service_x: %s", df['service_x'].iloc[0] if not df.empty else 'No data')
    df['service_relative_path_x'] = extract_service_relative_path_vectorized(
        df['file_path_x'].values, df['service_x'].values
    )
    df['service_relative_path_y'] = extract_service_relative_path_vectorized(
        df['file_path_y'].values, df['service_y'].values
    )
    logger.debug("After extracting relative paths - sample service_relative_path_x: %s", df['service_relative_path_x'].iloc[0] if not df.empty else 'No data')
    logger.debug("After extracting relative paths - sample service_relative_path_y: %s", df['service_relative_path_y'].iloc[0] if not df.empty else 'No data')
    
    # クローン集中度に基づくカラーマッピング用の値を正規化（高速化）
    max_overlap = df['filtered_overlap_count'].max()
    min_overlap = df['filtered_overlap_count'].min()
    
    # 正規化された値（0-1）を計算（ベクトル化）
    if max_overlap > min_overlap:
        df['normalized_density'] = (df['filtered_overlap_count'] - min_overlap) / (max_overlap - min_overlap)
    else:
        df['normalized_density'] = 0
    
    # ヒートマップ風カラーマップ（ベクトル化で高速化）
    color_map = {
        0: '#0066CC',  # 青
        1: '#00CC66',  # 緑  
        2: '#CCCC00',  # 黄
        3: '#FF6600',  # オレンジ
        4: '#CC0000'   # 赤
    }
    
    # ベクトル化されたカラーマッピング
    color_indices = np.clip((df['normalized_density'] * 5).astype(int), 0, 4)
    df['heatmap_color'] = [color_map[i] for i in color_indices]
    
    logger.info("Creating scatter plot...")
    
    # 空のfigureを作成
    fig = go.Figure()
    
    # データを関係別・検出手法別に分割
    intra_mask = df['relation'] == 'intra'
    inter_mask = df['relation'] == 'inter'
    method_col = 'detection_method' if 'detection_method' in df.columns else 'clone_type'
    tks_mask = df[method_col].astype(str).str.lower() == 'tks'
    ccfsw_mask = ~tks_mask
    
    # 共通のマーカー設定
    marker_base = dict(
        size=5 if static_mode else 8,  # 静的モードでは少し小さく
        line=dict(width=0 if static_mode else 1, color='white'),
        opacity=0.8
    )
    
    # ホバー設定
    # static_modeでもホバーを表示するため hoverinfo='skip' は設定しない
    hover_settings = dict()
    ScatterClass = go.Scattergl if static_mode else go.Scatter

    # サービス内クローン（丸いマーカー）- CCFSW
    if (intra_mask & ccfsw_mask).any():
        intra_data = df[intra_mask & ccfsw_mask]
        marker_settings = marker_base.copy()
        marker_settings.update(dict(symbol='circle', color=intra_data['heatmap_color']))
        
        trace_args = dict(
            x=intra_data['file_id_y'],
            y=intra_data['file_id_x'],
            mode='markers',
            marker=marker_settings,
            name='サービス内 (Normal)',
            showlegend=True
        )
        trace_args.update(hover_settings)
        
        trace_args['customdata'] = list(zip(
            intra_data.index,
            intra_data['clone_id'],
            intra_data['service_x'],
            intra_data['filtered_overlap_count'],
            intra_data['file_id_x'],
            intra_data['file_id_y'],
            intra_data['service_relative_path_x'],
            intra_data['service_relative_path_y'],
            intra_data[method_col]
        ))
        trace_args['hovertemplate'] = '<b>サービス内クローン (Normal)</b><br>' + \
                        'Clone ID: %{customdata[1]}<br>' + \
                        'Overlap Count: %{customdata[3]}<br>' + \
                        'Clone Type: %{customdata[8]}<br>' + \
                        '<br>' + \
                        '<b>X-Axis File:</b><br>' + \
                        'Service: %{customdata[2]}<br>' + \
                        'File: %{customdata[7]} (ID:%{customdata[5]})<br>' + \
                        '<br>' + \
                        '<b>Y-Axis File:</b><br>' + \
                        'Service: %{customdata[2]}<br>' + \
                        'File: %{customdata[6]} (ID:%{customdata[4]})<br>' + \
                        '<extra></extra>'
        
        fig.add_trace(ScatterClass(**trace_args))
    
    # サービス間クローン（四角いマーカー）- CCFSW
    if (inter_mask & ccfsw_mask).any():
        inter_data = df[inter_mask & ccfsw_mask]
        marker_settings = marker_base.copy()
        marker_settings.update(dict(symbol='square', color=inter_data['heatmap_color']))
        
        trace_args = dict(
            x=inter_data['file_id_y'],
            y=inter_data['file_id_x'],
            mode='markers',
            marker=marker_settings,
            name='サービス間 (Normal)',
            showlegend=True
        )
        trace_args.update(hover_settings)
        
        trace_args['customdata'] = list(zip(
            inter_data.index,
            inter_data['clone_id'],
            inter_data['service_x'],
            inter_data['service_y'],
            inter_data['filtered_overlap_count'],
            inter_data['file_id_x'],
            inter_data['file_id_y'],
            inter_data['service_relative_path_x'],
            inter_data['service_relative_path_y'],
            inter_data[method_col]
        ))
        trace_args['hovertemplate'] = '<b>サービス間クローン (Normal)</b><br>' + \
                        'Clone ID: %{customdata[1]}<br>' + \
                        'Overlap Count: %{customdata[4]}<br>' + \
                        'Clone Type: %{customdata[9]}<br>' + \
                        '<br>' + \
                        '<b>X-Axis File:</b><br>' + \
                        'Service: %{customdata[3]}<br>' + \
                        'File: %{customdata[8]} (ID:%{customdata[6]})<br>' + \
                        '<br>' + \
                        '<b>Y-Axis File:</b><br>' + \
                        'Service: %{customdata[2]}<br>' + \
                        'File: %{customdata[7]} (ID:%{customdata[5]})<br>' + \
                        '<extra></extra>'
        
        fig.add_trace(ScatterClass(**trace_args))
    
    # TKSサービス内クローン（丸いマーカー）
    if (intra_mask & tks_mask).any():
        tks_intra_data = df[intra_mask & tks_mask]
        marker_settings = marker_base.copy()
        marker_settings.update(dict(symbol='circle', color=tks_intra_data['heatmap_color']))
        
        trace_args = dict(
            x=tks_intra_data['file_id_y'],
            y=tks_intra_data['file_id_x'],
            mode='markers',
            marker=marker_settings,
            name='サービス内 (TKS)',
            showlegend=True
        )
        trace_args.update(hover_settings)
        
        trace_args['customdata'] = list(zip(
            tks_intra_data.index,
            tks_intra_data['clone_id'],
            tks_intra_data['service_x'],
            tks_intra_data['filtered_overlap_count'],
            tks_intra_data['file_id_x'],
            tks_intra_data['file_id_y'],
            tks_intra_data['service_relative_path_x'],
            tks_intra_data['service_relative_path_y'] if 'service_relative_path_y' in tks_intra_data.columns else tks_intra_data['service_relative_path_x'],
            tks_intra_data[method_col]
        ))
        trace_args['hovertemplate'] = '<b>サービス内クローン (TKS)</b><br>' + \
                        'Clone ID: %{customdata[1]}<br>' + \
                        'Overlap Count: %{customdata[3]}<br>' + \
                        'Clone Type: %{customdata[8]}<br>' + \
                        '<br>' + \
                        '<b>X-Axis File:</b><br>' + \
                        'Service: %{customdata[2]}<br>' + \
                        'File: %{customdata[7]} (ID:%{customdata[5]})<br>' + \
                        '<br>' + \
                        '<b>Y-Axis File:</b><br>' + \
                        'Service: %{customdata[2]}<br>' + \
                        'File: %{customdata[6]} (ID:%{customdata[4]})<br>' + \
                        '<extra></extra>'
        
        fig.add_trace(ScatterClass(**trace_args))
    
    # TKSサービス間クローン（四角いマーカー）
    if (inter_mask & tks_mask).any():
        tks_inter_data = df[inter_mask & tks_mask]
        marker_settings = marker_base.copy()
        marker_settings.update(dict(symbol='square', color=tks_inter_data['heatmap_color']))
        
        trace_args = dict(
            x=tks_inter_data['file_id_y'],
            y=tks_inter_data['file_id_x'],
            mode='markers',
            marker=marker_settings,
            name='サービス間 (TKS)',
            showlegend=True
        )
        trace_args.update(hover_settings)
        
        trace_args['customdata'] = list(zip(
            tks_inter_data.index,
            tks_inter_data['clone_id'],
            tks_inter_data['service_x'],
            tks_inter_data['service_y'] if 'service_y' in tks_inter_data.columns else tks_inter_data['service_x'],
            tks_inter_data['filtered_overlap_count'],
            tks_inter_data['file_id_x'],
            tks_inter_data['file_id_y'],
            tks_inter_data['service_relative_path_x'],
            tks_inter_data['service_relative_path_y'] if 'service_relative_path_y' in tks_inter_data.columns else tks_inter_data['service_relative_path_x'],
            tks_inter_data[method_col]
        ))
        trace_args['hovertemplate'] = '<b>サービス間クローン (TKS)</b><br>' + \
                        'Clone ID: %{customdata[1]}<br>' + \
                        'Overlap Count: %{customdata[4]}<br>' + \
                        'Clone Type: %{customdata[9]}<br>' + \
                        '<br>' + \
                        '<b>X-Axis File:</b><br>' + \
                        'Service: %{customdata[3]}<br>' + \
                        'File: %{customdata[8]} (ID:%{customdata[7]})<br>' + \
                        '<br>' + \
                        '<b>Y-Axis File:</b><br>' + \
                        'Service: %{customdata[2]}<br>' + \
                        'File: %{customdata[7]} (ID:%{customdata[5]})<br>' + \
                        '<extra></extra>'
        
        fig.add_trace(ScatterClass(**trace_args))

    logger.info("Adding service boundaries and labels...")
    add_service_boundaries(fig, file_ranges)
    # add_service_labels(fig, file_ranges) # ホバーで確認できるためラベルは非表示
    
    # カラーバーを追加して集中度の凡例を表示
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        marker=dict(
            colorscale=[
                [0, '#0066CC'],    # 青
                [0.25, '#00CC66'], # 緑
                [0.5, '#CCCC00'],  # 黄
                [0.75, '#FF6600'], # オレンジ
                [1, '#CC0000']     # 赤
            ],
            showscale=True,
            cmin=min_overlap,
            cmax=max_overlap,
            colorbar=dict(
                title=dict(
                    text="クローン集中度<br>(重複数)",
                    side="right"
                ),
                x=1.02
            )
        ),
        showlegend=False,
        hoverinfo='skip'
    ))

    fig.update_layout(
        xaxis_title="", 
        yaxis_title="",
        margin=dict(l=250, r=100, t=150, b=200),
        title=f"{project_name} ({language})",
        width=1200, height=1100, 
        showlegend=False,
        xaxis=dict(
            title=dict(font=dict(color="gray")),
            tickfont=dict(color="gray")
        ),
        yaxis=dict(
            title=dict(font=dict(color="gray")),
            tickfont=dict(color="gray")
        ),
        # プロジェクト変更時の強制更新用
        uirevision=f"{project_name}_{language}_{len(df)}"
    )
    
    logger.info("Scatter plot creation completed.")
    return fig
