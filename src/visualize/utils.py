from pathlib import Path
import functools
import re

LOCAL_STATIC_BASE = Path('dest/temp/static')
LOCAL_NO_IMPORTS_BASE = Path('dest/temp/no_imports')

@functools.lru_cache(maxsize=200)
def read_file_lines_cached(path: Path):
    """キャッシュ付きでファイルを読み込む"""
    try:
        with path.open('r', encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()
    except Exception:
        return []

def get_local_project_root(project: str) -> Path:
    """プロジェクトのソースコードが格納されているルートディレクトリを取得する"""
    # 最初にno_importsを確認（TKSデータ用）
    no_imports_base = LOCAL_NO_IMPORTS_BASE / project
    if no_imports_base.exists():
        return no_imports_base
    
    # 次にstaticを確認（従来のデータ用）
    static_base = LOCAL_STATIC_BASE / project
    if static_base.exists():
        return static_base
    
    # フォールバック: clone_analysis/repo 構造も考慮
    alt = Path('dest/clone_analysis') / project / 'repo'
    if alt.exists():
        return alt
    
    # 追加: dest/projects (現在の標準的な場所)
    projects_base = Path('dest/projects') / project
    if projects_base.exists():
        return projects_base
    
    # どれも存在しない場合は、no_importsを優先して返す
    return no_imports_base

def get_local_snippet(project: str, file_path: str, start_line: int, end_line: int, context=2):
    """ローカルファイルからコードスニペットを取得し、行番号とコンテキストを付けてフォーマットする"""
    try:
        if file_path is None:
            return "File path is missing."
            
        # no_importsデータの場合は既に絶対パスが含まれている
        if file_path.startswith('/'):
            # 絶対パスの場合はそのまま使用
            abs_path = Path(file_path).resolve()
        else:
            # 相対パスの場合は従来通りプロジェクトルートと結合
            root = get_local_project_root(project)
            abs_path = (root / file_path.lstrip('/')).resolve()
            if not str(abs_path).startswith(str(root.resolve())):
                raise ValueError('Path escape detected')

        if not abs_path.is_file():
            return f'Local file not found at: {abs_path}'

        lines = read_file_lines_cached(abs_path)
        if not lines:
            return 'File is empty or could not be read.'

        # 行番号の範囲を調整
        s = max(0, start_line - 1 - context)
        e = min(len(lines), end_line + context)
        
        out = []
        for i in range(s, e):
            prefix = '>' if (start_line - 1) <= i < end_line else ' '
            out.append(f"{prefix}{i+1:5d}: {lines[i]}")
        return '\n'.join(out)
    except ValueError as ve:
        return f'Path error: {ve}'
    except Exception as e:
        return f'Error getting snippet: {e}'

def get_file_content(project: str, file_path: str, start_line: int = -1, end_line: int = -1):
    """ファイル全体の内容を取得し、指定範囲をハイライトする"""
    try:
        # no_importsデータの場合は既に絶対パスが含まれている
        if file_path.startswith('/'):
            # 絶対パスの場合はそのまま使用
            abs_path = Path(file_path).resolve()
        else:
            # 相対パスの場合は従来通りプロジェクトルートと結合
            root = get_local_project_root(project)
            abs_path = (root / file_path.lstrip('/')).resolve()
            if not str(abs_path).startswith(str(root.resolve())):
                raise ValueError('Path escape detected')

        if not abs_path.is_file():
            return f'Local file not found at: {abs_path}'

        lines = read_file_lines_cached(abs_path)
        if not lines:
            return 'File is empty or could not be read.'

        # 行番号付きで表示し、クローン箇所をマーク
        formatted_lines = []
        for i, line in enumerate(lines, 1):
            if start_line <= i <= end_line:
                # クローン箇所の行には ">" のプレフィックスを付ける
                formatted_lines.append(f"> {i:4d} {line}")
            else:
                formatted_lines.append(f"  {i:4d} {line}")
        
        code_content = "\n".join(formatted_lines)
        
        # ファイル情報とクローン範囲を表示（> マーク付きの説明を削除）
        if start_line > 0 and end_line > 0:
            file_info = f"**ファイル**: `{file_path}`\n**クローン箇所**: {start_line}行目 - {end_line}行目\n\n"
        else:
            file_info = f"**ファイル**: `{file_path}`\n\n"
        
        return file_info + f"```\n{code_content}\n```"

    except ValueError as ve:
        return f'Path error: {ve}'
    except Exception as e:
        return f'Error getting file content: {e}'

def get_file_tree(project: str, file_path: str):
    """指定されたファイルのディレクトリツリーを生成する"""
    try:
        # rootを最初に絶対パスに解決する
        root = get_local_project_root(project).resolve()
        abs_path = (root / file_path.lstrip('/')).resolve()
        
        # パストラバーサルチェック
        if not str(abs_path).startswith(str(root)):
            raise ValueError(f'Path escape detected. {abs_path} is not under {root}')

        if not abs_path.is_file():
            return f'Local file not found at: {abs_path}'

        dir_path = abs_path.parent
        tree = []
        
        # ディレクトリを再帰的に探索
        def generate_tree(directory, prefix=""):
            # .gitや__pycache__などの不要なディレクトリ/ファイルをスキップ
            entries = sorted([p for p in directory.iterdir() if p.name not in ['.git', '__pycache__', '.DS_Store']])
            for i, path in enumerate(entries):
                is_last = i == (len(entries) - 1)
                connector = "└── " if is_last else "├── "
                
                # ハイライトするファイル
                marker = " *" if path == abs_path else ""
                
                tree.append(f"{prefix}{connector}{path.name}{marker}")
                
                if path.is_dir():
                    extension = "    " if is_last else "│   "
                    generate_tree(path, prefix + extension)

        tree.append(f"{dir_path.relative_to(root)}")
        generate_tree(dir_path)
        
        return "```\n" + "\n".join(tree) + "\n```"

    except ValueError as ve:
        return f'Path error: {ve}'
    except Exception as e:
        return f'Error getting file tree: {e}'
