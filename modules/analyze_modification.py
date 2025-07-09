from pathlib import Path
import sys
import git
import json
import csv

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from modules.util import FileMapper
import modules.claim_parser as claim_parser


class CodeCloneAnalyzer:
    def __init__(self, name: str, hcommit: git.Commit, language: str, workdir: Path):
        self.name = name
        self.language = language
        self.workdir = workdir
        self.hcommit = hcommit
        self.finished_commits = []
        self.commit_history = [[hcommit.hexsha]]
        
    def filter_clone_sets(self):
        hcommit_ccfsw_json = project_root / "dest/clones_json" / self.name / self.hcommit.hexsha / f"{self.language}.json"
        with open(hcommit_ccfsw_json, "r") as f:
            hcommit_ccfsw_json = json.load(f)
        file_mapper = FileMapper(hcommit_ccfsw_json["file_data"], str(self.workdir))
        clone_sets = self._analyze_co_modification()
        filtered_clone_sets_by_testing = self._filter_testing_clone_set(clone_sets, file_mapper)
        codebases = self._get_latest_codebases(self.name)
        filtered_clone_sets_by_cross_service = self._filter_cross_service_clone_set(codebases, filtered_clone_sets_by_testing, file_mapper)
        result = {
            "cross-production": {
                "co-modified": 0,
                "total": 0,
            },
            "cross-testing": {
                "co-modified": 0,
                "total": 0,
            },
            "within-production": {
                "co-modified": 0,
                "total": 0,
            },
            "within-testing": {
                "co-modified": 0,
                "total": 0,
            },
        }
        for clone_set in filtered_clone_sets_by_cross_service:
            if (clone_set["is_testing"] == False) and (clone_set["is_cross_service"] == False):
                result["within-production"]["total"] += 1
                if clone_set["is_co_modified"]:
                    result["within-production"]["co-modified"] += 1
            elif (clone_set["is_testing"] == True) and (clone_set["is_cross_service"] == False):
                result["within-testing"]["total"] += 1
                if clone_set["is_co_modified"]:
                    result["within-testing"]["co-modified"] += 1
            elif (clone_set["is_testing"] == False) and (clone_set["is_cross_service"] == True):
                result["cross-production"]["total"] += 1
                if clone_set["is_co_modified"]:
                    result["cross-production"]["co-modified"] += 1
            elif (clone_set["is_testing"] == True) and (clone_set["is_cross_service"] == True):
                result["cross-testing"]["total"] += 1
                if clone_set["is_co_modified"]:
                    result["cross-testing"]["co-modified"] += 1
        return result

    def _analyze_co_modification(self):
        clone_sets = []
        for index, child_commits in enumerate(self.commit_history):
            if index+1 >= len(self.commit_history):
                break
            for child_commit in child_commits:
                if index == 0:
                    child_commit_ccfsw_json = project_root / "dest/clones_json" / self.name / child_commit / f"{self.language}.json"
                    with open(child_commit_ccfsw_json, "r") as f:
                        child_commit_ccfsw_json = json.load(f)
                    for clone_set in child_commit_ccfsw_json["clone_sets"]:
                        fragments = []
                        for fragment in clone_set["fragments"]:
                            fragments.append({
                                "file_id": fragment["file_id"],
                                "start_line": fragment["start_line"],
                                "end_line": fragment["end_line"],
                                "modifications": [],
                                "traceable": True,
                                "history": {
                                    child_commit: fragment,
                                },
                            })
                        clone_sets.append({
                            "clone_id": clone_set["clone_id"],
                            "is_co_modified": False,
                            "fragments": fragments,
                        })
                for parent_commit in self.commit_history[index+1]:
                    for clone_set in clone_sets:
                        for fragment in clone_set["fragments"]:
                            fragment["history"][parent_commit] = fragment["history"][child_commit]
                    modification_result_dir = project_root / "dest/modified_clones" / self.name / f"{parent_commit}-{child_commit}"
                    modification_result_file = modification_result_dir / f"{self.language}.json"
                    if not modification_result_file.exists():
                        continue
                    with open(modification_result_file, "r") as f:
                        modification_result = json.load(f)
                    for modification_clone_set in modification_result:
                        for modification_fragment in modification_clone_set["fragments"]:
                            child_modification_fragment = modification_fragment["child"]
                            for clone_set in clone_sets:
                                for fragment in clone_set["fragments"]:
                                    if fragment["traceable"] == False:
                                        continue
                                    if fragment["file_id"] == child_modification_fragment["file_id"] and fragment["start_line"] == child_modification_fragment["start_line"] and fragment["end_line"] == child_modification_fragment["end_line"]:
                                        if modification_fragment["type"] == "added":
                                            fragment["traceable"] = False
                                        else:
                                            fragment["history"][parent_commit] = modification_fragment["parent"]
                                        fragment["modifications"].append({
                                            "child_commit": child_commit,
                                            "parent_commit": parent_commit,
                                            "type": modification_fragment["type"],
                                        })
                                        break
                                else:
                                    continue
                                break
                    for clone_set in clone_sets:
                        types = []
                        for fragment in clone_set["fragments"]:
                            for modification in fragment["modifications"]:
                                if (modification["child_commit"] == child_commit) and (modification["parent_commit"] == parent_commit):
                                    types.append(modification["type"])
                        if types.count("modified") >= 2:
                            clone_set["is_co_modified"] = True
                        if ("added" in types) and ("modified" in types):
                            clone_set["is_co_modified"] = True
        return clone_sets

    
    def analyze_commit(self, commit: git.Commit):
        if commit.hexsha in self.finished_commits:
            return
        self.finished_commits.append(commit.hexsha)
        commits = []
        for parent in commit.parents:
            modification_result_dir = project_root / "dest/modified_clones" / self.name / f"{parent.hexsha}-{commit.hexsha}"
            modification_result_file = modification_result_dir / f"{self.language}.json"
            if not modification_result_file.exists():
                continue
            if commit.hexsha not in self.commit_history[-1]:
                self.commit_history.append([commit.hexsha])
            commits.append(parent.hexsha)
        if len(commits) > 0:
            self.commit_history.append(commits)
                
    def _filter_testing_clone_set(self, clone_sets: list, file_mapper: FileMapper):
        result_clone_sets = []
        for clone_set in clone_sets:
            testing_fragments = []
            production_fragments = []
            for fragment in clone_set["fragments"]:
                file_path = file_mapper.get_file_path(fragment["file_id"])
                if "test" in file_path.lower():
                    testing_fragments.append(fragment)
                else:
                    production_fragments.append(fragment)
            if len(testing_fragments) > 2:
                result_clone_sets.append({
                    "clone_id": clone_set["clone_id"],
                    "is_testing": True,
                    "is_co_modified": clone_set["is_co_modified"],
                    "fragments": testing_fragments,
                })
            elif len(production_fragments) > 2:
                result_clone_sets.append({
                    "clone_id": clone_set["clone_id"],
                    "is_testing": False,
                    "is_co_modified": clone_set["is_co_modified"],
                    "fragments": production_fragments,
                })
        return result_clone_sets

    def _filter_cross_service_clone_set(self, codebases: list[str], clone_sets: list[dict], file_mapper: FileMapper):
        result_clone_sets = []
        for clone_set in clone_sets:
            clone_set_codebases = set()
            for fragment in clone_set["fragments"]:
                file_path = file_mapper.get_file_path(fragment["file_id"])
                for codebase in codebases:
                    if file_path.startswith(codebase):
                        clone_set_codebases.add(codebase)
            if len(clone_set_codebases) == 1:
                result_clone_sets.append({
                    "clone_id": clone_set["clone_id"],
                    "is_testing": clone_set["is_testing"],
                    "is_cross_service": False,
                    "is_co_modified": clone_set["is_co_modified"],
                    "fragments": clone_set["fragments"],
                })
            elif len(clone_set_codebases) > 1:
                result_clone_sets.append({
                    "clone_id": clone_set["clone_id"],
                    "is_testing": clone_set["is_testing"],
                    "is_co_modified": clone_set["is_co_modified"],
                    "is_cross_service": True,
                    "fragments": clone_set["fragments"],
                })
        return result_clone_sets

    def _get_latest_codebases(self, name: str):
        ms_detection_file = project_root / "dest/ms_detection" / f"{name}.csv"
        with open(ms_detection_file, "r") as f:
            ms_detection_csv = csv.DictReader(f, delimiter=",")
            latest_row = None
            for row in ms_detection_csv:
                latest_row = row
            uSs = claim_parser.parse_uSs(latest_row["uSs"])
            codebases = set()
            for uS in uSs:
                context = uS["build"]["context"]
                if context is None:
                    continue
                codebases.add(context)
            return list(codebases)
        

def calculate_modification_rate(clone_sets: list):
    total_clone_sets = len(clone_sets)
    co_modified_clone_sets = 0
    for clone_set in clone_sets:
        if clone_set["is_co_modified"]:
            co_modified_clone_sets += 1
    return co_modified_clone_sets / total_clone_sets

def analyze_repo(project: dict):
    url = project["URL"]
    name = url.split("/")[-2] + "." + url.split("/")[-1]
    workdir = project_root / "dest/projects" / name
    
    git_repo = git.Repo(str(workdir))
    hcommit = git_repo.head.commit

    result = {}
    for language in project["languages"].keys():
        print(f"Analyzing {language} clones for {name}:")
        print("=" * 50)
        
        # CodeCloneAnalyzerを初期化
        analyzer = CodeCloneAnalyzer(name, hcommit, language, workdir)
        
        # コミット履歴を辿る
        queue = [hcommit]
        processed_commits = set()
        
        while queue:
            commit = queue.pop(0)
            if commit.hexsha in processed_commits:
                continue
            processed_commits.add(commit.hexsha)
            
            # コミットを分析
            analyzer.analyze_commit(commit)
            
            # 親コミットをキューに追加
            for parent in commit.parents:
                if parent.hexsha not in processed_commits:
                    queue.append(parent)
        
        language_result = analyzer.filter_clone_sets()
        
        print(f"Completed analysis for {language}")
        print("-" * 50)

        result[language] = language_result

    return result