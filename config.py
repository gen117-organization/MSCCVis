# プロジェクトルートのPathを作成する．
# 設定ファイルではないので触らない．
from pathlib import Path
project_root = Path(__file__).parent

"""
    元のデータセット：
        選別前のデータセットのパスを記入してください．
        ヘッダーが存在しており，"URL"列にGitHubのURLが記載されている,';'区切りのCSVファイルに対応しています．
"""
BASED_DATASET = project_root / "dataset/Filtered.csv"

"""
    選別後のデータセット：
        コードベースを持つサービスが複数あるプロジェクトのみを選別したデータセットに対応しています．
        identify_microservice -> map_file -> select_projectの順番で実行することでも作成できます．
"""
SELECTED_DATASET = project_root / "dataset/selected_projects.json"

# CCFinderSWのパス
CCFINDERSW_JAR = project_root / "lib/CCFinderSW-1.0/lib/CCFinderSW-1.0.jar"

# CCFinderSW Parserのパス
CCFINDERSWPARSER = project_root / "lib/ccfindersw-parser/target/release/ccfindersw-parser"

# 対象のプログラミング言語
TARGET_PROGRAMING_LANGUAGES = (
    "Java",
    "Python",
    "JavaScript",
    "Go",
    "PHP",
    "TypeScript",
    "Rust",
    "C++",
    "C#",
    "Ruby",
    "Scala",
    "C",
)

# ANTRLから構文定義記述を抽出してCodeCloneを検出する言語
ANTLR_LANGUAGE = (
    "JavaScript",
    "TypeScript",
    "Rust",
    "C++",
    "C"
)

"""
    分析するコミットの決め方を設定します．
    tag: タグがついているコミットを分析する．
    frequency: ANALYSIS_FREQUENCYで設定したコミット区切りで分析する．
    merge_commit: デフォルトブランチのマージコミットを分析する．
"""
ANALYSIS_METHOD = "merge_commit"

# 何コミット区切りで分析するか
ANALYSIS_FREQUENCY = 50

# リポジトリマイニングするコミット数
SEARCH_DEPTH = 5