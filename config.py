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
    選別後のデータセット（コミット条件適用前）：
        コードベースを持つサービスが複数あるプロジェクトのみを選別したデータセットに対応しています．
        identify_microservice -> map_file -> select_projectの順番で実行することでも作成できます．
"""
SELECTED_DATASET_CANDIDATES = project_root / "dest/selected_projects_candidates.json"

"""
    コミット条件を適用した最終データセット：
        determine_analyzed_commits で SELECTED_DATASET_CANDIDATES からフィルタした結果を保存します．
"""
SELECTED_DATASET = project_root / "dataset/selected_projects.json"

# CCFinderSWのパス
CCFINDERSW_JAR = project_root / "lib/CCFinderSW-1.0/lib/CCFinderSW-1.0.jar"

# CCFinderSW Parserのパス
CCFINDERSWPARSER = (
    project_root / "lib/ccfindersw-parser/target/release/ccfindersw-parser"
)

# CCFinderSWのJava実行設定
# 例: "16G", "8G", "1024M"
CCFINDERSW_JAVA_XMX = "20G"
CCFINDERSW_JAVA_XSS = "512m"

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
ANTLR_LANGUAGE = ("JavaScript", "TypeScript", "Rust", "C++", "C")

"""
    分析するコミットの決め方を設定します．
    tag: タグがついているコミットを分析する．
    frequency: ANALYSIS_FREQUENCYで設定したコミット区切りで分析する．
    merge_commit: デフォルトブランチのマージコミットを分析する．
"""
ANALYSIS_METHOD = "merge_commit"

# 何コミット区切りで分析するか
ANALYSIS_FREQUENCY = 1

# リポジトリマイニングするコミット数（プロジェクト選定条件に使用）
SEARCH_DEPTH = -1

# 分析対象に含めるコミット数の最大値（-1 の場合は無制限）
# SEARCH_DEPTHとは独立した上限として適用されます。
MAX_ANALYZED_COMMITS = -1

# 分析対象のコミット上限日時（JST）。None の場合は制限なし。
# 例: "2024-03-31 23:59:59"
ANALYSIS_UNTIL = "2026-01-01 00:00:00"

# import 行フィルタを有効にするか
APPLY_IMPORT_FILTER = True
