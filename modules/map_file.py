from pathlib import Path
import csv
import re
import json
import sys
# プロジェクトのルートディレクトリを設定
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from config import TARGET_PROGRAMING_LANGUAGES, BASED_DATASET

def parse_uSs(uSs: str) -> list[dict]:
    """
    マイクロサービスの文字列表現を解析して、構造化されたデータに変換します。
    
    Args:
        uSs: マイクロサービスの文字列表現（例: "Microservice(name='service1', build=Build(...), confidence=0.8)"）
        
    Returns:
        マイクロサービスの情報を含む辞書のリスト。各辞書には名前、ビルド情報、信頼度が含まれます。
        入力が "set()" の場合は None を返します。
    """
    # 空のセットの場合はNoneを返す
    if uSs == "set()":
        return None

    # マイクロサービスの情報を抽出するための正規表現パターン
    pattern = r"Microservice\(name='(.*?)', build=Build\((.*?)\), confidence=(.*?)\)"
    matches = re.findall(pattern, uSs)

    result = []

    # 各マッチしたマイクロサービス情報を処理
    for match in matches:
        build = {}
        # ビルド情報を解析
        build["context"] = eval(match[1].split(",")[0].split("=")[1])
        build["rel_dockerfile"] = eval(match[1].split(",")[1].split("=")[1])
        build["remote"] = eval(match[1].split(",")[2].split("=")[1])
        build["absolute"] = eval(match[1].split(",")[3].split("=")[1])

        # 構造化されたデータを作成
        result.append({
            "name": match[0],
            "build": build,
            "confidence": match[2]
        })

    return result


def parse_containers(containers: str) -> list[dict]:
    """
    コンテナの文字列表現を解析して、構造化されたデータに変換します。
    
    Args:
        containers: コンテナの文字列表現（例: "Container(image='image1', build=Build(...), container_name='container1')"）
        
    Returns:
        コンテナの情報を含む辞書のリスト。各辞書にはイメージ名、ビルド情報、コンテナ名が含まれます。
        入力が "set()" の場合は None を返します。
    """
    # 空のセットの場合はNoneを返す
    if containers == "set()":
        return None

    # コンテナの情報を抽出するための正規表現パターン
    pattern = r"Container\(image=(.*?), build=(.*?), container_name='(.*?)'\)"
    matches = re.findall(pattern, containers)

    result = []

    # 各マッチしたコンテナ情報を処理
    for match in matches:
        build = {}
        # ビルド情報がある場合のみ解析
        if match[1] != "None":
            build_text = match[1].replace("Build(", "").replace(")", "")
            build["context"] = eval(build_text.split(",")[0].split("=")[1])
            build["rel_dockerfile"] = eval(build_text.split(",")[1].split("=")[1])
            build["remote"] = eval(build_text.split(",")[2].split("=")[1])
            build["absolute"] = eval(build_text.split(",")[3].split("=")[1])

        # 構造化されたデータを作成
        result.append({
            "image": eval(match[0]),
            "build": build,
            "container_name": match[2]
        })

    return result


def map_files(url: str) -> dict:
    """
    指定されたURLに対応するリポジトリのファイルマッピングを作成します。
    マイクロサービスとコンテナの情報を解析し、各マイクロサービスに関連するファイルを言語ごとに分類します。
    
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
            uSs = parse_uSs(row["uSs"])
            containers = parse_containers(row["CONTAINERS"])

        # GitHub Linguistの結果を読み込む
        target = project_root / "dest/github_linguist" / f"{name}.json"
        with open(target, "r") as f:
            linguist_result = json.load(f)

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
                with open(project_root / "dest/map" / f"{name}.json", "w") as f:
                    json.dump(result, f, indent=4)
            except FileNotFoundError:
                # ファイルが見つからない場合はエラーメッセージを表示して続行
                print(f"File not found: {row['URL']}")
                continue


if __name__ == "__main__":
    main()