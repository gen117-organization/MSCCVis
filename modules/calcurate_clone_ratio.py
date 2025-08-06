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
    ms_detection_file = project_root / "dest/ms_detection" / f"{name}.csv"
    with open(ms_detection_file, "r") as f:
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

def filter_testing_clone_set(clone_sets: list, file_mapper: FileMapper):
    result_clone_sets = []
    for clone_set in clone_sets:
        testing_fragments = []
        production_fragments = []
        for fragment in clone_set["fragments"]:
            file_path = file_mapper.get_file_path(fragment["file_id"])
            if "test" in file_path.lower():
                testing_fragments.append(fragment)
            else:
                production_fragments.append(fragment)
        if len(testing_fragments) > 2:
            result_clone_sets.append({
                "clone_id": clone_set["clone_id"],
                "is_testing": True,
                "is_co_modified": clone_set["is_co_modified"],
                "fragments": testing_fragments,
            })
        elif len(production_fragments) > 2:
            result_clone_sets.append({
                "clone_id": clone_set["clone_id"],
                "is_testing": False,
                "is_co_modified": clone_set["is_co_modified"],
                "fragments": production_fragments,
            })
    return result_clone_sets


def filter_cross_service_clone_set(codebases: list[str], clone_sets: list[dict], file_mapper: FileMapper):
    result_clone_sets = []
    for clone_set in clone_sets:
        clone_set_codebases = set()
        for fragment in clone_set["fragments"]:
            file_path = file_mapper.get_file_path(fragment["file_id"])
            for codebase in codebases:
                if file_path.startswith(codebase):
                    clone_set_codebases.add(codebase)
        if len(clone_set_codebases) == 1:
            result_clone_sets.append({
                "clone_id": clone_set["clone_id"],
                "is_testing": clone_set["is_testing"],
                "is_cross_service": False,
                "is_co_modified": clone_set["is_co_modified"],
                "fragments": clone_set["fragments"],
            })
        elif len(clone_set_codebases) > 1:
            result_clone_sets.append({
                "clone_id": clone_set["clone_id"],
                "is_testing": clone_set["is_testing"],
                "is_co_modified": clone_set["is_co_modified"],
                "is_cross_service": True,
                "fragments": clone_set["fragments"],
            })
    return result_clone_sets

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

def filter_testing_clone_set(clone_sets: list, file_mapper: FileMapper):
    """
    クローンセットをテストコードとプロダクションコードで分類
    """
    result_clone_sets = []
    for clone_set in clone_sets:
        testing_fragments = []
        production_fragments = []
        for fragment in clone_set["fragments"]:
            file_path = file_mapper.get_file_path(fragment["file_id"])
            if "test" in file_path.lower():
                testing_fragments.append(fragment)
            else:
                production_fragments.append(fragment)
        if len(testing_fragments) > 1:
            result_clone_sets.append({
                "clone_id": clone_set["clone_id"],
                "is_testing": True,
                "is_co_modified": clone_set.get("is_co_modified", False),
                "fragments": testing_fragments,
            })
        if len(production_fragments) > 1:
            result_clone_sets.append({
                "clone_id": clone_set["clone_id"],
                "is_testing": False,
                "is_co_modified": clone_set.get("is_co_modified", False),
                "fragments": production_fragments,
            })
    return result_clone_sets

def filter_cross_service_clone_set(codebases: list[str], clone_sets: list[dict], file_mapper: FileMapper):
    """
    サービス間・サービス内で分類
    """
    result_clone_sets = []
    for clone_set in clone_sets:
        clone_set_codebases = set()
        for fragment in clone_set["fragments"]:
            file_path = file_mapper.get_file_path(fragment["file_id"])
            for codebase in codebases:
                if file_path.startswith(codebase):
                    clone_set_codebases.add(codebase)
        # サービスのコードベースに含まれていないファイルは除外
        if len(clone_set_codebases) == 0:
            continue
        if len(clone_set_codebases) == 1:
            result_clone_sets.append({
                "clone_id": clone_set["clone_id"],
                "is_testing": clone_set["is_testing"],
                "is_cross_service": False,
                "is_co_modified": clone_set.get("is_co_modified", False),
                "fragments": [f for f in clone_set["fragments"] if any(file_mapper.get_file_path(f["file_id"]).startswith(cb) for cb in codebases)],
            })
        elif len(clone_set_codebases) > 1:
            result_clone_sets.append({
                "clone_id": clone_set["clone_id"],
                "is_testing": clone_set["is_testing"],
                "is_co_modified": clone_set.get("is_co_modified", False),
                "is_cross_service": True,
                "fragments": [f for f in clone_set["fragments"] if any(file_mapper.get_file_path(f["file_id"]).startswith(cb) for cb in codebases)],
            })
    return result_clone_sets

def calculate_clone_ratio(clone_sets: list[dict], file_datas: list[dict]):
    """
    クローン率を算出
    """
    result = {}

    cross_service_file_dict = {"test": {}, "production": {}}
    within_service_file_dict = {"test": {}, "production": {}}
    for file_data in file_datas:
        file_path = file_data["file_path"]
        if "test" in file_path.lower():
            within_service_file_dict["test"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)
            cross_service_file_dict["test"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)
        else:
            within_service_file_dict["production"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)
            cross_service_file_dict["production"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)

    for clone_set in clone_sets:
        for fragment in clone_set["fragments"]:
            if clone_set["is_cross_service"]:
                if clone_set["is_testing"]:
                    for fragment in clone_set["fragments"]:
                        for line in range(int(fragment["start_line"])-1, int(fragment["end_line"])):
                            cross_service_file_dict["test"][fragment["file_id"]][line] = True
                else:
                    for fragment in clone_set["fragments"]:
                        for line in range(int(fragment["start_line"])-1, int(fragment["end_line"])):
                            cross_service_file_dict["production"][fragment["file_id"]][line] = True
            else:
                if clone_set["is_testing"]:
                    for fragment in clone_set["fragments"]:
                        for line in range(int(fragment["start_line"])-1, int(fragment["end_line"])):
                            within_service_file_dict["test"][fragment["file_id"]][line] = True
                else:
                    for fragment in clone_set["fragments"]:
                        for line in range(int(fragment["start_line"])-1, int(fragment["end_line"])):
                            within_service_file_dict["production"][fragment["file_id"]][line] = True

    # クローン率を算出する処理
    for mode in ["test", "production"]:
        within_total = 0
        within_clone = 0
        cross_total = 0
        cross_clone = 0

        # サービス内クローン
        for file_path, line_flags in within_service_file_dict[mode].items():
            within_total += len(line_flags)
            within_clone += sum(line_flags)

        # サービス間クローン
        for file_path, line_flags in cross_service_file_dict[mode].items():
            cross_total += len(line_flags)
            cross_clone += sum(line_flags)

        result[f"{mode}_within_service_clone_ratio"] = within_clone / within_total if within_total > 0 else 0
        result[f"{mode}_cross_service_clone_ratio"] = cross_clone / cross_total if cross_total > 0 else 0

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
        clone_sets = filter_testing_clone_set(hcommit_ccfsw["clone_sets"], file_mapper)
        clone_sets = filter_cross_service_clone_set(codebases, clone_sets, file_mapper)
        result[language] = calculate_clone_ratio(clone_sets, hcommit_ccfsw["file_data"])
    return result