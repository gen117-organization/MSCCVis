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
    results = {}
    for project in dataset:
        comodification_rate = modules.calculate_comodification_rate.analyze_repo(project)
        for language in comodification_rate:
            if language not in results:
                results[language] = {
                    "within-testing": 0,
                    "within-production": 0,
                    "across-testing": 0,
                    "across-production": 0
                }
            for mode in comodification_rate[language]:
                if comodification_rate[language][mode]["comodification_count"] > 0:
                    results[language][mode] += 1
    print(results)