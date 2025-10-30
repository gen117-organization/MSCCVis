import json
from pathlib import Path
import sys
import git

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from modules.util import get_codeclones_classified_by_type
from modules.util import calculate_loc
from modules.util import FileMapper
import modules.github_linguist


def analyze_repo(project: dict):
    url = project["URL"]
    name = url.split("/")[-2] + "." + url.split("/")[-1]
    workdir = project_root / "dest/projects" / name
    git_repo = git.Repo(workdir)
    hcommit = git_repo.head.commit.hexsha
    with open(project_root / "dest/analyzed_commits" / f"{name}.json", "r") as f:
        analyzed_commits = json.load(f)
    first_commit = analyzed_commits[0]
    languages = project["languages"]
    result = {}
    for language in languages:
        first_commit_ccfsw_file = project_root / "dest/clones_json" / name / first_commit / f"{language}.json"
        with open(first_commit_ccfsw_file, "r") as f:
            project_ccfsw_data = json.load(f)
        file_mapper = FileMapper(project_ccfsw_data["file_data"], str(workdir))
        clonesets = get_codeclones_classified_by_type(project, language)
        codebases = project["languages"][language].keys()
        file_dict = {}
        for file_data in project_ccfsw_data["file_data"]:
            file_path = file_mapper.get_file_path(file_data["file_id"])
            for codebase in codebases:
                if file_path.startswith(codebase):
                    break
            else:
                continue
            if "test" in file_path.lower():
                file_dict.setdefault("within-testing", {})
                file_dict["within-testing"][file_path] = [False] * (calculate_loc(str(workdir / file_path))+1)
                file_dict.setdefault("across-testing", {})
                file_dict["across-testing"][file_path] = [False] * (calculate_loc(str(workdir / file_path))+1)
                file_dict.setdefault("within-utility", {})
                file_dict["within-utility"][file_path] = [False] * (calculate_loc(str(workdir / file_path))+1)
                file_dict.setdefault("across-utility", {})
                file_dict["across-utility"][file_path] = [False] * (calculate_loc(str(workdir / file_path))+1)
            else:
                file_dict.setdefault("within-production", {})
                file_dict["within-production"][file_path] = [False] * (calculate_loc(str(workdir / file_path))+1)
                file_dict.setdefault("across-production", {})
                file_dict["across-production"][file_path] = [False] * (calculate_loc(str(workdir / file_path))+1)
                file_dict.setdefault("within-utility", {})
                file_dict["within-utility"][file_path] = [False] * (calculate_loc(str(workdir / file_path))+1)
                file_dict.setdefault("across-utility", {})
                file_dict["across-utility"][file_path] = [False] * (calculate_loc(str(workdir / file_path))+1)
        result_lang = {}
        for mode in clonesets.keys():
            for _clone_id, fragments in clonesets[mode].items():
                for fragment in fragments:
                    file_path = fragment["file_path"]
                    for line in range(int(fragment["start_line"])-1, int(fragment["end_line"])):
                        file_dict[mode][file_path][line] = True

            total = 0
            clone = 0
            for file_path, line_flags in file_dict.get(mode, {}).items():
                total += len(line_flags)
                clone += sum(line_flags)
            result_lang[mode] = clone / total if total > 0 else 0
        result[language] = result_lang
    git_repo.git.checkout(hcommit)
    return result