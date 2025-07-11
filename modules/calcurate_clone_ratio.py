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


ts_repo_dict = {
    "languages": {
        "Java": {
            "ts-execute-service": [
                "ts-execute-service"
            ],
            "ts-price-service": [
                "ts-price-service"
            ],
            "ts-travel-service": [
                "ts-travel-service"
            ],
            "ts-verification-code-service": [
                "ts-verification-code-service"
            ],
            "ts-travel2-service": [
                "ts-travel2-service"
            ],
            "ts-consign-service": [
                "ts-consign-service"
            ],
            "ts-user-service": [
                "ts-user-service"
            ],
            "ts-preserve-other-service": [
                "ts-preserve-other-service"
            ],
            "ts-admin-basic-info-service": [
                "ts-admin-basic-info-service"
            ],
            "ts-travel-plan-service": [
                "ts-travel-plan-service"
            ],
            "ts-basic-service": [
                "ts-basic-service"
            ],
            "ts-route-service": [
                "ts-route-service"
            ],
            "ts-admin-route-service": [
                "ts-admin-route-service"
            ],
            "ts-admin-user-service": [
                "ts-admin-user-service"
            ],
            "ts-assurance-service": [
                "ts-assurance-service"
            ],
            "ts-security-service": [
                "ts-security-service"
            ],
            "ts-cancel-service": [
                "ts-cancel-service"
            ],
            "ts-contacts-service": [
                "ts-contacts-service"
            ],
            "ts-admin-travel-service": [
                "ts-admin-travel-service"
            ],
            "ts-order-service": [
                "ts-order-service"
            ],
            "ts-consign-price-service": [
                "ts-consign-price-service"
            ],
            "ts-train-service": [
                "ts-train-service"
            ],
            "ts-admin-order-service": [
                "ts-admin-order-service"
            ],
            "ts-order-other-service": [
                "ts-order-other-service"
            ],
            "ts-food-service": [
                "ts-food-service"
            ],
            "ts-config-service": [
                "ts-config-service"
            ],
            "ts-preserve-service": [
                "ts-preserve-service"
            ],
            "ts-rebook-service": [
                "ts-rebook-service"
            ],
            "ts-notification-service": [
                "ts-notification-service"
            ],
            "ts-route-plan-service": [
                "ts-route-plan-service"
            ],
            "ts-auth-service": [
                "ts-auth-service"
            ],
            "ts-payment-service": [
                "ts-payment-service"
            ],
            "ts-seat-service": [
                "ts-seat-service"
            ],
            "ts-station-service": [
                "ts-station-service"
            ],
            "ts-inside-payment-service": [
                "ts-inside-payment-service"
            ]
        },
        "JavaScript": {
            "ts-ui-dashboard": [
                "ts-ui-dashboard"
            ],
            "ts-ticket-office-service": [
                "ts-ticket-office-service"
            ]
        }
    },
    "URL": "https://github.com/FudanSELab/train-ticket"
}


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

if __name__ == "__main__":
    name = "FudanSELab.train-ticket"
    workdir = project_root / "dest/projects" / name
    git_repo = git.Repo(str(workdir))
    hcommit = git_repo.head.commit
    languages = ts_repo_dict["languages"]
    for language in languages:
        hcommit_ccfsw_file = project_root / "dest/clones_json" / name / hcommit.hexsha / f"{language}.json"
        with open(hcommit_ccfsw_file, "r") as f:
            ccfsw_dict = json.load(f)
        file_mapper = FileMapper(ccfsw_dict["file_data"], str(workdir))
        clone_sets = filter_testing_clone_set(ccfsw_dict["clone_sets"], file_mapper)
        clone_sets = filter_cross_service_clone_set(get_latest_codebases(name), clone_sets, file_mapper)
        result = calculate_clone_ratio(clone_sets, ccfsw_dict["file_data"])
        print(result)