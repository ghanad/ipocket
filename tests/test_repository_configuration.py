from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _workflow_job(workflow: str, name: str) -> str:
    lines = workflow.splitlines()
    start = lines.index(f"  {name}:")
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("  ")
            and not lines[index].startswith("    ")
            and lines[index].endswith(":")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_generated_react_bundles_are_ignored_and_untracked() -> None:
    gitignore_lines = {
        line.strip()
        for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "app/static/react/" in gitignore_lines
    assert not any(line.startswith("!app/static/react/") for line in gitignore_lines)

    for path in (
        "app/static/react/about/about.js",
        "app/static/react/shared/vendor-example.js",
    ):
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", path],
            cwd=REPO_ROOT,
            check=False,
        )
        assert ignored.returncode == 0, f"expected {path} to be ignored"

    tracked = subprocess.run(
        ["git", "ls-files", "app/static/react"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert tracked.stdout == ""


def test_frontend_ci_has_all_verification_gates() -> None:
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    frontend = _workflow_job(workflow, "frontend")

    assert "github.event_name == 'pull_request'" in frontend
    assert "github.ref == 'refs/heads/main'" in frontend
    assert "node-version: \"22\"" in frontend
    assert "cache: npm" in frontend
    assert "cache-dependency-path: frontend/package-lock.json" in frontend
    assert "working-directory: frontend" in frontend
    for command in ("npm ci", "npm test", "npm run typecheck", "npm run build"):
        assert f"run: {command}" in frontend


def test_docker_smoke_build_is_separate_from_tag_release() -> None:
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    smoke = _workflow_job(workflow, "docker-smoke")
    release = _workflow_job(workflow, "docker-release")

    assert "github.event_name == 'pull_request'" in smoke
    assert "github.ref == 'refs/heads/main'" in smoke
    assert "docker build" in smoke
    assert "docker/login-action" not in smoke
    assert "DOCKERHUB_" not in smoke
    assert "push: true" not in smoke

    assert "startsWith(github.ref, 'refs/tags/')" in release
    assert "docker/login-action@v3" in release
    assert "push: true" in release
    assert "${{ github.ref_name }}" in release
    assert "/ipocket:latest" in release
