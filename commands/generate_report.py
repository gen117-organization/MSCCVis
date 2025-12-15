import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config import SELECTED_DATASET  # noqa: E402
from modules.util import calculate_loc  # noqa: E402


def load_dataset() -> List[dict]:
    with open(SELECTED_DATASET, "r") as f:
        return json.load(f)


def classify_clones(rows_by_clone: Dict[str, List[dict]], codebases: dict) -> dict:
    """Split clone sets by detection range and code type."""
    clonesets = {
        "within-testing": {},
        "within-production": {},
        "within-utility": {},
        "across-testing": {},
        "across-production": {},
        "across-utility": {},
    }

    for clone_id, fragments in rows_by_clone.items():
        is_testing = any("test" in frag["file_path"].lower() for frag in fragments)
        is_production = any("test" not in frag["file_path"].lower() for frag in fragments)

        service_set = set()
        service_fragments = []
        for fragment in fragments:
            for codebase in codebases:
                if fragment["file_path"].startswith(codebase):
                    service_set.add(codebase)
                    service_fragments.append(fragment)
                    break

        if len(service_fragments) <= 1:
            continue

        if len(service_set) == 1:
            range_name = "within"
        elif len(service_set) >= 2:
            range_name = "across"
        else:
            continue

        if is_testing and not is_production:
            code_type = "testing"
        elif is_production and not is_testing:
            code_type = "production"
        else:
            code_type = "utility"

        key = f"{range_name}-{code_type}"
        clonesets[key][clone_id] = service_fragments

    return clonesets


def compute_clone_ratios(clonesets: dict, workdir: Path) -> Dict[str, Optional[float]]:
    """Calculate clone ratios per mode using fragment line ranges."""
    ratios: dict[str, float] = {}
    loc_cache: dict[str, int] = {}

    for mode, clone_map in clonesets.items():
        line_flags_by_file: Dict[str, List[bool]] = {}
        for fragments in clone_map.values():
            for fragment in fragments:
                file_path = fragment["file_path"]
                abs_path = workdir / file_path
                if not abs_path.exists():
                    continue

                if file_path not in loc_cache:
                    try:
                        loc_cache[file_path] = calculate_loc(str(abs_path))
                    except OSError:
                        continue

                if file_path not in line_flags_by_file:
                    line_flags_by_file[file_path] = [False] * loc_cache[file_path]

                start = max(int(fragment["start_line"]) - 1, 0)
                end = min(int(fragment["end_line"]), loc_cache[file_path])
                for idx in range(start, end):
                    line_flags_by_file[file_path][idx] = True

        if not line_flags_by_file:
            ratios[mode] = None
            continue

        total = sum(len(flags) for flags in line_flags_by_file.values())
        clones = sum(sum(flags) for flags in line_flags_by_file.values())
        ratios[mode] = clones / total if total else None

    return ratios


def compute_comodification(clonesets: dict) -> dict[str, dict[str, int]]:
    """Calculate comodification counts per mode."""
    comodification = {}
    for mode, clone_map in clonesets.items():
        count = 0
        comodified = 0
        for fragments in clone_map.values():
            count += 1
            modifications = defaultdict(list)
            for fragment in fragments:
                for entry in json.loads(fragment["modification"]):
                    modifications[entry.get("commit")].append(entry.get("type"))
            if any(types.count("modified") >= 2 for types in modifications.values()):
                comodified += 1
        comodification[mode] = {"count": count, "comodification_count": comodified}
    return comodification


def summarize(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"n": 0, "mean": None, "variance": None, "median": None, "min": None, "max": None}
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "variance": statistics.pvariance(values) if len(values) >= 2 else 0.0,
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def main():
    dataset = load_dataset()
    total_projects = len(dataset)

    projects_with_clones = set()
    projects_with_across = set()
    missing_csv = []

    fragment_total = 0
    fragment_modified = 0

    cloneset_total = 0
    cloneset_with_modified = 0

    clone_ratio_values = []
    comodification_rates = []

    for project in dataset:
        url = project["URL"]
        name = url.split("/")[-2] + "." + url.split("/")[-1]
        workdir = project_root / "dest/projects" / name

        for language in project["languages"]:
            csv_path = project_root / "dest/csv" / name / f"{language}.csv"
            if not csv_path.exists():
                missing_csv.append(str(csv_path))
                continue

            rows_by_clone: dict[str, list[dict]] = defaultdict(list)
            modified_clone_ids = set()

            with open(csv_path, "r") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    fragment_total += 1
                    clone_id = row["clone_id"]
                    rows_by_clone[clone_id].append(row)

                    modifications = json.loads(row["modification"])
                    if any(m.get("type") == "modified" for m in modifications):
                        fragment_modified += 1
                        modified_clone_ids.add(clone_id)

            if rows_by_clone:
                projects_with_clones.add(name)

            cloneset_total += len(rows_by_clone)
            cloneset_with_modified += len(modified_clone_ids)

            clonesets = classify_clones(rows_by_clone, project["languages"][language])
            if any(clonesets[key] for key in ("across-testing", "across-production", "across-utility")):
                projects_with_across.add(name)

            clone_ratios = compute_clone_ratios(clonesets, workdir)
            clone_ratio_values.extend([v for v in clone_ratios.values() if v is not None])

            comodification = compute_comodification(clonesets)
            for data in comodification.values():
                if data["count"] == 0:
                    continue
                comodification_rates.append(data["comodification_count"] / data["count"])

    clone_ratio_stats = summarize(clone_ratio_values)
    comodification_stats = summarize(comodification_rates)

    print("# Report")
    print(f"- Total projects: {total_projects}")
    print(f"- Projects with clones: {len(projects_with_clones)} ({len(projects_with_clones) / total_projects * 100:.2f}%)")
    print(f"- Projects with across-service clones: {len(projects_with_across)} ({len(projects_with_across) / total_projects * 100:.2f}%)")
    print(f"- Clone fragments: {fragment_total:,}; modified fragments: {fragment_modified:,} ({(fragment_modified / fragment_total * 100) if fragment_total else 0:.2f}%)")
    print(f"- Clone sets: {cloneset_total:,}; sets with modified fragments: {cloneset_with_modified:,} ({(cloneset_with_modified / cloneset_total * 100) if cloneset_total else 0:.2f}%)")
    print()
    print("## Clone ratio stats")
    print(f"- count: {clone_ratio_stats['n']}")
    print(f"- mean: {clone_ratio_stats['mean']}")
    print(f"- variance: {clone_ratio_stats['variance']}")
    print(f"- median: {clone_ratio_stats['median']}")
    print(f"- min: {clone_ratio_stats['min']}")
    print(f"- max: {clone_ratio_stats['max']}")
    print()
    print("## Comodification rate stats")
    print(f"- count: {comodification_stats['n']}")
    print(f"- mean: {comodification_stats['mean']}")
    print(f"- variance: {comodification_stats['variance']}")
    print(f"- median: {comodification_stats['median']}")
    print(f"- min: {comodification_stats['min']}")
    print(f"- max: {comodification_stats['max']}")

    if missing_csv:
        print("\n## Missing CSV files")
        for path in missing_csv:
            print(f"- {path}")


if __name__ == "__main__":
    main()
