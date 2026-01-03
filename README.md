MSCCATools を Docker で実行するためのセットアップ手順です。

## 事前準備
- Python や Java をローカルで用意する必要はありませんが、`lib/CCFinderSW-1.0` 配下の JAR はイメージに同梱されます。
- `ccfindersw-parser` は Docker ビルド時に `https://github.com/YukiOhta0519/ccfindersw-parser.git` から clone してビルドされ、イメージ内に同梱されます。
- GitHub からリポジトリを clone する処理を行うため、Docker ビルド・実行時ともにネットワークアクセスが必要です。
- GitHub Linguist は Docker ビルド時に gem としてインストールされます（`github-linguist` コマンドが利用可能）。

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

### run-all-steps の再開実行
`run-all-steps` は途中から再開できる引数を受け付けます（`--` 以降は `run_all_step.py` に渡されます）。
```bash
docker run --rm -it \
  -v "$(pwd)/dest:/app/dest" \
  -v "$(pwd)/dataset:/app/dataset" \
  msccatools run-all-steps -- --start-number 10
```
- `--start-index`: 0-based の開始位置
- `--start-number`: 1-based の開始位置
- `--start-url`: dataset 内の URL で開始位置を指定
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
