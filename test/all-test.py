import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent

sys.path.append(str(project_root))
import modules.clone_repo
import modules.identify_microservice
import modules.collect_datas
import modules.analyze_cc
import modules.analyze_modification

if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    outputs = []
    for project in dataset:
        url = project["URL"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]
        workdir = project_root / "dest/projects" / name
        #modules.clone_repo.clone_repo(url)
        #modules.identify_microservice.analyze_repo(url, name, str(workdir))
        modules.collect_datas.collect_datas_of_repo(project)
        modules.analyze_cc.analyze_repo(project)
        #result = modules.analyze_modification.analyze_repo(project)