import sys
from pathlib import Path
import matplotlib.pyplot as plt
import json
import git

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import calculate_comodification_rate
import calcurate_clone_ratio


if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
        for project in dataset:
            url = project["URL"]
            name = url.split("/")[-2] + "." + url.split("/")[-1]
            git_repo = git.Repo(project_root / "dest/projects" / name)
            head_commit = git_repo.head.commit
            comodification_rate = calculate_comodification_rate.analyze_repo(project)
            print(comodification_rate)
            for language in project["languages"]:
                hcommit_ccfsw_file = project_root / "dest/clones_json" / name / head_commit.hexsha / f"{language}.json"
                with open(hcommit_ccfsw_file, "r") as f:
                    hcommit_ccfsw = json.load(f)
                clone_ratio = calcurate_clone_ratio.calculate_clone_ratio(hcommit_ccfsw["clone_sets"], hcommit_ccfsw["file_data"])
                print(clone_ratio)
                