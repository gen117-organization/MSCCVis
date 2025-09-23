import json
import sys
from pathlib import Path
import csv

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import modules.calculate_comodification_rate

if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    for project in dataset:
        comodification_rate = modules.calculate_comodification_rate.analyze_repo(project)
        print(comodification_rate)