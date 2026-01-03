import sys
from pathlib import Path
import json
import argparse


def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return start


project_root = _find_repo_root(Path(__file__).resolve())
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))

import modules.collect_datas
import modules.analyze_cc
import modules.analyze_modification
from config import SELECTED_DATASET

STEP_ORDER = ("collect", "analyze-cc", "analyze-modification")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all CSV build steps.")
    parser.add_argument(
        "--dataset",
        default=SELECTED_DATASET,
        help="Dataset JSON path (default: config.SELECTED_DATASET).",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="0-based index to start from in the dataset list.",
    )
    parser.add_argument(
        "--start-number",
        type=int,
        default=None,
        help="1-based position to start from in the dataset list.",
    )
    parser.add_argument(
        "--start-url",
        default=None,
        help="Project URL to start from (matches dataset entries' URL).",
    )
    parser.add_argument(
        "--from-step",
        choices=STEP_ORDER,
        default="collect",
        help="Step to start from for each project.",
    )
    return parser.parse_args()


def _resolve_start_index(args: argparse.Namespace, dataset: list[dict]) -> int:
    if args.start_number is not None and args.start_index != 0:
        raise ValueError("Use only one of --start-index or --start-number.")
    if args.start_number is not None:
        if args.start_number <= 0:
            raise ValueError("--start-number must be 1 or greater.")
        return args.start_number - 1
    if args.start_url:
        for idx, project in enumerate(dataset):
            if project.get("URL") == args.start_url:
                return idx
        raise ValueError(f"URL not found in dataset: {args.start_url}")
    return args.start_index


def _run_project(project: dict, from_step: str) -> None:
    start_at = STEP_ORDER.index(from_step)
    for step in STEP_ORDER[start_at:]:
        if step == "collect":
            modules.collect_datas.collect_datas_of_repo(project)
        elif step == "analyze-cc":
            modules.analyze_cc.analyze_repo(project)
        elif step == "analyze-modification":
            modules.analyze_modification.analyze_repo(project)


if __name__ == "__main__":
    args = _parse_args()
    with open(args.dataset, "r") as f:
        dataset = json.load(f)
    start_index = _resolve_start_index(args, dataset)
    if start_index < 0 or start_index >= len(dataset):
        raise SystemExit(f"start index out of range: {start_index}")
    for project in dataset[start_index:]:
        _run_project(project, args.from_step)
