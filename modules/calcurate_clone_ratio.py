import os
import json
from pathlib import Path
import sys
import csv
import git

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from modules.util import get_codeclones_classified_by_type
import modules.github_linguist

# def calculate_clone_ratio(clone_sets: dict, file_datas: list[dict], file_mapper: FileMapper):
#     """
#     クローン率を算出
#     """
#     result = {}

#     file_dict = {
#         "within-testing": {},
#         "within-production": {},
#         "across-testing": {},
#         "across-production": {}
#     }
#     for file_data in file_datas:
#         file_path = file_data["file_path"]
#         if "test" in file_path.lower():
#             file_dict["within-testing"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)
#             file_dict["across-testing"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)
#         else:
#             file_dict["within-production"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)
#             file_dict["across-production"][file_data["file_id"]] = [False] * (int(file_data["loc"])+1)

#     # クローン率を算出する処理
#     for mode in ["within-testing", "within-production", "across-testing", "across-production"]:
#         for _clone_id, fragments in clone_sets[mode].items():
#             for fragment in fragments:
#                 for line in range(int(fragment["start_line"])-1, int(fragment["end_line"])):
#                     file_dict[mode][fragment["file_id"]][line] = True

#         total = 0
#         clone = 0
#         for file_id, line_flags in file_dict[mode].items():
#             total += len(line_flags)
#             clone += sum(line_flags)
#         result[f"{mode}_clone_ratio"] = clone / total if total > 0 else 0

#     return result


def analyze_repo(project: dict):
    url = project["URL"]
    name = url.split("/")[-2] + "." + url.split("/")[-1]
    workdir = project_root / "dest/projects" / name
    git_repo = git.Repo(workdir)
    hcommit = git_repo.head.commit.hexsha
    with open(project_root / "dest/analyzed_commits" / f"{name}.json", "r") as f:
        analyzed_commits = json.load(f)
    git_repo
    languages = project["languages"]
    result = {}
    
    for language in languages:
        clonesets = get_codeclones_classified_by_type(project, language)
        result_lang = {}
        for mode in clonesets.keys():
            pass