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
            reader = csv.DictReader(f)
        clonesets = {}
        for row in reader:
            clone_id = row["clone_id"]
            if clone_id not in clonesets:
                clonesets[clone_id] = []
            clonesets[clone_id].append(row)
        count = 0
        comodification_count = 0
        for clone_id, rows in clonesets.items():
            modifications = {}
            for row in rows:
                for m in row["modification"]:
                    if m["commit"] not in modifications:
                        modifications[m["commit"]] = []
                    modifications[m["commit"]].append(m["type"])
            comodification = False
            for commit, types in modifications.items():
                if types.count("modified") >= 2:
                    comodification = True
            if comodification:
                comodification_count += 1
            count += 1
        print(f"{name} {language} {comodification_count} / {count} = {comodification_count / count}")

if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    for project in dataset:
        analyze_repo(project)