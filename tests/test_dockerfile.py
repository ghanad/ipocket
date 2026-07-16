from pathlib import Path


def test_dockerfile_exists_and_runs_app():
    dockerfile_path = Path(__file__).resolve().parents[1] / "Dockerfile"
    content = dockerfile_path.read_text(encoding="utf-8")

    assert "uvicorn app.main:app" in content
    assert "alembic upgrade head" in content
    assert "requirements.txt" in content
    assert "ARG IPOCKET_VERSION=dev" in content
    assert "ENV IPOCKET_VERSION=${IPOCKET_VERSION}" in content
    assert "FROM node:22-slim AS frontend" in content
    assert "RUN npm ci" in content
    assert "RUN npm run build" in content
    assert "COPY --from=frontend /app/static/react ./app/static/react" in content


def test_docker_build_context_excludes_local_frontend_artifacts():
    dockerignore_path = Path(__file__).resolve().parents[1] / ".dockerignore"
    content = dockerignore_path.read_text(encoding="utf-8")

    assert "frontend/node_modules" in content
    assert "app/static/react" in content
    assert ".venv" in content


def test_vite_build_has_a_library_entry():
    vite_config = (
        Path(__file__).resolve().parents[1] / "frontend" / "vite.config.ts"
    ).read_text(encoding="utf-8")

    assert 'library: resolve(__dirname, "src/library/main.tsx")' in vite_config
    assert 'entryFileNames: "[name]/[name].js"' in vite_config


def test_docker_compose_configures_database_and_admin():
    compose_path = Path(__file__).resolve().parents[1] / "docker-compose.yml"
    content = compose_path.read_text(encoding="utf-8")

    assert "ipocket:" in content
    assert "./data:/data" in content
    assert "8000:8000" in content
    assert "ADMIN_BOOTSTRAP_USERNAME: admin" in content
    assert "ADMIN_BOOTSTRAP_PASSWORD: admin-pass" in content
