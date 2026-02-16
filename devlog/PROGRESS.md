# Dev Progress Log

## 2026-02-16: Web UI JavaScript 切り出し

### 変更ファイル

- devlog/PROGRESS.md — 本エントリを追加し, 作業開始を記録

### テスト結果

- `/home/genko/lab/MSCCATools-Public/.venv/bin/python -m pytest -q` , 成功, 2 passed in 0.11s

### 判断メモ

- 最小差分で保守性を上げるため, `index.html` の inline JavaScript を外部ファイルへ分離する

### 残課題

- TODO(gen): 必要に応じて `app.js` の責務分割を検討する
