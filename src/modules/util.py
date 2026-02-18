import sys
import csv
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return start


project_root = _find_repo_root(Path(__file__).resolve())
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))


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


def get_file_type(file_path: str) -> str:
    """ファイルパスからコード種別を推定する.

    Args:
        file_path: ファイルパス（相対/絶対どちらでも可）.

    Returns:
        "test" | "config" | "data" | "logic" のいずれか.
    """
    lower = file_path.lower().replace("\\", "/")
    name = lower.rsplit("/", 1)[-1] if "/" in lower else lower

    # テストファイル
    test_indicators = (
        "/test/", "/tests/", "/test_", "test_",
        "_test.", ".test.", "/spec/", "/specs/",
        "_spec.", ".spec.", "/__tests__/",
    )
    if any(ind in lower for ind in test_indicators):
        return "test"

    # 設定ファイル
    config_names = {
        "dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "makefile", ".env", "tsconfig.json", "package.json",
        "setup.py", "setup.cfg", "pyproject.toml", "pom.xml",
        "build.gradle", "build.sbt", "cargo.toml", "go.mod",
        ".eslintrc", ".prettierrc", ".babelrc", "jest.config.js",
        "webpack.config.js", "rollup.config.js", "vite.config.ts",
        "nginx.conf", "requirements.txt", "gemfile",
    }
    config_extensions = {".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf"}
    if name in config_names:
        return "config"
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if ext in config_extensions:
        return "config"
    config_dirs = ("/config/", "/configs/", "/.github/", "/.circleci/")
    if any(d in lower for d in config_dirs):
        return "config"

    # データ/モデルファイル
    data_indicators = (
        "/model/", "/models/", "/entity/", "/entities/",
        "/schema/", "/schemas/", "/dto/", "/proto/",
        "/migration/", "/migrations/", "/seed/", "/seeds/",
        "/fixture/", "/fixtures/",
    )
    data_extensions = {".sql", ".graphql", ".proto", ".avsc"}
    if any(ind in lower for ind in data_indicators):
        return "data"
    if ext in data_extensions:
        return "data"

    return "logic"


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
            if "test" in path.lower():
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
                    break

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
