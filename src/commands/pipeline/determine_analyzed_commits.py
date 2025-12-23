import json
import sys
from pathlib import Path

import git

def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return start


project_root = _find_repo_root(Path(__file__).resolve())
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))

from config import (
    SELECTED_DATASET,
    SELECTED_DATASET_CANDIDATES,
    ANALYSIS_FREQUENCY,
    SEARCH_DEPTH,
    ANALYSIS_METHOD,
)
import modules.clone_repo


def determine_by_frequency(workdir: Path) -> list[str]:
    """Pick commits at a fixed frequency walking back from HEAD."""
    git_repo = git.Repo(str(workdir))
    head_commit = git_repo.head.commit
    queue = [head_commit]
    target_commits: list[str] = []
    visited_hexsha: set[str] = set()
    count = 0
    while len(queue) > 0 and (SEARCH_DEPTH == -1 or count <= SEARCH_DEPTH):
        commit = queue.pop(0)
        if commit.hexsha in visited_hexsha:
            continue
        if count % ANALYSIS_FREQUENCY == 0:
            target_commits.append(commit.hexsha)
        for parent in commit.parents:
            queue.append(parent)
        count += 1
        visited_hexsha.add(commit.hexsha)
    return target_commits


def determine_by_tag(workdir: Path) -> list[str]:
    """Pick commits corresponding to the newest tags."""
    git_repo = git.Repo(str(workdir))
    tags = git_repo.tags
    tag_list = [
        {
            "tag": tag.name,
            "sha": tag.commit.hexsha,
            "date": tag.commit.committed_datetime,
        }
        for tag in tags
    ]
    tag_list.sort(key=lambda tag: tag["date"], reverse=True)

    target_commits: list[str] = []
    for count, tag in enumerate(tag_list):
        if count >= SEARCH_DEPTH:
            break
        target_commits.append(tag["sha"])
    return target_commits


def determine_analyzed_commits_by_mergecommits(workdir: Path) -> list[str]:
    """Pick newest merge commits from the remote default branch."""
    git_repo = git.Repo(str(workdir))
    remote_name = "origin"
    if remote_name not in git_repo.remotes:
        return []
    try:
        head_ref = git_repo.refs[f"{remote_name}/HEAD"]   # 例: origin/HEAD
        target = head_ref.reference    # 例: origin/main
        merge_commits_newest_first = [
            commit for commit in git_repo.iter_commits(target)
            if len(commit.parents) >= 2
        ][:5]
        return [commit.hexsha for commit in merge_commits_newest_first]
    except (IndexError, AttributeError, KeyError):
        return []


if __name__ == "__main__":
    with open(SELECTED_DATASET_CANDIDATES, "r") as f:
        dataset = json.load(f)
    analyzed_commits_dir = project_root / "dest/analyzed_commits"
    analyzed_commits_dir.mkdir(parents=True, exist_ok=True)
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
        elif ANALYSIS_METHOD == "merge_commit":
            target_commits = determine_analyzed_commits_by_mergecommits(workdir)
        if len(target_commits) >= SEARCH_DEPTH:
            target_projects.append(project)
            with open(analyzed_commits_dir / f"{name}.json", "w") as f:
                json.dump(target_commits, f)

    Path(SELECTED_DATASET).parent.mkdir(parents=True, exist_ok=True)
    with open(SELECTED_DATASET, "w") as f:
        json.dump(target_projects, f)
    print(f"選択されたプロジェクト数: {len(target_projects)}")
