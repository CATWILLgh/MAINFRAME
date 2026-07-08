#!/usr/bin/env python3
"""Stack recon for python-backend-engineer. Emits RECON block to stdout.

Usage: python3 recon.py [project_root]   (defaults to cwd)
Parses pyproject.toml (PEP 621 + Poetry) and requirements.txt. Pipfile / setup.py — manual fallback (see recon.md)."""
from __future__ import annotations
import sys
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib

DETECT: dict[str, list[tuple[str, str]]] = {
    "framework":          [("fastapi","fastapi"), ("django","django"), ("flask","flask"), ("litestar","litestar")],
    "orm":                [("sqlalchemy","sqlalchemy-2"), ("tortoise-orm","tortoise"), ("sqlmodel","sqlmodel")],
    "validation":         [("pydantic-settings","pydantic-2"), ("pydantic","pydantic-2"), ("marshmallow","marshmallow"), ("djangorestframework","drf")],
    "async_driver":       [("asyncpg","async"), ("aiomysql","async"), ("aiosqlite","async"), ("psycopg2","sync")],
    "background_workers": [("celery","celery"), ("arq","arq"), ("taskiq","taskiq"), ("dramatiq","dramatiq"), ("rq ","rq"), ("\nrq\n","rq")],
    "caching":            [("redis","redis"), ("python-memcached","memcached"), ("cachetools","in-process")],
    "error_reporting":    [("sentry-sdk","sentry")],
    "observability":      [("opentelemetry-api","otel"), ("structlog","structlog")],
    "openapi_gen":        [("flask-smorest","flask-smorest"), ("drf-spectacular","drf-spectacular"), ("apispec","apispec")],
    "config":             [("pydantic-settings","pydantic-settings"), ("dynaconf","dynaconf")],
    "testing":            [("testcontainers","pytest+testcontainers"), ("pytest","pytest")],
}


def collect(root: Path) -> tuple[list[str], str, str]:
    deps: list[str] = []
    py = "unknown"
    pm = "unknown"
    pp = root / "pyproject.toml"
    if pp.exists():
        data = tomllib.loads(pp.read_text())
        proj = data.get("project", {})
        deps.extend(proj.get("dependencies", []))
        py = proj.get("requires-python", py)
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        if isinstance(poetry_deps, dict):
            deps.extend(poetry_deps.keys())
            pm = "poetry"
        if "uv" in data.get("tool", {}):
            pm = "uv"
    if (root / "uv.lock").exists(): pm = "uv"
    elif (root / "poetry.lock").exists() and pm == "unknown": pm = "poetry"
    elif (root / "Pipfile.lock").exists(): pm = "pipenv"
    rt = root / "requirements.txt"
    if rt.exists():
        for ln in rt.read_text().splitlines():
            ln = ln.split("#", 1)[0].strip()
            if ln: deps.append(ln)
    return deps, py, pm


def detect_all(deps: list[str]) -> dict[str, str]:
    blob = "\n" + "\n".join(d.lower() for d in deps) + "\n"
    return {cat: next((v for k, v in cands if k in blob), "none") for cat, cands in DETECT.items()}


def detect_type_checker(root: Path) -> str:
    """Detect configured type-checker(s) by config presence, not dep strings.

    A configured checker (`[tool.pyright]`/`[tool.mypy]` or a config file) is a
    stronger signal than a dep guess, and reading it here leaves the deps blob —
    and every other detector that scans it — untouched. '+'-joined sorted, or 'none'."""
    found: set[str] = set()
    pp = root / "pyproject.toml"
    if pp.exists():
        try:
            tool = tomllib.loads(pp.read_text()).get("tool", {})
        except (tomllib.TOMLDecodeError, OSError):
            tool = {}
        found.update(t for t in ("pyright", "basedpyright", "mypy", "ty") if t in tool)
    if (root / "pyrightconfig.json").exists(): found.add("pyright")
    if (root / "mypy.ini").exists(): found.add("mypy")
    cfg = root / "setup.cfg"
    if cfg.exists():
        try:
            if "[mypy]" in cfg.read_text(): found.add("mypy")
        except OSError:
            pass
    return "+".join(sorted(found)) if found else "none"


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    deps, py, pm = collect(root)
    found = detect_all(deps)
    found["type_checker"] = detect_type_checker(root)
    print("RECON:")
    print(f"  python_version: {py}")
    print(f"  package_manager: {pm}")
    for k, v in found.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
