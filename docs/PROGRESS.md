# Progress Log

## 2026-02-13: Web UI 入力の適用強化

### 変更ファイル

- src/web/app.py — web ui 入力の検証と 再計算時の 既存結果クリア を追加
- src/web/static/index.html — 再計算トグルを追加し api パラメータに反映
- src/modules/collect_datas.py — import フィルタの条件分岐を追加し 引数で制御可能にした
- src/web/app.py — import フィルタの有無を 引数で渡すように変更
- src/web/app.py — CCFinderSW の min token 引数を -w から -t に修正
- src/web/static/index.html — min token の説明を -t に修正
- config.py — CLI の import 行フィルタ設定を追加
- README.md — CLI の import 行フィルタ設定を追記
- src/modules/collect_datas.py — commit 切替時と終了時を `git checkout -f` に変更
- src/web/app.py — API 側で全入力項目のバリデーションを追加
- src/web/static/index.html — UI 側で全入力項目のバリデーションを追加
- src/web/static/index.html — ? アイコンとトグルの重なりを解消
- pyproject.toml — pytest 収集から `dest` を除外する設定を追加
- docs/PROGRESS.md — 本エントリを更新

### テスト結果

- C:/Users/genko/Documents/MSCCATools-Public/.venv/Scripts/python.exe -m pytest -q , 失敗 No module named pytest
- python -m pytest -q , 失敗 no tests ran in 0.06s
- python -m pytest -q , 中断 Ctrl+C
- python -m pytest -q , docker の ログが出力され 中断
- python -m pytest -q , 失敗 dest/projects 配下の外部リポジトリ tests 収集で NameError
- python -m pytest -q , 失敗 dest/projects 配下の外部リポジトリ tests 収集で 11 件エラー
- python -m pytest -q , no tests ran in 0.09s

### 判断メモ

- web ui の 入力値が 既存結果で無効化されないよう 再計算時に成果物を削除する方針にした
- 未実装の検出方式と comod 方式は エラー扱いで 明示的に入力を反映するようにした
- CCFinderSW の 失敗原因を ログで見えるよう stderr を 捕捉して 表示する方針にした
- import 行フィルタは 引数で制御し 既存のモンキーパッチ依存を避ける方針にした
- CLI 側は config で既定値を切り替えられるようにした
- CCFinderSW の Range mode Error は -w に 50 を渡していたことが原因で, -w は 0..2 なので -t に分離した
- `apply_filter` で作業ツリーが変更されるため, 次コミットへの checkout は `-f` で強制切替する方針にした
- 入力異常は API 前に UI で検出し, さらに API 側でも同じ制約を検証する二重防御にした
- 外部クローン済みリポジトリの test 収集を避けるため `norecursedirs = ["dest"]` を採用した

### 残課題

- TODO(gen): pytest を導入して テストを再実行する
- TODO(gen): web ui で 実際の repo を指定して フィルタ反映を確認する
- TODO(gen): docker build して web ui で 失敗ログを 再確認する
- TODO(gen): python -m pytest -q を 再実行して 結果を確認する
- TODO(gen): pytest の 対象から dest/projects を 除外するか, 実行前にクリーンする

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
