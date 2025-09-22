import sys
from pathlib import Path
import json
import csv

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects-mo.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    for project in dataset:
        url = project["URL"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]
        workdir = project_root / "dest/projects" / name
        languages = project["languages"].keys()
        for language in languages:
            with open(project_root / "dest/csv" / name / f"{language}.csv", "r") as f:
                reader = csv.DictReader(f, delimiter=";")
                temp = {}
                for row in reader:
                    clone_id = row["clone_id"]
                    if clone_id not in temp:
                        temp[clone_id] = []
                    temp[clone_id].append(row)
                clonesets = {
                    "within-testing": {},
                    "within-production": {},
                    "across-testing": {},
                    "across-production": {}
                }
                for clone_id, fragments in temp.items():
                    testing_fragments = []
                    production_fragments = []
                    for fragment in fragments:
                        if "test" in fragment["file_path"]:
                            testing_fragments.append(fragment)
                        else:
                            production_fragments.append(fragment)
                    testing_sets = set()
                    for fragment in testing_fragments:
                        for codebase in project["languages"][language]:
                            if fragment["file_path"].startswith(codebase):
                                testing_sets.add(codebase)
                    production_sets = set()
                    for fragment in production_fragments:
                        for codebase in project["languages"][language]:
                            if fragment["file_path"].startswith(codebase):
                                production_sets.add(codebase)
                    if len(testing_sets) == 1:
                        if len(testing_fragments) >= 2:
                            clonesets["within-testing"][clone_id] = testing_fragments
                    elif len(testing_sets) >= 2:
                        if len(testing_fragments) >= 2:
                            clonesets["across-testing"][clone_id] = testing_fragments
                    if len(production_sets) == 1:
                        if len(production_fragments) >= 2:
                            clonesets["within-production"][clone_id] = production_fragments
                    elif len(production_sets) >= 2:
                        if len(production_fragments) >= 2:
                            clonesets["across-production"][clone_id] = production_fragments
                for clone_id, fragments in clonesets["within-testing"].items():
                    modifications = {}
                    for fragment in fragments:
                        m_list = json.loads(fragment["modification"])
                        for m in m_list:
                            if m["commit"] not in modifications:
                                modifications[m["commit"]] = []
                            modifications[m["commit"]].append(m["type"])
                    for commit, types in modifications.items():
                        if types.count("modified") >= 2:
                            print(f"within-testing:{clone_id}")
                            print("---")
                            for fragment in fragments:
                                print(f"    {fragment["file_path"]}:{fragment["start_line"]}-{fragment["end_line"]}, ({fragment["modification"]})")
                            break
                for clone_id, fragments in clonesets["within-production"].items():
                    modifications = {}
                    for fragment in fragments:
                        m_list = json.loads(fragment["modification"])
                        for m in m_list:
                            if m["commit"] not in modifications:
                                modifications[m["commit"]] = []
                            modifications[m["commit"]].append(m["type"])
                    for commit, types in modifications.items():
                        if types.count("modified") >= 2:
                            print(f"within-production: {clone_id}")
                            print("---")
                            for fragment in fragments:
                                print(f"    {fragment["file_path"]}:{fragment["start_line"]}-{fragment["end_line"]}, ({fragment["modification"]})")
                            break
                for clone_id, fragments in clonesets["across-testing"].items():
                    modifications = {}
                    for fragment in fragments:
                        m_list = json.loads(fragment["modification"])
                        for m in m_list:
                            if m["commit"] not in modifications:
                                modifications[m["commit"]] = []
                            modifications[m["commit"]].append(m["type"])
                    for commit, types in modifications.items():
                        if types.count("modified") >= 2:
                            print(f"across-testing: {clone_id}")
                            print("---")
                            for fragment in fragments:
                                print(f"    {fragment["file_path"]}:{fragment["start_line"]}-{fragment["end_line"]}, ({fragment["modification"]})")
                            break
                for clone_id, fragments in clonesets["across-production"].items():
                    modifications = {}
                    for fragment in fragments:
                        m_list = json.loads(fragment["modification"])
                        for m in m_list:
                            if m["commit"] not in modifications:
                                modifications[m["commit"]] = []
                            modifications[m["commit"]].append(m["type"])
                    for commit, types in modifications.items():
                        if types.count("modified") >= 2:
                            print(f"across-production: {clone_id}")
                            print("---")
                            for fragment in fragments:
                                print(f"    {fragment["file_path"]}:{fragment["start_line"]}-{fragment["end_line"]}, ({fragment["modification"]})")
                            break