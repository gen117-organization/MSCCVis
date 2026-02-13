MSCCATools を Docker で実行するためのセットアップ手順です。

## 事前準備
- Python や Java をローカルで用意する必要はありませんが、`lib/CCFinderSW-1.0` 配下の JAR はイメージに同梱されます。
- `ccfindersw-parser` は Docker ビルド時に `https://github.com/YukiOhta0519/ccfindersw-parser.git` から clone してビルドされ、イメージ内に同梱されます。
- GitHub からリポジトリを clone する処理を行うため、Docker ビルド・実行時ともにネットワークアクセスが必要です。
- GitHub Linguist は Docker ビルド時に gem としてインストールされます（`github-linguist` コマンドが利用可能）。
- CCFinderSW の Java メモリ設定は `config.py` の `CCFINDERSW_JAVA_XMX` / `CCFINDERSW_JAVA_XSS` で調整できます。

## データセットの取得（Filtered 版）
公開リポジトリにはデータセットを含めていないため、以下から Filtered 版を取得して配置してください。
- 取得元: `https://github.com/darioamorosodaragona-tuni/Microservices-Dataset`
- 配置先: `dataset/Filtered.csv`

例（手動ダウンロード後に配置）:
```bash
cp /path/to/Filtered.csv dataset/Filtered.csv
```

## イメージのビルド
```bash
docker build -t msccatools .
```

## コンテナの実行例
成果物をホスト側に残すために `dest` をマウントして実行します。
```bash
docker run --rm -it \
  -v "$(pwd)/dest:/app/dest" \
  -v "$(pwd)/dataset:/app/dataset" \
  msccatools run-all-steps
```
他のサブコマンドを使う場合は `run-all-steps` を適宜置き換えてください。
- 主なサブコマンド例
  - `generate-dataset`: `src/commands/pipeline/generate_dataset.py` を実行
  - `determine-analyzed-commits`: `src/commands/pipeline/determine_analyzed_commits.py` を実行
  - `refresh-service-map`: 対象コミットに合わせてサービス情報とマッピングを再生成
  - `check-run-all-steps`: `run-all-steps` の進捗を確認（`dest/csv` の生成状況をチェック）
  - `summarize-csv`: 生成済みの CSV から集計レポートを出力（`dest/csv` 配下が必要）
  - `csv-boxplot`: クローン率を6分類（within/inter × testing/production/mixed）で集計し、分類ごとの箱ひげ図PDFを `dest/figures/` に出力（`dest/csv` 配下が必要）
  - `web-ui`: 解析実行のためのUIを起動

### Web UI (設定画面)
クローン検出のパラメーター設定や実行を行うための Web 画面を提供しています.

> **注意**: クローン検出の実行には Java, CCFinderSW, ccfindersw-parser, github-linguist が必要です.
> これらは Docker イメージ内にのみ同梱されるため, **Docker コンテナ内での起動を推奨**します.
> ローカル起動では画面の表示は可能ですが, 分析実行時にエラーになります.

#### 起動方法 (Docker — 推奨)
ポート 8000 を公開して起動します. コンテナ外のブラウザからアクセスするため `--host 0.0.0.0` を指定します.
```bash
docker run --rm -it -p 8000:8000 \
  -v "$(pwd)/dest:/app/dest" \
  -v "$(pwd)/dataset:/app/dataset" \
  msccatools web-ui --host 0.0.0.0
```
起動後, ブラウザで `http://localhost:8000` にアクセスしてください.

#### 起動方法 (Local — 画面確認のみ)
外部ツールが揃っていないため分析の実行はできませんが, UI の確認は可能です.
```bash
pip install -r requirements.txt
python main.py web-ui
```
起動後, ブラウザで `http://127.0.0.1:8000` にアクセスしてください.

### run-all-steps の再開実行
`run-all-steps` は途中から再開できる引数を受け付けます。
```bash
docker run --rm -it \
  -v "$(pwd)/dest:/app/dest" \
  -v "$(pwd)/dataset:/app/dataset" \
  msccatools run-all-steps --start-number 10
```
- `--start-index`: 0-based の開始位置
- `--start-number`: 1-based の開始位置
- `--start-url`: dataset 内の URL で開始位置を指定
- `--only-index`: 0-based の1件だけを実行
- `--only-number`: 1-based の1件だけを実行
- `--only-url`: dataset 内の URL に一致する1件だけを実行
- `--from-step`: `collect` / `analyze-cc` / `analyze-modification` のいずれか

### ccfindersw-parser バイナリについて
- Docker ビルド時に自動で clone & build され、イメージ内の `/usr/local/bin/ccfindersw-parser` および `/app/lib/ccfindersw-parser/target/release/ccfindersw-parser` に配置されます。
- 既に手元にバイナリがあり、それを使いたい場合は上記のようにディレクトリを `-v` でマウントしてください（自動ビルドを上書きできます）。

### ccfindersw-parser のビルド（ホスト側）
レポジトリを clone してバイナリを生成するヘルパーを用意しています（Rust toolchain 必須）。
```bash
./scripts/build_ccfindersw_parser.sh
```
ビルド後、`lib/ccfindersw-parser/target/release/ccfindersw-parser` が生成されます。そのまま Docker ビルドで同梱するか、`docker run` 時に該当ディレクトリをマウントしてください。

## 動作確認
イメージが正常に動作するかを簡易確認するには以下を実行します（ヘルプの表示のみ）。
```bash
docker run --rm msccatools --help
```
