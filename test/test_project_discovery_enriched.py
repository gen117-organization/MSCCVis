"""_gather_options_from_enriched / _build_enriched_label / _load_analysis_params のテスト."""

import json
from pathlib import Path

import pytest


# --- _build_enriched_label ---


class TestBuildEnrichedLabel:
    """_build_enriched_label の単体テスト."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from visualize.data_loader.project_discovery import _build_enriched_label

        self.build = _build_enriched_label

    def test_default_params_produces_standard_label(self):
        params = {
            "detection_method": "normal",
            "min_tokens": 50,
            "import_filter": True,
            "comod_method": "clone_set",
            "analysis_method": "merge_commit",
            "analysis_frequency": 1,
            "search_depth": -1,
            "max_analyzed_commits": -1,
        }
        label = self.build("JavaScript", params)
        assert "Language: JavaScript" in label
        assert "Detection: CCFinderSW (Normal)" in label
        assert "Filter: Import Filtered" in label
        assert "Analysis: Merge Commit" in label
        assert "Comod: Clone Set" in label
        assert "Min Tokens: 50" in label
        # search_depth=-1, mac=-1 → 表示しない
        assert "Search Depth" not in label
        assert "Max Commits" not in label

    def test_nofilter_label(self):
        params = {"import_filter": False}
        label = self.build("Go", params)
        assert "Filter: No Filter" in label

    def test_tks_detection_label(self):
        params = {"detection_method": "TKS12"}
        label = self.build("Java", params)
        assert "Detection: TKS (12)" in label

    def test_rnr_detection_label(self):
        params = {"detection_method": "RNR5"}
        label = self.build("Python", params)
        assert "Detection: RNR (5)" in label

    def test_frequency_analysis_label(self):
        params = {"analysis_method": "frequency", "analysis_frequency": 50}
        label = self.build("Java", params)
        assert "Analysis: Frequency (50)" in label

    def test_tag_analysis_label(self):
        params = {"analysis_method": "tag"}
        label = self.build("C++", params)
        assert "Analysis: Tag" in label

    def test_clone_pair_comod_label(self):
        params = {"comod_method": "clone_pair"}
        label = self.build("Rust", params)
        assert "Comod: Clone Pair" in label

    def test_search_depth_shown_when_positive(self):
        params = {"search_depth": 100}
        label = self.build("Go", params)
        assert "Search Depth: 100" in label

    def test_max_commits_shown_when_positive(self):
        params = {"max_analyzed_commits": 500}
        label = self.build("Go", params)
        assert "Max Commits: 500" in label


# --- _load_analysis_params ---


class TestLoadAnalysisParams:
    """_load_analysis_params の単体テスト."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from visualize.data_loader.project_discovery import _load_analysis_params

        self.load = _load_analysis_params

    def test_loads_from_json_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        params_dir = tmp_path / "dest" / "analysis_params"
        params_dir.mkdir(parents=True)
        params_file = params_dir / "my_project.json"
        expected = {
            "detection_method": "TKS12",
            "min_tokens": 30,
            "import_filter": False,
            "comod_method": "clone_pair",
            "analysis_method": "tag",
            "analysis_frequency": 1,
            "search_depth": 200,
            "max_analyzed_commits": 50,
        }
        params_file.write_text(json.dumps(expected), encoding="utf-8")

        result = self.load("my_project")
        assert result == expected

    def test_fallback_to_config_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # analysis_params ディレクトリなし → config.py フォールバック
        result = self.load("nonexistent_project")
        # 最低限キーが含まれていること
        assert "detection_method" in result
        assert "min_tokens" in result
        assert "import_filter" in result
        assert "analysis_method" in result

    def test_fallback_returns_default_keys(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = self.load("no_file")
        expected_keys = {
            "detection_method",
            "min_tokens",
            "import_filter",
            "comod_method",
            "analysis_method",
            "analysis_frequency",
            "search_depth",
            "max_analyzed_commits",
        }
        assert expected_keys.issubset(set(result.keys()))


# --- _gather_options_from_enriched ---


class TestGatherOptionsFromEnriched:
    """_gather_options_from_enriched の単体テスト."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from visualize.data_loader.project_discovery import (
            _gather_options_from_enriched,
        )

        self.gather = _gather_options_from_enriched

    def _setup_enriched(self, tmp_path, project, languages, *, filtered=False):
        """enriched_fragments ディレクトリにダミー CSV を配置する."""
        ed = tmp_path / "dest" / "enriched_fragments" / project
        ed.mkdir(parents=True)
        prefix = "filtered_" if filtered else ""
        for lang in languages:
            (ed / f"{prefix}{lang}.csv").write_text("dummy", encoding="utf-8")

    def _setup_params(self, tmp_path, project, params):
        """analysis_params JSON を配置する."""
        pd = tmp_path / "dest" / "analysis_params"
        pd.mkdir(parents=True, exist_ok=True)
        (pd / f"{project}.json").write_text(
            json.dumps(params), encoding="utf-8"
        )

    def test_returns_options_for_enriched_csv(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_enriched(tmp_path, "org.repo", ["JavaScript", "Go"])
        self._setup_params(
            tmp_path,
            "org.repo",
            {"detection_method": "normal", "min_tokens": 50},
        )

        options = self.gather("org.repo")
        assert len(options) == 2
        langs = [o["language"] for o in options]
        assert "JavaScript" in langs
        assert "Go" in langs

    def test_option_value_format(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_enriched(tmp_path, "org.repo", ["Java"])

        options = self.gather("org.repo")
        assert len(options) == 1
        assert options[0]["value"] == "org.repo|||latest|||Java"

    def test_label_contains_analysis_params(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_enriched(tmp_path, "org.repo", ["Python"])
        self._setup_params(
            tmp_path,
            "org.repo",
            {
                "detection_method": "TKS12",
                "min_tokens": 30,
                "import_filter": False,
                "analysis_method": "tag",
                "comod_method": "clone_pair",
            },
        )

        options = self.gather("org.repo")
        label = options[0]["label"]
        assert "Language: Python" in label
        assert "Detection: TKS (12)" in label
        assert "Filter: No Filter" in label
        assert "Analysis: Tag" in label
        assert "Comod: Clone Pair" in label
        assert "Min Tokens: 30" in label

    def test_returns_empty_when_no_csv_dirs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        options = self.gather("nonexistent")
        assert options == []

    def test_filtered_prefix_stripped(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_enriched(tmp_path, "org.repo", ["TypeScript"], filtered=True)

        options = self.gather("org.repo")
        assert len(options) == 1
        assert options[0]["language"] == "TypeScript"

    def test_fallback_to_dest_csv(self, tmp_path, monkeypatch):
        """enriched_fragments がない場合 dest/csv にフォールバック."""
        monkeypatch.chdir(tmp_path)
        csv_dir = tmp_path / "dest" / "csv" / "org.repo"
        csv_dir.mkdir(parents=True)
        (csv_dir / "JavaScript.csv").write_text("dummy", encoding="utf-8")

        options = self.gather("org.repo")
        assert len(options) == 1
        assert options[0]["language"] == "JavaScript"

    def test_sorted_by_language(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self._setup_enriched(tmp_path, "org.repo", ["TypeScript", "Go", "Java"])

        options = self.gather("org.repo")
        langs = [o["language"] for o in options]
        assert langs == sorted(langs)

    def test_fallback_to_services_json_language_stats(self, tmp_path, monkeypatch):
        """enriched_fragments も dest/csv もない場合, services.json から言語を取得."""
        monkeypatch.chdir(tmp_path)
        sj_dir = tmp_path / "dest" / "services_json"
        sj_dir.mkdir(parents=True)
        sj_data = {
            "services": {},
            "language_stats": {
                "Python": {"services": {}, "total_files": 10, "total_loc": 500},
                "Go": {"services": {}, "total_files": 5, "total_loc": 200},
            },
        }
        (sj_dir / "org.repo.json").write_text(
            json.dumps(sj_data), encoding="utf-8"
        )

        options = self.gather("org.repo")
        assert len(options) == 2
        langs = {o["language"] for o in options}
        assert langs == {"Python", "Go"}


# --- get_csv_options_for_project (統合テスト) ---


class TestGetCsvOptionsForProject:
    """get_csv_options_for_project の結合テスト."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from visualize.data_loader.project_discovery import (
            get_csv_options_for_project,
        )

        self.get_opts = get_csv_options_for_project

    def test_enriched_fallback_when_no_scatter(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # enriched_fragments を配置
        ed = tmp_path / "dest" / "enriched_fragments" / "org.repo"
        ed.mkdir(parents=True)
        (ed / "Java.csv").write_text("dummy", encoding="utf-8")

        options = self.get_opts("org.repo")
        assert len(options) == 1
        assert options[0]["language"] == "Java"
        assert "Detection:" in options[0]["label"]

    def test_returns_empty_when_nothing_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        options = self.get_opts("nonexistent")
        assert options == []
