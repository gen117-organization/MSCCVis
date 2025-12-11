import argparse
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).parent


def run_script(script_name: str, script_args: list[str] | None = None) -> int:
    """commands/ 配下のスクリプトを別プロセスで実行する。"""
    script_path = project_root / "commands" / script_name
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

    subparsers.add_parser("generate-dataset", help="commands/generate_dataset.py を実行")
    subparsers.add_parser("run-all-steps", help="commands/run_all_step.py を実行")
    subparsers.add_parser("determine-analyzed-commits", help="commands/determine_analyzed_commits.py を実行")

    args, unknown = parser.parse_known_args()

    if args.command == "generate-dataset":
        return run_script("generate_dataset.py", unknown)
    if args.command == "run-all-steps":
        return run_script("run_all_step.py", unknown)
    if args.command == "determine-analyzed-commits":
        return run_script("determine_analyzed_commits.py", unknown)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
