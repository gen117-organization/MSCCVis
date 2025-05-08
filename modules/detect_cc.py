from pathlib import Path
import json
import sys
import os
import subprocess
import git
import shutil
import traceback

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from modules.github_linguist import run_github_linguist
from config import ANTLR_LANGUAGE, SEARCH_DEPTH, TARGET_PROGRAMING_LANGUAGES


CCFINDERSW_JAR = project_root / "lib/CCFinderSW-1.0/lib/CCFinderSW-1.0.jar"
CCFINDERSWPARSER = project_root / "lib/ccfindersw-parser/target/release/ccfindersw-parser"


def get_exts(workdir: Path) -> dict:
    result = {}
    github_linguist_result = run_github_linguist(str(workdir))
    for language in github_linguist_result.keys():
        if language not in TARGET_PROGRAMING_LANGUAGES:
            continue
        exts = set()
        for file in github_linguist_result[language]["files"]:
            ext = os.path.splitext(file)[1].replace(".", "")
            if ext != "":
                exts.add(ext)
        result[language] = tuple(exts)
    return result


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
        dest_dir = project_root / "dest/temp/clones" / name / commit_hash
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / language
        if language in ANTLR_LANGUAGE:
            cmd = ["java", "-jar", "-Xss128m", str(CCFINDERSW_JAR), "D", "-d", str(project), "-l", convert_language_for_ccfindersw(language), "-o", str(dest_file), "-antlr", "|".join(exts), "-w", "2", "-ccfsw", "set"]
        else:
            cmd = ["java", "-jar" ,str(CCFINDERSW_JAR), "D", "-d", str(project), "-l", convert_language_for_ccfindersw(language), "-o", str(dest_file), "-w", "2", "-ccfsw", "set"]
        subprocess.run(cmd, check=True)
        
        json_dest_dir = project_root / "dest/codeclones" / name / commit_hash
        json_dest_dir.mkdir(parents=True, exist_ok=True)
        json_dest_file = json_dest_dir / f"{language}.json"
        cmd = [str(CCFINDERSWPARSER), "-i", str(f"{dest_file}_ccfsw.txt"), "-o", str(json_dest_file)]
        subprocess.run(cmd, check=True)
    except Exception as e:
        print("CCFinderの実行に失敗しました．")
        raise e


def output_diff(commit: git.Commit):
    for parent in commit.parents:
        diff = parent.diff(commit, create_patch=True)
        changes = []
        for diff_item in diff:
            if diff_item.diff:
                is_rename: bool = (diff_item.a_path != diff_item.b_path)
                diff_text_split = diff_item.diff.decode("utf-8").split("@@")
                try:
                    hunk_range_split = diff_text_split[1].replace("+", "").replace("-", "").split(" ")
                    hunk = diff_text_split[2].split("\n")
                    hunk_range_old = hunk_range_split[1]
                    hunk_range_new = hunk_range_split[2]
                    old_line_count = int(hunk_range_old.split(",")[0])
                    new_line_count = int(hunk_range_new.split(",")[0])
                except:
                    continue
                parent_change = []
                child_change = []
                for line in hunk:
                    if line.startswith("-"):
                        parent_change.append(old_line_count)
                        old_line_count += 1
                    elif line.startswith("+"):
                        child_change.append(new_line_count)
                        new_line_count += 1
                    else:
                        old_line_count += 1
                        new_line_count += 1
                changes.append({
                    "is_rename": is_rename,
                    "parent": {
                        "path": diff_item.a_path,
                        "modified_lines": parent_change
                    },
                    "child": {
                        "path": diff_item.b_path,
                        "modified_lines": child_change
                    }
                })
        # 親コミットと子コミットのハッシュを取得
        parent_hash = parent.hexsha
        child_hash = commit.hexsha
        
        # JSONファイルの保存先ディレクトリを設定
        diff_dir = project_root / "dest" / "diffs"
        diff_dir.mkdir(parents=True, exist_ok=True)
        
        # ファイル名を{親のコミットハッシュ}-{子のコミットハッシュ}.jsonの形式で作成
        diff_file = diff_dir / f"{parent_hash}-{child_hash}.json"
        
        # changesをJSONファイルとして保存
        with open(diff_file, 'w', encoding='utf-8') as f:
            json.dump(changes, f, ensure_ascii=False)
        
        print(f"変更情報を保存しました: {diff_file}")
                
        
def analyze_all_commit(url: str, languages: list[str], codebases: set[str]):
    # リポジトリの識別子とプロジェクトディレクトリの設定
    name = url.split('/')[-2] + '.' + url.split('/')[-1]
    print("--------------------------------")
    print(name)
    print("--------------------------------")
    project_dir = project_root / "dest/projects" / name
    # 言語ごとの拡張子一覧の取得
    exts = get_exts(project_dir)
    print(exts)
    # GitPythonのインスタンスの作成(分析に便利!)
    git_repo = git.Repo(str(project_dir))
    hcommit = git_repo.head.commit
    try:
        finished_commits = []
        queue = [hcommit.hexsha]
        count = 0
        # コミットを幅優先探索
        while (count <= SEARCH_DEPTH):
            commit_hash = queue.pop(0)
            commit = git_repo.commit(commit_hash)
            if commit_hash in finished_commits:
                continue
            print(f"checkout to {commit_hash}...")
            git_repo.git.checkout(commit_hash)
            # 修正を保存
            output_diff(commit)
            # 作業フォルダを作成
            temp_dir = project_root / "dest/temp" / name 
            temp_dir.mkdir(parents=True, exist_ok=True)
            for codebase in codebases:
                copy_from = project_dir / codebase
                copy_to = temp_dir / codebase
                shutil.copytree(copy_from, copy_to)
            # コードクローン検出
            for language in languages:
                detect_cc(temp_dir, name, language, commit_hash, exts[language])
            shutil.rmtree(temp_dir)
            finished_commits.append(commit_hash)
            count += 1
            for parent in commit.parents:
                queue.append(parent.hexsha)
    except Exception as e:
        print(traceback.format_exc())
        print(e)
    finally:
        print("checkout to latest commit...")
        git_repo.git.checkout(hcommit.hexsha)


def analyze_repo(project: dict):
        languages = []
        code_bases = set()
        for key in project.keys():
            if key != "URL":
                languages.append(key)
                for code_base in project[key].keys():
                    code_bases.add(code_base)
        analyze_all_commit(project["URL"], languages, code_bases)


def main():
    dataset_file = project_root / "dest/results/selected_projects.json"
    with open(dataset_file, "r") as f:
        projects = json.load(f)

    os.makedirs(project_root / "dest/code_clone", exist_ok=True)
    for project in projects:
        analyze_repo(project)


if __name__ == "__main__":
    main()