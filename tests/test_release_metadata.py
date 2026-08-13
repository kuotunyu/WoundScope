from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import yaml

from woundscope import __version__
from woundscope.repository_privacy import audit_repository_privacy

REPOSITORY_URL = "https://github.com/kuotunyu/WoundScope"
RESULT_BUNDLE_SHA256 = "6FF4D1F14F4242C72FA2EF3382BCBFADC15DF93DD4AEB739AE1864F7DE24F221"
REMOVED_PUBLIC_PATHS = (
    "PROGRESS.md",
    "PROJECT_PLAN.md",
    "notebooks/WoundScope_FUSeg_c7ec606_Postprocess_Resume_Colab.ipynb",
    "docs/releases/v0.1.0.md",
    "docs/releases/v0.2.0.md",
    "docs/releases/v0.2.1.md",
)


def test_release_identity_and_repository_urls() -> None:
    cff = yaml.safe_load(Path("CITATION.cff").read_text(encoding="utf-8"))
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert cff["authors"] == [{"name": "kuotunyu"}]
    assert cff["version"] == "0.2.2"
    assert str(cff["date-released"]) == "2026-08-13"
    assert cff["repository-code"] == REPOSITORY_URL
    assert cff["url"] == REPOSITORY_URL

    project = pyproject["project"]
    assert project["version"] == "0.2.2"
    assert project["authors"] == [{"name": "kuotunyu"}]
    assert project["urls"] == {
        "Homepage": REPOSITORY_URL,
        "Repository": REPOSITORY_URL,
        "Issues": f"{REPOSITORY_URL}/issues",
    }
    assert __version__ == "0.2.2"


def test_python_support_contract_matches_locked_runtime_wheels() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads(Path("uv.lock").read_text(encoding="utf-8"))
    readme = Path("README.md").read_text(encoding="utf-8")

    project = pyproject["project"]
    woundscope_package = next(
        package for package in lock["package"] if package["name"] == "woundscope"
    )
    assert project["requires-python"] == ">=3.11,<3.13"
    assert "Programming Language :: Python :: 3.10" not in project["classifiers"]
    assert "Programming Language :: Python :: 3.11" in project["classifiers"]
    assert "Programming Language :: Python :: 3.12" in project["classifiers"]
    assert lock["requires-python"] == ">=3.11, <3.13"
    assert woundscope_package["version"] == "0.2.2"
    assert "Python 支援 3.11–3.12。" in readme


def test_public_repository_excludes_internal_and_historical_files() -> None:
    completed = subprocess.run(
        ["git", "ls-files", "--", *REMOVED_PUBLIC_PATHS],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.stdout.strip() == ""


def test_tracked_repository_passes_shared_privacy_audit() -> None:
    report = audit_repository_privacy(Path.cwd())

    assert report["status"] == "ok"
    assert report["violations"] == []


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
    assert "docs/releases/" not in readme
    assert "releases/tag/v0.2.2" in readme
    assert "releases/tag/v0.2.0" not in readme
    assert "releases/tag/v0.1.0" in readme
    assert "Space%20Code--only" in readme
    assert "docs/huggingface-space-deployment.md" in readme
    assert "公開 model artifacts 與 hosted live inference 不在目前發布範圍" in readme
    assert "PERMISSION_PENDING" not in readme
    issue_form = Path(".github/ISSUE_TEMPLATE/bug_report.yml").read_text(encoding="utf-8")
    assert "例如 v0.2.2 或 40-character Git SHA" in issue_form


def test_public_cards_bind_verified_results_and_scientific_boundaries() -> None:
    model_card = Path("MODEL_CARD.md").read_text(encoding="utf-8")
    data_card = Path("DATA_CARD.md").read_text(encoding="utf-8")

    assert RESULT_BUNDLE_SHA256.casefold() in model_card.casefold()
    assert "c7ec6060f1bd0a813a890b95b50c2855d3c2640c" in model_card
    assert "0.8508±0.0035" in model_card
    assert "不是 official test、外部或臨床效能" in model_card
    assert "不可宣稱 patient-wise split" in data_card
    assert "授權資訊視為不完整" in data_card


def test_public_positioning_uses_precise_scientific_claims() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    public_copy = "\n".join(
        [
            readme,
            Path("DATA_CARD.md").read_text(encoding="utf-8"),
            Path("MODEL_CARD.md").read_text(encoding="utf-8"),
        ]
    )

    for required in (
        "CV research flagship",
        "binary semantic segmentation",
        "duplicate-group-aware",
        "SHA-256 exact duplicate",
        "pHash near-duplicate",
        "image-level Bootstrap",
    ):
        assert required in public_copy

    for overclaim in (
        "糖尿病足部潰瘍實例語意分割",
        "pHash 去除",
        "進行盲測",
        "生產級邊緣部署",
    ):
        assert overclaim not in public_copy


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


def test_readme_presents_review_workbench_without_model_overclaim() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "reports/public/woundscope-ui-showcase.webp" in readme
    assert "React + TypeScript + Vite" in readme
    assert "FastAPI" in readme
    assert "研究展示模式" in readme
    assert "模型可用時才開啟本機分割複核" in readme
    assert "啟動本機 Gradio Web UI" not in readme


def test_ci_and_public_bug_intake_are_least_privilege() -> None:
    workflow_text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)
    issue_form = yaml.safe_load(
        Path(".github/ISSUE_TEMPLATE/bug_report.yml").read_text(encoding="utf-8")
    )

    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert "workflow_dispatch:" in workflow_text
    jobs = workflow["jobs"]
    assert set(jobs) == {
        "python-311-tests",
        "python-312-build",
        "frontend-tests",
        "synthetic-gates",
    }
    setup_versions: dict[str, str] = {}
    commands: dict[str, str] = {}
    for job_name, job in jobs.items():
        commands[job_name] = "\n".join(step["run"] for step in job["steps"] if "run" in step)
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"].split(" #", 1)[0])
        setup = next(
            (
                step
                for step in job["steps"]
                if str(step.get("uses", "")).startswith("astral-sh/setup-uv@")
            ),
            None,
        )
        if setup is not None:
            setup_versions[job_name] = setup["with"]["python-version"]
    assert setup_versions == {"python-311-tests": "3.11", "python-312-build": "3.12"}
    frontend_job = jobs["frontend-tests"]
    setup_node = frontend_job["steps"][1]
    assert str(setup_node["uses"]).startswith(
        "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e"
    )
    assert setup_node["with"]["node-version"] == "24"
    assert setup_node["with"]["package-manager-cache"] is False
    for command in (
        "pnpm install --frozen-lockfile",
        "pnpm test:run",
        "pnpm typecheck",
        "pnpm lint",
        "pnpm build",
    ):
        assert command in commands["frontend-tests"]
    assert "scripts/audit_repository_privacy.py" in commands["python-311-tests"]
    assert "grep -E" not in commands["python-311-tests"]
    assert "uv run pytest -q" in commands["python-312-build"]
    assert "uv build" in commands["python-312-build"]
    assert "uv run --isolated --no-project --with" in commands["python-312-build"]
    assert "PACKAGE_INSTALL_SMOKE_PASS" in commands["python-312-build"]
    required_gate = jobs["synthetic-gates"]
    assert required_gate["name"] == "synthetic-gates"
    assert required_gate["if"] == "${{ always() }}"
    assert set(required_gate["needs"]) == {
        "python-311-tests",
        "python-312-build",
        "frontend-tests",
    }
    assert "PYTHON_311_RESULT" in commands["synthetic-gates"]
    assert "PYTHON_312_RESULT" in commands["synthetic-gates"]
    assert "FRONTEND_RESULT" in commands["synthetic-gates"]
    assert 'test "$PYTHON_311_RESULT" = "success"' in commands["synthetic-gates"]
    assert 'test "$PYTHON_312_RESULT" = "success"' in commands["synthetic-gates"]
    assert 'test "$FRONTEND_RESULT" = "success"' in commands["synthetic-gates"]
    issue_copy = yaml.safe_dump(issue_form, allow_unicode=True)
    for forbidden_upload in ("醫療影像", "模型權重", "secret"):
        assert forbidden_upload in issue_copy
    assert Path("SECURITY.md").is_file()
