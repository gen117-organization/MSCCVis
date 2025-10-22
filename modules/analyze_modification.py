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
        with open(project_root / "dest/analyzed_commits" / f"{name}.json", "r") as f:
            analyzed_commit_hashes = json.load(f)
        head_commit = git_repo.commit(analyzed_commit_hashes[0])
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
        prev_commit = head_commit
        count = 0
        for commit_hash in analyzed_commit_hashes:
            if count > 5:
                break
            if commit_hash == head_commit.hexsha:
                count += 1
                continue
            commit = git_repo.commit(commit_hash)
            print("commit:", commit.hexsha)
            modified_clones_file = project_root / "dest/modified_clones" / name / f"{commit.hexsha}-{prev_commit.hexsha}" / f"{language}.json"
            if not modified_clones_file.exists():
                prev[commit.hexsha] = prev[prev_commit.hexsha]
                count += 1
                continue
            with open(modified_clones_file, "r") as f:
                modified_clones = json.load(f)
            prev[commit.hexsha] = {}
            for modified_clone in modified_clones:
                for fragment in modified_clone["fragments"]:
                    if fragment["type"] != "added":
                        prev[commit.hexsha].setdefault(int(fragment["parent"]["clone_id"]), {})
                        # 子コミットの対応が取れていなければNoneにして辿るのをやめる．
                        if (int(fragment["child"]["clone_id"]) not in prev[prev_commit.hexsha]) or (int(fragment["child"]["index"]) not in prev[prev_commit.hexsha][int(fragment["child"]["clone_id"])]):
                            prev[commit.hexsha][int(fragment["parent"]["clone_id"])][int(fragment["parent"]["index"])] = (None, None)
                        # 子コミットの対応が取れていれば親コミットに引き継ぐ
                        else:
                            prev[commit.hexsha][int(fragment["parent"]["clone_id"])][int(fragment["parent"]["index"])] = prev[prev_commit.hexsha][int(fragment["child"]["clone_id"])][int(fragment["child"]["index"])]    
                    if (int(fragment["child"]["clone_id"]) not in prev[commit.hexsha]) or (int(fragment["child"]["index"]) not in prev[commit.hexsha][int(fragment["child"]["clone_id"])]):
                        continue
                    if fragment["type"] == "modified":
                        latest_clone_id, latest_index = prev[prev_commit.hexsha][int(fragment["child"]["clone_id"])][int(fragment["child"]["index"])]
                        if latest_clone_id is not None and latest_index is not None:
                            latest_codeclones[latest_clone_id][latest_index]["modification"].append({"type": "modified", "commit": commit.hexsha})
                    elif fragment["type"] == "added":
                        latest_clone_id, latest_index = prev[prev_commit.hexsha][int(fragment["child"]["clone_id"])][int(fragment["child"]["index"])]
                        if latest_clone_id is not None and latest_index is not None:
                            latest_codeclones[latest_clone_id][latest_index]["modification"].append({"type": "added", "commit": commit.hexsha})
            count += 1
            prev_commit = commit
        dest_dir = project_root / "dest/csv" / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(dest_dir / f"{language}.csv", "w") as f:
            f.write("clone_id;index;file_path;start_line;end_line;start_column;end_column;modification\n")
            for clone_id in latest_codeclones:
                for index in latest_codeclones[clone_id]:
                    modification_str = json.dumps(latest_codeclones[clone_id][index]["modification"])
                    f.write(f"{clone_id};{index};{latest_codeclones[clone_id][index]["file_path"]};{latest_codeclones[clone_id][index]["start_line"]};{latest_codeclones[clone_id][index]["end_line"]};{latest_codeclones[clone_id][index]["start_col"]};{latest_codeclones[clone_id][index]["end_col"]};{modification_str}\n")
