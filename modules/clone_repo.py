# 必要なライブラリをインポート
from pathlib import Path
import os
import git
import shutil

# プロジェクトのルートディレクトリを取得
project_root = Path(__file__).parent.parent


def clone_repo(url: str):
    """
    指定されたURLからGitリポジトリをクローンする関数
    
    Args:
        url (str): クローンするGitリポジトリのURL
    """
    # リポジトリ名をURLから抽出（owner/repo形式）
    name = url.split('/')[-2] + '.' + url.split('/')[-1]
    print(f"Cloning {url}...")
    # クローン先のディレクトリを作成
    os.makedirs(project_root / "dest/projects", exist_ok=True)
    # リポジトリをクローン
    shutil.rmtree(project_root / "dest/projects" / name, ignore_errors=True)
    git.Repo.clone_from(url, project_root / "dest/projects" / name)