from pathlib import Path
import json
import sys
import os
import subprocess
import pydriller
import git
import shutil
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config import ANTLR_LANGUAGE, SEARCH_DEPTH

CCFINDERSW_JAR = project_root / "detect_cc/CCFinderSW-1.0/lib/CCFinderSW-1.0.jar"


def get_exts(name: str, language: str):
    map_file = project_root / "dest/results/map" / f"{name}.json"
    with open(map_file, "r") as f:
        map = json.load(f)

    exts = set()
    for service in map.values():
        if service["type"] == "container":
            continue
        if language not in service["files"]:
            continue
        for file in service["files"][language]:
            ext = os.path.splitext(file)[1].replace(".", "")
            if ext != "":
                exts.add(ext)

    return tuple(exts)


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
        dest_dir = project_root / "dest/code_clone" / name / commit_hash
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / language
        if language in ANTLR_LANGUAGE:
            cmd = ["java", "-jar", "-Xms16g", "-Xmx16g", "-Xss512m", str(CCFINDERSW_JAR), "D", "-d", str(project), "-l", convert_language_for_ccfindersw(language), "-o", str(dest_file), "-antlr", "|".join(exts), "-w", "2", "-ccfsw", "set"]
        else:
            cmd = ["java", "-jar", "-Xms16g", "-Xmx16g", "-Xss512m", str(CCFINDERSW_JAR), "D", "-d", str(project), "-l", convert_language_for_ccfindersw(language), "-o", str(dest_file), "-w", "2", "-ccfsw", "set"]

        subprocess.run(cmd, check=True)
    except Exception as e:
        raise e


def analyze_repo(url: str, languages: list[str], codebases: set[str]):
    # リポジトリの識別子とプロジェクトディレクトリの設定
    name = url.split('/')[-2] + '.' + url.split('/')[-1]
    project_dir = project_root / "dest/projects" / name
    # 言語ごとの拡張子一覧の取得
    exts = {}
    for language in languages:
        exts[language] = get_exts(name, language)
    # PyDrillerとGitPythonのインスタンスの作成(分析に便利!)
    repository = pydriller.Repository(str(project_dir))
    git_repo = git.Repo(str(project_dir))
    # コミットのリストの作成
    commits = []
    for commit in repository.traverse_commits():
        commits.append(commit)
    # コミットを最新順に取得するために，コミットリストを逆順にする．    
    commits.reverse()
    print("--------------------------------")
    print(name)
    print("--------------------------------")
    try:
        latest_commit = commits[0]
        finished_commits = []
        queue = [latest_commit.hash]
        count = 0
        # コミットを幅優先探索
        while (count <= SEARCH_DEPTH) or (len(queue) > 0):
            commit_hash = queue.pop(0)
            if commit_hash in finished_commits:
                continue
            print(f"checkout to {commit_hash}...")
            git_repo.git.checkout(commit_hash)
            # 作業フォルダを作成
            temp_dir = project_root / "dest/temp" / name 
            temp_dir.mkdir(parents=True, exist_ok=True)
            for codebase in codebases:
                copy_from = project_dir / codebase
                copy_to = temp_dir / codebase
                shutil.copytree(copy_from, copy_to)
            shutil.rmtree(temp_dir)
            # コードクローン検出
            for language in languages:
                detect_cc(temp_dir, name, language, commit_hash, exts[language])
            finished_commits.append(commit_hash)
            count += 1
            for parent in commit.parents:
                queue.append(parent)
    except Exception as e:
        print(e)
    finally:
        print("checkout to latest commit...")
        git_repo.git.checkout(latest_commit.hash)
        shutil.rmtree(temp_dir)


def only_latest_commit_analysis(url: str, languages: list[str], code_bases: set[str]):
    name = url.split('/')[-2] + '.' + url.split('/')[-1]
    project_dir = project_root / "dest/projects" / name
    dest_dir = project_root / "dest/latest_code_clone" / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = project_root / "dest/temp" / name
    temp_dir.mkdir(parents=True, exist_ok=True)

    for code_base in code_bases:
        copy_from = project_dir / code_base
        copy_to = temp_dir / code_base
        shutil.copytree(copy_from, copy_to)

    exts = {}
    for language in languages:
        dest = dest_dir / language
        exts[language] = get_exts(name, language)
        if language in ANTLR_LANGUAGE:
            cmd = ["java", "-jar", "-Xms16g", "-Xmx16g", "-Xss512m", str(CCFINDERSW_JAR), "D", "-d", str(temp_dir), "-l", convert_language_for_ccfindersw(language), "-o", str(dest), "-antlr", "|".join(exts[language]), "-w", "2", "-ccfsw", "set"]
        else:
            cmd = ["java", "-jar", "-Xms16g", "-Xmx16g", "-Xss512m", str(CCFINDERSW_JAR), "D", "-d", str(temp_dir), "-l", convert_language_for_ccfindersw(language), "-o", str(dest), "-w", "2", "-ccfsw", "set"]
        subprocess.run(cmd, check=True)
        
    shutil.rmtree(temp_dir)


def main():
    dataset_file = project_root / "dest/results/selected_projects.json"
    with open(dataset_file, "r") as f:
        projects = json.load(f)

    os.makedirs(project_root / "dest/code_clone", exist_ok=True)
    for project in projects:
        languages = []
        code_bases = set()
        for key in project.keys():
            if key != "URL":
                languages.append(key)
                for code_base in project[key].keys():
                    code_bases.add(code_base)
        analyze_repo(project["URL"], languages)
        # only_latest_commit_analysis(project["URL"], languages, code_bases)


if __name__ == "__main__":
    main()