from pathlib import Path
import sys
import subprocess
import git
import traceback
import json
from typing import Optional, Tuple

def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return start


project_root = _find_repo_root(Path(__file__).resolve())
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))
from modules.github_linguist import get_exts
from config import ANTLR_LANGUAGE, CCFINDERSW_JAR, CCFINDERSWPARSER


def parse_diff_str(diff: str) -> Optional[Tuple[list[str], int, int]]:
    """diff 文字列からハンク行と開始行番号を抽出する。"""
    diff_at_split = diff.split("@@")
    if len(diff_at_split) < 3:
        return None
    try:
        hunk_range_split = diff_at_split[1].replace("+", "").replace("-", "").split(" ")
        hunk_range_old = hunk_range_split[1]
        hunk_range_new = hunk_range_split[2]
        old_line_count = int(hunk_range_old.split(",")[0])
        new_line_count = int(hunk_range_new.split(",")[0])
    except (IndexError, ValueError):
        return None
    hunk_lines = diff_at_split[2].split("\n")
    return hunk_lines, old_line_count, new_line_count


def find_moving_lines(commit: git.Commit, prev: git.Commit, name: str):
    """2 つのコミット間で追加・削除・変更された行を収集して保存する。"""
    diff_hunks = prev.diff(commit, create_patch=True)
    output_result = []
    for diff_hunk in diff_hunks:
        if diff_hunk.diff:
            child_path = diff_hunk.b_path
            parent_path = diff_hunk.a_path
            try:
                result = parse_diff_str(diff_hunk.diff.decode("utf-8"))
                if result is None:
                    continue
            except UnicodeDecodeError:
                print(f"diff.diff.decode('utf-8')のデコードに失敗しました．")
                print(diff_hunk.diff)
                continue
            hunk, old_file_line_count, new_file_line_count = result
            potential_inserted_lines: list[int] = []
            potential_deleted_lines: list[int] = []
            for line in hunk:
                if line.startswith("+"):
                    potential_inserted_lines.append(new_file_line_count)
                    new_file_line_count += 1
                elif line.startswith("-"):
                    potential_deleted_lines.append(old_file_line_count)
                    old_file_line_count += 1
                else:
                    old_file_line_count += 1
                    new_file_line_count += 1
            inserted_lines = []
            deleted_lines = []
            modified_lines = []
            for inserted_line in potential_inserted_lines:
                if inserted_line not in potential_deleted_lines:
                    inserted_lines.append(inserted_line)
                else:
                    modified_lines.append(inserted_line)
            for deleted_line in potential_deleted_lines:
                if deleted_line not in potential_inserted_lines:
                    deleted_lines.append(deleted_line)
            output_result.append(
                {
                    "child_path": child_path,
                    "parent_path": parent_path,
                    "inserted_lines": inserted_lines,
                    "deleted_lines": deleted_lines,
                    "modified_lines": modified_lines,
                }
            )
    if output_result:
        dest_dir = project_root / "dest/moving_lines" / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{commit.hexsha}-{prev.hexsha}.json"
        with open(dest_file, "w") as f:
            json.dump(output_result, f)


def convert_language_for_ccfindersw(language: str) -> str:
    match language:
        case "C++":
            return "cpp"
        case "C#":
            return "csharp"
        case _:
            return language.lower()


def detect_cc(project: Path, name: str, language: str, commit_hash: str, exts: tuple[str]):
    """対象言語とコミットで CC-Finder SW を実行し、結果を保存する。"""
    try:
        dest_dir = project_root / "dest/temp/ccfswtxt" / name / commit_hash
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / language
        language_arg = convert_language_for_ccfindersw(language)
        base_cmd = [
            "java", "-jar", "-Xmx16G", "-Xss256m", str(CCFINDERSW_JAR), "D",
            "-d", str(project), "-l", language_arg, "-o", str(dest_file)
        ]
        if language in ANTLR_LANGUAGE:
            cmd = [*base_cmd, "-antlr", "|".join(exts), "-w", "2", "-ccfsw", "set"]
        else:
            cmd = [*base_cmd, "-w", "2", "-ccfsw", "set"]
        subprocess.run(cmd, check=True)
        
        json_dest_dir = project_root / "dest/clones_json" / name / commit_hash
        json_dest_dir.mkdir(parents=True, exist_ok=True)
        json_dest_file = json_dest_dir / f"{language}.json"
        cmd = [str(CCFINDERSWPARSER), "-i", str(f"{dest_file}_ccfsw.txt"), "-o", str(json_dest_file)]
        subprocess.run(cmd, check=True)
    except Exception as e:
        print("CCFinderの実行に失敗しました．")
        print(traceback.format_exc())
        raise e


def collect_datas_of_repo(project: dict):
    """対象コミットに対してコードクローンと変更行情報を収集する。"""
    url = project["URL"]
    # リポジトリの識別子とプロジェクトディレクトリの設定
    name = url.split('/')[-2] + '.' + url.split('/')[-1]
    print("--------------------------------")
    print(name)
    print("--------------------------------")
    project_dir = project_root / "dest/projects" / name
    analyzed_commits_path = project_root / "dest/analyzed_commits" / f"{name}.json"

    # 言語ごとの拡張子一覧の取得
    exts = get_exts(project_dir)
    languages = project["languages"].keys()
    # GitPythonのインスタンスの作成(分析に便利!)
    git_repo = git.Repo(str(project_dir))
    with open(analyzed_commits_path, "r") as f:
        analyzed_commit_hashes = json.load(f)
    hcommit = git_repo.commit(analyzed_commit_hashes[0])
    try:
        prev_commit = hcommit
        for commit_hash in analyzed_commit_hashes:
            print(f"checkout to {commit_hash}...")
            git_repo.git.checkout(commit_hash)
            for language in languages:
                detect_cc(project_dir, name, language, commit_hash, exts[language])
            if commit_hash == hcommit.hexsha:
                continue
            commit = git_repo.commit(commit_hash)
            # 修正を保存
            find_moving_lines(commit, prev_commit, name)
            prev_commit = commit
    except Exception as e:
        print(traceback.format_exc())
        print(e)
    finally:
        print("checkout to latest commit...")
        git_repo.git.checkout(hcommit.hexsha)
