"""Contract test for the read-only, non-deploying Pages review workflow (plan Task 6)."""

from __future__ import annotations

from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY / ".github" / "workflows" / "pages-review.yml"

PINNED_ACTIONS = (
    "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
    "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b",
    "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e",
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
)


def test_pages_review_workflow_is_read_only() -> None:
    text = WORKFLOW.read_text("utf-8")
    assert "permissions:\n  contents: read" in text
    assert "fetch-depth: 0" in text
    assert "fetch-tags: true" in text
    policy = (
        "python scripts/verify_pages_review_package.py"
        " --package site-review/package.json --lockfile site-review/pnpm-lock.yaml"
    )
    install = "pnpm -C site-review install --frozen-lockfile --ignore-scripts"
    # pnpm 11 skips bin-linking under --ignore-scripts, so the CLI file is invoked directly.
    browser_acquire = (
        "pnpm -C site-review exec -- node node_modules/@playwright/test/cli.js install"
        " --with-deps chromium firefox webkit"
    )
    browser_execute = "pnpm -C site-review exec -- node node_modules/@playwright/test/cli.js test"
    assert text.count(install) == 1
    assert text.index(policy) < text.index(install) < text.index(browser_acquire)
    assert text.index(browser_acquire) < text.index(browser_execute)
    for forbidden in (
        "pull_request_target",
        "pages: write",
        "id-token: write",
        "deploy-pages",
        "configure-pages",
        "secrets.",
        "environment:",
    ):
        assert forbidden not in text
    for action in PINNED_ACTIONS:
        assert action in text
    assert 'node-version: "24.16.0"' in text
    assert "corepack prepare pnpm@11.16.0 --activate" in text
    assert "path: temp/pages-review/export" in text
    assert "if-no-files-found: error" in text


def test_pages_review_workflow_uses_only_pinned_action_shas() -> None:
    text = WORKFLOW.read_text("utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- uses:") or stripped.startswith("uses:"):
            reference = stripped.split("uses:", 1)[1].split("#", 1)[0].strip()
            assert reference in PINNED_ACTIONS, reference
