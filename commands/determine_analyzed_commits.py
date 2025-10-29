import sys
from pathlib import Path
import json

import git

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config import SELECTED_DATASET, ANALYSIS_FREQUENCY, SEARCH_DEPTH, ANALYSIS_METHOD
import modules.clone_repo


def determine_by_frequency(workdir: Path) -> list[str]:
    git_repo = git.Repo(str(workdir))
    head_commit = git_repo.head.commit
    target_commits = []
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
    return target_commits


def determine_by_tag(workdir: Path) -> list[str]:
    git_repo = git.Repo(str(workdir))
    tags = git_repo.tags
    target_commits = []
    count = 0
    tag_list = []
    for tag in tags:
        commit = tag.commit
        tag_list.append({
            "tag": tag.name,
            "sha": commit.hexsha,
            "date": commit.committed_datetime
        })
    # コミット日時の新しい順（降順）にソート
    tag_list.sort(key=lambda x: x["date"], reverse=True)
    for tag in tag_list:
        if count >= SEARCH_DEPTH:
            break
        target_commits.append(tag["sha"])
        count += 1
    return target_commits


if __name__ == "__main__":
    with open(SELECTED_DATASET, "r") as f:
        dataset = json.load(f)
    dest_dir = project_root / "dest/analyzed_commits"
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_projects = []
    for project in dataset:
        url = project["URL"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]
        workdir = project_root / "dest/projects" / name
        modules.clone_repo.clone_repo(url)
        if ANALYSIS_METHOD == "frequency":
            target_commits = determine_by_frequency(workdir)
        elif ANALYSIS_METHOD == "tag":
            target_commits = determine_by_tag(workdir)
        if len(target_commits) >= SEARCH_DEPTH:
            target_projects.append(project)
            with open(dest_dir / f"{name}.json", "w") as f:
                json.dump(target_commits, f)
    dest_dir = project_root / "dest"
    with open(dest_dir / "selected_projects.json", "w") as f:
        json.dump(target_projects, f)
    print(f"選択されたプロジェクト数: {len(target_projects)}")