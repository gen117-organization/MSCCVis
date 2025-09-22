import sys
from pathlib import Path
import json

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import modules.github_linguist
import modules.util

if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    for project in dataset:
        url = project["URL"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]
        workdir = project_root / "dest/projects" / name
        languages = project["languages"].keys()
        github_linguist_result = modules.github_linguist.run_github_linguist(workdir)
        print("--------------------------------")
        print(name)
        print("--------------------------------")
        for language in languages:
            print(f"[{language}]")
            result = {"total_loc": 0}
            for service in project["languages"][language]: 
                result[service] = 0
            for file in github_linguist_result[language]["files"]:
                result["total_loc"] += modules.util.calculate_loc(workdir / file)
                for service in project["languages"][language]:
                    if file.startswith(service):
                        result[service] += modules.util.calculate_loc(workdir / file)
            print(result)