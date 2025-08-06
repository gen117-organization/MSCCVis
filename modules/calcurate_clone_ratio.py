import os
import json
from pathlib import Path
import sys
import csv
import git

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from modules.util import FileMapper
from modules.claim_parser import parse_uSs


def get_latest_codebases(name: str):
    """
    サービス名から最新のコードベース一覧を取得する
    """
    ms_detection_file = project_root / "dest/ms_detection" / f"{name}.csv"
    with open(ms_detection_file, "r") as f:
        import csv
        ms_detection_csv = csv.DictReader(f, delimiter=",")
        latest_row = None
        for row in ms_detection_csv:
            latest_row = row
        uSs = parse_uSs(latest_row["uSs"])
        codebases = set()
        for uS in uSs:
            context = uS["build"]["context"]
            if context is None:
                continue
            codebases.add(context)
        return list(codebases)
    

def calculate_clone_ratio(clone_sets: dict, file_datas: list[dict], file_mapper: FileMapper):
    """
    クローン率を算出
    """
    result = {}

    file_dict = {
        "within-testing": {},
        "within-production": {},
        "across-testing": {},
        "across-production": {}
    }
    for file_data in file_datas:
        file_path = file_data["file_path"]
        if "test" in file_path.lower():
            file_dict["within-testing"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)
            file_dict["across-testing"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)
        else:
            file_dict["within-production"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)
            file_dict["across-production"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)

    # クローン率を算出する処理
    for mode in ["within-testing", "within-production", "across-testing", "across-production"]:
        for _clone_id, fragments in clone_sets[mode].items():
            for fragment in fragments:
                for line in range(int(fragment["start_line"])-1, int(fragment["end_line"])):
                    file_dict[mode][fragment["file_id"]][line] = True

        total = 0
        clone = 0
        for file_id, line_flags in file_dict[mode].items():
            total += len(line_flags)
            clone += sum(line_flags)
        result[f"{mode}_clone_ratio"] = clone / total if total > 0 else 0

    return result


def analyze_repo(project: dict):
    url = project["URL"]
    name = url.split("/")[-2] + "." + url.split("/")[-1]
    workdir = project_root / "dest/projects" / name
    git_repo = git.Repo(workdir)
    head_commit = git_repo.head.commit
    languages = project["languages"]
    result = {}
    for language in languages:
        hcommit_ccfsw_file = project_root / "dest/clones_json" / name / head_commit.hexsha / f"{language}.json"
        with open(hcommit_ccfsw_file, "r") as f:
            hcommit_ccfsw = json.load(f)
        codebases = get_latest_codebases(name)
        file_mapper = FileMapper(hcommit_ccfsw["file_data"], str(workdir))
        clonesets = {
            "within-testing": {},
            "within-production": {},
            "across-testing": {},
            "across-production": {}
        }
        for clone_set in hcommit_ccfsw["clone_sets"]:
            testing_fragments = []
            production_fragments = []
            clone_id = clone_set["clone_id"]
            for fragment in clone_set["fragments"]:
                file_path = file_mapper.get_file_path(fragment["file_id"])
                if "test" in file_path.lower():
                    testing_fragments.append(fragment)
                else:
                    production_fragments.append(fragment)
            testing_sets = set()
            for fragment in testing_fragments:
                file_path = file_mapper.get_file_path(fragment["file_id"])
                for codebase in codebases:
                    if file_path.startswith(codebase):
                        testing_sets.add(codebase)
            if len(testing_sets) == 1:
                if len(testing_fragments) >= 2:
                    clonesets["within-testing"][clone_id] = testing_fragments
            elif len(testing_sets) >= 2:
                if len(testing_fragments) >= 2:
                    clonesets["across-testing"][clone_id] = testing_fragments
            production_sets = set()
            for fragment in production_fragments:
                file_path = file_mapper.get_file_path(fragment["file_id"])
                for codebase in codebases:
                    if file_path.startswith(codebase):
                        production_sets.add(codebase)
            if len(production_sets) == 1:
                if len(production_fragments) >= 2:
                    clonesets["within-production"][clone_id] = production_fragments
            elif len(production_sets) >= 2:
                if len(production_fragments) >= 2:
                    clonesets["across-production"][clone_id] = production_fragments
        result[language] = calculate_clone_ratio(clonesets, hcommit_ccfsw["file_data"])
    return result