import sys
from pathlib import Path
import json
import csv
import git

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import modules.collect_datas
import modules.analyze_cc

if __name__ == "__main__":
    url = "https://github.com/818000/bus"
    name = url.split("/")[-2] + "." + url.split("/")[-1]
    workdir = project_root / "dest/projects" / name
    git_repo = git.Repo(workdir)
    head_commit = git_repo.head.commit
    languages = ["Java"]
    exts = modules.collect_datas.get_exts(workdir)
    for language in languages:
        modules.collect_datas.detect_cc(workdir, name, language, head_commit.hexsha, exts[language])
        modules.analyze_cc.analyze_commit(name, language, head_commit)