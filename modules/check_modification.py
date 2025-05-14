from pathlib import Path
import sys
import json
import os

import git

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from modules.util import FileMapper
from config import SEARCH_DEPTH


def analyze_clone_set(name: str, language: str, clone_set: dict, patchs: list, filemapper: FileMapper, hcommit_hash: str) -> dict:
    diffs_dir = project_root / "dest/diffs"
    codeclone_dir = project_root / "dest/codeclones" / name
    project_dir = project_root / "dest/temp" / name
    temp_dict = {
        hcommit_hash: {
            "clone_set": clone_set,
            "filemapper": filemapper
        }
    }
    result = {
        "latest": clone_set,
        "modification": [],
        "type": "alive"
    }
    for patch in patchs:
        child = patch[0]
        parent = patch[1]
        prev_clone_set = temp_dict[child]["clone_set"]
        prev_filemapper = temp_dict[child]["filemapper"]
        with open(diffs_dir/f"{parent}-{child}.json") as f:
            diffs = json.load(f)
        with open(codeclone_dir/parent/f"{language}.json") as f:
            parent_codeclones = json.load(f)
        stable_fragments = []
        for fragment in prev_clone_set["fragments"]:
            is_modification, modification_diff = check_fragment_modification(fragment, diffs, prev_filemapper)
            if is_modification:
                result["modification"].append({"commit": child, "fragment": fragment, "diff": modification_diff})
            else:
                stable_fragments.append(fragment)
        if len(stable_fragments) < 2:
            result["type"] = "disappear"
            return result
        parent_filemapper = FileMapper(parent_codeclones["file_data"], str(project_dir))
        exact_cs = None
        for parent_clone_set in parent_codeclones["clone_sets"]:
            for f in parent_clone_set["fragments"]:
                p = parent_filemapper.get_file_path(int(f["file_id"]))
                for sf in stable_fragments:
                    sp = prev_filemapper.get_file_path(int(sf["file_id"]))
                    if p != sp:
                        continue
                    if (sf["start_line"] == f["start_line"]) and (sf["end_line"] == f["end_line"]):
                        exact_cs = parent_clone_set
                        break
                if exact_cs is not None:
                    break
            if exact_cs is not None:
                break
        if exact_cs is None:
            result["type"] = "disappear"
            return result
        temp_dict[parent] = {
            "clone_set": exact_cs,
            "filemapper": parent_filemapper
        }

    return result        


def check_fragment_modification(fragment: dict, diffs: list, child_filemapper: FileMapper) -> tuple:
    file_path = child_filemapper.get_file_path(int(fragment["file_id"]))
    for diff in diffs:
        child = diff["child"]
        if file_path != child["path"]:
            continue
        for line_num in range(int(fragment["start_line"]), int(fragment["end_line"]) + 1):
            if line_num in child["modified_lines"]:
                return (True, diff)
    return (False, None)


def analyze_repo(project: dict):
    languages = []
    code_bases = set()
    for key in project.keys():
        if key != "URL":
            languages.append(key)
            for code_base in project[key].keys():
                code_bases.add(code_base)
    url = project["URL"]
    name = url.split('/')[-2] + '.' + url.split('/')[-1]
    project_dir = project_root / "dest/projects" / name
    git_repo = git.Repo(str(project_dir))
    hcommit = git_repo.head.commit
    queue = [hcommit]
    count = 0
    patchs = []
    while (count <= SEARCH_DEPTH):
        commit = queue.pop(0)
        for parent in commit.parents:
            queue.append(parent)
            patchs.append((commit.hexsha, parent.hexsha))
        count += 1
    for language in languages:
        result = []
        codeclone_dir = project_dir / "dest/codeclones" / name
        with open(codeclone_dir/hcommit.hexsha/f"{language}.json") as f:
            hcommit_cc = json.load(f)
        temp_dir = project_root / "dest/temp" / name
        filemapper = FileMapper(hcommit_cc["file_data"], str(temp_dir))
        for clone_set in hcommit_cc["clone_sets"]:
            result.append(analyze_clone_set(name, language, clone_set, patchs, filemapper, hcommit.hexsha))

        # 結果をJSONファイルに保存
        output_dir = project_root / f"dest/modifications"
        os.makedirs(output_dir, exist_ok=True)
        output_path = output_dir / f"{language}.json"
        
        print(f"{language}の修正情報を保存中: {output_path}")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    project = \
    """
        "Java": {
            "ts-food-service": [
                "ts-food-service"
            ],
            "ts-user-service": [
                "ts-user-service"
            ],
            "ts-consign-price-service": [
                "ts-consign-price-service"
            ],
            "ts-travel-service": [
                "ts-travel-service"
            ],
            "ts-admin-travel-service": [
                "ts-admin-travel-service"
            ],
            "ts-consign-service": [
                "ts-consign-service"
            ],
            "ts-preserve-other-service": [
                "ts-preserve-other-service"
            ],
            "ts-assurance-service": [
                "ts-assurance-service"
            ],
            "ts-cancel-service": [
                "ts-cancel-service"
            ],
            "ts-seat-service": [
                "ts-seat-service"
            ],
            "ts-admin-user-service": [
                "ts-admin-user-service"
            ],
            "ts-train-service": [
                "ts-train-service"
            ],
            "ts-execute-service": [
                "ts-execute-service"
            ],
            "ts-route-plan-service": [
                "ts-route-plan-service"
            ],
            "ts-contacts-service": [
                "ts-contacts-service"
            ],
            "ts-price-service": [
                "ts-price-service"
            ],
            "ts-admin-route-service": [
                "ts-admin-route-service"
            ],
            "ts-travel-plan-service": [
                "ts-travel-plan-service"
            ],
            "ts-config-service": [
                "ts-config-service"
            ],
            "ts-travel2-service": [
                "ts-travel2-service"
            ],
            "ts-preserve-service": [
                "ts-preserve-service"
            ],
            "ts-route-service": [
                "ts-route-service"
            ],
            "ts-payment-service": [
                "ts-payment-service"
            ],
            "ts-verification-code-service": [
                "ts-verification-code-service"
            ],
            "ts-notification-service": [
                "ts-notification-service"
            ],
            "ts-rebook-service": [
                "ts-rebook-service"
            ],
            "ts-admin-basic-info-service": [
                "ts-admin-basic-info-service"
            ],
            "ts-order-other-service": [
                "ts-order-other-service"
            ],
            "ts-admin-order-service": [
                "ts-admin-order-service"
            ],
            "ts-basic-service": [
                "ts-basic-service"
            ],
            "ts-security-service": [
                "ts-security-service"
            ],
            "ts-inside-payment-service": [
                "ts-inside-payment-service"
            ],
            "ts-station-service": [
                "ts-station-service"
            ],
            "ts-auth-service": [
                "ts-auth-service"
            ],
            "ts-order-service": [
                "ts-order-service"
            ]
        },
        "JavaScript": {
            "ts-ui-dashboard": [
                "ts-ui-dashboard"
            ],
            "ts-ticket-office-service": [
                "ts-ticket-office-service"
            ]
        },
        "URL": "https://github.com/FudanSELab/train-ticket"
    }
    """
    analyze_repo(json.loads(project))