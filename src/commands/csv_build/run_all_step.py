import sys
from pathlib import Path
import json


def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return start


project_root = _find_repo_root(Path(__file__).resolve())
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))

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
