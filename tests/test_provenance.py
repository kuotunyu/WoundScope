from __future__ import annotations

from pathlib import Path

from woundscope.provenance import build_provenance


def test_bundle_source_commit_is_preserved_without_git_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("sample_id\nsynthetic\n", encoding="utf-8")
    source_commit = "a" * 40
    monkeypatch.setenv("WOUNDSCOPE_SOURCE_COMMIT", source_commit)
    config = {
        "data": {"source_revision": "revision"},
        "project": {"seed": 42},
        "model": {"name": "tiny"},
    }

    provenance = build_provenance(config, manifest, seed=42, device="cuda")

    assert provenance["source_commit"] == source_commit
