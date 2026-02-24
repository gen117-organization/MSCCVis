import logging
import os
import re

from dash import html, dcc
import difflib

from ..utils import get_local_snippet
from .clone_metrics import generate_github_file_url
from modules.util import get_file_type

logger = logging.getLogger(__name__)

def build_clone_details_view(row, project, df, file_ranges):
    """クリックされたクローンの詳細な比較ビューを生成する"""
    # この関数は単一クローン表示に特化
    return build_clone_details_view_single(row, project)


def build_clone_details_view_single(row, project):
    """単一クローンの詳細ビューを生成する"""
    file_x, file_y = row.get("file_path_x"), row.get("file_path_y")
    sx, ex = int(row.get("start_line_x", 0)), int(row.get("end_line_x", 0))
    sy, ey = int(row.get("start_line_y", 0)), int(row.get("end_line_y", 0))

    snippet_x_lines = get_local_snippet(project, file_x, sx, ex, context=0).splitlines()
    snippet_y_lines = get_local_snippet(project, file_y, sy, ey, context=0).splitlines()

    code_x_for_copy = "\n".join(
        [re.sub(r"^[ >]\s*\d+:\s*", "", line) for line in snippet_x_lines]
    )
    code_y_for_copy = "\n".join(
        [re.sub(r"^[ >]\s*\d+:\s*", "", line) for line in snippet_y_lines]
    )

    # 行番号を除いた純粋なコード内容で比較
    code_x_lines = [re.sub(r"^[ >]\s*\d+:\s*", "", line) for line in snippet_x_lines]
    code_y_lines = [re.sub(r"^[ >]\s*\d+:\s*", "", line) for line in snippet_y_lines]
    sm = difflib.SequenceMatcher(None, code_x_lines, code_y_lines)
    rows_x, rows_y = [], []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        # 表示用には元の行番号付きの行を使用
        block_x, block_y = snippet_x_lines[i1:i2], snippet_y_lines[j1:j2]

        is_diff = tag == "equal"  # 完全一致の場合に背景色を付ける

        for line in block_x:
            rows_x.append(_diff_pane(line, is_diff))

        for line in block_y:
            rows_y.append(_diff_pane(line, is_diff))

    return html.Div(
        [
            # ヘッダーやメタ情報は各ペイン内に移動させるため、トップレベルはシンプルに
            html.Div(
                [
                    # Left Pane (Pane X)
                    html.Div(
                        [
                            _file_header(
                                file_x,
                                row.get("service_x", ""),
                                project,
                                sx,
                                ex,
                                row.get("file_id_x", "N/A"),
                            ),
                            html.Div(
                                _code_pane(
                                    rows_x,
                                    code_x_for_copy,
                                    "X",
                                    file_x,
                                    project,
                                    sx,
                                    ex,
                                ),
                                style={"flex": "1", "overflow": "hidden"},
                            ),
                        ],
                        className="split-pane",
                        style={"flex": "0 0 50%"},
                    ),  # Initial 50% width
                    # Gutter (Splitter)
                    html.Div(className="split-gutter", title="Drag to resize"),
                    # Right Pane (Pane Y)
                    html.Div(
                        [
                            _file_header(
                                file_y,
                                row.get("service_y", ""),
                                project,
                                sy,
                                ey,
                                row.get("file_id_y", "N/A"),
                            ),
                            html.Div(
                                _code_pane(
                                    rows_y,
                                    code_y_for_copy,
                                    "Y",
                                    file_y,
                                    project,
                                    sy,
                                    ey,
                                ),
                                style={"flex": "1", "overflow": "hidden"},
                            ),
                        ],
                        className="split-pane",
                        style={"flex": "1"},
                    ),  # Takes remaining space
                ],
                className="split-container",
            )
        ]
    )


def _file_header(file_path, service, project, start_line, end_line, file_id):
    """ファイルヘッダーコンポーネント (VS Code Tab風)"""
    # ファイルタイプ判定
    ftype = get_file_type(file_path)

    # タイプごとのスタイル定義（テキスト色のみ）
    type_styles = {
        "logic": {"color": "#0366d6", "borderColor": "#0366d6"},  # Blue
        "test": {"color": "#28a745", "borderColor": "#28a745"},  # Green
        "data": {"color": "#d73a49", "borderColor": "#d73a49"},  # Red
        "config": {"color": "#6a737d", "borderColor": "#6a737d"},  # Gray
    }
    t_style = type_styles.get(ftype, {"color": "#586069", "borderColor": "#e1e4e8"})

    # ファイル名だけ抽出
    filename = file_path.split("/")[-1] if file_path else "Unknown"
    # ディレクトリパス
    dir_path = os.path.dirname(file_path) if file_path else ""

    # GitHub URL
    github_url = generate_github_file_url(project, file_path, start_line, end_line)

    return html.Div(
        [
            # 左側: タイプバッジ(テキスト), ファイル名, パス
            html.Div(
                [
                    html.Span(
                        ftype.upper(),
                        style={
                            "color": t_style["color"],
                            "fontSize": "10px",
                            "fontWeight": "bold",
                            "border": f"1px solid {t_style['borderColor']}",
                            "padding": "1px 4px",
                            "borderRadius": "3px",
                            "marginRight": "8px",
                        },
                    ),
                    html.Span(
                        filename,
                        title=file_path,
                        style={
                            "fontWeight": "600",
                            "fontSize": "13px",
                            "marginRight": "8px",
                            "color": "#24292e",
                        },
                    ),
                    html.Span(
                        dir_path,
                        title=file_path,
                        style={
                            "color": "#6a737d",
                            "fontSize": "11px",
                            "fontFamily": "monospace",
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "overflow": "hidden",
                    "whiteSpace": "nowrap",
                    "flex": "1",
                },
            ),
            # 右側: サービス名, File ID, Actions
            html.Div(
                [
                    html.Span(
                        [html.B("Svc: "), service],
                        style={
                            "fontSize": "11px",
                            "color": "#586069",
                            "marginRight": "10px",
                        },
                    ),
                    html.Span(
                        [html.B("ID: "), str(file_id)],
                        style={
                            "fontSize": "11px",
                            "color": "#586069",
                            "marginRight": "10px",
                        },
                    ),
                    (
                        html.A(
                            "GitHub ↗",
                            href=github_url,
                            target="_blank",
                            style={
                                "fontSize": "11px",
                                "color": "#0366d6",
                                "textDecoration": "none",
                            },
                        )
                        if github_url
                        else None
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "flexShrink": "0"},
            ),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "8px 12px",
            "borderBottom": "1px solid #e1e4e8",
            "backgroundColor": "#f6f8fa",
            "height": "36px",
            "boxSizing": "border-box",
            "borderTopLeftRadius": "6px",
            "borderTopRightRadius": "6px",
        },
    )


def _code_pane(rows, code_for_copy, suffix, file_path, project, start_line, end_line):
    # ファイル全体の内容を読み込み
    from ..utils import get_file_content

    full_content = get_file_content(project, file_path, start_line, end_line)

    # コード片部分 (dcc.Clipboardはヘッダーに移動してもいいが、一旦ここ)
    # オーバーレイコピーボタンのデザイン調整
    code_snippet = html.Div(
        [
            dcc.Clipboard(
                content=code_for_copy,
                className="copy-button",
                title=f"Copy code {suffix}",
                style={
                    "position": "absolute",
                    "top": "5px",
                    "right": "5px",
                    "zIndex": "10",
                },
            ),
            html.Div(rows, className="code-pane-content", style={"padding": "15px"}),
        ],
        className="code-pane",
        style={
            "position": "relative",
            "backgroundColor": "#fff",
            "borderBottom": "1px solid #eee",
        },
    )

    # ファイル全体部分 (高さ制限を撤廃し、自然に展開)
    full_file_section = html.Div(
        [
            html.Div(
                [
                    html.Span(
                        "📄 Full Source Code",
                        style={
                            "fontWeight": "600",
                            "color": "#444",
                            "fontSize": "13px",
                        },
                    ),
                ],
                style={
                    "padding": "10px 15px",
                    "background": "#f8f9fa",
                    "borderBottom": "1px solid #e1e4e8",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "space-between",
                },
            ),
            dcc.Markdown(
                full_content,
                className="full-code-markdown",
                style={
                    "padding": "15px",
                    "fontSize": "12px",
                    "lineHeight": "1.5",
                    "fontFamily": "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
                },
            ),
        ],
        className="full-file-content",
        style={
            "borderTop": "none",
            "height": "70vh",
            "overflowY": "auto",
            "display": "block",
        },
    )

    return html.Div(
        [
            html.Div(
                "🔍 Matched Snippet",
                style={
                    "fontSize": "11px",
                    "fontWeight": "bold",
                    "color": "#888",
                    "textTransform": "uppercase",
                    "padding": "10px 15px 5px",
                    "letterSpacing": "0.5px",
                },
            ),
            code_snippet,
            full_file_section,
        ],
        style={
            "backgroundColor": "white",
            "display": "flex",
            "flexDirection": "column",
        },
    )


def _diff_pane(line, is_diff):
    # utils.py generates: f"{prefix}{i+1:5d}: {lines[i]}"
    # old regex: r'([ >])\s*(\d+):\s*(.*)' <- \s* ate leading spaces of code
    # new regex preserves the content after the single space separator
    match = re.match(r"([ >])\s*(\d+): (.*)", line)
    if not match:
        # Fallback for empty lines or unexpected format (try matching without trailing content)
        match = re.match(r"([ >])\s*(\d+):(.*)", line)

    if not match:
        # Completely failed to match format, return as simple line
        return html.Div(line, className="diff-line", style={"whiteSpace": "pre"})

    prefix, ln, text = match.groups()
    return html.Div(
        [
            html.Span(
                ln,
                className="line-num",
                **({"data-prefix": prefix} if prefix != " " else {}),
            ),
            html.Span(text),
        ],
        className=f"diff-line {'diff' if is_diff else ''}",
    )


def _legend_chip(label, color):
    return html.Div(
        label,
        style={
            "background": color,
            "border": "1px solid #ddd",
            "padding": "2px 6px",
            "borderRadius": "3px",
            "fontSize": "11px",
        },
    )


