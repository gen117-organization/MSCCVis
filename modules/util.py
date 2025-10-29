import sys
import csv
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


class FileMapper:
    def __init__(self, files: list, project_dir: str) -> None:
        self.id_to_path = {}
        self.path_to_id = {}
        self.file_loc = {}
        for file in files:
            file_id = int(file["file_id"])
            path = str(file["file_path"]).replace(project_dir+"/", "")
            self.id_to_path[file_id] = path
            self.path_to_id[path] = file_id
            self.file_loc[path] = int(file["loc"])
    
    def get_file_id(self, path: str) -> int:
        return self.path_to_id[path]
    
    def get_file_path(self, file_id: int) -> str:
        return self.id_to_path[file_id]
    
    def get_file_loc(self, path: str) -> int:
        if path not in self.file_loc.keys():
            return -1
        return self.file_loc[path]


def calculate_loc(file_path: str) -> int:
    with open(file_path, "r") as f:
        return len(f.readlines())
    

def get_codeclones_classified_by_type(project: dict, language: str) -> dict:
    """
    クローンをコード種別・検出範囲ごとに分類して返す．
    """
    name = project["URL"].split("/")[-2] + "." + project["URL"].split("/")[-1]
    temp = {}
    with open(project_root / "dest/csv" / name / f"{language}.csv", "r") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            clone_id = row["clone_id"]
            temp.setdefault(clone_id, [])
            temp[clone_id].append(row)

    clonesets = {
        "within-testing": {},
        "within-production": {},
        "within-utility": {},
        "across-testing": {},
        "across-production": {},
        "across-utility": {}
    }

    codebases = project["languages"][language]
    for clone_id, fragments in temp.items():
        is_testing = False
        is_production = False
        for row in fragments:
            path = row["file_path"]
            if "test" in path:
                is_testing = True    
            else:
                is_production = True
        service_set = set()
        service_fragments = []
        for fragment in fragments:
            for codebase in codebases:
                if fragment["file_path"].startswith(codebase):
                    service_set.add(codebase)
                    service_fragments.append(fragment)

        # 有効なフラグメントがなければスキップ
        if len(service_fragments) <= 1:
            continue

        # 検出範囲の決定
        if len(service_set) == 1:
            range_name = "within"
        elif len(service_set) >= 2:
            range_name = "across"
        else:
            continue

        # コード種別の決定
        if is_testing and not is_production:
            code_type = "testing"
        elif is_production and not is_testing:
            code_type = "production"
        else:
            code_type = "utility"

        key = f"{range_name}-{code_type}"
        clonesets[key][clone_id] = service_fragments

    return clonesets