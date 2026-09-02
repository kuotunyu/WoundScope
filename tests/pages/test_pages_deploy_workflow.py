"""Contract test for the Pages activation workflow (spec section 16.2)."""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY / ".github" / "workflows" / "pages-deploy.yml"

PINNED_ACTIONS = (
    "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
    "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b",
    "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9",
    "actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346",
)


def _jobs(text: str) -> dict[str, str]:
    body = text.split("\njobs:\n", 1)[1]
    names = re.findall(r"^  ([a-z]+):\n", body, flags=re.MULTILINE)
    chunks = re.split(r"^  [a-z]+:\n", body, flags=re.MULTILINE)[1:]
    return dict(zip(names, chunks, strict=True))


def test_pages_deploy_workflow_is_dispatch_only_with_bound_inputs() -> None:
    text = WORKFLOW.read_text("utf-8")
    assert text.startswith("name: Pages deploy\n\non:\n  workflow_dispatch:\n")
    for trigger in ("push:", "pull_request:", "pull_request_target", "schedule:"):
        assert trigger not in text
    assert "permissions:\n  contents: read" in text
    for forbidden in ("secrets.", "configure-pages", "peaceiris", "gh-pages"):
        assert forbidden not in text
    for action in PINNED_ACTIONS:
        assert action in text
    assert "site_sha:" in text and "publish_tree_sha256:" in text
    assert text.count("required: true") == 2
    assert "grep -Eq '^[0-9a-f]{40}$'" in text
    assert "grep -Eq '^[0-9a-f]{64}$'" in text
    assert "DIGEST_BINDING" in text
    assert "LIVE_MANIFEST_BINDING" in text


def test_pages_deploy_workflow_confines_write_permissions_to_the_deploy_job() -> None:
    jobs = _jobs(WORKFLOW.read_text("utf-8"))
    assert set(jobs) == {"build", "deploy", "smoke"}
    assert "pages: write" not in jobs["build"] and "id-token: write" not in jobs["build"]
    assert "pages: write" not in jobs["smoke"] and "id-token: write" not in jobs["smoke"]
    assert "pages: write" in jobs["deploy"] and "id-token: write" in jobs["deploy"]
    assert "environment:\n      name: github-pages" in jobs["deploy"]
    assert "needs: build" in jobs["deploy"]
    assert "needs: [build, deploy]" in jobs["smoke"]
    assert "actions/deploy-pages@" in jobs["deploy"]
    assert "actions/deploy-pages@" not in jobs["build"]
    assert "actions/upload-pages-artifact@" in jobs["build"]


def test_pages_deploy_workflow_uses_only_pinned_action_shas() -> None:
    text = WORKFLOW.read_text("utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- uses:") or stripped.startswith("uses:"):
            reference = stripped.split("uses:", 1)[1].split("#", 1)[0].strip()
            assert reference in PINNED_ACTIONS, reference
