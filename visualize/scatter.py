from dash import Dash
import plotly.graph_objects as go
import os
import dash_bootstrap_components as dbc
import sys
from pathlib import Path

# パッケージ未解決時のためにプロジェクトrootをパスに追加
if __package__ is None or __package__ == "":
    project_root = Path(__file__).resolve().parent.parent
    sys.path.append(str(project_root))

# 可視化モジュール（パッケージとして実行/スクリプト実行の両対応）
from visualize.data_loader import get_available_projects_enhanced, get_available_languages, load_and_process_data
from visualize.plotting import create_scatter_plot
from visualize.components import create_layout, build_project_summary, create_ide_layout
from visualize.callbacks import register_callbacks, app_data

# --- アプリケーションの初期化 ---
# assetsフォルダへの絶対パスを構築
# __file__ はこのファイル(scatter.py)のパス
# os.path.dirnameでディレクトリを取得し、'..'で親ディレクトリ(プロジェクトルート)に移動
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
assets_path = os.path.join(project_root, 'assets')

# assets_folderに絶対パスを指定してDashアプリを初期化
app = Dash(__name__, assets_folder=assets_path, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "マイクロサービス コードクローン可視化"
app.config.suppress_callback_exceptions = True  # 動的コンポーネント用の設定

# 利用可能なプロジェクトと言語を取得（改善版）
available_projects = get_available_projects_enhanced()
available_languages = get_available_languages()

# 初期表示用のデータを準備（重いデータを初回ロードしない）
default_value = None
if not available_projects:
    initial_fig = go.Figure().update_layout(title="CSVファイルが見つかりません")
    initial_summary = build_project_summary(None, {}, "N/A", "N/A", "N/A")
else:
    initial_fig = go.Figure().update_layout(title="プロジェクトを選択してください")
    initial_summary = build_project_summary(None, {}, "N/A", "N/A", "N/A")

# レイアウトとコールバックを設定
# Use create_ide_layout instead of create_layout
app.layout = create_ide_layout(available_projects, available_languages, default_value, initial_fig, initial_summary)
register_callbacks(app)

# --- アプリケーションの実行 ---
if __name__ == '__main__':
    app.run(debug=True, port=8050)
