import sys
from pathlib import Path
import json

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import modules.clone_repo
import modules.collect_datas
import modules.analyze_cc
import modules.analyze_modification
from config import SELECTED_DATASET

if __name__ == "__main__":
    args = sys.argv
    dataset_file = SELECTED_DATASET
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    if len(args) == 1:
        for project in dataset:
            #modules.clone_repo.clone_repo(project["URL"])
            modules.collect_datas.collect_datas_of_repo(project)
            modules.analyze_cc.analyze_repo(project)
            modules.analyze_modification.analyze_repo(project)