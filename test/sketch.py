import sys
from pathlib import Path
import json
import csv

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    total = 0
    no_detected = 0
    for project in dataset:
        url = project["URL"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]
        for language in project["languages"]:
            clones_csv = project_root / "dest/csv" / name / f"{language}.csv"
            with open(clones_csv, "r") as f:
                reader = csv.DictReader(f, delimiter=";")
                count = 0
                for row in reader:
                    count += 1
                if count == 0:
                    no_detected += 1
                total += 1
    print(f"total: {total} no_detected: {no_detected}")

