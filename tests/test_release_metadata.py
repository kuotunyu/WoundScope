from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import yaml

REPOSITORY_URL = "https://github.com/kuotunyu/WoundScope"
RESULT_BUNDLE_SHA256 = "6FF4D1F14F4242C72FA2EF3382BCBFADC15DF93DD4AEB739AE1864F7DE24F221"


def test_release_identity_and_repository_urls() -> None:
    cff = yaml.safe_load(Path("CITATION.cff").read_text(encoding="utf-8"))
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert cff["authors"] == [{"name": "kuotunyu"}]
    assert cff["version"] == "0.1.0"
    assert str(cff["date-released"]) == "2026-08-04"
    assert cff["repository-code"] == REPOSITORY_URL
    assert cff["url"] == REPOSITORY_URL

    project = pyproject["project"]
    assert project["authors"] == [{"name": "kuotunyu"}]
    assert project["urls"] == {
        "Homepage": REPOSITORY_URL,
        "Repository": REPOSITORY_URL,
        "Issues": f"{REPOSITORY_URL}/issues",
    }


def test_python_support_contract_matches_locked_runtime_wheels() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads(Path("uv.lock").read_text(encoding="utf-8"))
    readme = Path("README.md").read_text(encoding="utf-8")

    project = pyproject["project"]
    assert project["requires-python"] == ">=3.11,<3.13"
    assert "Programming Language :: Python :: 3.10" not in project["classifiers"]
    assert "Programming Language :: Python :: 3.11" in project["classifiers"]
    assert "Programming Language :: Python :: 3.12" in project["classifiers"]
    assert lock["requires-python"] == ">=3.11, <3.13"
    assert "Python 支援 3.11–3.12。" in readme


def test_tracked_markdown_does_not_expose_local_home_paths() -> None:
    tracked = (
        subprocess.run(
            ["git", "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
        .stdout.decode("utf-8")
        .split("\0")
    )
    markdown_files = [Path(name) for name in tracked if Path(name).suffix.casefold() == ".md"]
    home_path = re.compile(
        r"(?i)(?:[a-z]:(?:\\users\\|/users/)[^\\/\s`\"'<>]+|"
        r"(?<![a-z0-9:])/(?:home|users)/[^/\s`\"'<>]+)"
    )
    violations = [
        (path.as_posix(), line_number)
        for path in markdown_files
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if home_path.search(line)
    ]

    assert violations == []


def test_readme_exposes_public_colab_and_reproducible_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert (
        "https://colab.research.google.com/github/kuotunyu/WoundScope/blob/main/"
        "notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb"
    ) in readme
    assert "uv sync --all-extras --frozen" in readme
    assert "$env:WOUNDSCOPE_MODEL_PATH" in readme
    assert "$env:WOUNDSCOPE_CALIBRATION_PATH" in readme
    assert "set WOUNDSCOPE_MODEL_PATH" not in readme
    assert "releases/tag/v0.1.0" in readme
    assert "Space%20授權確認中" in readme
    assert "docs/huggingface-space-deployment.md" in readme


def test_release_notes_bind_the_verified_safe_result_bundle() -> None:
    notes = Path("docs/releases/v0.1.0.md").read_text(encoding="utf-8")

    assert "344,656 bytes" in notes
    assert RESULT_BUNDLE_SHA256 in notes
    assert "c7ec6060f1bd0a813a890b95b50c2855d3c2640c" in notes
    assert "不包含" in notes
    for forbidden_claim in ("official-test metrics", "patient-wise split", "臨床效能"):
        assert f"不宣稱 {forbidden_claim}" in notes


def test_public_model_comparison_is_aggregate_only_and_matches_results() -> None:
    svg = Path("reports/public/model_comparison.svg").read_text(encoding="utf-8")

    assert 'aria-labelledby="title desc"' in svg
    assert '<title id="title">' in svg
    assert '<desc id="desc">' in svg
    for value in ("0.8508", "0.7772", "0.8270", "0.7437"):
        assert value in svg
    assert "n=3 seeds" in svg
    assert "official-test" in svg
    assert not any(token in svg.lower() for token in ("patient", ".jpg", ".png", "sample_id"))

    readme = Path("README.md").read_text(encoding="utf-8")
    assert "reports/public/model_comparison.svg" in readme


def test_ci_and_public_bug_intake_are_least_privilege() -> None:
    workflow_text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)
    issue_form = yaml.safe_load(
        Path(".github/ISSUE_TEMPLATE/bug_report.yml").read_text(encoding="utf-8")
    )

    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert "workflow_dispatch:" in workflow_text
    issue_copy = yaml.safe_dump(issue_form, allow_unicode=True)
    for forbidden_upload in ("醫療影像", "模型權重", "secret"):
        assert forbidden_upload in issue_copy
    assert Path("SECURITY.md").is_file()
