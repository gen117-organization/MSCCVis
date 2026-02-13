# Progress Log

## 2026-02-13: Web UI 入力の適用強化

### 変更ファイル

- src/web/app.py — web ui 入力の検証と 再計算時の 既存結果クリア を追加
- src/web/static/index.html — 再計算トグルを追加し api パラメータに反映
- src/modules/collect_datas.py — import フィルタ適用のため apply_filter を明示 import
- docs/PROGRESS.md — 本エントリを更新

### テスト結果

- C:/Users/genko/Documents/MSCCATools-Public/.venv/Scripts/python.exe -m pytest -q , 失敗 No module named pytest

### 判断メモ

- web ui の 入力値が 既存結果で無効化されないよう 再計算時に成果物を削除する方針にした
- 未実装の検出方式と comod 方式は エラー扱いで 明示的に入力を反映するようにした

### 残課題

- TODO(gen): pytest を導入して テストを再実行する

## 2026-02-13: Web UI Docker 対応とドキュメント整備

### 変更ファイル

- Dockerfile — `EXPOSE 8000` を追加し, Web UI をコンテナ外から利用可能にした
- README.md — Web UI セクションを追加. Docker (推奨) とローカル (確認のみ) の起動方法, 外部ツール依存の注意を明記
- docs/PROGRESS.md — 本エントリを追加

### テスト結果

- `python main.py web-ui` でローカル起動し, `curl http://127.0.0.1:8000/` で 200 OK を確認
- クローン検出パイプラインは Java / CCFinderSW / ccfindersw-parser / github-linguist に依存しており, Docker 外では実行不可であることを確認

### 判断メモ

- 既存コードの変更を避け, Dockerfile に `EXPOSE 8000` を追加するのみとした
- ローカル起動は UI 確認用途に限定し, 実際の分析には Docker を使う方針を README に明記した

### 残課題

- TODO(gen): Docker イメージをビルドして `web-ui --host 0.0.0.0` でエンドツーエンドの分析実行を確認する
