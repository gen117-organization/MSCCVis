import sys
from pathlib import Path
import json
import statistics

import git

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config import SELECTED_DATASET, ANALYSIS_FREQUENCY, SEARCH_DEPTH
import modules.clone_repo

if __name__ == "__main__":
    with open(SELECTED_DATASET, "r") as f:
        dataset = json.load(f)
    dest_dir = project_root / "dest/analyzed_commits"
    dest_dir.mkdir(parents=True, exist_ok=True)
    projects = []
    for project in dataset:
        url = project["URL"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]
        workdir = project_root / "dest/projects" / name
        modules.clone_repo.clone_repo(url)
        git_repo = git.Repo(workdir)
        head_commit = git_repo.head.commit
        queue = [head_commit]
        target_commits = []
        finished_commits = []
        count = 0
        while len(queue) > 0 and (SEARCH_DEPTH == -1 or count <= SEARCH_DEPTH):
            commit = queue.pop(0)
            if commit.hexsha in finished_commits:
                continue
            if count % ANALYSIS_FREQUENCY == 0:
                target_commits.append(commit.hexsha)
            for parent in commit.parents:
                queue.append(parent)
            count += 1
            finished_commits.append(commit.hexsha)
        projects.append(len(target_commits))
        print(f"{name} の分析コミット数: {len(target_commits)}")
        with open(dest_dir / f"{name}.json", "w") as f:
            json.dump(target_commits, f)
    print(f"平均分析コミット数: {statistics.mean(projects)}")
    print(f"最大分析コミット数: {max(projects)}")
    print(f"最小分析コミット数: {min(projects)}")
    print(f"分析コミット数の中央値: {statistics.median(projects)}")