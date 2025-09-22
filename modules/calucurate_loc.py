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
            production_result = {"total_loc": 0}
            testing_result = {"total_loc": 0}
            for service in project["languages"][language]: 
                production_result[service] = 0
                testing_result[service] = 0
            for file in github_linguist_result[language]["files"]:
                if "test" in file.lower():
                    for service in project["languages"][language]:
                        if file.startswith(service):
                            testing_result["total_loc"] += modules.util.calculate_loc(workdir / file)
                            testing_result[service] += modules.util.calculate_loc(workdir / file)
                else:
                    for service in project["languages"][language]:
                        if file.startswith(service):
                            production_result["total_loc"] += modules.util.calculate_loc(workdir / file)
                            production_result[service] += modules.util.calculate_loc(workdir / file)
            print(f"[{language} - production] {production_result['total_loc']}")
            for service in production_result:
                print(f"| {service} | {production_result[service]} |")
            print(f"[{language} - testing] {testing_result['total_loc']}")
            for service in testing_result:
                print(f"| {service} | {testing_result[service]} |")