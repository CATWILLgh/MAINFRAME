#!/usr/bin/env python3
"""Inspect a Python package without importing it or contacting the network."""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


SIGNALS: dict[str, dict[str, str]] = {
    "frameworks": {
        "fastapi": "fastapi",
        "django": "django",
        "flask": "flask",
        "litestar": "litestar",
    },
    "data_access": {
        "sqlalchemy": "sqlalchemy",
        "flask-sqlalchemy": "sqlalchemy",
        "django": "django-orm",
        "tortoise-orm": "tortoise",
        "sqlmodel": "sqlmodel",
        "psycopg": "psycopg",
        "psycopg2": "psycopg2",
        "asyncpg": "asyncpg",
    },
    "validation": {
        "pydantic": "pydantic",
        "marshmallow": "marshmallow",
        "djangorestframework": "drf",
    },
    "api_layers": {
        "flask-smorest": "flask-smorest",
        "djangorestframework": "drf",
    },
    "migrations": {
        "alembic": "alembic",
        "flask-migrate": "flask-migrate",
        "django": "django",
    },
    "workers": {
        "celery": "celery",
        "arq": "arq",
        "taskiq": "taskiq",
        "dramatiq": "dramatiq",
        "rq": "rq",
    },
    "caching": {
        "redis": "redis",
        "python-memcached": "memcached",
        "cachetools": "in-process",
    },
    "observability": {
        "opentelemetry-api": "otel",
        "structlog": "structlog",
        "sentry-sdk": "sentry",
        "prometheus-client": "prometheus",
        "prometheus-flask-exporter": "prometheus",
    },
    "auth": {
        "authlib": "oauth-oidc",
        "pyjwt": "jwt",
    },
    "realtime": {
        "flask-socketio": "socketio",
        "gevent": "gevent",
        "gevent-websocket": "gevent-websocket",
    },
    "storage": {
        "minio": "s3-compatible",
        "boto3": "s3-compatible",
        "aioboto3": "async-s3-compatible",
    },
    "outbound": {
        "requests": "requests",
        "httpx": "httpx",
        "aiohttp": "aiohttp",
        "pywebpush": "web-push",
    },
    "documents": {
        "fpdf2": "pdf",
        "openpyxl": "xlsx",
        "qrcode": "qr",
    },
    "rate_limits": {
        "flask-limiter": "flask-limiter",
    },
    "testing": {
        "pytest": "pytest",
        "testcontainers": "testcontainers",
    },
}


def dependency_name(specification: str) -> str | None:
    candidate = specification.split(";", 1)[0].strip()
    match = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)", candidate)
    return match.group(1).lower().replace("_", "-") if match else None


def read_pyproject(root: Path) -> dict:
    path = root / "pyproject.toml"
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def collect(root: Path) -> tuple[set[str], str, str]:
    data = read_pyproject(root)
    project = data.get("project", {})
    raw: list[str] = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        raw.extend(group)
    for group in data.get("dependency-groups", {}).values():
        raw.extend(item for item in group if isinstance(item, str))

    tool = data.get("tool", {})
    poetry = tool.get("poetry", {})
    for name in poetry.get("dependencies", {}):
        if name != "python":
            raw.append(name)
    for group in poetry.get("group", {}).values():
        raw.extend(group.get("dependencies", {}).keys())

    for requirements in sorted(root.glob("requirements*.txt")):
        try:
            raw.extend(requirements.read_text(encoding="utf-8").splitlines())
        except OSError:
            continue

    dependencies = {name for item in raw if (name := dependency_name(str(item)))}
    managers = []
    if (root / "uv.lock").exists() or "uv" in tool:
        managers.append("uv")
    if (root / "poetry.lock").exists() or poetry:
        managers.append("poetry")
    if (root / "Pipfile.lock").exists():
        managers.append("pipenv")
    if not managers and any(root.glob("requirements*.txt")):
        managers.append("pip")
    return dependencies, str(project.get("requires-python", "unknown")), "+".join(managers) or "unknown"


def detect_all(dependencies: set[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for category, candidates in SIGNALS.items():
        values = sorted({value for name, value in candidates.items() if name in dependencies})
        found[category] = "+".join(values) or "none"
    if "django" in dependencies and found["data_access"] == "none":
        found["data_access"] = "django-orm"
    return found


def detect_type_checker(root: Path) -> str:
    found: set[str] = set()
    tool = read_pyproject(root).get("tool", {})
    found.update(name for name in ("pyright", "basedpyright", "mypy", "ty") if name in tool)
    if (root / "pyrightconfig.json").exists():
        found.add("pyright")
    if (root / "mypy.ini").exists():
        found.add("mypy")
    setup_cfg = root / "setup.cfg"
    if setup_cfg.exists():
        try:
            if "[mypy]" in setup_cfg.read_text(encoding="utf-8"):
                found.add("mypy")
        except OSError:
            pass
    return "+".join(sorted(found)) or "none"


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    dependencies, python_requirement, package_manager = collect(root)
    report = detect_all(dependencies)
    report["type_checker"] = detect_type_checker(root)
    print("RECON:")
    print(f"  python_requirement: {python_requirement}")
    print(f"  package_manager: {package_manager}")
    print("  dependency_values: declared manifests; verify resolved lock or environment")
    for key, value in report.items():
        print(f"  {key}: {value}")
    print("  runtime_wiring: inspect entrypoints and imports")
    print("  multitenancy: inspect schemas, policies, and request context")


if __name__ == "__main__":
    main()
