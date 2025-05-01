from pathlib import Path
import csv
import traceback
import subprocess
import json
import git  # GitPython
import sys
from pathlib import Path

import dc_choice
import ms_detection
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from lib.CLAIM.src.utils.print_utils import print_progress, print_major_step, print_info
from lib.CLAIM.src.utils.repo import clear_repo


def analyze_repo_by_linguist(workdir: str, name: str):
    cmd = ["github-linguist", workdir, "--json", "--breakdown"]
    output = str(subprocess.run(cmd, capture_output=True, text=True).stdout).replace("\\n", "")
    output_json = json.loads(output)

    result_file = project_root / "dest/results/github_linguist" / f"{name}.json"
    with open(result_file, 'w') as result_output:
        result_output.write(json.dumps(output_json, indent=4))


def analyze_dataset():
    dataset_file = project_root / "Filtered.csv"

    total_repos = -1
    for _ in open(dataset_file):
        total_repos += 1

    with open(dataset_file) as dataset:
        repos = csv.DictReader(dataset, delimiter=';')
        for index, repo in enumerate(repos):
            print_progress(f"Processing {index + 1}/{total_repos}")

            url = repo["URL"]
            name = url.split('/')[-2] + '.' + url.split('/')[-1]
            workdir = str(project_root / "dest/temp/clones" / name)
            try:
                git.Repo.clone_from(url, workdir, depth=1)  # GitPython: useful to work with repo
                analyze_repo_by_linguist(workdir, name)
                res = dc_choice.analyze_repo(url)
                dc_choice.print_results(url, res)
                dc_choice.save_results(url, res)
                res = ms_detection.analyze_repo(url)
                ms_detection.print_results(url, res)
                ms_detection.save_results(url, res)
            except Exception as e:
                print(traceback.format_exc())
                continue
            finally:
                print_info('   Clearing temporary directories')
                clear_repo(Path(workdir))


def main():
    print_major_step("# Start dataset analysis")
    analyze_dataset()


if __name__ == "__main__":
    main()