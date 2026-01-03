import argparse
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).parent


def run_script(script_name: str, script_args: list[str] | None = None) -> int:
    """src/commands 配下のスクリプトを別プロセスで実行する。"""
    script_path = project_root / "src" / "commands" / script_name
    if not script_path.exists():
        print(f"スクリプトが見つかりません: {script_path}")
        return 1
    cmd = [sys.executable, str(script_path)]
    if script_args:
        cmd.extend(script_args)
    completed = subprocess.run(cmd)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="MSCCATools CLI launcher")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("generate-dataset", help="src/commands/pipeline/generate_dataset.py を実行")
    subparsers.add_parser(
        "run-all-steps",
        help="src/commands/csv_build/run_all_step.py を実行",
        description="CSV build を全ステップ実行（追加の引数は run_all_step.py に渡されます）。",
    )
    subparsers.add_parser(
        "determine-analyzed-commits",
        help="src/commands/pipeline/determine_analyzed_commits.py を実行",
    )
    subparsers.add_parser(
        "refresh-service-map",
        help="src/commands/pipeline/refresh_service_map.py を実行",
    )
    subparsers.add_parser("check-run-all-steps", help="run-all-steps の進捗を確認")
    subparsers.add_parser("summarize-csv", help="src/commands/csv_analysis/generate_report.py を実行")
    subparsers.add_parser("csv-boxplot", help="src/commands/csv_analysis/generate_figure.py を実行")

    args, unknown = parser.parse_known_args()

    if args.command == "generate-dataset":
        return run_script("pipeline/generate_dataset.py", unknown)
    if args.command == "run-all-steps":
        return run_script("csv_build/run_all_step.py", unknown)
    if args.command == "determine-analyzed-commits":
        return run_script("pipeline/determine_analyzed_commits.py", unknown)
    if args.command == "refresh-service-map":
        return run_script("pipeline/refresh_service_map.py", unknown)
    if args.command == "check-run-all-steps":
        return run_script("misc/check_progress.py", unknown)
    if args.command == "summarize-csv":
        return run_script("csv_analysis/generate_report.py", unknown)
    if args.command == "csv-boxplot":
        return run_script("csv_analysis/generate_figure.py", unknown)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
