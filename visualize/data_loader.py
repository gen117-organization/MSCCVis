import pandas as pd
import os
import glob
import json
import logging
import re
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)

# データキャッシュ用のグローバル変数
_data_cache = {}  # キャッシュをクリア（統一データローダー統合）

# @lru_cache(maxsize=32)  # 一時的に無効化
def load_service_file_ranges_cached(services_json_path: str, language: str):
    """services.json から言語別の file_ranges を取得する（キャッシュ版）"""
    print(f"DEBUG: Loading service ranges from {services_json_path}")  # デバッグ用
    with open(services_json_path, encoding='utf-8') as f:
        data = json.load(f)
    
    # 言語キーの大文字小文字を吸収して検索
    target_lang = (language or '').lower()
    languages_data = data.get('languages', {})
    
    # 完全一致または大文字小文字無視で検索
    lang_section = {}
    if language in languages_data:
        lang_section = languages_data[language]
    else:
        # キーを走査して大文字小文字無視でマッチ
        for key, val in languages_data.items():
            if key.lower() == target_lang:
                lang_section = val
                break
    
    if isinstance(lang_section, dict) and 'file_ranges' in lang_section:
        result = lang_section['file_ranges']
    else:
        result = data.get('file_ranges', {})
    print(f"DEBUG: Loaded service ranges: {result}")  # デバッグ用
    return result

def load_project_summary(summary_path='visualize/project_summary.json'):
    """プロジェクトサマリーを読み込む"""
    if not os.path.exists(summary_path):
        return None
    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading project summary: {e}")
        return None

def load_dashboard_data(scatter_dir='dest/scatter'):
    """ダッシュボード用のデータを読み込む"""
    dashboard_path = os.path.join(scatter_dir, 'dashboard.json')
    if not os.path.exists(dashboard_path):
        return None
    
    try:
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading dashboard data: {e}")
        return None

def get_actual_service_count(project_name: str, language: str):
    """実際のservices.jsonからサービス数を取得する"""
    try:
        services_json_path = f"dest/scatter/{project_name}/services.json"
        file_ranges = load_service_file_ranges_cached(services_json_path, language)
        return len(file_ranges) if file_ranges else 0
    except Exception as e:
        print(f"Warning: Could not get service count for {project_name}: {e}")
        return 0

def get_available_projects_enhanced(language_filter=None):
    """
    プロジェクトサマリーを利用して改善されたプロジェクト一覧を取得
    
    Args:
        language_filter: 特定の言語でフィルター（None=全言語）
    """
    scatter_options = _gather_scatter_projects()
    if scatter_options:
        return scatter_options

    summary = load_project_summary()
    if not summary:
        print("Warning: Project summary not found. Using fallback method.")
        return get_available_projects()
    
    options = []
    
    for project_name, project_data in summary['projects'].items():
        metadata = project_data.get('metadata', {})
        
        for language, lang_data in project_data['languages'].items():
            # 言語フィルターがある場合、指定言語以外をスキップ
            if language_filter and language != language_filter:
                continue
                
            stats = lang_data['stats']
            commit = lang_data.get('commit', 'latest')
            
            # 表示用ラベルの作成
            base_display = f"{project_name} ({language})"
            if commit != 'latest':
                base_display += f", {commit[:7]}"
            
            # 統計情報を表示に追加（実際のサービス数を使用）
            actual_service_count = get_actual_service_count(project_name, language)
            stats_info = []
            if stats.get('total_clones', 0) > 0:
                stats_info.append(f"{stats['total_clones']:,} clones")
            if actual_service_count > 0:
                stats_info.append(f"{actual_service_count} services")
            if metadata.get('stars', 0) > 0:
                stats_info.append(f"⭐{metadata['stars']}")
            
            display = base_display
            if stats_info:
                display += f" - {', '.join(stats_info)}"
            
            value = f"{project_name}|||{commit}|||{language}"
            
            option_data = {
                'label': display,
                'value': value,
                'project_name': project_name,
                'language': language,
                'commit': commit,
                'stats': stats,
                'metadata': metadata,
                'clone_count': stats.get('total_clones', 0)
            }
            options.append(option_data)
    
    if not options:
        print("Warning: No valid projects found in summary. Using fallback method.")
        return get_available_projects()
    
    # 常にクローン数で降順ソート
    options.sort(key=lambda x: x['clone_count'], reverse=True)
    
    # 言語別にグループ化（言語フィルターがない場合のみ）
    if not language_filter:
        grouped_options = []
        current_lang = None
        lang_options = []
        
        # まず言語でソートしてからクローン数でソート
        options.sort(key=lambda x: (x['language'], -x['clone_count']))
        
        for option in options:
            if current_lang != option['language']:
                if lang_options:
                    # 前の言語グループを追加
                    grouped_options.append({
                        'label': f"── {current_lang} ({len(lang_options)} projects) ──",
                        'value': f"HEADER_{current_lang}",
                        'disabled': True
                    })
                    grouped_options.extend(lang_options)
                
                current_lang = option['language']
                lang_options = []
            
            lang_options.append({
                'label': option['label'],
                'value': option['value']
            })
        
        # 最後のグループを追加
        if lang_options:
            grouped_options.append({
                'label': f"── {current_lang} ({len(lang_options)} projects) ──",
                'value': f"HEADER_{current_lang}",
                'disabled': True
            })
            grouped_options.extend(lang_options)
        
        return grouped_options
    
    # 言語フィルターがある場合はグループ化なし
    return [{'label': opt['label'], 'value': opt['value']} for opt in options]

def get_available_languages():
    """利用可能な言語の一覧を取得"""
    summary = load_project_summary()
    if summary:
        languages = set()
        for project_data in summary['projects'].values():
            languages.update(project_data['languages'].keys())
        return sorted(list(languages))

    scatter_options = _gather_scatter_projects()
    if scatter_options:
        langs = {opt['value'].split('|||')[2] for opt in scatter_options}
        return sorted(langs)

    return []

def get_available_projects():
    """利用可能なプロジェクトの一覧を取得する.

    優先順位: dest/scatter -> data/csv -> visualize/csv(legacy).
    """

    options = _gather_scatter_projects()
    if options:
        return options

    options.extend(_gather_project_csv_projects())
    options.extend(_gather_legacy_projects())

    seen = set()
    unique = [opt for opt in options if opt['value'] not in seen and not seen.add(opt['value'])]
    return sorted(unique, key=lambda o: o['label'])


def _gather_scatter_projects():
    base_dir = Path('dest/scatter')
    if not base_dir.exists():
        return []

    pattern = re.compile(r'^(?P<prefix>tks_|import_)?(?P<lang>.+)_scatter(?!_unknown)\.csv$', re.IGNORECASE)
    options = []

    for project_dir in sorted(base_dir.iterdir()):
        csv_dir = project_dir / 'csv'
        if not csv_dir.is_dir():
            continue

        languages = set()
        for csv_path in csv_dir.iterdir():
            if not csv_path.name.endswith('.csv'):
                continue
            match = pattern.match(csv_path.name)
            if not match:
                continue
            languages.add(match.group('lang'))

        for lang in sorted(languages):
            label = f"{project_dir.name} ({lang}, scatter)"
            value = f"{project_dir.name}|||latest|||{lang}"
            options.append({'label': label, 'value': value})

    return sorted(options, key=lambda o: o['label'])


def _gather_project_csv_projects():
    csv_data_folder = Path('data/csv')
    options = []
    if not csv_data_folder.exists():
        return options

    for project_dir in csv_data_folder.iterdir():
        if not project_dir.is_dir():
            continue
        for csv_file in project_dir.glob('*.csv'):
            filename = csv_file.name
            name_parts = filename[:-4].split('_')
            if len(name_parts) != 2:
                continue
            detection_type, language = name_parts
            if detection_type not in ['ccfsw', 'tks']:
                continue
            display = f"{project_dir.name} ({language.upper()}, {detection_type.upper()})"
            value = f"{project_dir.name}|||latest|||{language.upper()}"
            options.append({'label': display, 'value': value})
    return options


def _gather_legacy_projects():
    legacy_csv_folder = Path('visualize/csv')
    options = []
    if not legacy_csv_folder.exists():
        return options

    for csv_file in legacy_csv_folder.glob('*_all.csv'):
        base = csv_file.name[:-8]
        parts = base.split('_')
        if len(parts) < 3:
            continue
        language, commit, project = parts[-1], parts[-2], '_'.join(parts[:-2])
        display = f"{project} ({language.upper()}, LEGACY)"
        value = f"{project}|||{commit}|||{language.upper()}"
        options.append({'label': display, 'value': value})
    return options

@lru_cache(maxsize=32)
def load_full_services_json(services_json_path: str):
    """services.json の全データを読み込む"""
    if not os.path.exists(services_json_path):
        return None
    try:
        with open(services_json_path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading services.json: {e}")
        return None

def load_service_file_ranges(services_json_path: str, language: str):
    """services.json から言語別の file_ranges を取得する（レガシー互換性のため）"""
    return load_service_file_ranges_cached(services_json_path, language)

def file_id_to_service(file_id: int, file_ranges: dict):
    """ファイルIDからサービス名を特定する"""
    for svc, ranges in file_ranges.items():
        for start, end in ranges:
            if start <= file_id <= end:
                return svc
    return 'unknown'

def vectorized_file_id_to_service(file_ids, file_ranges):
    """ベクトル化されたファイルIDからサービス名への変換"""
    services = ['unknown'] * len(file_ids)
    for i, file_id in enumerate(file_ids):
        services[i] = file_id_to_service(file_id, file_ranges)
    return services

def _unified_sources_exist(project_name: str, language: str) -> bool:
    project_csv_dir = f'data/csv/{project_name}'
    return (
        os.path.exists(f'{project_csv_dir}/ccfsw_{language.lower()}.csv') or
        os.path.exists(f'{project_csv_dir}/tks_{language.lower()}.csv')
    )


from .constants import DetectionMethod

def _scatter_sources(project_name: str, language: str):
    base_dir = Path('dest/scatter') / project_name / 'csv'
    if not base_dir.exists():
        return []

    pattern = re.compile(r'^(?P<prefix>tks_|import_)?(?P<lang>.+)_scatter(_unknown)?\.csv$', re.IGNORECASE)
    sources = []
    for csv_path in base_dir.iterdir():
        match = pattern.match(csv_path.name)
        if not match:
            continue
        lang = match.group('lang')
        if lang.lower() != language.lower():
            continue

        prefix = match.group('prefix') or ''
        detection_method = DetectionMethod.from_prefix(prefix)

        # UIでサポートされていないCCFSW (Legacy) は読み込まない
        if detection_method == DetectionMethod.CCFSW:
            continue

        sources.append((csv_path, detection_method))

    return sorted(sources, key=lambda s: s[0].name)


def load_from_scatter_csv(sources, services_json_path: str, cache_key: str, language: str):
    """dest/scatter 出力からクローンデータを読み込む"""
    file_ranges = {}
    if os.path.exists(services_json_path):
        try:
            file_ranges = load_service_file_ranges_cached(services_json_path, language)
        except Exception as exc:
            logger.warning("services.json unreadable, continue without boundaries: path=%s err=%s", services_json_path, exc)
            file_ranges = {}
    else:
        logger.warning("services.json not found, continue without boundaries: path=%s", services_json_path)

    frames = []
    MAX_FILE_SIZE_MB = 2000  # 2000MB制限 (静的モード対応のため緩和)

    for csv_path, detection_method in sources:
        # ファイルサイズチェック
        try:
            file_size_mb = csv_path.stat().st_size / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                logger.warning(f"ファイルサイズが大きすぎます ({file_size_mb:.0f} MB)。このファイルはスキップされます: {csv_path.name}")
                continue
        except Exception as e:
            logger.warning(f"Failed to check file size for {csv_path}: {e}")

        try:
            # メモリ使用量削減のために型を明示的に指定
            dtypes = {
                'clone_id': 'Int64',
                'file_id_x': 'Int64',
                'file_id_y': 'Int64',
                'start_line_x': 'Int64',
                'end_line_x': 'Int64',
                'start_line_y': 'Int64',
                'end_line_y': 'Int64',
                'token_count': 'Int64',
                'clone_type': 'category',
                'relation': 'category',
                'file_type_x': 'category',
                'file_type_y': 'category',
                'service_x': 'string',
                'service_y': 'string',
                'file_path_x': 'string',
                'file_path_y': 'string',
                'comodified': 'boolean'
            }
            df = pd.read_csv(csv_path, dtype=dtypes)
            print(f"DEBUG: Loaded {csv_path.name} with {len(df)} rows. Method: {detection_method}")
        except Exception as exc:
            error_msg = f"scatter CSV 読み込みに失敗: path={csv_path}"
            logger.error(error_msg)
            result = (None, None, error_msg)
            _data_cache[cache_key] = result
            return result

        df['detection_method'] = detection_method
        frames.append(df)

    if not frames:
        print("DEBUG: No frames loaded from scatter sources.")
        result = (None, None, "scatter CSV が見つかりません")
        _data_cache[cache_key] = result
        return result

    df = pd.concat(frames, ignore_index=True)

    # サービス名の欠損補完 (unknown対応)
    if 'service_x' in df.columns:
        df['service_x'] = df['service_x'].fillna('unknown').replace('', 'unknown')
    if 'service_y' in df.columns:
        df['service_y'] = df['service_y'].fillna('unknown').replace('', 'unknown')

    # relationの欠損補完
    if 'relation' in df.columns:
        mask = df['relation'].isna() | (df['relation'] == '')
        if mask.any():
            is_intra = df.loc[mask, 'service_x'] == df.loc[mask, 'service_y']
            df.loc[mask, 'relation'] = is_intra.map({True: 'intra', False: 'inter'})

    if 'coord_pair' not in df.columns and {'file_id_x', 'file_id_y'} <= set(df.columns):
        df['coord_pair'] = df['file_id_y'].astype(str) + '_' + df['file_id_x'].astype(str)

    numeric_cols = [
        'file_id_x', 'file_id_y', 'start_line_x', 'end_line_x', 'start_line_y', 'end_line_y'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')

    if 'clone_id' in df.columns:
        df['clone_id'] = pd.to_numeric(df['clone_id'], errors='coerce').astype('Int64')

    if 'service_x' not in df.columns and 'file_id_x' in df.columns:
        if file_ranges:
            df['service_x'] = vectorized_file_id_to_service(df['file_id_x'].fillna(-1).astype(int).values, file_ranges)
        else:
            df['service_x'] = 'unknown'
    if 'service_y' not in df.columns and 'file_id_y' in df.columns:
        if file_ranges:
            df['service_y'] = vectorized_file_id_to_service(df['file_id_y'].fillna(-1).astype(int).values, file_ranges)
        else:
            df['service_y'] = 'unknown'

    df = df.dropna(subset=['file_id_x', 'file_id_y'])

    result = (df, file_ranges, None)
    _data_cache[cache_key] = result
    return result


def _no_imports_sources(project_name: str, language: str):
    return (
        f'dest/codeclones/{project_name}/latest/{language}_no_imports.json',
        f'dest/clone_analysis/{project_name}/services.json'
    )


def _project_csv_sources(project_name: str, language: str):
    base = f'data/csv/{project_name}'
    return (
        base,
        f'{base}/ccfsw_{language.lower()}.csv',
        f'{base}/tks_{language.lower()}.csv',
        f'{base}/rnr_{language.lower()}.csv'
    )


def _legacy_csv_path(project_name: str, commit_hash: str, language: str):
    legacy = f'visualize/csv/{project_name}_{commit_hash}_{language}_all.csv'
    if os.path.exists(legacy):
        return legacy
    fallback = f'visualize/csv/{project_name}_latest_{language}_all.csv'
    return fallback if os.path.exists(fallback) else None


def load_and_process_data(project_name: str, commit_hash: str, language: str):
    """可視化用クローンデータをロード。

    優先順位: dest/scatter > 統一ローダー > no_imports JSON > プロジェクトCSV > レガシーCSV
    """
    cache_key = f"{project_name}_{commit_hash}_{language}"
    if cache_key in _data_cache:
        print(f"Loading from cache: {cache_key}")
        return _data_cache[cache_key]

    print(f"Loading and processing data: {cache_key}")

    # 0) dest/scatter 出力
    scatter_sources = _scatter_sources(project_name, language)
    services_json_path = f'dest/scatter/{project_name}/services.json'
    if scatter_sources:
        result = load_from_scatter_csv(scatter_sources, services_json_path, cache_key, language)
        if result[0] is not None:
            return result
        print(f"Scatter CSV loading failed or empty: {result[2]}, falling back...")

    # 1) 統一データローダー
    try:
        from core.unified_data_loader import UnifiedDataLoader  # noqa: F401
        if _unified_sources_exist(project_name, language):
            print("Using unified data loader")
            return load_from_unified_loader(project_name, language, cache_key)
    except ImportError:
        print("Unified data loader not available, falling back")

    # 2) no_imports JSON
    no_imports_json_path, services_json_path = _no_imports_sources(project_name, language)
    if os.path.exists(no_imports_json_path) and os.path.exists(services_json_path):
        print(f"Using no_imports JSON data: {no_imports_json_path}")
        return load_from_no_imports_json(no_imports_json_path, services_json_path, cache_key, project_name, language)

    # 3) プロジェクトCSV (CCFSW/TKS/RNR)
    project_csv_dir, ccfsw_csv_path, tks_csv_path, rnr_csv_path = _project_csv_sources(project_name, language)
    if os.path.exists(services_json_path) and (
        os.path.exists(ccfsw_csv_path) or os.path.exists(tks_csv_path) or os.path.exists(rnr_csv_path)
    ):
        print(f"Using project-based CSV data: {project_csv_dir}")
        return load_from_project_csv_with_rnr(project_csv_dir, ccfsw_csv_path, tks_csv_path, rnr_csv_path, services_json_path, cache_key, language)

    # 4) レガシーCSV
    legacy_csv_path = _legacy_csv_path(project_name, commit_hash, language)
    if legacy_csv_path and os.path.exists(services_json_path):
        print(f"Fallback to legacy CSV data: {legacy_csv_path}")
        return load_from_csv_fallback(legacy_csv_path, services_json_path, cache_key, language)

    error_msg = f"No data source found for {project_name}_{language}"
    result = (None, None, error_msg)
    _data_cache[cache_key] = result
    return result


def load_from_unified_loader(project_name: str, language: str, cache_key: str):
    """統一データローダーからデータを読み込み"""
    try:
        from core.unified_data_loader import UnifiedDataLoader

        loader = UnifiedDataLoader(project_name, language)
        df, service_ranges, error = loader.load_unified_data()

        if error:
            print(f"Unified loader error: {error}")
            result = (None, None, error)
        else:
            print(f"Unified data loaded: {len(df)} clone pairs")
            result = (df, service_ranges, None)

        _data_cache[cache_key] = result
        return result

    except Exception as e:
        print(f"Unified loader failed: {e}")
        error_msg = f"Unified data loader error: {e}"
        result = (None, None, error_msg)
        _data_cache[cache_key] = result
        return result

def load_from_no_imports_json(json_path: str, services_json_path: str, cache_key: str, project_name: str, language: str):
    """
    no_importsのJSONファイルからクローンデータを読み込む（推奨方式）
    
    no_importsデータには以下の利点があります：
    - importステートメントが除外されているため、実質的なコードクローンのみが検出される
    - file_dataにfile_idとfile_pathの完全なマッピングが含まれている
    - 処理速度が高速
    """
    try:
        print("Loading no_imports JSON file...")
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        print("Loading service file ranges...")
        file_ranges = load_service_file_ranges_cached(services_json_path, language)
        
        # file_idからfile_pathへのマッピングを作成
        file_id_to_path = {}
        for file_info in json_data.get('file_data', []):
            file_id_to_path[file_info['file_id']] = file_info['file_path']
        
        # JSONからクローンペアのDataFrameを構築
        clone_pairs = []
        clone_sets = json_data.get('clone_sets', [])
        
        print(f"Processing {len(clone_sets)} clone sets...")
        
        for clone_id, clone_set in enumerate(clone_sets):
            fragments = clone_set.get('fragments', [])
            if len(fragments) < 2:
                continue
                
            # クローンセット内のすべてのペアを生成
            for i in range(len(fragments)):
                for j in range(i + 1, len(fragments)):
                    frag1, frag2 = fragments[i], fragments[j]
                    
                    clone_pairs.append({
                        'clone_id': clone_id,
                        'file_id_x': frag1['file_id'],
                        'start_line_x': frag1['start_line'],
                        'end_line_x': frag1['end_line'],
                        'file_id_y': frag2['file_id'],
                        'start_line_y': frag2['start_line'],
                        'end_line_y': frag2['end_line'],
                        'file_path_x': file_id_to_path.get(frag1['file_id'], ''),
                        'file_path_y': file_id_to_path.get(frag2['file_id'], '')
                    })
        
        if not clone_pairs:
            result = (None, None, "No clone pairs found in JSON data")
            _data_cache[cache_key] = result
            return result
            
        print(f"Generated {len(clone_pairs)} clone pairs from JSON")
        df = pd.DataFrame(clone_pairs)
        
        # 型を最適化
        df = df.astype({
            'file_id_x': 'int32',
            'file_id_y': 'int32', 
            'start_line_x': 'int32',
            'end_line_x': 'int32',
            'start_line_y': 'int32', 
            'end_line_y': 'int32',
            'clone_id': 'int32'
        })
        
        # サービス情報の計算
        print("Computing service mappings...")
        df['service_x'] = vectorized_file_id_to_service(df['file_id_x'].values, file_ranges)
        df['service_y'] = vectorized_file_id_to_service(df['file_id_y'].values, file_ranges)
        
        # 関係性の計算
        print("Computing relations...")
        df['relation'] = 'inter'
        df.loc[df['service_x'] == df['service_y'], 'relation'] = 'intra'
        df['clone_type'] = 'Normal'  # デフォルトはNormal
        
        # TKSデータを統合
        tks_csv_path = f'data/csv/{project_name}/tks_{language.lower()}.csv'
        if os.path.exists(tks_csv_path):
            print(f"Loading and integrating TKS data from: {tks_csv_path}")
            try:
                tks_df = pd.read_csv(tks_csv_path, dtype={
                    'file_id_x': 'int32',
                    'file_id_y': 'int32', 
                    'start_line_x': 'int32',
                    'end_line_x': 'int32',
                    'start_line_y': 'int32', 
                    'end_line_y': 'int32',
                    'clone_id': 'int32'
                })
                
                if not tks_df.empty:
                    # TKSデータの前処理
                    tks_df['service_x'] = vectorized_file_id_to_service(tks_df['file_id_x'].values, file_ranges)
                    tks_df['service_y'] = vectorized_file_id_to_service(tks_df['file_id_y'].values, file_ranges)
                    tks_df['relation'] = 'inter'
                    tks_df.loc[tks_df['service_x'] == tks_df['service_y'], 'relation'] = 'intra'
                    tks_df['clone_type'] = 'TKS'
                    
                    # TKSデータを統合
                    df = pd.concat([df, tks_df], ignore_index=True)
                    print(f"Integrated {len(tks_df)} TKS clone pairs")
                    
            except Exception as e:
                print(f"Warning: Failed to load TKS data: {e}")
        
        # coord_pair列を作成
        print("Computing coordinate pairs...")
        df['coord_pair'] = df['file_id_x'].astype(str) + '_' + df['file_id_y'].astype(str)
        
        # overlap_countとcoord_total_linesの計算
        print("Computing overlap counts and total lines...")
        coord_counts = df['coord_pair'].value_counts()
        df['overlap_count'] = df['coord_pair'].map(coord_counts)
        df['total_lines'] = (df['end_line_x'] - df['start_line_x'] + 1) + (df['end_line_y'] - df['start_line_y'] + 1)
        coord_total_lines = df.groupby('coord_pair')['total_lines'].sum()
        df['coord_total_lines'] = df['coord_pair'].map(coord_total_lines)

        print(f"Data processing completed. Shape: {df.shape}")
        
        # 結果をキャッシュに保存
        result = (df, file_ranges, None)
        _data_cache[cache_key] = result
        
        return result
    except Exception as e:
        result = (None, None, f"Error loading no_imports JSON: {e}")
        _data_cache[cache_key] = result
        return result

def load_from_project_csv_with_rnr(project_csv_dir: str, ccfsw_csv_path: str, tks_csv_path: str, rnr_csv_path: str, services_json_path: str, cache_key: str, language: str):
    """プロジェクトベースCSVファイルからデータを読み込む（CCFSW、TKS、RNR統合）"""
    try:
        dfs = []
        ccfsw_df = None
        tks_df = None
        rnr_df = None
        
        # CCFSWデータの読み込み
        if os.path.exists(ccfsw_csv_path):
            print(f"Loading CCFSW CSV: {ccfsw_csv_path}")
            ccfsw_df = pd.read_csv(ccfsw_csv_path, dtype={
                'file_id_x': 'int32',
                'file_id_y': 'int32', 
                'start_line_x': 'int32',
                'end_line_x': 'int32',
                'start_line_y': 'int32', 
                'end_line_y': 'int32',
                'clone_id': 'int32'
            })
            # clone_typeがない場合はNormalとして設定
            if 'clone_type' not in ccfsw_df.columns:
                ccfsw_df['clone_type'] = 'Normal'
            print(f"CCFSW data loaded: {ccfsw_df.shape[0]} rows")
        
        # TKSデータの読み込み
        if os.path.exists(tks_csv_path):
            print(f"Loading TKS CSV: {tks_csv_path}")
            tks_df = pd.read_csv(tks_csv_path, dtype={
                'file_id_x': 'int32',
                'file_id_y': 'int32', 
                'start_line_x': 'int32',
                'end_line_x': 'int32',
                'start_line_y': 'int32', 
                'end_line_y': 'int32',
                'clone_id': 'int32'
            })
            # clone_typeがない場合はTKSとして設定
            if 'clone_type' not in tks_df.columns:
                tks_df['clone_type'] = 'TKS'
            print(f"TKS data loaded: {tks_df.shape[0]} rows")
        
        # RNRデータの読み込み
        if os.path.exists(rnr_csv_path):
            print(f"Loading RNR CSV: {rnr_csv_path}")
            rnr_df = pd.read_csv(rnr_csv_path, dtype={
                'file_id_x': 'int32',
                'file_id_y': 'int32', 
                'start_line_x': 'int32',
                'end_line_x': 'int32',
                'start_line_y': 'int32', 
                'end_line_y': 'int32',
                'clone_id': 'int32'
            })
            # clone_typeがない場合はRNRとして設定
            if 'clone_type' not in rnr_df.columns:
                rnr_df['clone_type'] = 'RNR'
            print(f"RNR data loaded: {rnr_df.shape[0]} rows")

        # データフレームが存在しない場合のエラーハンドリング
        if ccfsw_df is None and tks_df is None and rnr_df is None:
            raise FileNotFoundError(f"No valid CSV files found in {project_csv_dir}")
        
        # データ統合
        available_dfs = []
        if ccfsw_df is not None:
            available_dfs.append(ccfsw_df)
        if tks_df is not None:
            available_dfs.append(tks_df)
        if rnr_df is not None:
            available_dfs.append(rnr_df)
        
        # 統合
        df = pd.concat(available_dfs, ignore_index=True)
        print(f"Integrated data: {len(df)} total rows")
        
        print("Loading service file ranges...")
        file_ranges = load_service_file_ranges_cached(services_json_path, language)

        # サービス情報の計算（ベクトル化で高速化）
        if 'service_x' not in df.columns or 'service_y' not in df.columns:
            print("Computing service mappings...")
            df['service_x'] = vectorized_file_id_to_service(df['file_id_x'].values, file_ranges)
            df['service_y'] = vectorized_file_id_to_service(df['file_id_y'].values, file_ranges)
        
        # 関係性の計算（ベクトル化）
        if 'relation' not in df.columns:
            print("Computing relations...")
            df['relation'] = 'inter'
            df.loc[df['service_x'] == df['service_y'], 'relation'] = 'intra'

        # coord_pair列を常に作成（高速化）
        if 'coord_pair' not in df.columns:
            print("Computing coordinate pairs...")
            df['coord_pair'] = df['file_id_x'].astype(str) + '_' + df['file_id_y'].astype(str)

        # overlap_countとcoord_total_linesの計算（高速化）
        if 'overlap_count' not in df.columns or 'coord_total_lines' not in df.columns:
            print("Computing overlap counts and total lines...")
            coord_counts = df['coord_pair'].value_counts()
            df['overlap_count'] = df['coord_pair'].map(coord_counts)
            df['total_lines'] = (df['end_line_x'] - df['start_line_x'] + 1) + (df['end_line_y'] - df['start_line_y'] + 1)
            coord_total_lines = df.groupby('coord_pair')['total_lines'].sum()
            df['coord_total_lines'] = df['coord_pair'].map(coord_total_lines)

        print(f"RNR-integrated data processing completed. Shape: {df.shape}")
        
        # 結果をキャッシュに保存
        result = (df, file_ranges, None)
        _data_cache[cache_key] = result
        
        return result
        
    except Exception as e:
        result = (None, None, f"Error loading RNR-integrated CSV data: {e}")
        _data_cache[cache_key] = result
        return result

def load_from_project_csv(project_csv_dir: str, ccfsw_csv_path: str, tks_csv_path: str, services_json_path: str, cache_key: str, language: str):
    """プロジェクトベースCSVファイルからデータを読み込む（CCFSWとTKS最適化統合）"""
    try:
        dfs = []
        ccfsw_df = None
        tks_df = None
        
        # CCFSWデータの読み込み
        if os.path.exists(ccfsw_csv_path):
            print(f"Loading CCFSW CSV: {ccfsw_csv_path}")
            ccfsw_df = pd.read_csv(ccfsw_csv_path, dtype={
                'file_id_x': 'int32',
                'file_id_y': 'int32', 
                'start_line_x': 'int32',
                'end_line_x': 'int32',
                'start_line_y': 'int32', 
                'end_line_y': 'int32',
                'clone_id': 'int32'
            })
            # clone_typeがない場合はNormalとして設定
            if 'clone_type' not in ccfsw_df.columns:
                ccfsw_df['clone_type'] = 'Normal'
            print(f"CCFSW data loaded: {ccfsw_df.shape[0]} rows")
        
        # TKSデータの読み込み
        if os.path.exists(tks_csv_path):
            print(f"Loading TKS CSV: {tks_csv_path}")
            tks_df = pd.read_csv(tks_csv_path, dtype={
                'file_id_x': 'int32',
                'file_id_y': 'int32', 
                'start_line_x': 'int32',
                'end_line_x': 'int32',
                'start_line_y': 'int32', 
                'end_line_y': 'int32',
                'clone_id': 'int32'
            })
            # clone_typeがない場合はTKSとして設定
            if 'clone_type' not in tks_df.columns:
                tks_df['clone_type'] = 'TKS'
            print(f"TKS data loaded: {tks_df.shape[0]} rows")
        
        # データフレームが存在しない場合のエラーハンドリング
        if ccfsw_df is None and tks_df is None:
            raise FileNotFoundError(f"No valid CSV files found in {project_csv_dir}")
        
        # T047: データ品質検証とエラーハンドリング統合
        # CCFSW/TKSの内部重複除去と品質検証を実行
        try:
            from core.data_quality_validator import DataQualityValidator
            validator = DataQualityValidator()
            
            # CCFSW内部重複除去
            if ccfsw_df is not None:
                ccfsw_validation = validator.validate_ccfsw_data(ccfsw_df)
                ccfsw_df = ccfsw_validation['cleaned_data']
                print(f"CCFSW quality validation: {ccfsw_validation['original_count']} -> "
                      f"{len(ccfsw_df)} rows ({ccfsw_validation['cleaning_stats'].get('removal_rate', 0):.1f}% duplicates removed)")
            
            # TKS内部重複除去
            if tks_df is not None:
                tks_validation = validator.validate_tks_data(tks_df)
                tks_df = tks_validation['cleaned_data']
                print(f"TKS quality validation: {tks_validation['original_count']} -> "
                      f"{len(tks_df)} rows ({tks_validation['cleaning_stats'].get('removal_rate', 0):.1f}% duplicates removed)")
            
        except ImportError:
            print("Warning: Data quality validator not available, skipping internal deduplication")
        
        # T046: CCFSW/TKS間重複除去最適化
        if ccfsw_df is not None and tks_df is not None:
            # 両方存在する場合：CCFSW/TKS間の重複を分析して最適化
            try:
                from core.deduplication_optimizer import analyze_clone_overlap, remove_duplicate_clones
                
                overlap_analysis = analyze_clone_overlap(ccfsw_df, tks_df)
                if overlap_analysis.get('significant_overlap', False):
                    # 重要な重複がある場合：CCFSWを優先してTKSから重複除去
                    df, dedup_stats = remove_duplicate_clones(ccfsw_df, tks_df, strategy='keep_ccfsw')
                    print(f"Inter-dataset deduplication: removed {dedup_stats['removed_duplicates']} duplicates")
                else:
                    # 重複が少ない場合：両方を統合
                    df = pd.concat([ccfsw_df, tks_df], ignore_index=True)
                    print(f"Both datasets integrated: {len(ccfsw_df)} CCFSW + {len(tks_df)} TKS = {len(df)} total")
            except ImportError:
                # フォールバック：単純統合
                df = pd.concat([ccfsw_df, tks_df], ignore_index=True)
                print(f"Fallback integration: {len(ccfsw_df)} CCFSW + {len(tks_df)} TKS = {len(df)} total")
        elif ccfsw_df is not None:
            # CCFSWのみ（内部重複除去済み）
            df = ccfsw_df
            print(f"Using cleaned CCFSW data: {len(df)} rows")
        else:
            # TKSのみ（内部重複除去済み）
            df = tks_df
            print(f"Using cleaned TKS data: {len(df)} rows")
        
        # 統合完了後の処理
        
        print("Loading service file ranges...")
        file_ranges = load_service_file_ranges_cached(services_json_path, language)

        # サービス情報の計算（ベクトル化で高速化）
        if 'service_x' not in df.columns or 'service_y' not in df.columns:
            print("Computing service mappings...")
            df['service_x'] = vectorized_file_id_to_service(df['file_id_x'].values, file_ranges)
            df['service_y'] = vectorized_file_id_to_service(df['file_id_y'].values, file_ranges)
        
        # 関係性の計算（ベクトル化）
        if 'relation' not in df.columns:
            print("Computing relations...")
            df['relation'] = 'inter'
            df.loc[df['service_x'] == df['service_y'], 'relation'] = 'intra'

        # coord_pair列を常に作成（高速化）
        if 'coord_pair' not in df.columns:
            print("Computing coordinate pairs...")
            df['coord_pair'] = df['file_id_x'].astype(str) + '_' + df['file_id_y'].astype(str)

        # overlap_countとcoord_total_linesの計算（高速化）
        if 'overlap_count' not in df.columns or 'coord_total_lines' not in df.columns:
            print("Computing overlap counts and total lines...")
            coord_counts = df['coord_pair'].value_counts()
            df['overlap_count'] = df['coord_pair'].map(coord_counts)
            df['total_lines'] = (df['end_line_x'] - df['start_line_x'] + 1) + (df['end_line_y'] - df['start_line_y'] + 1)
            coord_total_lines = df.groupby('coord_pair')['total_lines'].sum()
            df['coord_total_lines'] = df['coord_pair'].map(coord_total_lines)

        print(f"Project-based data processing completed. Shape: {df.shape}")
        
        # 結果をキャッシュに保存
        result = (df, file_ranges, None)
        _data_cache[cache_key] = result
        
        return result
    except Exception as e:
        result = (None, None, f"Error loading project CSV data: {e}")
        _data_cache[cache_key] = result
        return result

def load_from_csv_fallback(csv_path: str, services_json_path: str, cache_key: str, language: str):
    """従来のCSVファイルからデータを読み込む（no_importsが利用できない場合のフォールバック）"""
    try:
        # CSVファイルの読み込み（高速化）
        print("Loading CSV file...")
        df = pd.read_csv(csv_path, dtype={
            'file_id_x': 'int32',
            'file_id_y': 'int32', 
            'start_line_x': 'int32',
            'end_line_x': 'int32',
            'start_line_y': 'int32', 
            'end_line_y': 'int32',
            'clone_id': 'int32'  # intに修正
        })
        
        print("Loading service file ranges...")
        file_ranges = load_service_file_ranges_cached(services_json_path, language)

        # サービス情報の計算（ベクトル化で高速化）
        if 'service_x' not in df.columns or 'service_y' not in df.columns:
            print("Computing service mappings...")
            df['service_x'] = vectorized_file_id_to_service(df['file_id_x'].values, file_ranges)
            df['service_y'] = vectorized_file_id_to_service(df['file_id_y'].values, file_ranges)
        
        # 関係性の計算（ベクトル化）
        if 'relation' not in df.columns:
            print("Computing relations...")
            df['relation'] = 'inter'
            df.loc[df['service_x'] == df['service_y'], 'relation'] = 'intra'

        # coord_pair列を常に作成（高速化）
        if 'coord_pair' not in df.columns:
            print("Computing coordinate pairs...")
            df['coord_pair'] = df['file_id_x'].astype(str) + '_' + df['file_id_y'].astype(str)

        # overlap_countとcoord_total_linesの計算（高速化）
        if 'overlap_count' not in df.columns or 'coord_total_lines' not in df.columns:
            print("Computing overlap counts and total lines...")
            coord_counts = df['coord_pair'].value_counts()
            df['overlap_count'] = df['coord_pair'].map(coord_counts)
            df['total_lines'] = (df['end_line_x'] - df['start_line_x'] + 1) + (df['end_line_y'] - df['start_line_y'] + 1)
            coord_total_lines = df.groupby('coord_pair')['total_lines'].sum()
            df['coord_total_lines'] = df['coord_pair'].map(coord_total_lines)

        print(f"Data processing completed. Shape: {df.shape}")
        
        # 結果をキャッシュに保存
        result = (df, file_ranges, None)
        _data_cache[cache_key] = result
        
        return result
    except Exception as e:
        result = (None, None, f"Error loading CSV data: {e}")
        _data_cache[cache_key] = result
        return result

def clear_data_cache():
    """データキャッシュをクリアする"""
    global _data_cache
    _data_cache.clear()
    # load_service_file_ranges_cached.cache_clear()  # lru_cache無効化のため一時的にコメントアウト
    print("Data cache cleared.")

def build_file_tree_data(file_paths):
    """
    ファイルパスのリストからネストされた辞書構造（ツリー）を生成する
    
    Args:
        file_paths: ['src/A/f1.java', 'src/B/f2.java'] のようなパスリスト
        
    Returns:
        {
            'src': {
                'A': {'f1.java': '__FILE__'},
                'B': {'f2.java': '__FILE__'}
            }
        }
    """
    tree = {}
    for path in file_paths:
        if not path:
            continue
        parts = path.split('/')
        current = tree
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
            # もし__FILE__がある場合（ディレクトリと同盟のファイルがあった場合など）の考慮が必要だが
            # 今回は簡易的に上書きしないようにする
            if current == '__FILE__':
                current = {} # 構造が壊れるが、実データでは稀

        # ファイルを示すマーカー
        current[parts[-1]] = '__FILE__'
    
    return tree

def get_clone_related_files(df):
    """
    クローンデータフレームから関連する全ファイルパスを抽出する
    """
    if df is None or df.empty:
        return []
    
    files = set()
    if 'file_path_x' in df.columns:
        files.update(df['file_path_x'].dropna().unique())
    if 'file_path_y' in df.columns:
        files.update(df['file_path_y'].dropna().unique())
        
    return sorted(list(files))
