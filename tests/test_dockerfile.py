from pathlib import Path


def test_dockerfile_exists_and_runs_app():
    dockerfile_path = Path(__file__).resolve().parents[1] / "Dockerfile"
    content = dockerfile_path.read_text(encoding="utf-8")

    assert "uvicorn app.main:app" in content
    assert "alembic upgrade head" in content
    assert "requirements.txt" in content
    assert "ARG IPOCKET_VERSION=dev" in content
    assert "ENV IPOCKET_VERSION=${IPOCKET_VERSION}" in content


def test_docker_compose_configures_database_and_admin():
    compose_path = Path(__file__).resolve().parents[1] / "docker-compose.yml"
    content = compose_path.read_text(encoding="utf-8")

    assert "ipocket:" in content
    assert "./data:/data" in content
    assert "8000:8000" in content
    assert "ADMIN_BOOTSTRAP_USERNAME: admin" in content
    assert "ADMIN_BOOTSTRAP_PASSWORD: admin-pass" in content
