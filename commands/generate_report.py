import sys
from pathlib import Path
import json

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config import SELECTED_DATASET
import modules.calculate_comodification_rate
import modules.calculate_clone_ratio
from modules.util import get_codeclones_classified_by_type


def main():
    """
    実験結果をまとめたレポートをmarkdown形式で生成する．
    """
    dataset_file = SELECTED_DATASET
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    results = {}
    for project in dataset:
        url = project["URL"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]
        comodification_rate = modules.calculate_comodification_rate.analyze_repo(project)
        clone_ratio = modules.calculate_clone_ratio.analyze_repo(project)
        for language in project["languages"].keys():
            clonesets = get_codeclones_classified_by_type(project, language)
            results[f"{name}_{language}"] = {}
            results[f"{name}_{language}"]["clonesets"] = clonesets
            results[f"{name}_{language}"]["comodification_rate"] = comodification_rate[language]
            results[f"{name}_{language}"]["clone_ratio"] = clone_ratio[language]

    output_lines = []

    output_lines.append("# clonesetcount")
    output_lines.append("| Project_Language | Within-Testing | Within-Production | Within-Utility | Across-Testing | Across-Production | Across-Utility |")
    output_lines.append("|--------------------|----------------|-------------------|----------------|----------------|-------------------|----------------|")
    for key, value in results.items():
        output_lines.append(f"| {key} | {len(value['clonesets']['within-testing']):,} | {len(value['clonesets']['within-production']):,} | {len(value['clonesets']['within-utility']):,} | {len(value['clonesets']['across-testing']):,} | {len(value['clonesets']['across-production']):,} | {len(value['clonesets']['across-utility']):,} |")

    output_lines.append("# withinservice")
    output_lines.append("| Project_Language | Clone Ratio (Testing) | Clone Ratio (Production) | Clone Ratio (Utility) | Comodification Rate (Testing) | Comodification Rate (Production) | Comodification Rate (Utility) |")
    output_lines.append("|--------------------|-----------------------|-------------------------|----------------------|-------------------------------|---------------------------------|-------------------------------|")

    for key, value in results.items():
        output_lines.append(f"| {key} | {value['clone_ratio']['within-testing']:3f} | {value['clone_ratio']['within-production']:3f} | {value['clone_ratio']['within-utility']:3f} | {value['comodification_rate']['within-testing']["comodification_count"]:,}/{value["comodification_rate"]["within-testing"]["count"]:,} | {value['comodification_rate']['within-production']["comodification_count"]:,}/{value['comodification_rate']['within-production']["count"]:,} | {value['comodification_rate']['within-utility']["comodification_count"]:,}/{value['comodification_rate']['within-utility']["count"]:,} |")

    output_lines.append("\n# acrossservice")
    output_lines.append("| Project_Language | Clone Ratio (Testing) | Clone Ratio (Production) | Clone Ratio (Utility) | Comodification Rate (Testing) | Comodification Rate (Production) | Comodification Rate (Utility) |")
    output_lines.append("|--------------------|-----------------------|-------------------------|----------------------|-------------------------------|---------------------------------|-------------------------------|")
    for key, value in results.items():
        output_lines.append(f"| {key} | {value['clone_ratio']['across-testing']:3f} | {value['clone_ratio']['across-production']:3f} | {value['clone_ratio']['across-utility']:3f} | {value['comodification_rate']['across-testing']["comodification_count"]:,}/{value["comodification_rate"]["across-testing"]["count"]:,} | {value['comodification_rate']['across-production']["comodification_count"]:,}/{value['comodification_rate']['across-production']["count"]:,} | {value['comodification_rate']['across-utility']["comodification_count"]:,}/{value['comodification_rate']['across-utility']["count"]:,} |")
    print("\n".join(output_lines))

if __name__ == "__main__":
    main()