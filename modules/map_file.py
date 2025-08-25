from pathlib import Path
import csv
import json
import sys
import os
# プロジェクトのルートディレクトリを設定
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from config import TARGET_PROGRAMING_LANGUAGES, BASED_DATASET
import claim_parser

def map_files(url: str) -> dict:
    """
    指定されたURLに対応するリポジトリのファイルマッピングを作成します。
    マイクロサービスとコンテナの情報を解析し、各マイクロサービスに関連するファイルを言語ごとに分類します。
    最新のコミットのみを分析します。
    
    Args:
        url: GitHubリポジトリのURL
        
    Returns:
        マイクロサービスとコンテナの情報を含む辞書。
        各マイクロサービスには、ビルド情報、信頼度、関連するファイル（言語ごとに分類）が含まれます。
        各コンテナには、イメージ名とビルド情報が含まれます。
        
    Raises:
        FileNotFoundError: 必要なファイルが見つからない場合
    """
    # URLからリポジトリ名を抽出
    name = url.split('/')[-2] + '.' + url.split('/')[-1]
    # マイクロサービス検出結果のファイルパス
    target = project_root / "dest/ms_detection" / f"{name}.csv"

    try:
        # マイクロサービスとコンテナの情報を読み込む
        with open(target, "r") as f:
            reader = csv.DictReader(f)
            row = next(reader)
            uSs = claim_parser.parse_uSs(row["uSs"])
            containers = claim_parser.parse_containers(row["CONTAINERS"])

        # GitHub Linguistの結果を読み込む
        target = project_root / "dest/github_linguist" / f"{name}.json"
        with open(target, "r") as f:
            linguist_result = json.load(f)
        os.remove(target)

        result = {}
        # マイクロサービスの情報を処理
        if uSs is not None:
            for uS in uSs:
                result[uS["name"]] = {
                    "type": "microservice",
                    "build": uS["build"],
                    "confidence": uS["confidence"],
                    "files": {}
                }

        # 言語ごとのファイルをマイクロサービスに割り当てる
        for language in linguist_result.keys():
            # 対象外の言語はスキップ
            if language not in TARGET_PROGRAMING_LANGUAGES:
                continue
            # 各ファイルを処理
            for file in linguist_result[language]["files"]:
                # 各マイクロサービスに対して処理
                for microservice in result.keys():
                    context = result[microservice]["build"]["context"]
                    # コンテキストが無効な場合はスキップ
                    if context is None or context == ".":
                        continue
                    # ファイルがマイクロサービスのコンテキスト内にある場合
                    if file.startswith(context):
                        # 言語ごとのファイルリストを初期化（必要に応じて）
                        if language not in result[microservice]["files"].keys():
                            result[microservice]["files"][language] = []
                        # ファイルを追加
                        result[microservice]["files"][language].append(file)
        
        # コンテナの情報を追加
        if containers is not None:
            for container in containers:
                result[container["container_name"]] = {
                    "type": "container",
                    "image": container["image"],
                    "build": container["build"],
                }

        return result
        
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {target}")


def main():
    """
    メイン関数。
    Filtered.csvファイルからリポジトリのURLを読み込み、
    各リポジトリに対してファイルマッピングを作成し、結果をJSONファイルとして保存します。
    """
    # データセットファイルを開く
    dataset_file = BASED_DATASET
    with open(dataset_file, "r") as f:
        reader = csv.DictReader(f, delimiter=';')
        # 各行（リポジトリ）を処理
        for row in reader:
            try:
                # ファイルマッピングを作成
                result = map_files(row["URL"])
                # リポジトリ名を抽出
                name = row["URL"].split('/')[-2] + '.' + row["URL"].split('/')[-1]
                # 結果をJSONファイルとして保存
                dest_dir = project_root / "dest/map"
                dest_dir.mkdir(parents=True, exist_ok=True)
                with open(dest_dir / f"{name}.json", "w") as f:
                    json.dump(result, f, indent=4)
            except FileNotFoundError:
                # ファイルが見つからない場合はエラーメッセージを表示して続行
                print(f"File not found: {row['URL']}")
                continue


if __name__ == "__main__":
    main()