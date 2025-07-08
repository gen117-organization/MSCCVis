from pathlib import Path
import sys
import git
import json

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def analyze_commit(commit: git.Commit, name: str, language: str) -> dict:
    modification_count = 0
    result = {}
    for parent in commit.parents:
        modification_clones_file = project_root / "dest/modified_clones" / name / f"{parent.hexsha}-{commit.hexsha}" / f"{language}.json"
        if not modification_clones_file.exists():
            continue
        result[parent.hexsha] = {
            "generated": 0,
            "added": 0,
            "modified": 0,
            "co-modified": 0,
            "stable": 0,
            "child_total": 0,
            "parent_total": 0,
        }
        modification_count += 1
        with open(modification_clones_file, "r") as f:
            modification_clones = json.load(f)
        for clone_set in modification_clones:
            fragment_types = []
            for fragment in clone_set["fragments"]:
                fragment_types.append(fragment["type"])
            if fragment_types.count("modified") >= 2:
                result[parent.hexsha]["co-modified"] += 1
                print(f"co-modified: {clone_set}")
            else:
                fragment_types = list(set(fragment_types))
                if len(fragment_types) == 1:
                    if "added" in fragment_types:
                        result[parent.hexsha]["generated"] += 1
                    else:
                        result[parent.hexsha]["stable"] += 1
                else:
                    if ("added" in fragment_types) and ("stable" in fragment_types):
                        result[parent.hexsha]["added"] += 1
                    elif ("modified" in fragment_types) and ("stable" in fragment_types):
                        result[parent.hexsha]["added"] += 1
                    elif ("modified" in fragment_types) and ("added" in fragment_types):
                        result[parent.hexsha]["co-modified"] += 1
                        print(f"co-modified: {clone_set}")

        child_clone_file = project_root / "dest/clones_json" / name / commit.hexsha / f"{language}.json"
        with open(child_clone_file, "r") as f:
            child_clone = json.load(f)
        result[parent.hexsha]["child_total"] = len(child_clone["clone_sets"])
        parent_clone_file = project_root / "dest/clones_json" / name / parent.hexsha / f"{language}.json"
        with open(parent_clone_file, "r") as f:
            parent_clone = json.load(f)
        result[parent.hexsha]["parent_total"] = len(parent_clone["clone_sets"])
    return result


def print_result(result: dict, commit: git.Commit):
    for parent_hash in result.keys():
        print(f"{commit.hexsha} -> {parent_hash}:\n")
        is_exist = False
        for key in result[parent_hash].keys():
            if (key != "child_total" and key != "parent_total"):
                if result[parent_hash][key] > 0:
                    is_exist = True
                    break
        if not is_exist:
            continue   
        print(f"    added: {result[parent_hash]['added']}\n")
        print(f"    deleted: {result[parent_hash]['deleted']}\n")
        print(f"    modified: {result[parent_hash]['modified']}\n")
        print(f"    co-modified: {result[parent_hash]['co-modified']}\n")
        print(f"    stable: {result[parent_hash]['stable']}\n")
        print(f"    child_total: {result[parent_hash]['child_total']}\n")
        print(f"    parent_total: {result[parent_hash]['parent_total']}\n")
        print("\n")


def get_md_of_modification(result: dict, name: str, commit: git.Commit) -> list[str]:
    outputs = []
    for parent_hash in result.keys():
        moving_lines_file = project_root / "dest/moving_lines" / name / f"{parent_hash}-{commit.hexsha}.json"
        if not moving_lines_file.exists():
            print(moving_lines_file)
            continue
        with open(moving_lines_file, "r") as f:
            moving_lines = json.load(f)
        outputs.append(f"#### {commit.hexsha} -> {parent_hash}:\n")
        outputs.append("<details><summary>Moving Lines</summary>\n")
        outputs.append("```\n")
        for hunk in moving_lines:
            outputs.append(f"{hunk}")
        outputs.append("\n")
        outputs.append("```\n")
        outputs.append("</details>\n")
        outputs.append("\n")
        is_exist = False
        for key in result[parent_hash].keys():
            if (key != "child_total" and key != "parent_total"):
                if result[parent_hash][key] > 0:
                    is_exist = True
                    break
        if not is_exist:
            continue
        outputs.append("| type | count |\n")
        outputs.append("| --- | --- |\n")
        outputs.append(f"| added | {result[parent_hash]['added']} |\n")
        outputs.append(f"| generated | {result[parent_hash]['generated']} |\n")
        outputs.append(f"| modified | {result[parent_hash]['modified']} |\n")
        outputs.append(f"| co-modified | {result[parent_hash]['co-modified']} |\n")
        outputs.append(f"| stable | {result[parent_hash]['stable']} |\n")
        outputs.append("\n")
        outputs.append(f"child_total: {result[parent_hash]['child_total']}\n")
        outputs.append(f"parent_total: {result[parent_hash]['parent_total']}\n")
        outputs.append("\n")
    return outputs


def analyze_repo(project: dict):
    url = project["URL"]
    name = url.split("/")[-2] + "." + url.split("/")[-1]
    workdir = project_root / "dest/projects" / name
    for language in project["languages"].keys():
        print(f"{language}:")
        print("--------------------------------")
        git_repo = git.Repo(str(workdir))
        hcommit = git_repo.head.commit
        queue = [hcommit]
        finished_commits = []
        markdown_outputs = []
        while (len(queue) > 0):
            commit = queue.pop(0)
            if commit.hexsha in finished_commits:
                continue
            result = analyze_commit(commit, name, language)
            markdown_output = get_md_of_modification(result, name, commit)
            if len(markdown_output) > 0:
                markdown_outputs += markdown_output
            finished_commits.append(commit.hexsha)
            for parent in commit.parents:
                if parent in queue:
                    continue
                queue.append(parent)
        dest_dir = project_root / "dest/modification_result" / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(project_root / "dest/modification_result" / name / f"{language}.md", "w") as f:
            f.writelines(markdown_outputs)