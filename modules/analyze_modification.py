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
    print("name:", name)
    for language in project["languages"]:
        print("language:", language)
        head_commit = git_repo.head.commit
        hcommit_ccfsw_file = project_root / "dest/clones_json" / name / head_commit.hexsha / f"{language}.json"
        with open(hcommit_ccfsw_file, "r") as f:
            hcommit_ccfsw = json.load(f)
        latest_file_map = FileMapper(hcommit_ccfsw["file_data"], str(workdir))
        latest_codeclones = {}
        prev = {head_commit.hexsha: {}}
        for clone_set in hcommit_ccfsw["clone_sets"]:
            clone_id = clone_set["clone_id"]
            latest_codeclones[clone_id] = {}
            prev[head_commit.hexsha][clone_id] = {}
            for index, fragment in enumerate(clone_set["fragments"]):
                latest_codeclones[clone_id][index] = {
                    "file_path": latest_file_map.get_file_path(fragment["file_id"]),
                    "start_line": fragment["start_line"],
                    "end_line": fragment["end_line"],
                    "start_col": fragment["start_col"],
                    "end_col": fragment["end_col"],
                    "modification": []
                }
                prev[head_commit.hexsha][clone_id][index] = (clone_id, index)
        finished_commits = []
        queue = [head_commit]
        count = 0
        while len(queue) > 0 and (count <= 100):
            commit = queue.pop(0)
            print("commit:", commit.hexsha)
            if commit.hexsha in finished_commits:
                continue
            for parent in commit.parents:
                queue.append(parent)
                modified_clones_file = project_root / "dest/modified_clones" / name / f"{parent.hexsha}-{commit.hexsha}" / f"{language}.json"
                if not modified_clones_file.exists():
                    prev[parent.hexsha] = prev[commit.hexsha]
                    continue
                with open(modified_clones_file, "r") as f:
                    modified_clones = json.load(f)
                prev[parent.hexsha] = {}
                for modified_clone in modified_clones:
                    for fragment in modified_clone["fragments"]:
                        if fragment["type"] != "added":
                            if int(fragment["parent"]["clone_id"]) not in prev[parent.hexsha]:
                                prev[parent.hexsha][int(fragment["parent"]["clone_id"])] = {}
                            if (int(fragment["child"]["clone_id"]) not in prev[commit.hexsha]) or (int(fragment["child"]["index"]) not in prev[commit.hexsha][int(fragment["child"]["clone_id"])]):
                                prev[parent.hexsha][int(fragment["parent"]["clone_id"])][int(fragment["parent"]["index"])] = (None, None)
                            else:
                                prev[parent.hexsha][int(fragment["parent"]["clone_id"])][int(fragment["parent"]["index"])] = prev[commit.hexsha][int(fragment["child"]["clone_id"])][int(fragment["child"]["index"])]    
                        if (int(fragment["child"]["clone_id"]) not in prev[commit.hexsha]) or (int(fragment["child"]["index"]) not in prev[commit.hexsha][int(fragment["child"]["clone_id"])]):
                            continue
                        if fragment["type"] == "modified":
                            latest_clone_id, latest_index = prev[commit.hexsha][int(fragment["child"]["clone_id"])][int(fragment["child"]["index"])]
                            if latest_clone_id is not None and latest_index is not None:
                                latest_codeclones[latest_clone_id][latest_index]["modification"].append({"type": "modified", "commit": commit.hexsha})
                        elif fragment["type"] == "added":
                            latest_clone_id, latest_index = prev[commit.hexsha][int(fragment["child"]["clone_id"])][int(fragment["child"]["index"])]
                            if latest_clone_id is not None and latest_index is not None:
                                latest_codeclones[latest_clone_id][latest_index]["modification"].append({"type": "added", "commit": commit.hexsha})
            count += 1
            finished_commits.append(commit.hexsha)
            prev.pop(commit.hexsha)
        dest_dir = project_root / "dest/csv" / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(dest_dir / f"{language}.csv", "w") as f:
            f.write("clone_id;index;file_path;start_line;end_line;start_column;end_column;modification\n")
            for clone_id in latest_codeclones:
                for index in latest_codeclones[clone_id]:
                    modification_str = json.dumps(latest_codeclones[clone_id][index]["modification"])
                    f.write(f"{clone_id};{index};{latest_codeclones[clone_id][index]["file_path"]};{latest_codeclones[clone_id][index]["start_line"]};{latest_codeclones[clone_id][index]["end_line"]};{latest_codeclones[clone_id][index]["start_col"]};{latest_codeclones[clone_id][index]["end_col"]};{modification_str}\n")
