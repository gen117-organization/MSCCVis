from pathlib import Path

def filter_imports(file_path: Path, language: str):
    """指定されたファイルのimport行をコメントアウトする"""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return

    new_lines = []
    for line in lines:
        stripped = line.strip()
        is_import = False
        comment_char = ""
        
        # 言語ごとのimport構文とコメントアウト記号の定義
        if language == "Python":
            if stripped.startswith("import ") or stripped.startswith("from "):
                is_import = True
                comment_char = "# "
        elif language in ["Java", "C#", "Go", "TypeScript", "JavaScript", "C", "C++", "Rust", "Kotlin", "Scala", "Swift", "PHP", "Ruby"]:
            if language in ["C", "C++"] and stripped.startswith("#include "):
                is_import = True
                comment_char = "// "
            elif language == "Rust" and stripped.startswith("use "):
                is_import = True
                comment_char = "// "
            elif language == "PHP" and (stripped.startswith("use ") or stripped.startswith("require ") or stripped.startswith("include ")):
                is_import = True
                comment_char = "// "
            elif language == "Ruby" and (stripped.startswith("require ") or stripped.startswith("load ")):
                is_import = True
                comment_char = "# "
            elif language == "Go" and (stripped.startswith("import ") or stripped.startswith("package ")):
                is_import = True
                comment_char = "// "
            elif language in ["Java", "Scala", "Kotlin"] and (stripped.startswith("import ") or stripped.startswith("package ")):
                is_import = True
                comment_char = "// "
            elif stripped.startswith("import "):
                is_import = True
                comment_char = "// "
        
        if is_import:
            # 行番号を変えないために、行を削除せずコメントアウトする
            new_lines.append(comment_char + line)
        else:
            new_lines.append(line)
            
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def apply_filter(project_dir: Path, languages: list, exts: dict):
    """プロジェクト内の対象言語ファイルすべてにフィルタを適用"""
    for language in languages:
        if language not in exts:
            continue
        extensions = exts[language]
        for ext in extensions:
            for file_path in project_dir.rglob(f"*{ext}"):
                if file_path.is_file():
                    filter_imports(file_path, language)
