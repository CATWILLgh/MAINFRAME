#!/usr/bin/env python3
"""Bounded, read-only Python package reconnaissance."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 or an intentionally minimal runtime.
    tomllib = None  # type: ignore[assignment]


def fail(message: str) -> int:
    print(f"mainframe-python-backend recon: {message}", file=sys.stderr)
    return 2


def repository_boundary(root: Path) -> Path:
    current = root
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return current
        current = current.parent


def relative(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)) or "."
    except ValueError:
        return str(path)


def parse_toml(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if tomllib is None:
        return None, "tomllib is unavailable; TOML content was not parsed"
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except (OSError, ValueError) as error:
        return None, f"{path.name} could not be parsed: {type(error).__name__}"
    if not isinstance(value, dict):
        return None, f"{path.name} did not parse to a table"
    return value, None


NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def dependency_name(specifier: Any) -> str | None:
    if not isinstance(specifier, str):
        return None
    line = specifier.strip()
    if not line or line.startswith(("#", "-", "git+", "http://", "https://")):
        return None
    match = NAME_RE.match(line)
    return match.group(0).lower().replace("_", "-") if match else None


def add_list(target: set[str], values: Any) -> None:
    if isinstance(values, list):
        for value in values:
            name = dependency_name(value)
            if name:
                target.add(name)


def add_keys(target: set[str], values: Any, *, omit: set[str] | None = None) -> None:
    if not isinstance(values, dict):
        return
    omitted = omit or set()
    for value in values:
        if isinstance(value, str) and value.lower() not in omitted:
            name = dependency_name(value)
            if name:
                target.add(name)


def collect_pyproject(data: dict[str, Any], limitations: list[str]) -> tuple[set[str], dict[str, Any]]:
    dependencies: set[str] = set()
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    tool = data.get("tool") if isinstance(data.get("tool"), dict) else {}

    add_list(dependencies, project.get("dependencies"))
    optional = project.get("optional-dependencies")
    if isinstance(optional, dict):
        for values in optional.values():
            add_list(dependencies, values)

    groups = data.get("dependency-groups")
    if isinstance(groups, dict):
        for values in groups.values():
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str):
                    name = dependency_name(value)
                    if name:
                        dependencies.add(name)
                elif isinstance(value, dict) and "include-group" in value:
                    limitations.append("dependency-group includes were not expanded")
                    continue
                else:
                    limitations.append("an unsupported dependency-group item was omitted")

    poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
    add_keys(dependencies, poetry.get("dependencies"), omit={"python"})
    add_keys(dependencies, poetry.get("dev-dependencies"), omit={"python"})
    poetry_groups = poetry.get("group")
    if isinstance(poetry_groups, dict):
        for group in poetry_groups.values():
            if isinstance(group, dict):
                add_keys(dependencies, group.get("dependencies"), omit={"python"})

    pdm = tool.get("pdm") if isinstance(tool.get("pdm"), dict) else {}
    pdm_dev = pdm.get("dev-dependencies")
    if isinstance(pdm_dev, dict):
        for values in pdm_dev.values():
            add_list(dependencies, values)

    script_names: set[str] = set()
    add_keys(script_names, project.get("scripts"))
    add_keys(script_names, poetry.get("scripts"))

    requires_python = project.get("requires-python")
    if not isinstance(requires_python, str) or not re.fullmatch(r"[A-Za-z0-9*~^<>=!|,. _+()-]+", requires_python):
        requires_python = None

    known_tools = {
        "basedpyright", "black", "coverage", "hatch", "mypy", "pdm",
        "poetry", "pyright", "pytest", "ruff", "setuptools", "tox", "uv",
    }
    tool_names = sorted(name for name in tool if isinstance(name, str) and name in known_tools)
    return dependencies, {
        "requires_python": requires_python,
        "script_names": sorted(script_names),
        "configured_tools": tool_names,
    }


def collect_requirements(root: Path, limitations: list[str]) -> tuple[set[str], list[str]]:
    dependencies: set[str] = set()
    files: list[str] = []
    for path in sorted(root.glob("requirements*.txt")):
        if not path.is_file():
            continue
        files.append(path.name)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            limitations.append(f"{path.name} could not be read")
            continue
        for line in lines:
            name = dependency_name(line)
            if name:
                dependencies.add(name)
    return dependencies, files


SIGNALS: dict[str, dict[str, tuple[str, ...]]] = {
    "frameworks": {
        "fastapi": ("fastapi",), "django": ("django",), "flask": ("flask",),
        "litestar": ("litestar",), "starlette": ("starlette",), "sanic": ("sanic",),
    },
    "data_access": {
        "sqlalchemy": ("sqlalchemy",), "sqlmodel": ("sqlmodel",), "django-orm": ("django",),
        "tortoise-orm": ("tortoise-orm",), "peewee": ("peewee",), "psycopg": ("psycopg", "psycopg2", "psycopg2-binary"),
        "asyncpg": ("asyncpg",), "mysql": ("pymysql", "mysqlclient"), "mongodb": ("pymongo", "motor"),
    },
    "validation_api": {
        "pydantic": ("pydantic",), "marshmallow": ("marshmallow",), "django-rest-framework": ("djangorestframework",),
        "flask-smorest": ("flask-smorest",), "connexion": ("connexion",), "graphql": ("strawberry-graphql", "graphene"),
    },
    "auth": {
        "authlib": ("authlib",), "pyjwt": ("pyjwt",), "python-jose": ("python-jose",),
    },
    "migrations": {
        "alembic": ("alembic",), "django": ("django",), "flask-migrate": ("flask-migrate",),
    },
    "workers": {
        "celery": ("celery",), "arq": ("arq",), "taskiq": ("taskiq",), "dramatiq": ("dramatiq",),
        "rq": ("rq",), "huey": ("huey",),
    },
    "realtime": {
        "django-channels": ("channels",), "socketio": ("python-socketio", "flask-socketio"), "websockets": ("websockets",),
    },
    "storage_cache": {
        "redis": ("redis",), "memcached": ("pymemcache",), "cachetools": ("cachetools",),
        "s3": ("boto3", "aioboto3"), "minio": ("minio",),
    },
    "outbound": {
        "httpx": ("httpx",), "requests": ("requests",), "aiohttp": ("aiohttp",),
    },
    "observability": {
        "opentelemetry": ("opentelemetry-api", "opentelemetry-sdk"), "structlog": ("structlog",),
        "sentry": ("sentry-sdk",), "prometheus": ("prometheus-client",),
    },
    "testing": {
        "pytest": ("pytest",), "pytest-asyncio": ("pytest-asyncio",), "hypothesis": ("hypothesis",),
        "testcontainers": ("testcontainers",), "factory-boy": ("factory-boy",),
    },
    "type_checking": {
        "mypy": ("mypy",), "pyright": ("pyright",), "basedpyright": ("basedpyright",), "ty": ("ty",),
    },
}


def detected_signals(dependencies: set[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for category, candidates in SIGNALS.items():
        result[category] = sorted(
            label for label, names in candidates.items() if any(name in dependencies for name in names)
        )
    return result


def nearest_lockfile(root: Path, boundary: Path) -> dict[str, str] | None:
    candidates = (
        ("uv", "uv.lock"), ("poetry", "poetry.lock"), ("pdm", "pdm.lock"),
        ("pipenv", "Pipfile.lock"), ("pylock", "pylock.toml"),
    )
    current = root
    while True:
        for manager, filename in candidates:
            path = current / filename
            if path.is_file():
                return {"manager": manager, "path_from_package_root": relative(root, path)}
        if current == boundary or current.parent == current:
            return None
        current = current.parent


def main() -> int:
    if len(sys.argv) != 2:
        return fail("usage: python3 recon.py <package-root>")

    root = Path(sys.argv[1]).resolve()
    if not root.exists():
        return fail(f"package root does not exist: {root}")
    if not root.is_dir():
        return fail(f"package root is not a directory: {root}")

    recognized = ["pyproject.toml", "setup.py", "setup.cfg", "Pipfile"]
    requirements = sorted(path.name for path in root.glob("requirements*.txt") if path.is_file())
    manifests = [name for name in recognized if (root / name).is_file()] + requirements
    if not manifests:
        return fail(f"no recognized Python package manifest found in: {root}")

    limitations: list[str] = []
    manifest_errors: list[str] = []
    dependencies: set[str] = set()
    metadata: dict[str, Any] = {"requires_python": None, "script_names": [], "configured_tools": []}
    pyproject_state = "absent"

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data, error = parse_toml(pyproject)
        if error:
            if tomllib is None:
                pyproject_state = "unparsed"
                limitations.append(error)
            else:
                pyproject_state = "invalid"
                manifest_errors.append(error)
        else:
            pyproject_state = "parsed"
            dependencies, metadata = collect_pyproject(data or {}, limitations)

    requirement_dependencies, requirement_files = collect_requirements(root, limitations)
    dependencies.update(requirement_dependencies)

    boundary = repository_boundary(root)
    entrypoints = [
        path for path in ("manage.py", "app.py", "main.py", "wsgi.py", "asgi.py", "src/app.py", "src/main.py")
        if (root / path).is_file()
    ]
    config_files = [
        path for path in ("mypy.ini", "pyrightconfig.json", "ruff.toml", "pytest.ini", "tox.ini")
        if (root / path).is_file()
    ]

    status = "invalid" if manifest_errors else "partial" if limitations else "complete"
    report = {
        "status": status,
        "package_root": str(root),
        "repository_boundary": str(boundary),
        "manifests_present": sorted(manifests),
        "pyproject": {"status": pyproject_state, "parser": "tomllib" if tomllib is not None else None},
        "package_management": {
            "nearest_lockfile": nearest_lockfile(root, boundary),
            "requirements_files": requirement_files,
        },
        "runtime": {
            "requires_python": metadata["requires_python"],
            "entrypoint_files_present": entrypoints,
            "configuration_files_present": config_files,
            "configured_tool_names": metadata["configured_tools"],
            "declared_script_names": metadata["script_names"],
        },
        "signals": detected_signals(dependencies),
        "manifest_errors": manifest_errors,
        "limitations": sorted(set(limitations)),
        "evidence_limits": [
            "declared dependencies are not installed-version or active-use proof",
            "dependency versions, URLs, requirement lines, and script bodies are intentionally omitted",
            "filenames and tool tables do not prove the served entrypoint or effective configuration",
            "application code was not imported or executed",
            "environment variables, secrets, network resources, and runtime services were not inspected",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if manifest_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
