import sys
import csv
from pathlib import Path
import json

import git

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
import modules.claim_parser as claim_parser
from modules.util import FileMapper
from config import SEARCH_DEPTH


#     def correspond_clonesets(self, corresponded_lines: dict, parent_clonesets: list[dict], child_clonesets: list[dict], parent_filemap: FileMapper, child_filemap: FileMapper):
#         parent_clone_map = {}
#         parent_clonesets_dict = {}
#         corresponded_clonesets = {}
#         if len(corresponded_lines) == 0:
#             return {}
#         for parent_clone_set in parent_clonesets:
#             parent_clone_id = parent_clone_set["clone_id"]
#             parent_fragments = []
#             for parent_fragment in parent_clone_set["fragments"]:
#                 parent_fragment_path = parent_filemap.get_file_path(parent_fragment["file_id"])
#                 if parent_fragment_path not in parent_clone_map.keys():
#                     parent_clone_map[parent_fragment_path] = []
#                 parent_clone_map[parent_fragment_path].append({
#                     "clone_id": parent_clone_id,
#                     "file_id": parent_fragment["file_id"],
#                     "start_line": parent_fragment["start_line"],
#                     "end_line": parent_fragment["end_line"]
#                 })
#                 parent_fragments.append({
#                     "file_path": parent_fragment_path,
#                     "start_line": parent_fragment["start_line"],
#                     "end_line": parent_fragment["end_line"]
#                 })
#             parent_clonesets_dict[parent_clone_id] = parent_fragments
        
#         for child_clone_set in child_clonesets:
#             num_child_fragments = len(child_clone_set["fragments"])
#             num_traceable_fragments = 0
#             child_clone_id = child_clone_set["clone_id"]
#             traceable_fragments = []
#             parent_clone_ids= set()
#             for child_fragment in child_clone_set["fragments"]:
#                 child_fragment_path = child_filemap.get_file_path(child_fragment["file_id"])
#                 if child_fragment_path in parent_clone_map.keys():
#                     child_start_line = child_fragment["start_line"]
#                     if child_fragment_path in corresponded_lines.keys():
#                         if child_start_line in corresponded_lines[child_fragment_path]["lines"].keys():
#                             child_start_line = corresponded_lines[child_fragment_path]["lines"][child_start_line]
#                     child_end_line = child_fragment["end_line"]
#                     if child_fragment_path in corresponded_lines.keys():
#                         if child_end_line in corresponded_lines[child_fragment_path]["lines"].keys():
#                             child_end_line = corresponded_lines[child_fragment_path]["lines"][child_end_line]
#                     for file_fragment in parent_clone_map[child_fragment_path]:
#                         if (file_fragment["start_line"] == child_start_line) and (file_fragment["end_line"] == child_end_line):
#                             traceable_fragments.append({
#                                 "clone_id": file_fragment["clone_id"],
#                                 "file_id": file_fragment["file_id"],
#                                 "start_line": file_fragment["start_line"],
#                                 "end_line": file_fragment["end_line"]
#                             })
#                             num_traceable_fragments += 1
#                             parent_clone_ids.add(file_fragment["clone_id"])
#                             break
                    
#             if (len(parent_clone_ids) == 1):
#                 if (num_traceable_fragments == num_child_fragments):
#                     if num_traceable_fragments == len(parent_clonesets_dict[list(parent_clone_ids)[0]]):
#                         corresponded_clonesets[child_clone_id] = {
#                             "type": "stable",
#                             "child": {
#                                 "clone_id": child_clone_id,
#                                 "fragments": child_clone_set["fragments"]
#                             },
#                             "parent": {
#                                 "clone_id": list(parent_clone_ids)[0],
#                                 "fragments": traceable_fragments
#                             }
#                         }
#                     elif num_traceable_fragments < len(parent_clonesets_dict[list(parent_clone_ids)[0]]):
#                         corresponded_clonesets[child_clone_id] = {
#                             "type": "remove",
#                             "child": {
#                                 "clone_id": child_clone_id,
#                                 "fragments": child_clone_set["fragments"]
#                             },
#                             "parent": {
#                                 "clone_id": list(parent_clone_ids)[0],
#                                 "fragments": parent_clonesets_dict[list(parent_clone_ids)[0]]
#                             }
#                         }
#                 elif num_traceable_fragments >= 2:
#                     corresponded_clonesets[child_clone_id] = {
#                         "type": "add",
#                         "child": {
#                             "clone_id": child_clone_id,
#                             "fragments": child_clone_set["fragments"]
#                         },
#                         "parent": {
#                             "clone_id": list(parent_clone_ids)[0],
#                             "fragments": parent_clonesets_dict[list(parent_clone_ids)[0]]
#                         }
#                     }
#         return corresponded_clonesets

#     def analyze_commit(self, commit: git.Commit):
#         print(commit.hexsha)
#         child_commit_hash = commit.hexsha
#         child_clones_file = project_root / "dest/clones_json" / self.name / child_commit_hash / f"{self.language}.json"
#         with open(child_clones_file, "r") as f:
#             child_clones = json.load(f)
#         for parent in commit.parents:      
#             parent_commit_hash = parent.hexsha
#             parent_clones_file = project_root / "dest/clones_json" / self.name / parent_commit_hash / f"{self.language}.json"
#             with open(parent_clones_file, "r") as f:
#                 parent_clones = json.load(f)
#             moving_lines_file = project_root / "dest/moving_lines" / self.name / f"{parent_commit_hash}-{child_commit_hash}.json"
#             if not moving_lines_file.exists():
#                 continue
#             with open(moving_lines_file, "r") as f:
#                 moving_lines = json.load(f)
#             parent_filemap = FileMapper(parent_clones["file_data"], str(project_root / "dest/projects" / self.name))
#             child_filemap = FileMapper(child_clones["file_data"], str(project_root / "dest/projects" / self.name))
#             corresponded_lines = self.corresponde_lines(moving_lines, child_filemap, parent_filemap)
#             corresponded_clonesets = self.correspond_clonesets(corresponded_lines, child_commit_hash, parent_commit_hash, parent_clones["clone_sets"], child_clones["clone_sets"], parent_filemap, child_filemap)
#             if len(corresponded_clonesets) == 0:
#                 continue
#             stable = 0
#             remove = 0
#             add = 0
#             for clone_id in corresponded_clonesets.keys():
#                 clone_set_type = corresponded_clonesets[clone_id]["type"]
#                 if clone_set_type == "stable":
#                     stable += 1
#                 elif clone_set_type == "remove":
#                     remove += 1
#                 elif clone_set_type == "add":
#                     add += 1
#             print(f"{child_commit_hash}-{parent_commit_hash}: {stable}/{remove}/{add}/{len(child_clones['clone_sets'])}")


class CorrespondedLines:
    def __init__(self, line_diffs: list[dict], child_filemap: FileMapper, parent_filemap: FileMapper):
        self.corresponded_lines = self._correspond_lines(line_diffs, child_filemap, parent_filemap)
        self.line_diffs = line_diffs
    
    def get_parent_line(self, child_path: str, child_line: int):
        if child_path not in self.corresponded_lines.keys():
            return child_line
        if child_line not in self.corresponded_lines[child_path]["lines"].keys():
            return child_line
        return self.corresponded_lines[child_path]["lines"][child_line]
    
    def is_file_having_moved_lines(self, child_path):
        if child_path not in self.corresponded_lines.keys():
            return False
        if len(self.corresponded_lines[child_path]["lines"].keys()) == 0:
            return False
        return True

    def _correspond_lines(self, line_diffs: list[dict], child_filemap: FileMapper, parent_filemap: FileMapper):
        result = {}
        for diff in line_diffs:
            child_path = diff["child_path"]
            child_file_loc = child_filemap.get_file_loc(child_path)
            if child_file_loc == -1:
                continue
            parent_path = diff["parent_path"]
            parent_file_loc = parent_filemap.get_file_loc(parent_path)
            if parent_file_loc == -1:
                continue
            if child_path != parent_path:
                continue
            if child_path in result.keys():
                if len(diff["inserted_lines"]) > 0:
                    for inserted_line in diff["inserted_lines"]:
                        tmp1 = result[child_path]["lines"][inserted_line]
                        result[child_path]["lines"][inserted_line] = None
                        for l in range(inserted_line+1, child_file_loc+1):
                            tmp2 = result[child_path]["lines"][l]
                            result[child_path]["lines"][l] = tmp1
                            tmp1 = tmp2
                elif len(diff["removed_lines"]) > 0:
                    for child_line in result[child_path]["lines"].keys():
                        if result[child_path]["lines"][child_line] in diff["removed_lines"]:
                            for l in range(child_line, child_file_loc):
                                result[child_path]["lines"][l] = result[child_path]["lines"][l+1]
                            result[child_path]["lines"][child_file_loc] = parent_file_loc
            else:   
                lines = {}
                if len(diff["inserted_lines"]) > 0:
                    parent_line = 1
                    for l in range(1, child_file_loc+1):
                        if l in diff["inserted_lines"]:
                            lines[l] = None
                        else:
                            lines[l] = parent_line
                            parent_line += 1
                elif len(diff["removed_lines"]) > 0:
                    child_line = 1
                    for l in range(1, parent_file_loc+1):
                        if l not in diff["removed_lines"]:
                            lines[child_line] = l
                            child_line += 1
                else:
                    continue
                result[child_path] = {
                    "lines": lines
                }


def correspond_code_fragments(corresponded_lines: CorrespondedLines, child_clonesets: list[dict], parent_clonesets: list[dict]):
    corresponded_clonesets = {}
    for child_clone_set in child_clonesets:
        has_moved_lines = False
        child_clone_id = child_clone_set["clone_id"]
        for child_fragment in child_clone_set["fragments"]:
            if not corresponded_lines.is_file_having_moved_lines(child_fragment["file_path"]):
                continue
            has_moved_lines = True
            


def analyze_commit(name: str, language: str, commit: git.Commit):
    workdir = project_root / "dest/projects" / name
    # childのCCFinderSWファイルの読み込み
    child_ccfsw_file = project_root / "dest/clones_json" / name / commit.hexsha / f"{language}.json"
    with open(child_ccfsw_file, "r") as f:
        child_ccfsw = json.load(f)
    child_filemap = FileMapper(child_ccfsw["file_data"], str(workdir))

    for parent in commit.parents:
        print(f"{commit.hexsha}-{parent.hexsha}")
        # parentのCCFinderSWファイルの読み込み
        parent_ccfsw_file = project_root / "dest/clones_json" / name / parent.hexsha / f"{language}.json"
        with open(parent_ccfsw_file, "r") as f:
            parent_ccfsw = json.load(f)
        parent_filemap = FileMapper(parent_ccfsw["file_data"], str(workdir))
        # コミット間のLineDiffファイルの読み込み
        line_diff_file = project_root / "dest/moving_lines" / name / f"{parent.hexsha}-{commit.hexsha}.json"
        with open(line_diff_file, "r") as f:
            line_diffs = json.load(f)
        # 修正がなければこのコミットの処理は終了
        if len(line_diffs) == 0:
            continue
        # CCFinderSWの対象ファイルに修正がなければ終了
        for hunk in line_diffs:
            if (child_filemap.get_file_loc(hunk["child_path"]) != -1) and (parent_filemap.get_file_loc(hunk["parent_path"]) != -1):
                break
        else:
            continue
        # 親コミットのファイルと子コミットのファイルの行を対応付ける．
        corresponded_lines = CorrespondedLines(line_diffs, child_filemap, parent_filemap)


def analyze_repo(project: dict):
    url = project["URL"]
    name = url.split("/")[-2] + "." + url.split("/")[-1]
    languages = project["languages"].keys()
    workdir = project_root / "dest/projects" / name
    git_repo = git.Repo(workdir)
    for language in languages:
        hcommit = git_repo.commit("HEAD")
        queue = [hcommit]
        finished_commits = []
        while len(queue) > 0:
            commit = queue.pop(0)
            if commit.hexsha in finished_commits:
                continue
            for parent in commit.parents:
                if parent.hexsha in finished_commits:
                    continue
                queue.append(parent)
            finished_commits.append(commit.hexsha)


if __name__ == "__main__":
    analyze_repo()