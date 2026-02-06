from pathlib import Path


def test_dockerfile_exists_and_runs_app():
    dockerfile_path = Path(__file__).resolve().parents[1] / "Dockerfile"
    content = dockerfile_path.read_text(encoding="utf-8")

    assert "uvicorn app.main:app" in content
    assert "alembic upgrade head" in content
    assert "requirements.txt" in content
