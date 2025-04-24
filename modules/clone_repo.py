# 必要なライブラリをインポート
from pathlib import Path
import os
import json
import git

# プロジェクトのルートディレクトリを取得
project_dir = Path(__file__).parent.parent


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
    os.makedirs(project_dir / "dest/projects", exist_ok=True)
    # リポジトリをクローン
    git.Repo.clone_from(url, project_dir / "dest/projects" / name)


def main():
    """
    メイン関数：選択されたプロジェクトのリストを読み込み、それぞれをクローン
    """
    # 選択されたプロジェクトの情報をJSONファイルから読み込み
    datset_dir = project_dir / "dest/results/selected_projects.json"
    with open(datset_dir, "r") as f:
        selected_projects = json.load(f)

    # 各プロジェクトをクローン
    for project in selected_projects:
        url = project["URL"]
        clone_repo(url)


if __name__ == "__main__":
    main()