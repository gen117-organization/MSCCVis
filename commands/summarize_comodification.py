import json
import sys
from pathlib import Path

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
        url = project["URL"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]
        for language in comodification_rate:
            if language not in results:
                results[language] = {
                    "within-testing": [],
                    "within-production": [],
                    "across-testing": [],
                    "across-production": []
                }
            flag = False
            for mode in comodification_rate[language]:
                if comodification_rate[language][mode]["count"] > 0:
                    results[language][mode].append(comodification_rate[language][mode]["comodification_count"] / comodification_rate[language][mode]["count"])
                else:
                    results[language][mode].append(0)
    for language in results:
        print(f"{language}: {len(results[language])}")
        for mode in results[language]:
            print(f"{mode}: max_{max(results[language][mode]):.3f}, min_{min(results[language][mode]):.3f}")