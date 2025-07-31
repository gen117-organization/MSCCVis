import json
import sys
from pathlib import Path
import csv

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


def analyze_repo(project):
    url = project["URL"]
    name = url.split("/")[-2] + "." + url.split("/")[-1]
    languages = project["languages"]
    for language in languages:
        with open(project_root / "dest/csv" / name / f"{language}.csv", "r") as f:
            reader = csv.DictReader(f, delimiter=";")
            clonesets = {
                "within-testing": {},
                "within-production": {},
                "across-testing": {},
                "across-production": {}
            }
            temp = {}
            codebases = project["languages"][language]
            for row in reader:
                clone_id = row["clone_id"]
                if clone_id not in temp:
                    temp[clone_id] = []
                temp[clone_id].append(row)
            for clone_id, rows in temp.items():
                testing_fragments = []
                production_fragments = []
                for row in rows:
                    path = row["file_path"]
                    if "test" in path:
                        testing_fragments.append(row)
                    else:
                        production_fragments.append(row)
                testing_sets = set()
                for fragment in testing_fragments:
                    for codebase in codebases:
                        if fragment["file_path"].startswith(codebase):
                            testing_sets.add(codebase)
                if len(testing_sets) == 1:
                    if len(testing_fragments) >= 2:
                        clonesets["within-testing"][clone_id] = testing_fragments
                elif len(testing_sets) >= 2:
                    if len(testing_fragments) >= 2:
                        clonesets["across-testing"][clone_id] = testing_fragments
                production_sets = set()
                for fragment in production_fragments:
                    for codebase in codebases:
                        if fragment["file_path"].startswith(codebase):
                            production_sets.add(codebase)
                if len(production_sets) == 1:
                    if len(production_fragments) >= 2:
                        clonesets["within-production"][clone_id] = production_fragments
                elif len(production_sets) >= 2:
                    if len(production_fragments) >= 2:
                        clonesets["across-production"][clone_id] = production_fragments
            result = {
                "within-testing": {
                    "count": 0,
                    "comodification_count": 0
                },
                "within-production": {
                    "count": 0,
                    "comodification_count": 0
                },
                "across-testing": {
                    "count": 0,
                    "comodification_count": 0
                },
                "across-production": {
                    "count": 0,
                    "comodification_count": 0
                }
            }
            for clone_id, fragments in clonesets["within-testing"].items():
                result["within-testing"]["count"] += 1
                modifications = {}
                for fragment in fragments:
                    m_list = json.loads(fragment["modification"])
                    for m in m_list:
                        if m["commit"] not in modifications:
                            modifications[m["commit"]] = []
                        modifications[m["commit"]].append(m["type"])
                for commit, types in modifications.items():
                    if types.count("modified") >= 2:
                        result["within-testing"]["comodification_count"] += 1
            for clone_id, fragments in clonesets["within-production"].items():
                result["within-production"]["count"] += 1
                modifications = {}
                for fragment in fragments:
                    m_list = json.loads(fragment["modification"])
                    for m in m_list:
                        if m["commit"] not in modifications:
                            modifications[m["commit"]] = []
                        modifications[m["commit"]].append(m["type"])
                for commit, types in modifications.items():
                    if types.count("modified") >= 2:
                        result["within-production"]["comodification_count"] += 1
            for clone_id, fragments in clonesets["across-testing"].items():
                result["across-testing"]["count"] += 1
                modifications = {}
                for fragment in fragments:
                    m_list = json.loads(fragment["modification"])
                    for m in m_list:
                        if m["commit"] not in modifications:
                            modifications[m["commit"]] = []
                        modifications[m["commit"]].append(m["type"])
                for commit, types in modifications.items():
                    if types.count("modified") >= 2:
                        result["across-testing"]["comodification_count"] += 1
            for clone_id, fragments in clonesets["across-production"].items():
                result["across-production"]["count"] += 1
                modifications = {}
                for fragment in fragments:
                    m_list = json.loads(fragment["modification"])
                    for m in m_list:
                        if m["commit"] not in modifications:
                            modifications[m["commit"]] = []
                        modifications[m["commit"]].append(m["type"])
                for commit, types in modifications.items():
                    if types.count("modified") >= 2:
                        result["across-production"]["comodification_count"] += 1
            print("[within-testing]")
            if result['within-testing']['count'] > 0:
                print(f"{name} {language} {result['within-testing']['comodification_count']} / {result['within-testing']['count']} = {result['within-testing']['comodification_count'] / result['within-testing']['count']}")
            else:
                print(f"{name} {language} 0 / 0 = 0")
            print("[within-production]")
            if result['within-production']['count'] > 0:
                print(f"{name} {language} {result['within-production']['comodification_count']} / {result['within-production']['count']} = {result['within-production']['comodification_count'] / result['within-production']['count']}")
            else:
                print(f"{name} {language} 0 / 0 = 0")
            print("[across-testing]")
            if result['across-testing']['count'] > 0:
                print(f"{name} {language} {result['across-testing']['comodification_count']} / {result['across-testing']['count']} = {result['across-testing']['comodification_count'] / result['across-testing']['count']}")
            else:
                print(f"{name} {language} 0 / 0 = 0")
            print("[across-production]")
            if result['across-production']['count'] > 0:
                print(f"{name} {language} {result['across-production']['comodification_count']} / {result['across-production']['count']} = {result['across-production']['comodification_count'] / result['across-production']['count']}")
            else:
                print(f"{name} {language} 0 / 0 = 0")

if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    for project in dataset:
        analyze_repo(project)