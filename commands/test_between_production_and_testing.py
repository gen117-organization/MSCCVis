import sys
from pathlib import Path
import json

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import modules.calcurate_clone_ratio
import modules.calculate_comodification_rate
import scipy.stats as stats

TARGET_LANGUAGES = ("Python", "JavaScript", "TypeScript", "Java")

if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    comodification_rate_lists = {}
    clone_ratio_lists = {}
    for language in TARGET_LANGUAGES:
        clone_ratio_lists[language] = {
            "within-testing_clone_ratio": [],
            "within-production_clone_ratio": [],
            "across-testing_clone_ratio": [],
            "across-production_clone_ratio": []
        }
        comodification_rate_lists[language] = {
            "within-testing": [],
            "within-production": [],
            "across-testing": [],
            "across-production": []
        }
    for project in dataset:
        clone_ratio = modules.calcurate_clone_ratio.analyze_repo(project)
        comodification_rate = modules.calculate_comodification_rate.analyze_repo(project)
        for language in TARGET_LANGUAGES:
            if language in clone_ratio:
                for mode in clone_ratio[language]:
                    clone_ratio_lists[language][mode].append(clone_ratio[language][mode])
            if language in comodification_rate:
                for mode in comodification_rate[language]:
                    if comodification_rate[language][mode]["comodification_count"] > 0:
                        comodification_rate_lists[language][mode].append(comodification_rate[language][mode]["comodification_count"] / comodification_rate[language][mode]["count"])
                    else:
                        comodification_rate_lists[language][mode].append(0)
    for language in TARGET_LANGUAGES:
        print(f"{language} within-testing vs within-production(clone ratio): {stats.ttest_ind(clone_ratio_lists[language]["within-testing_clone_ratio"], clone_ratio_lists[language]["within-production_clone_ratio"])}")
        print(f"{language} across-testing vs across-production(clone ratio): {stats.ttest_ind(clone_ratio_lists[language]["across-testing_clone_ratio"], clone_ratio_lists[language]["across-production_clone_ratio"])}")
        print(f"{language} within-testing vs within-production(comodification rate): {stats.ttest_ind(comodification_rate_lists[language]["within-testing"], comodification_rate_lists[language]["within-production"])}")
        print(f"{language} across-testing vs across-production(comodification rate): {stats.ttest_ind(comodification_rate_lists[language]["across-testing"], comodification_rate_lists[language]["across-production"])}")