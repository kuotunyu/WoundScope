# WoundScope Hugging Face Space 安全部署 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可重現、可稽核且不含 data／weights／ONNX／secrets 的 Hugging Face Space 純程式碼部署包，並強化共用 Gradio UI 的隱私預設。

**Architecture:** 擴充既有 `woundscope.bundles` deterministic ZIP／manifest 能力，從 committed Git HEAD 的固定 allowlist 產生 code-only staging directory 與 ZIP；`scripts/` 維持 thin CLI。Local 與未來 Space 共用同一個 Gradio `build_demo`，模型仍只經 local path 或明確的 immutable Hugging Face revision 解析；未取得 FUSeg 書面授權前不建立 live Space 或 model repository。

**Tech Stack:** Python 3.11+、`pathlib`、Git、`zipfile`、SHA-256、Gradio 6.x、pytest、Ruff、Docker CPU image。

## Global Constraints

- 狀態維持 `PERMISSION_PENDING`；本計畫不建立或修改 Hugging Face Space／model repository，也不操作 token 或寄出授權信。
- 不追蹤或打包 FUSeg images／masks、image-level manifests、private galleries、sample predictions、checkpoints、`.safetensors`、`.pt`、`.pth`、ONNX、calibration artifacts 或 `.env`。
- 所有路徑使用 `pathlib`；不得寫死 Windows、WSL、Colab 或 Google Drive absolute path。
- 所有行為變更先寫 failing test，再做最小實作；測試只使用 synthetic fixtures、CPU 與 committed source bytes。
- README、Space metadata、部署文件與 UI 以正體中文（`zh-TW`）為主，technical proper nouns 保留原文。
- UI 不提供 diagnosis、severity、prognosis 或 treatment advice，並禁止上傳含可識別個人資料的影像。
- Git author／committer 只能是 `kuotunyu <61350295+kuotunyu@users.noreply.github.com>`；不得加入共同作者、trailers 或 bot commit。
- 本計畫只建立本機 commit 與 gitignored candidate；不得 push GitHub 或 Hugging Face。

---

## File structure

### 新增

- `deploy/huggingface/README.md`：Hugging Face Space YAML front matter、正體中文用途、`PERMISSION_PENDING` 與 privacy copy。
- `scripts/build_huggingface_space_bundle.py`：只解析 CLI、呼叫 core builder 並輸出 JSON summary。
- `tests/test_huggingface_space_bundle.py`：allowlist、path safety、privacy、manifest、determinism 與 clean-extract tests。
- `tests/test_huggingface_space_metadata.py`：Space front matter、文件狀態、README badge/link 與禁止內容 tests。
- `docs/huggingface-space-deployment.md`：建立 candidate、權限模式、secrets、發布 gate、rollback 與 teardown 指南。
- `docs/permissions/fuseg-model-artifact-permission-request.md`：不會自動寄送的授權詢問信草稿。

### 修改

- `src/woundscope/bundles.py`：加入 committed-HEAD Space allowlist、candidate/ZIP builder 與 verifier；共用既有 deterministic ZIP primitives。
- `src/woundscope/gradio_app.py`：關閉 analytics、設定 cache cleanup、upload-only/no-share、private event 與 immutable HF revision gate。
- `tests/test_onnx_inference_app.py`：Gradio privacy config 與 HF revision fail-closed regressions。
- `tests/test_script_interfaces.py`：鎖定新 CLI options。
- `tests/test_release_metadata.py`：鎖定 README 的授權狀態與 deployment guide link。
- `README.md`：將 Space badge／說明更新為「授權確認中」，連結 code-only deployment guide。
- `PROJECT_PLAN.md`：Decision Log 鎖定 code-only／written-permission gate，不改 scientific protocol。
- `PROGRESS.md`：新增 M7 deployment-readiness 狀態與 exact PASS/FAIL evidence。

---

### Task 1: Committed-HEAD code-only bundle engine

**Files:**
- Create: `tests/test_huggingface_space_bundle.py`
- Modify: `src/woundscope/bundles.py`

**Interfaces:**
- Consumes: existing `_git(repository: Path, *arguments: str, text: bool = True)`, `_safe_archive_path(value: str)`, `_sha256_bytes(content: bytes)`, `_write_zip(output: Path, files: dict[str, bytes], manifest: dict[str, Any])` and `verify_bundle(bundle, expected_kind, expected_source_commit)`.
- Produces: `build_huggingface_space_bundle(repository: str | Path, output_directory: str | Path, output_zip: str | Path) -> dict[str, Any]` and `verify_huggingface_space_candidate(directory: str | Path, bundle: str | Path, *, expected_source_commit: str | None = None) -> dict[str, Any]`.
- Manifest contract: `schema_version=1`、`kind="huggingface_space"`、40-character lowercase `source_commit`，`files` 依 destination path 排序並包含 `path`、`source_path`、`size`、`sha256`。
- Source mapping: `deploy/huggingface/README.md -> README.md`；`Dockerfile`、`LICENSE`、`pyproject.toml`、`uv.lock` 保持檔名；`app/**/*.py` 與 `src/**/*.py` 保持 relative path。

- [ ] **Step 1: Write the failing happy-path and determinism tests**

在新 test file 建立 temporary Git repository，寫入最小合法 source、commit，連續建立兩個 candidate：

```python
import hashlib
import subprocess
from pathlib import Path

import pytest

from woundscope import bundles


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _commit_all(repository: Path, message: str) -> None:
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _space_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    files = {
        "deploy/huggingface/README.md": "---\nsdk: docker\napp_port: 7860\n---\nPERMISSION_PENDING\n",
        "Dockerfile": "FROM python:3.11-slim\n",
        "LICENSE": "Apache License 2.0\n",
        "pyproject.toml": "[project]\nname='woundscope'\nversion='0.1.0'\n",
        "uv.lock": "version = 1\n",
        "app/app.py": "from woundscope import __version__\n",
        "src/woundscope/__init__.py": '__version__ = "0.1.0"\n',
    }
    for relative, content in files.items():
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.name", "Test")
    _git(repository, "config", "user.email", "test@example.com")
    _commit_all(repository, "fixture")
    return repository


def test_space_bundle_uses_committed_allowlist_and_is_deterministic(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_zip = tmp_path / "first.zip"
    second_zip = tmp_path / "second.zip"

    first = bundles.build_huggingface_space_bundle(
        repository, first_dir, first_zip
    )
    second = bundles.build_huggingface_space_bundle(
        repository, second_dir, second_zip
    )

    assert first == second
    assert _sha256(first_zip) == _sha256(second_zip)
    assert first["kind"] == "huggingface_space"
    assert (first_dir / "README.md").read_text(encoding="utf-8").startswith("---\n")
    assert not (first_dir / "deploy").exists()
    assert {record["path"] for record in first["files"]} == {
        "Dockerfile",
        "LICENSE",
        "README.md",
        "app/app.py",
        "pyproject.toml",
        "src/woundscope/__init__.py",
        "uv.lock",
    }
    assert bundles.verify_huggingface_space_candidate(
        first_dir, first_zip, expected_source_commit=first["source_commit"]
    ) == first
```

- [ ] **Step 2: Run the happy-path test to verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_huggingface_space_bundle.py::test_space_bundle_uses_committed_allowlist_and_is_deterministic -v
```

Expected: FAIL because `woundscope.bundles` has no `build_huggingface_space_bundle`.

- [ ] **Step 3: Write prohibited-content and path-safety tests**

加入 parameterized cases，逐一驗證：

```python
@pytest.mark.parametrize(
    ("relative_path", "content", "message"),
    [
        ("app/model.onnx", b"weights", "prohibited"),
        ("src/woundscope/patient.png", b"image", "prohibited"),
        ("app/.env", b"HF_TOKEN=secret", "prohibited"),
        ("app/private.py", b"HF_TOKEN = 'secret'\n", "secret-like"),
        ("app/path.py", b"ROOT = 'C:\\\\Users\\\\owner\\\\private'\n", "absolute path"),
        ("app/unexpected.txt", b"unexpected", "unexpected"),
    ],
)
def test_space_bundle_rejects_prohibited_committed_members(
    tmp_path: Path, relative_path: str, content: bytes, message: str
) -> None:
    repository = _space_repository(tmp_path)
    path = repository / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    _commit_all(repository, "unsafe fixture")

    with pytest.raises(ValueError, match=message):
        bundles.build_huggingface_space_bundle(
            repository, tmp_path / "candidate", tmp_path / "candidate.zip"
        )
    assert not (tmp_path / "candidate").exists()
    assert not (tmp_path / "candidate.zip").exists()
```

另加 tests：allowlisted symlink 被拒絕、non-empty output directory 被拒絕、output ZIP 位於 staging directory 被拒絕、tracked worktree dirty 被拒絕、tampered directory／ZIP checksum 被 verifier 拒絕。

- [ ] **Step 4: Run all new bundle tests to verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_huggingface_space_bundle.py -v
```

Expected: FAIL on missing builder/verifier; fixture setup itself passes.

- [ ] **Step 5: Implement the minimal bundle contract**

在 `bundles.py` 加入明確 mapping 與 validator；只讀 committed `HEAD:<path>`，不得讀 working-tree bytes：

```python
SPACE_FILE_MAP = {
    "deploy/huggingface/README.md": "README.md",
    "Dockerfile": "Dockerfile",
    "LICENSE": "LICENSE",
    "pyproject.toml": "pyproject.toml",
    "uv.lock": "uv.lock",
}
SPACE_SOURCE_ROOTS = ("app/", "src/")
SPACE_SOURCE_SUFFIXES = {".py"}
SPACE_PROHIBITED_SUFFIXES = {
    ".bmp", ".gif", ".jpeg", ".jpg", ".onnx", ".png", ".pt",
    ".pth", ".safetensors", ".tif", ".tiff", ".webp",
}

def build_huggingface_space_bundle(
    repository: str | Path,
    output_directory: str | Path,
    output_zip: str | Path,
) -> dict[str, Any]:
    """Build and verify a code-only Space candidate from committed HEAD."""
```

Implementation requirements:

- 驗證 tracked worktree clean 與 immutable 40-character source commit。
- 解析整個 `git ls-tree -r HEAD`；mapping exact files 必須存在，`app/`／`src/` 內只允許 regular `.py`，allowlisted symlink 立即失敗。
- Candidate member 全部 UTF-8 decode；套用既有 `SECRET_PATTERN`／`ABSOLUTE_PATH_PATTERN`，並拒絕 prohibited suffix、`.env` basename 與 unsafe archive path。
- Staging directory 不存在或為空才可使用；ZIP 不可位於 staging tree。
- 先把所有 bytes 保存在記憶體並完整驗證，再建立 directory／ZIP；例外時只清理由本次呼叫建立的不完整 output。
- 使用既有 fixed ZIP timestamp／stable ordering；`bundle_manifest.json` 同時存在 staging 與 ZIP，directory／ZIP inventory 必須一致。

- [ ] **Step 6: Run focused and existing bundle tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_huggingface_space_bundle.py tests/test_bundles.py -q
.venv\Scripts\python.exe -m ruff check src/woundscope/bundles.py tests/test_huggingface_space_bundle.py
.venv\Scripts\python.exe -m ruff format --check src/woundscope/bundles.py tests/test_huggingface_space_bundle.py
```

Expected: all tests PASS; Ruff and format PASS.

- [ ] **Step 7: Commit the bundle engine**

```powershell
git add src/woundscope/bundles.py tests/test_huggingface_space_bundle.py
git diff --cached --check
git -c user.name=kuotunyu -c user.email=61350295+kuotunyu@users.noreply.github.com commit -m "feat: add safe Hugging Face bundle builder"
```

Expected: one commit authored and committed only by `kuotunyu`.

---

### Task 2: Space template and thin builder CLI

**Files:**
- Create: `deploy/huggingface/README.md`
- Create: `scripts/build_huggingface_space_bundle.py`
- Create: `tests/test_huggingface_space_metadata.py`
- Modify: `tests/test_script_interfaces.py`

**Interfaces:**
- Consumes: `build_huggingface_space_bundle(repository, output_directory, output_zip)` from Task 1.
- Produces CLI options `--repository`、`--output-dir`、`--output-zip`; success prints JSON containing `status="verified"`、absolute outputs、source commit、file count 與 ZIP SHA-256。
- Default outputs: `artifacts/huggingface-space/candidate/` and `artifacts/huggingface-space/WoundScope_hf_space_code_only.zip`.

- [ ] **Step 1: Write failing metadata and CLI-interface tests**

```python
def test_space_readme_declares_code_only_permission_pending_contract() -> None:
    text = Path("deploy/huggingface/README.md").read_text(encoding="utf-8")
    front_matter = yaml.safe_load(text.split("---", 2)[1])
    assert front_matter["sdk"] == "docker"
    assert front_matter["app_port"] == 7860
    assert front_matter["license"] == "apache-2.0"
    assert "PERMISSION_PENDING" in text
    assert "不包含模型權重" in text
    assert "不得上傳可識別個人資料" in text

def test_space_builder_cli_exposes_safe_output_options() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/build_huggingface_space_bundle.py", "--help"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    assert "--output-dir" in completed.stdout
    assert "--output-zip" in completed.stdout
```

同時在 `test_staged_pipeline_scripts_expose_locked_interfaces` 的 parameter list 加入：

```python
("scripts/build_huggingface_space_bundle.py", "--output-dir"),
```

- [ ] **Step 2: Run tests to verify RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_huggingface_space_metadata.py tests/test_script_interfaces.py -q
```

Expected: FAIL because template and CLI do not exist.

- [ ] **Step 3: Create the Space README template**

Front matter 必須使用以下固定 contract：

```yaml
---
title: WoundScope
emoji: 🩹
colorFrom: blue
colorTo: teal
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: 足部潰瘍影像 segmentation 研究展示（授權確認中）
---
```

Body 必須以 `# WoundScope（授權確認中）` 開頭，顯示 `PERMISSION_PENDING`、code-only/no-model 狀態、FUSeg attribution、PHI upload prohibition、non-clinical boundary，以及缺少正式 model configuration 時 inference 會 fail closed。

- [ ] **Step 4: Implement the thin CLI**

```python
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/huggingface-space/candidate"),
    )
    parser.add_argument(
        "--output-zip",
        type=Path,
        default=Path("artifacts/huggingface-space/WoundScope_hf_space_code_only.zip"),
    )
    args = parser.parse_args()
    manifest = build_huggingface_space_bundle(
        args.repository, args.output_dir, args.output_zip
    )
    print(json.dumps(_summary(args, manifest), ensure_ascii=False, indent=2))
    return 0
```

`_summary` 使用 `Path.resolve()` 與 streaming SHA-256 計算 ZIP hash；不輸出環境變數、model ID 或 token。

- [ ] **Step 5: Run focused tests and CLI smoke**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_huggingface_space_metadata.py tests/test_script_interfaces.py -q
.venv\Scripts\python.exe scripts/build_huggingface_space_bundle.py --help
.venv\Scripts\python.exe -m ruff check deploy scripts/build_huggingface_space_bundle.py tests/test_huggingface_space_metadata.py tests/test_script_interfaces.py
.venv\Scripts\python.exe -m ruff format --check scripts/build_huggingface_space_bundle.py tests/test_huggingface_space_metadata.py tests/test_script_interfaces.py
```

Expected: tests PASS, help returns exit code 0, Ruff/format PASS.

- [ ] **Step 6: Commit template and CLI**

```powershell
git add deploy/huggingface/README.md scripts/build_huggingface_space_bundle.py tests/test_huggingface_space_metadata.py tests/test_script_interfaces.py
git diff --cached --check
git -c user.name=kuotunyu -c user.email=61350295+kuotunyu@users.noreply.github.com commit -m "feat: add code-only Space template"
```

---

### Task 3: Gradio privacy defaults and immutable model revision gate

**Files:**
- Modify: `src/woundscope/gradio_app.py`
- Modify: `tests/test_onnx_inference_app.py`

**Interfaces:**
- Consumes: Gradio 6.20 `Blocks(analytics_enabled=False, delete_cache=(600, 600))`, `Image(sources=["upload"], buttons=["fullscreen"])`, and event `api_visibility="private"`.
- Produces: `build_demo()` with analytics disabled、`delete_cache=(600, 600)`、upload-only image input、fullscreen-only image controls and private prediction dependency.
- Model gate: local `WOUNDSCOPE_MODEL_PATH` remains first priority; remote model download requires `HF_MODEL_ID` plus `HF_MODEL_REVISION` matching `[0-9a-f]{40}`.

- [ ] **Step 1: Write failing Gradio configuration tests**

Replace the existing single smoke assertion with explicit config assertions:

```python
def test_gradio_demo_uses_private_upload_only_defaults() -> None:
    demo = build_demo()
    image_components = [
        component for component in demo.config["components"]
        if component["type"] == "image"
    ]
    markdown = "\n".join(
        component["props"].get("value", "")
        for component in demo.config["components"]
        if component["type"] == "markdown"
    )

    assert demo.analytics_enabled is False
    assert demo.delete_cache == (600, 600)
    assert image_components[0]["props"]["sources"] == ["upload"]
    assert all(component["props"]["buttons"] == ["fullscreen"] for component in image_components)
    assert all(
        dependency["api_visibility"] == "private"
        for dependency in demo.config["dependencies"]
    )
    assert "不得上傳可識別個人資料" in markdown
    assert "Patient Health Information（PHI）" in markdown
    assert "不是疾病診斷" in markdown
```

- [ ] **Step 2: Write failing immutable revision tests**

```python
@pytest.mark.parametrize("revision", ["", "main", "master", "v0.1.0", "ABCDEF"])
def test_remote_model_requires_immutable_commit_revision(
    monkeypatch: pytest.MonkeyPatch, revision: str
) -> None:
    monkeypatch.delenv("WOUNDSCOPE_MODEL_PATH", raising=False)
    monkeypatch.setenv("HF_MODEL_ID", "owner/private-model")
    monkeypatch.setenv("HF_MODEL_REVISION", revision)
    with pytest.raises(RuntimeError, match="40-character"):
        gradio_app._resolve_model_artifacts()
```

另加正例，monkeypatch `huggingface_hub.hf_hub_download`，使用 `"a" * 40`，驗證 model 與 calibration 兩次 download 都收到相同 revision，且 token value 不出現在任何 exception／captured output。

```python
def test_remote_model_uses_one_immutable_revision_without_printing_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[dict[str, object]] = []
    model = tmp_path / "model.onnx"
    calibration = tmp_path / "calibration.json"
    model.write_bytes(b"onnx")
    calibration.write_text("{}", encoding="utf-8")

    def fake_download(model_id: str, *, filename: str, revision: str, token: str | None) -> str:
        calls.append(
            {"model_id": model_id, "filename": filename, "revision": revision, "token": token}
        )
        return str(model if filename == "model.onnx" else calibration)

    monkeypatch.delenv("WOUNDSCOPE_MODEL_PATH", raising=False)
    monkeypatch.setenv("HF_MODEL_ID", "owner/private-model")
    monkeypatch.setenv("HF_MODEL_REVISION", "a" * 40)
    monkeypatch.setenv("HF_TOKEN", "test-private-token")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_download)

    resolved = gradio_app._resolve_model_artifacts()

    assert resolved == (model, calibration)
    assert [call["revision"] for call in calls] == ["a" * 40, "a" * 40]
    assert "test-private-token" not in capsys.readouterr().out
```

- [ ] **Step 3: Run focused tests to verify RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_onnx_inference_app.py -q
```

Expected: current defaults report analytics enabled、all image sources/buttons、public API and `main` revision fallback, so new assertions FAIL.

- [ ] **Step 4: Implement privacy configuration and fail-closed model resolution**

```python
IMMUTABLE_HF_REVISION = re.compile(r"[0-9a-f]{40}")

def _require_immutable_hf_revision() -> str:
    revision = os.environ.get("HF_MODEL_REVISION", "").strip()
    if IMMUTABLE_HF_REVISION.fullmatch(revision) is None:
        raise RuntimeError(
            "HF_MODEL_REVISION 必須是 40-character lowercase Git commit SHA。"
        )
    return revision
```

在 `_resolve_model_artifacts` 的 local-file 與 empty-`HF_MODEL_ID` early returns 後呼叫
`revision = _require_immutable_hf_revision()`，再把同一個 `revision` 傳給 model 與 calibration
兩次 `hf_hub_download`。不得保留 `"main"` fallback。

`build_demo` 使用以下 exact values：

```python
with gr.Blocks(
    title="WoundScope",
    analytics_enabled=False,
    delete_cache=(600, 600),
) as demo:
    input_image = gr.Image(
        type="pil",
        label="上傳影像",
        sources=["upload"],
        buttons=["fullscreen"],
    )
    original = gr.Image(label="原圖", interactive=False, buttons=["fullscreen"])
    overlay = gr.Image(label="Mask overlay", interactive=False, buttons=["fullscreen"])
    run_button.click(
        _predict,
        inputs=[input_image],
        outputs=[original, overlay, ratio, confidence, timing, warning],
        api_visibility="private",
    )
```

Markdown 加入 PHI prohibition，但保留 FUSeg attribution、人工複核與 non-clinical boundary。不要新增 filename/image logging。

- [ ] **Step 5: Run Gradio and inference regressions**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_onnx_inference_app.py -q
.venv\Scripts\python.exe -m ruff check src/woundscope/gradio_app.py tests/test_onnx_inference_app.py
.venv\Scripts\python.exe -m ruff format --check src/woundscope/gradio_app.py tests/test_onnx_inference_app.py
```

Expected: all focused tests PASS; model is not loaded while building demo; no GPU is used.

- [ ] **Step 6: Commit Gradio privacy hardening**

```powershell
git add src/woundscope/gradio_app.py tests/test_onnx_inference_app.py
git diff --cached --check
git -c user.name=kuotunyu -c user.email=61350295+kuotunyu@users.noreply.github.com commit -m "fix: harden Gradio privacy defaults"
```

---

### Task 4: Permission gate, deployment guide, README and governance

**Files:**
- Create: `docs/huggingface-space-deployment.md`
- Create: `docs/permissions/fuseg-model-artifact-permission-request.md`
- Modify: `README.md`
- Modify: `PROJECT_PLAN.md`
- Modify: `tests/test_huggingface_space_metadata.py`
- Modify: `tests/test_release_metadata.py`

**Interfaces:**
- Consumes: Task 1/2 CLI and manifest fields; Task 3 immutable revision/privacy behavior.
- Produces: human deployment contract, unsent permission-request draft, README status/link and Locked Decision Log entry.

- [ ] **Step 1: Write failing documentation contract tests**

```python
def test_deployment_docs_keep_external_actions_permission_gated() -> None:
    guide = Path("docs/huggingface-space-deployment.md").read_text(encoding="utf-8")
    request = Path(
        "docs/permissions/fuseg-model-artifact-permission-request.md"
    ).read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    for required in (
        "PERMISSION_PENDING", "Public Space", "Protected Space", "Private Space",
        "HF_MODEL_REVISION", "40-character", "rollback", "teardown",
    ):
        assert required in guide
    for question in (
        "CC BY-NC", "derived model weights", "public non-commercial inference",
        "ONNX", "attribution",
    ):
        assert question in request
    assert "這是草稿，尚未寄送" in request
    assert "Space%20授權確認中" in readme
    assert "docs/huggingface-space-deployment.md" in readme
```

在 `tests/test_release_metadata.py::test_readme_exposes_public_colab_and_reproducible_commands` 加入同樣的 badge status 與 guide link assertions，避免 deployment test 被單獨跳過時 status 漂移。

- [ ] **Step 2: Run documentation tests to verify RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_huggingface_space_metadata.py tests/test_release_metadata.py -q
```

Expected: FAIL because guide、request draft and README status/link are absent.

- [ ] **Step 3: Write the deployment guide**

Guide 必須依序包含：

1. `PERMISSION_PENDING` 與 code-only scope。
2. `build_huggingface_space_bundle.py` 的 PowerShell command、default output、manifest/ZIP hash 查核。
3. Candidate exact inventory 與 forbidden inventory。
4. Public／Protected／Private Space 差異；目前不選擇任何 live mode。
5. 未來 secrets/variables 最小權限：fine-grained write token 只用於人工 publish session，runtime 只使用 read-only model access，禁止寫入 repository/file/log。
6. Immutable `HF_MODEL_REVISION` 40-character commit SHA 與 fail-closed behavior。
7. 人工 pre-publish checklist：owner=`kuotunyu`、visibility、CPU Basic、port 7860、privacy copy、model hash、rollback commit。
8. Rollback：切回上一個 verified Space commit；teardown：停用 Space、撤銷 token、移除 runtime secret、保留不含 secret 的 audit record。
9. 明確說明 temporary cache 10-minute policy 不是 absolute deletion guarantee。

- [ ] **Step 4: Write the unsent permission-request draft**

草稿使用正體中文主文與必要英文名詞，收件者欄位寫「FUSeg dataset maintainer / rights holder」，不得捏造姓名或 email。五個問題必須逐項詢問 license version/legal code、private storage of derived weights、public non-commercial inference、ONNX/checkpoint redistribution、required attribution/retention restrictions；結尾要求可保存的書面回覆。

- [ ] **Step 5: Update README and Decision Log**

- Badge text 改成 `Hugging Face-Space 授權確認中`，仍連到 `#gradio-demo`，不使用不存在的 live URL。
- Gradio section 加入 deployment guide 與 code-only builder command；重申本階段不含 weights/ONNX。
- `PROJECT_PLAN.md` Decision Log 新增 2026-08-04 Locked row：只建立 deterministic code-only Space candidate；未取得書面授權前，不上傳 derived weights／ONNX、不建立 model-backed live Space。
- 不修改 verified metrics、scientific protocol、`v0.1.0` tag/release text。

- [ ] **Step 6: Run documentation and release tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_huggingface_space_metadata.py tests/test_release_metadata.py -q
.venv\Scripts\python.exe -m ruff check tests/test_huggingface_space_metadata.py tests/test_release_metadata.py
.venv\Scripts\python.exe -m ruff format --check tests/test_huggingface_space_metadata.py tests/test_release_metadata.py
git diff --check
```

Expected: all tests and checks PASS.

- [ ] **Step 7: Commit permission and deployment documentation**

```powershell
git add README.md PROJECT_PLAN.md docs/huggingface-space-deployment.md docs/permissions/fuseg-model-artifact-permission-request.md tests/test_huggingface_space_metadata.py tests/test_release_metadata.py
git diff --cached --check
git -c user.name=kuotunyu -c user.email=61350295+kuotunyu@users.noreply.github.com commit -m "docs: define Space permission gate"
```

---

### Task 5: Build the verified candidate, run milestone gates and record evidence

**Files:**
- Modify: `PROGRESS.md`
- Generated, gitignored: `artifacts/huggingface-space/candidate/`
- Generated, gitignored: `artifacts/huggingface-space/WoundScope_hf_space_code_only.zip`

**Interfaces:**
- Consumes: clean committed HEAD after Tasks 1–4.
- Produces: verified local code-only candidate + exact manifest/ZIP evidence; `M7 — HF Space code-only readiness` marked Completed only if every required gate passes.

- [ ] **Step 1: Confirm clean source identity and ignore policy**

```powershell
git status --short --branch
git log -1 --format="%H%n%an <%ae>%n%cn <%ce>%n%B"
git check-ignore -v artifacts/huggingface-space/candidate artifacts/huggingface-space/WoundScope_hf_space_code_only.zip
```

Expected: working tree clean; author/committer are only `kuotunyu`; both generated paths match `artifacts/` ignore rule; commit message has no author trailer.

- [ ] **Step 2: Build the real code-only candidate from committed HEAD**

```powershell
.venv\Scripts\python.exe scripts/build_huggingface_space_bundle.py
```

Expected JSON: `status="verified"`、40-character source commit、non-zero file count、absolute candidate/ZIP paths and 64-character ZIP SHA-256. Save only these non-secret values for `PROGRESS.md`.

- [ ] **Step 3: Independently audit candidate inventory**

```powershell
.venv\Scripts\python.exe -c "import json,zipfile; from pathlib import Path; p=Path('artifacts/huggingface-space/WoundScope_hf_space_code_only.zip'); z=zipfile.ZipFile(p); m=json.loads(z.read('bundle_manifest.json')); assert m['kind']=='huggingface_space'; assert set(z.namelist())=={'bundle_manifest.json',*[r['path'] for r in m['files']]}; print(json.dumps({'source_commit':m['source_commit'],'file_count':len(m['files'])},indent=2))"
```

Then run a case-insensitive filename audit over staging and ZIP. Expected forbidden matches: 0 for `.env`、`.onnx`、`.safetensors`、`.pt`、`.pth`、raster images、`data_manifest`、`checkpoint`、`gallery`、`sample_prediction` and `tensorboard`.

```powershell
.venv\Scripts\python.exe -c "import re,zipfile; from pathlib import Path; p=Path('artifacts/huggingface-space/WoundScope_hf_space_code_only.zip'); z=zipfile.ZipFile(p); pattern=re.compile(r'(^|/)(\.env($|\.)|.*(data_manifest|checkpoint|gallery|sample_prediction|tensorboard).*)|\.(onnx|safetensors|pt|pth|bmp|gif|jpe?g|png|tiff?|webp)$',re.I); bad=[n for n in z.namelist() if pattern.search(n)]; assert not bad,bad; print('HF_SPACE_FORBIDDEN_ARTIFACT_AUDIT_PASS')"
```

- [ ] **Step 4: Run focused, full and formatting gates**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_huggingface_space_bundle.py tests/test_huggingface_space_metadata.py tests/test_onnx_inference_app.py tests/test_release_metadata.py tests/test_script_interfaces.py -q
.venv\Scripts\python.exe -m ruff check --no-cache .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Expected: every command PASS. Existing legacy ONNX exporter deprecation warnings may remain, but no new warning is accepted without recording it.

- [ ] **Step 5: Run candidate import and CPU Docker smoke**

```powershell
$env:PYTHONPATH = (Resolve-Path 'artifacts/huggingface-space/candidate/src').Path
.venv\Scripts\python.exe -c "from woundscope.gradio_app import build_demo; d=build_demo(); assert d.analytics_enabled is False; assert d.delete_cache==(600,600); print('HF_SPACE_IMPORT_SMOKE_PASS')"
Remove-Item Env:PYTHONPATH
docker build -t woundscope:hf-space-code-only artifacts/huggingface-space/candidate
```

Expected: import smoke PASS and Docker build exit 0; no model load、network model download、GPU or container launch occurs. If Docker daemon is unavailable, mark M7 Blocked rather than claiming Docker PASS.

- [ ] **Step 6: Run clean committed-source reproduction**

Create a new local clone outside the repository so the committed-HEAD builder still has Git metadata, then run:

```powershell
$verificationRoot = Join-Path $env:TEMP ("woundscope-hf-verify-" + [guid]::NewGuid().ToString("N"))
$verificationSource = Join-Path $verificationRoot "source"
New-Item -ItemType Directory -Path $verificationRoot | Out-Null
git clone --no-local --no-hardlinks . $verificationSource
Push-Location $verificationSource
uv sync --all-extras --frozen
uv run ruff check --no-cache .
uv run ruff format --check .
uv run pytest -q
uv run python scripts/build_huggingface_space_bundle.py
Pop-Location
```

Expected: dependency sync, Ruff, format, full tests and candidate build PASS from clean source; generated candidate remains ignored inside the extraction.

- [ ] **Step 7: Update PROGRESS with exact evidence**

Update Current status without erasing `RELEASED_V0.1.0`:

- Project state: `RELEASED_V0.1.0 / M7_HF_SPACE_CODE_ONLY_READY` only after all gates PASS.
- Active blocker: `FUSeg derived-weight permission pending`；這是 live deployment blocker，不是 code-only candidate blocker。
- Next action: user reviews the unsent permission request; no external action until explicit direction。
- Add M7 dashboard row and a dated session entry containing source commit、candidate file count、ZIP bytes/SHA-256、focused/full test counts、Ruff/format、Docker、clean reproduction、privacy audit and `GPU not used`。
- State explicitly: no Space/model repo/token/message/push was created or used。

- [ ] **Step 8: Commit the progress evidence**

```powershell
git add PROGRESS.md
git diff --cached --check
git -c user.name=kuotunyu -c user.email=61350295+kuotunyu@users.noreply.github.com commit -m "docs(progress): record Space readiness gate"
```

- [ ] **Step 9: Verify final HEAD identity and repository cleanliness**

```powershell
.venv\Scripts\python.exe -m ruff check --no-cache .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short --branch
git log --format="%an <%ae>|%cn <%ce>|%B" origin/main..HEAD
```

Expected: gates PASS; only gitignored candidate remains unreported by status; every new commit has sole author/committer `kuotunyu` and no `Co-authored-by`／`Signed-off-by`／`Reviewed-by` trailers. Do not push.

---

## Self-review results

- Spec coverage: deterministic allowlist、manifest/hash、path/secret/artifact refusal、Gradio privacy、immutable model revision、permission draft、deployment guide、failure handling、CPU/Docker/clean-source tests and no external mutation are each assigned to Tasks 1–5.
- Subsystem boundary: bundle engine、Space adapter、UI privacy、permission/docs and integrated release evidence each end in an independently reviewable commit.
- Type consistency: Task 2 and Task 5 consume the exact `build_huggingface_space_bundle(repository, output_directory, output_zip)` and manifest fields produced by Task 1.
- Placeholder scan: the plan contains executable assertions、exact strings、paths、commands and failure expectations; no implementation step depends on unspecified behavior.
- Scope control: no GPU training、metric changes、model upload、Space creation、token operation、email sending、GitHub push or unrelated refactor is included.
