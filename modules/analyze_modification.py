import json
import sys
from pathlib import Path
import git

project_root = Path(__file__).parent.parent

sys.path.append(str(project_root))
from modules.util import FileMapper


def analyze_repo(project):
    url = project["URL"]
    name = url.split("/")[-2] + "." + url.split("/")[-1]
    workdir = project_root / "dest/projects" / name
    git_repo = git.Repo(workdir)
    for language in project["languages"]:
        head_commit = git_repo.head.commit
        hcommit_ccfsw_file = project_root / "dest/clones_json" / name / head_commit.hexsha / f"{language}.json"
        with open(hcommit_ccfsw_file, "r") as f:
            hcommit_ccfsw = json.load(f)
        latest_file_map = FileMapper(hcommit_ccfsw["file_data"], str(workdir))
        history = {head_commit.hexsha: {}}
        for clone_set in hcommit_ccfsw["clone_sets"]:
            clone_id = clone_set["clone_id"]
            history[head_commit.hexsha][clone_id] = {}
            for index, fragment in enumerate(clone_set["fragments"]):
                history[head_commit.hexsha][clone_id][index] = []
        finished_commits = []
        queue = [head_commit]
        while len(queue) > 0:
            commit = queue.pop(0)
            if commit.hexsha in finished_commits:
                continue
            for parent in commit.parents:
                modified_clones_file = project_root / "dest/modified_clones" / name / f"{parent.hexsha}-{commit.hexsha}" / f"{language}.json"
                if not modified_clones_file.exists():
                    for clone_id in history[commit.hexsha]:
                        for index in history[commit.hexsha][clone_id]:
                            history[parent.hexsha] = {clone_id: {index: []}}
                            for t in history[commit.hexsha][clone_id][index]:
                                if (t[1] is not None) and (t[2] is not None):
                                    history[commit.hexsha][clone_id][index].append((parent.hexsha, t[1], t[2]))
                    continue
                with open(modified_clones_file, "r") as f:
                    modified_clones = json.load(f)
                for modified_clone in modified_clones:
                    for fragment in modified_clone["fragments"]:
                        if fragment["type"] == "added":
                            history[commit.hexsha][int(fragment["child"]["clone_id"])][int(fragment["parent"]["index"])].append((parent.hexsha, None, None))
                        else:
                            history[commit.hexsha][int(fragment["child"]["clone_id"])][int(fragment["child"]["index"])].append((parent.hexsha, int(fragment["parent"]["clone_id"]), int(fragment["parent"]["index"])))
                            history[parent.hexsha] = {int(fragment["parent"]["clone_id"]): {int(fragment["parent"]["index"]): []}}
                queue.append(parent)
            finished_commits.append(commit.hexsha)