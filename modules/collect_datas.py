from pathlib import Path
import sys
import subprocess
import git
import traceback
import json

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from modules.github_linguist import get_exts
from config import ANTLR_LANGUAGE, CCFINDERSW_JAR, CCFINDERSWPARSER


def parse_diff_str(diff: str):
    diff_at_split = diff.split("@@")
    try:
        hunk_range_split = diff_at_split[1].replace("+", "").replace("-", "").split(" ")
        hunk = diff_at_split[2].split("\n")
        hunk_range_old = hunk_range_split[1]
        hunk_range_new = hunk_range_split[2]
        old_line_count = int(hunk_range_old.split(",")[0])
        new_line_count = int(hunk_range_new.split(",")[0])
    except:
        return None
    return hunk, old_line_count, new_line_count


def find_moving_lines(commit: git.Commit, name: str) -> tuple[list[str], list[str]]:
    for parent in commit.parents:
        diffs = parent.diff(commit, create_patch=True)
        output_result = []
        for diff in diffs:
            if diff.diff:
                child_path = diff.b_path
                parent_path = diff.a_path
                result = parse_diff_str(diff.diff.decode("utf-8"))
                if result is None:
                    continue
                hunk, old_line_count, new_line_count = result
                temp_added_lines = []
                temp_deleted_lines = []
                for line in hunk:
                    if line.startswith("+"):
                        temp_added_lines.append(new_line_count)
                        new_line_count += 1
                    elif line.startswith("-"):
                        temp_deleted_lines.append(old_line_count)
                        old_line_count += 1
                    else:
                        old_line_count += 1
                        new_line_count += 1
                inserted_lines = []
                deleted_lines = []
                modified_lines = []
                for added_line in temp_added_lines:
                    if added_line not in deleted_lines:
                        inserted_lines.append(added_line)
                    else:
                        modified_lines.append(added_line)
                for deleted_line in temp_deleted_lines:
                    if deleted_line not in temp_added_lines:
                        deleted_lines.append(deleted_line)
                output_result.append({
                    "child_path": child_path,
                    "parent_path": parent_path,
                    "inserted_lines": inserted_lines,
                    "deleted_lines": deleted_lines,
                    "modified_lines": modified_lines
                })
        if len(output_result) > 0:
            dest_dir = project_root / "dest/moving_lines" / name
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / f"{parent.hexsha}-{commit.hexsha}.json"
            with open(dest_file, "w") as f:
                json.dump(output_result, f)
                

def convert_language_for_ccfindersw(language: str):
    match language:
        case "C++":
            return "cpp"
        case "C#":
            return "csharp"
        case _:
            return language.lower()


def detect_cc(project: Path, name: str, language: str, commit_hash: str, exts: tuple[str]):
    try:
        dest_dir = project_root / "dest/temp/ccfswtxt" / name / commit_hash
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / language
        if language in ANTLR_LANGUAGE:
            cmd = ["java", "-jar", "-Xss128m", str(CCFINDERSW_JAR), "D", "-d", str(project), "-l", convert_language_for_ccfindersw(language), "-o", str(dest_file), "-antlr", "|".join(exts), "-w", "2", "-ccfsw", "set"]
        else:
            cmd = ["java", "-jar" ,str(CCFINDERSW_JAR), "D", "-d", str(project), "-l", convert_language_for_ccfindersw(language), "-o", str(dest_file), "-w", "2", "-ccfsw", "set"]
        subprocess.run(cmd, check=True)
        
        json_dest_dir = project_root / "dest/clones_json" / name / commit_hash
        json_dest_dir.mkdir(parents=True, exist_ok=True)
        json_dest_file = json_dest_dir / f"{language}.json"
        cmd = [str(CCFINDERSWPARSER), "-i", str(f"{dest_file}_ccfsw.txt"), "-o", str(json_dest_file)]
        subprocess.run(cmd, check=True)
    except Exception as e:
        print("CCFinderの実行に失敗しました．")
        raise e


def collect_datas_of_repo(project: dict):
    languages = project["languages"].keys()
    url = project["URL"]
    # リポジトリの識別子とプロジェクトディレクトリの設定
    name = url.split('/')[-2] + '.' + url.split('/')[-1]
    print("--------------------------------")
    print(name)
    print("--------------------------------")
    project_dir = project_root / "dest/projects" / name
    # 言語ごとの拡張子一覧の取得
    exts = get_exts(project_dir)
    # GitPythonのインスタンスの作成(分析に便利!)
    git_repo = git.Repo(str(project_dir))
    hcommit = git_repo.head.commit
    try:
        finished_commits = []
        queue = [hcommit.hexsha]
        # コミットを幅優先探索
        while (len(queue) > 0):
            commit_hash = queue.pop(0)
            commit = git_repo.commit(commit_hash)
            if commit_hash in finished_commits:
                continue
            print(f"checkout to {commit_hash}...")
            git_repo.git.checkout(commit_hash)
            # 修正を保存
            find_moving_lines(commit, name)
            # コードクローン検出
            for language in languages:
                detect_cc(project_dir, name, language, commit_hash, exts[language])
            finished_commits.append(commit_hash)
            for parent in commit.parents:
                if parent.hexsha in finished_commits:
                    continue
                queue.append(parent.hexsha)
    except Exception as e:
        print(traceback.format_exc())
        print(e)
    finally:
        print("checkout to latest commit...")
        git_repo.git.checkout(hcommit.hexsha)