from pathlib import Path
import sys
import subprocess
import git
import traceback
import json

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from modules.github_linguist import get_exts, run_github_linguist
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


def find_moving_lines(commit: git.Commit, name: str) -> dict:
    return_result = {}
    for parent_commit in commit.parents:
        diff_hunks = parent_commit.diff(commit, create_patch=True)
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
                potential_inserted_lines = []
                potential_deleted_lines = []
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
            dest_file = dest_dir / f"{parent_commit.hexsha}-{commit.hexsha}.json"
            with open(dest_file, "w") as f:
                json.dump(output_result, f)
            return_result[parent_commit.hexsha] = output_result
    return return_result
                

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
            cmd = ["java", "-jar", "-Xmx20G", "-Xss128m", str(CCFINDERSW_JAR), "D", "-d", str(project), "-l", convert_language_for_ccfindersw(language), "-o", str(dest_file), "-antlr", "|".join(exts), "-w", "2", "-ccfsw", "set"]
        else:
            cmd = ["java", "-jar" , "-Xmx20G" , "-Xss128m", str(CCFINDERSW_JAR), "D", "-d", str(project), "-l", convert_language_for_ccfindersw(language), "-o", str(dest_file), "-w", "2", "-ccfsw", "set"]
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
    for language in languages:
        detect_cc(project_dir, name, language, hcommit.hexsha, exts[language])
    try:
        finished_commits = []
        detected_commits = {}
        need_to_detect_commits = {}
        queue = [hcommit.hexsha]
        count = 0
        # コミットを幅優先探索
        while (len(queue) > 0) and (count <= 110):
            commit_hash = queue.pop(0)
            commit = git_repo.commit(commit_hash)
            if commit_hash in finished_commits:
                continue
            print(f"checkout to {commit_hash}...")
            git_repo.git.checkout(commit_hash)
            # 修正を保存
            moving_lines = find_moving_lines(commit, name)
            if len(moving_lines) == 0:
                continue
            # github-linguistの適用
            github_linguist_result = run_github_linguist(str(project_dir))
            languages = github_linguist_result.keys()
            github_linguist_dest_dir = project_root / "dest/github_linguist" / name
            github_linguist_dest_dir.mkdir(parents=True, exist_ok=True)
            github_linguist_dest_file = github_linguist_dest_dir / f"{commit_hash}.json"
            with open(github_linguist_dest_file, "w") as f:
                json.dump(github_linguist_result, f)
            detectable_languages = project["languages"].keys()
            # コードクローン検出
            for language in languages:
                if language not in detectable_languages:
                    continue
                if language not in detected_commits.keys():
                    detected_commits[language] = []
                if language not in need_to_detect_commits.keys():
                    need_to_detect_commits[language] = set()
                # 既に検出していれば次に行く
                if commit_hash in detected_commits[language]:
                    continue
                if commit_hash == hcommit.hexsha:
                    detect_cc(project_dir, name, language, commit_hash, exts[language])
                    detected_commits[language].append(commit_hash)
                    continue
                # まだCCFinderSWを実行していないコミットで必要な場合は実行する
                if commit_hash in need_to_detect_commits[language]:
                    detect_cc(project_dir, name, language, commit_hash, exts[language])
                    detected_commits[language].append(commit_hash)
                    need_to_detect_commits[language].remove(commit_hash)
                    continue
                # この言語のファイルの修正が含まれているか判定する
                is_modified = False
                for parent_hash in moving_lines.keys():
                    moving_lines_of_parent = moving_lines[parent_hash]
                    for moving_line in moving_lines_of_parent:
                        if moving_line["child_path"] in github_linguist_result[language]["files"]:
                            is_modified = True
                            break
                    if is_modified:
                        if language not in need_to_detect_commits.keys():
                            need_to_detect_commits[language] = set()
                        need_to_detect_commits[language].add(parent_hash)
                if is_modified:
                    detect_cc(project_dir, name, language, commit_hash, exts[language])
                    detected_commits[language].append(commit_hash)
            finished_commits.append(commit_hash)
            count += 1
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