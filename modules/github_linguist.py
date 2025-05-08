import subprocess
import json


def run_github_linguist(target: str) -> dict:
    """
    GitHub Linguistを使用して指定されたディレクトリの言語構成を分析します．

    Args:
        target (str): 分析対象のディレクトリパス

    Returns:
        dict: 言語ごとの使用量を含むJSONデータ
    """
    # コマンドは環境によって書き換えてください．
    cmd = ["github-linguist", target, "--json", "--breakdown"]
    output = str(subprocess.run(cmd, capture_output=True, text=True).stdout).replace("\\n", "")
    return json.loads(output)