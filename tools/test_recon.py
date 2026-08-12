#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True


RECON_PATH = (
    Path(__file__).resolve().parents[1]
    / "adapters"
    / "claude-code"
    / "plugin"
    / "skills"
    / "python-backend-patterns"
    / "recon.py"
)
SPEC = importlib.util.spec_from_file_location("python_backend_recon", RECON_PATH)
recon = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recon)


def project(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def output(root: Path) -> str:
    buffer, previous = io.StringIO(), sys.argv
    sys.argv = ["recon.py", str(root)]
    try:
        with contextlib.redirect_stdout(buffer):
            recon.main()
    finally:
        sys.argv = previous
    return buffer.getvalue()


def test_dependency_name_handles_pep_508_shapes():
    assert recon.dependency_name("FastAPI[standard]>=0.115; python_version>'3.10'") == "fastapi"
    assert recon.dependency_name("my_package @ https://example.invalid/pkg.whl") == "my-package"


def test_collects_main_optional_poetry_group_and_requirement_dependencies():
    root = project(
        {
            "pyproject.toml": """
[project]
name = "service"
requires-python = ">=3.12"
dependencies = ["fastapi>=0.115"]
[project.optional-dependencies]
test = ["pytest>=8"]
[tool.poetry.group.worker.dependencies]
celery = "^5"
""",
            "requirements-local.txt": "redis[hiredis]>=5\n",
            "uv.lock": "",
        }
    )
    dependencies, python_version, manager = recon.collect(root)
    assert {"fastapi", "pytest", "celery", "redis"} <= dependencies
    assert python_version == ">=3.12"
    assert manager == "uv+poetry"


def test_collects_pep_735_dependency_groups():
    root = project(
        {
            "pyproject.toml": """
[project]
name = "service"
dependencies = ["Flask==3.1.3"]
[dependency-groups]
dev = ["ruff>=0.11"]
test = ["pytest>=9", "pytest-cov>=4"]
"""
        }
    )
    dependencies, _, _ = recon.collect(root)
    assert {"flask", "ruff", "pytest", "pytest-cov"} <= dependencies


def test_reports_multiple_frameworks_without_selecting_one():
    report = recon.detect_all({"django", "fastapi", "pydantic", "sqlalchemy"})
    assert report["frameworks"] == "django+fastapi"
    assert report["data_access"] == "django-orm+sqlalchemy"
    assert report["validation"] == "pydantic"


def test_django_implies_its_orm_when_no_other_data_library_is_declared():
    assert recon.detect_all({"django"})["data_access"] == "django-orm"


def test_detects_type_checkers_from_supported_config_locations():
    root = project(
        {
            "pyproject.toml": "[tool.pyright]\ntypeCheckingMode = \"standard\"\n",
            "mypy.ini": "[mypy]\n",
        }
    )
    assert recon.detect_type_checker(root) == "mypy+pyright"


def test_malformed_pyproject_fails_open_for_local_inspection():
    root = project({"pyproject.toml": "not valid toml ::: ["})
    assert recon.read_pyproject(root) == {}
    assert recon.detect_type_checker(root) == "none"


def test_main_output_separates_manifest_signals_from_runtime_inspection():
    root = project(
        {
            "pyproject.toml": """
[project]
name = "service"
dependencies = ["fastapi", "sqlalchemy", "asyncpg"]
[tool.pyright]
typeCheckingMode = "standard"
"""
        }
    )
    report = output(root)
    assert "frameworks: fastapi" in report
    assert "data_access: asyncpg+sqlalchemy" in report
    assert "type_checker: pyright" in report
    assert "runtime_wiring: inspect entrypoints and imports" in report
    assert "multitenancy: inspect schemas, policies, and request context" in report


def test_reports_established_flask_service_boundaries_without_project_names():
    root = project(
        {
            "pyproject.toml": """
[project]
name = "manufacturing-service"
dependencies = [
  "Flask==3.1.3",
  "Flask-SQLAlchemy==3.1.1",
  "Flask-SocketIO==5.6.1",
  "gevent>=24",
  "gevent-websocket>=0.10",
  "marshmallow==3.26.2",
  "authlib>=1.7",
  "pyjwt>=2.13",
  "redis>=5",
  "rq>=1.15",
  "minio>=7",
  "requests>=2.31",
  "pywebpush>=2",
  "openpyxl==3.1.5",
  "fpdf2==2.8.6",
  "qrcode[pil]==8.2",
  "Flask-Limiter>=3",
  "structlog>=25",
  "prometheus-flask-exporter>=0.23",
]
[dependency-groups]
test = ["pytest>=9"]
""",
            "uv.lock": "",
        }
    )
    report = output(root)
    for expected in (
        "package_manager: uv",
        "frameworks: flask",
        "data_access: sqlalchemy",
        "validation: marshmallow",
        "workers: rq",
        "auth: jwt+oauth-oidc",
        "realtime: gevent+gevent-websocket+socketio",
        "storage: s3-compatible",
        "outbound: requests+web-push",
        "documents: pdf+qr+xlsx",
        "rate_limits: flask-limiter",
        "observability: prometheus+structlog",
        "testing: pytest",
    ):
        assert expected in report
