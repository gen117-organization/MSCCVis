import sys
from pathlib import Path
import json

import git

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from modules.util import FileMapper


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
    
    def is_line_deleted(self, parent_path: str, parent_line: int):
        for diff in self.line_diffs:
            if diff["parent_path"] != parent_path:
                continue
            if parent_line in diff["deleted_lines"]:
                return True
        return False
    
    def is_line_added(self, child_path: str, child_line: int):
        for diff in self.line_diffs:
            if diff["child_path"] != child_path:
                continue
            if child_line in diff["inserted_lines"]:
                return True
        return False
    
    def is_line_modified(self, path: str, line: int):
        for diff in self.line_diffs:
            if diff["child_path"] != path:
                continue
            if line in diff["modified_lines"]:
                return True
        return False
    
    def get_fragment_loc_of_parent(self, child_path: str, child_start_line: int, child_end_line: int):
        if child_path not in self.corresponded_lines.keys():
            return child_end_line - child_start_line + 1
        loc = 0
        for l in range(child_start_line, child_end_line+1):
            if l not in self.corresponded_lines[child_path]["lines"].keys():
                continue
            if self.corresponded_lines[child_path]["lines"][l] is not None:
                loc += 1
        return loc

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
                elif len(diff["deleted_lines"]) > 0:
                    for child_line in result[child_path]["lines"].keys():
                        if result[child_path]["lines"][child_line] in diff["deleted_lines"]:
                            for l in range(child_line, child_file_loc):
                                result[child_path]["lines"][l] = result[child_path]["lines"][l+1]
                            if child_file_loc+1 in result[child_path]["lines"].keys():
                                result[child_path]["lines"][child_file_loc] = result[child_path]["lines"][child_file_loc+1]
                                l = child_file_loc+1
                                while True:
                                    if l in result[child_path]["lines"].keys():
                                        result[child_path]["lines"].pop(l)
                                        l += 1
                                    else:
                                        break
                            else:
                                result[child_path]["lines"][child_file_loc] = child_file_loc
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
                elif len(diff["deleted_lines"]) > 0:
                    child_line = 1
                    for l in range(1, parent_file_loc+1):
                        if l not in diff["deleted_lines"]:
                            lines[child_line] = l
                            child_line += 1
                elif len(diff["modified_lines"]) > 0:
                    child_line = 1
                    for l in range(1, parent_file_loc+1):
                        lines[child_line] = parent_line
                else:
                    continue
                result[child_path] = {
                    "lines": lines
                }
        return result

def get_clone_map(clonesets: list[dict], filemap: FileMapper):
    clone_map = {}
    for clone_set in clonesets:
        for index, fragment in enumerate(clone_set["fragments"]):
            fragment_path = filemap.get_file_path(fragment["file_id"])
            if fragment_path not in clone_map.keys():
                clone_map[fragment_path] = []
            clone_map[fragment_path].append({
                "clone_id": clone_set["clone_id"],
                "index": index,
                "file_id": fragment["file_id"],
                "start_line": fragment["start_line"],
                "end_line": fragment["end_line"],
            })
    return clone_map


def correspond_code_fragments(corresponded_lines: CorrespondedLines, child_clonesets: list[dict], parent_clonesets: list[dict], child_filemap: FileMapper, parent_filemap: FileMapper):
    corresponded_fragments = {}
    
    # コード片をファイルごとに整理する．
    parent_clone_map = get_clone_map(parent_clonesets, parent_filemap)
    
    # 子コミットのコードの移動があるクローンセットのコード片を親コミットのコード片と対応させる．
    for child_clone_set in child_clonesets:
        child_clone_id = child_clone_set["clone_id"]
        for index, child_fragment in enumerate(child_clone_set["fragments"]):
            child_fragment_path = child_filemap.get_file_path(child_fragment["file_id"])
            # ファイル名一致のパターンしか対応しないため，pathは一緒であるが一応明示しておく．
            parent_fragment_path = child_fragment_path
            # 行の移動が発生していないフラグメントは対応する必要がないのでスルー
            if not corresponded_lines.is_file_having_moved_lines(child_fragment_path):
                continue
            child_start_line = child_fragment["start_line"]
            child_end_line = child_fragment["end_line"]
            # 親コミットのクローンの開始行と終了行を予測
            predict_parent_start_line = corresponded_lines.get_parent_line(child_fragment_path, child_start_line)
            predict_parent_end_line = corresponded_lines.get_parent_line(child_fragment_path, child_end_line)
            # 無いときは確実に新規追加フラグメントなのでNoneにする．
            if child_fragment_path not in parent_clone_map.keys():
                if child_clone_id not in corresponded_fragments.keys():
                    corresponded_fragments[child_clone_id] = {}
                corresponded_fragments[child_clone_id][index] = None
                continue
            for parent_file_fragment in parent_clone_map[child_fragment_path]:
                # 親コミットのクローンの開始行と終了行が予測と一致しているものは確定
                if (parent_file_fragment["start_line"] == predict_parent_start_line) and (parent_file_fragment["end_line"] == predict_parent_end_line):
                    if child_clone_id not in corresponded_fragments.keys():
                        corresponded_fragments[child_clone_id] = {}
                    corresponded_fragments[child_clone_id][index] = (parent_file_fragment["clone_id"], parent_file_fragment["index"])
                    break
                predict_parent_fragment_loc = corresponded_lines.get_fragment_loc_of_parent(child_fragment_path, child_start_line, child_end_line)
                # 親コミットのクローンの行数が0のものは新しく作成されたクローンなのでNone
                if predict_parent_fragment_loc == 0:
                    if child_clone_id not in corresponded_fragments.keys():
                        corresponded_fragments[child_clone_id] = {}
                    corresponded_fragments[child_clone_id][index] = None
                    break
                # 完全一致はすでに対応させている．
                if (parent_file_fragment["end_line"] - parent_file_fragment["start_line"] + 1) == (child_end_line - child_start_line + 1):
                    continue
                # 子コミットの方が行数が多いパターンは子コミットのコード片の先頭または末尾に挿入されているので，親コミットの行番号を探す．
                if (parent_file_fragment["end_line"] - parent_file_fragment["start_line"] + 1) < (child_end_line - child_start_line + 1):
                    if (predict_parent_start_line is None) and (predict_parent_end_line is not None):
                        for l in range(child_start_line, child_end_line+1):
                            if corresponded_lines.get_parent_line(child_fragment_path, l) is None:
                                continue
                            if corresponded_lines.get_parent_line(child_fragment_path, l) == parent_file_fragment["start_line"]:
                                if child_clone_id not in corresponded_fragments.keys():
                                    corresponded_fragments[child_clone_id] = {}
                                corresponded_fragments[child_clone_id][index] = (parent_file_fragment["clone_id"], parent_file_fragment["index"])
                                break
                    elif (predict_parent_start_line is not None) and (predict_parent_end_line is None):
                        for l in reversed(range(child_start_line, child_end_line+1)):
                            if corresponded_lines.get_parent_line(child_fragment_path, l) is None:
                                continue
                            if corresponded_lines.get_parent_line(child_fragment_path, l) == parent_file_fragment["end_line"]:
                                if child_clone_id not in corresponded_fragments.keys():
                                    corresponded_fragments[child_clone_id] = {}
                                corresponded_fragments[child_clone_id][index] = (parent_file_fragment["clone_id"], parent_file_fragment["index"])
                                break
                    elif (predict_parent_start_line is not None) and (predict_parent_end_line is not None):
                        parent_start_line = -1
                        for l in range(child_start_line, child_end_line+1):
                            if corresponded_lines.get_parent_line(child_fragment_path, l) is None:
                                continue
                            if corresponded_lines.get_parent_line(child_fragment_path, l) == parent_file_fragment["start_line"]:
                                parent_start_line = parent_file_fragment["start_line"]
                                break
                        if parent_start_line == -1:
                            continue
                        parent_end_line = -1
                        for l in reversed(range(child_start_line, child_end_line+1)):
                            if corresponded_lines.get_parent_line(child_fragment_path, l) is None:
                                continue
                            if corresponded_lines.get_parent_line(child_fragment_path, l) == parent_file_fragment["end_line"]:
                                parent_end_line = parent_file_fragment["end_line"]
                                break
                        if parent_end_line == -1:
                            continue
                        if (parent_start_line == parent_file_fragment["start_line"]) and (parent_end_line == parent_file_fragment["end_line"]):
                            if child_clone_id not in corresponded_fragments.keys():
                                corresponded_fragments[child_clone_id] = {}
                            corresponded_fragments[child_clone_id][index] = (parent_file_fragment["clone_id"], parent_file_fragment["index"])
                            break
                # 親コミットの方が行数が多いパターンは親コミットのコード片の先頭または末尾から行が削除されているので，子コミットの行番号を探す．
                if (parent_file_fragment["end_line"] - parent_file_fragment["start_line"] + 1) > (child_end_line - child_start_line + 1):
                    predict_child_start_line = -1
                    for l in range(parent_file_fragment["start_line"], parent_file_fragment["end_line"]+1):
                        if corresponded_lines.is_line_deleted(parent_fragment_path, l):
                            continue
                        else:
                            predict_child_start_line = l
                            break
                    if predict_child_start_line == -1:
                        continue
                    predict_child_end_line = -1
                    for l in reversed(range(parent_file_fragment["start_line"], parent_file_fragment["end_line"]+1)):
                        if corresponded_lines.is_line_deleted(parent_fragment_path, l):
                            continue
                        else:
                            predict_child_end_line = l
                            break
                    if predict_child_end_line == -1:
                        continue
                    if (predict_child_start_line == child_start_line) and (predict_child_end_line == child_end_line):
                        if child_clone_id not in corresponded_fragments.keys():
                            corresponded_fragments[child_clone_id] = {}
                        corresponded_fragments[child_clone_id][index] = (parent_file_fragment["clone_id"], parent_file_fragment["index"])
                        break
    return corresponded_fragments


def identify_modified_clones(corresponded_fragments: dict, corresponded_lines: CorrespondedLines, child_clonesets: list[dict], parent_clonesets: list[dict], child_filemap: FileMapper, parent_filemap: FileMapper):
    modified_clones = []
    for child_clone_set in child_clonesets:
        child_clone_id = child_clone_set["clone_id"]
        if child_clone_id not in corresponded_fragments.keys():
            continue
        modified_clone = {
            "clone_id": child_clone_id,
            "fragments": []
        }
        for index, child_fragment in enumerate(child_clone_set["fragments"]):
            if index not in corresponded_fragments[child_clone_id].keys():
                modified_clone["fragments"].append({
                    "type": "stable",
                    "parent": child_fragment,
                    "child": child_fragment
                })
                continue
            parent_clone_id, parent_fragment_index = corresponded_fragments[child_clone_id][index]
            parent_fragment = parent_clonesets[parent_clone_id-1]["fragments"][parent_fragment_index]
            parent_modification = False
            for l in range(parent_fragment["start_line"], parent_fragment["end_line"]+1):
                if corresponded_lines.is_line_modified(parent_filemap.get_file_path(parent_fragment["file_id"]), l):
                    parent_modification = True
                    break
                if corresponded_lines.is_line_deleted(parent_filemap.get_file_path(parent_fragment["file_id"]), l):
                    parent_modification = True
                    break
            for l in range(child_fragment["start_line"], child_fragment["end_line"]+1):
                if corresponded_lines.is_line_modified(child_filemap.get_file_path(child_fragment["file_id"]), l):
                    child_modification = True
                    break
                if corresponded_lines.is_line_added(child_filemap.get_file_path(child_fragment["file_id"]), l):
                    child_modification = True
                    break
            if parent_modification and child_modification:
                modified_clone["fragments"].append({
                    "type": "modified",
                        "parent": parent_fragment,
                        "child": child_fragment
                    })
            else:
                modified_clone["fragments"].append({
                    "type": "stable",
                    "parent": parent_fragment,
                    "child": child_fragment
                })
        modified_clones.append(modified_clone)
    return modified_clones


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
        if not line_diff_file.exists():
            continue
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
        corresponded_fragments = correspond_code_fragments(corresponded_lines, child_ccfsw["clone_sets"], parent_ccfsw["clone_sets"], child_filemap, parent_filemap)

        # 修正を特定
        modified_clones = identify_modified_clones(corresponded_fragments, child_ccfsw["clone_sets"], parent_ccfsw["clone_sets"], child_filemap, parent_filemap)

        # 保存
        dest_dir = project_root / "dest/modified_clones" / name / f"{parent.hexsha}-{commit.hexsha}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(dest_dir / f"{language}.json", "w") as f:
            json.dump(modified_clones, f, indent=4)
        

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
            analyze_commit(name, language, commit)
            for parent in commit.parents:
                if parent.hexsha in finished_commits:
                    continue
                queue.append(parent)
            finished_commits.append(commit.hexsha)


if __name__ == "__main__":
    analyze_repo()