"""Bounded local evidence for advisory candidates, never task/authority inference.

No traversal, process, network, environment or credential reads. Source and
nearest package metadata are capped; missing/ambiguous evidence stays silent.
"""
import ast
import json
from pathlib import Path
import re
import tomllib

MAX_BYTES = 65536
MAX_PARENTS = 8
EXCLUDED = {'fixtures', 'fixture', 'vendor', 'generated', 'node_modules', 'dist',
            'build', '.git', '.agents', '.codex', '.venv', '__tests__', 'tests',
            'test', 'spec', 'specs', 'docs', 'examples', 'example', 'cli', 'scripts',
            '.ssh', '.aws', '.gnupg', 'secrets', 'credentials'}
SOURCE_SUFFIXES = {'.py', '.go', '.sql', '.ts', '.mts', '.cts', '.tsx', '.jsx',
                   '.js', '.mjs', '.cjs', '.yaml', '.yml', '.tf'}
BACKEND = {'backend', 'backends', 'server', 'servers', 'api'}
GO_SERVICE = {'app', 'service', 'services', 'repository', 'repositories', 'store',
              'stores', 'httpserver', 'handler', 'handlers', 'worker', 'workers'}


def _safe(path: Path, root: Path) -> bool:
    """Reject symlink components before resolving, including the root itself."""
    if not path.is_absolute() or not root.is_absolute():
        return False
    if len(str(path).encode('utf-8')) > 4096 or len(path.parts) > 128:
        return False
    if '..' in path.parts or '..' in root.parts or not path.is_relative_to(root):
        return False
    return not any(p.is_symlink() for p in (path, *path.parents))


def _text(path: Path, root: Path) -> str:
    if not _safe(path, root) or not path.is_file():
        return ''
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    return data.decode('utf-8') if len(data) <= MAX_BYTES else ''


def _nearest(path: Path, root: Path, filename: str) -> tuple[Path, str] | None:
    for parent in (path.parent, *path.parent.parents)[:MAX_PARENTS]:
        if not parent.is_relative_to(root):
            break
        target = parent / filename
        # A present but unusable nearest manifest shadows outer packages.
        if target.exists() or target.is_symlink():
            return parent, _text(target, root)
    return None


def _dependencies(body: str) -> set[str]:
    data = json.loads(body)
    if not isinstance(data, dict):
        return set()
    result = set()
    for group in ('dependencies', 'devDependencies', 'peerDependencies'):
        values = data.get(group, {})
        if not isinstance(values, dict):
            return set()
        result.update(values)
    return result


def _python_web(path: Path, root: Path, source: str) -> bool:
    tree = ast.parse(source)
    imports = {node.module.split('.')[0] for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom) and node.module}
    imports.update(alias.name.split('.')[0] for node in ast.walk(tree)
                   if isinstance(node, ast.Import) for alias in node.names)
    if imports & {'fastapi', 'flask', 'django', 'starlette', 'aiohttp', 'litestar'}:
        return True
    manifest = _nearest(path, root, 'pyproject.toml')
    if not manifest or not manifest[1]:
        return False
    data = tomllib.loads(manifest[1])
    project_data = data.get('project', {})
    if not isinstance(project_data, dict):
        return False
    dependencies = project_data.get('dependencies', [])
    if not isinstance(dependencies, list):
        return False
    names = {re.split(r'[\s<>=!~\[;]', item.lower(), maxsplit=1)[0]
             for item in dependencies if isinstance(item, str)}
    return bool(names & {'fastapi', 'flask', 'django', 'starlette', 'aiohttp', 'litestar'})


def _clickhouse(path: Path, root: Path, source: str) -> bool:
    if path.suffix == '.py':
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(a.name.split('.')[0] in {'clickhouse_connect', 'clickhouse_driver'} for a in node.names):
                    return True
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split('.')[0] in {'clickhouse_connect', 'clickhouse_driver'}:
                    return True
    if path.suffix == '.go':
        return any(re.search(r'"github.com/ClickHouse/clickhouse-go(?:/v2)?"', block)
                   for block in _go_imports(source))
    if path.suffix in {'.ts', '.mts', '.cts', '.tsx', '.jsx', '.js', '.mjs', '.cjs'}:
        manifest = _nearest(path, root, 'package.json')
        if manifest and manifest[1] and '@clickhouse/client' in _dependencies(manifest[1]):
            clean = re.sub(r'`(?:\\.|[^`\\])*`', '', source, flags=re.S)
            clean = re.sub(r'/\*.*?\*/|//[^\n]*', '', clean, flags=re.S)
            return bool(re.search(r'(?m)^\s*import\s+(?:[^;\n]*?\s+from\s+)?[\"\']@clickhouse/client[\"\']', clean))
    if path.suffix == '.sql':
        # Require actual leading DDL and a ClickHouse-specific engine, not a
        # prose mention or a generic SQL statement containing a quoted example.
        clean = re.sub(r'/\*.*?\*/|--[^\n]*', '', source, flags=re.S).strip()
        clean = re.sub(r"'(?:''|[^'])*'", "''", clean)
        return bool(re.match(r'CREATE\s+TABLE\b', clean, re.I)
                    and re.search(r'\bENGINE\s*=\s*(?:\w*MergeTree|Distributed|ReplacingMergeTree)\b', clean, re.I))
    return False


def _go_imports(source: str) -> list[str]:
    clean = re.sub(r'`[^`]*`', '', source, flags=re.S)
    clean = re.sub(r'/\*.*?\*/|//[^\n]*', '', clean, flags=re.S)
    return re.findall(r'(?m)^\s*import\s+(?:\([^)]*\)|[^\n]+)', clean)


def _go_service_import(source: str) -> bool:
    return any(re.search(r'"(?:net/http|database/sql|github.com/(?:gin-gonic/gin|labstack/echo[^"\n]*|jackc/pgx[^"\n]*))"', block)
               for block in _go_imports(source))


def _web_app(owner: Path, root: Path, deps: set[str]) -> bool:
    """Distinguish an application owner from a React component library."""
    if 'next' in deps:
        for rel in ('app/page.tsx', 'src/app/page.tsx', 'pages/_app.tsx',
                    'src/pages/_app.tsx', 'pages/index.tsx', 'src/pages/index.tsx'):
            entry = _text(owner / rel, root)
            if re.search(r'(?m)^\s*export\s+default\b', entry):
                return True
    for rel in ('src/main.tsx', 'src/main.jsx', 'src/index.tsx', 'src/index.jsx'):
        entry = _text(owner / rel, root)
        entry = re.sub(r'`(?:\\.|[^`\\])*`|/\*.*?\*/|//[^\n]*', '', entry, flags=re.S)
        mount = re.search(r'\b(?:createRoot\s*\(|ReactDOM\.render\s*\()', entry)
        imported = re.search(r'(?m)^\s*import\s+[^;\n]*?\s+from\s+[\"\']react-dom(?:/client)?[\"\']', entry)
        if mount and imported:
            return True
    return False


def candidates(path: Path, project: Path) -> set[str]:
    try:
        path, project = Path(path), Path(project)
        filename = path.name.lower()
        if (filename.startswith('.env') or re.search(
                r'(^|[._-])(?:secret|secrets|credential|credentials|password|private|key)(?:[._-]|$)', filename)
                or filename in {'id_rsa', 'id_ed25519', 'id_ecdsa'}):
            return set()
        if path.suffix.lower() not in SOURCE_SUFFIXES and not (path.name == 'Dockerfile' or path.name.startswith('Dockerfile.')):
            return set()
        if not _safe(path, project):
            return set()
        rel = path.relative_to(project)
        if any(p.lower() in EXCLUDED for p in rel.parts[:-1]):
            return set()
        if re.search(r'(?:\.test\.|\.spec\.|_test\.|^test_)', path.name):
            return set()
        source = _text(path, project)
        if not source or re.search(r'(?im)^\s*(?://|#|/\*)\s*(?:code )?generated\b', source):
            return set()
        result = set()
        parts = {p.lower() for p in rel.parts[:-1]}
        backend_path = bool(parts & BACKEND or any(p.endswith('-backend') for p in parts))
        if _clickhouse(path, project, source):
            result.add('mainframe-clickhouse')
        if path.suffix == '.go' and 'internal' in parts and parts & GO_SERVICE:
            manifest = _nearest(path, project, 'go.mod')
            if manifest and re.search(r'(?m)^module\s+\S+', manifest[1]):
                if _go_service_import(source):
                    result.add('mainframe-go-backend')
        if path.suffix == '.py' and backend_path and _python_web(path, project, source):
            result.add('mainframe-python-backend')
        if path.suffix in {'.ts', '.mts', '.cts', '.tsx', '.jsx', '.js', '.mjs', '.cjs'}:
            manifest = _nearest(path, project, 'package.json')
            if manifest and manifest[1]:
                deps = _dependencies(manifest[1])
                local = path.relative_to(manifest[0])
                local_parts = {p.lower() for p in local.parts[:-1]}
                next_server = 'next' in deps and (
                    ('app' in local_parts and 'api' in local_parts and path.stem == 'route')
                    or ('pages' in local_parts and 'api' in local_parts)
                    or bool(re.match(r'\s*[\"\']use server[\"\'][ \t]*(?:;|\r?\n|$)', source)))
                server_package = bool(deps & {'@nestjs/core', 'express', 'fastify', 'hono', 'koa'})
                nest_source = '@nestjs/core' in deps and 'src' in local_parts and bool(local_parts & {'modules', 'services', 'controllers', 'workers'})
                if next_server or (server_package and (backend_path or nest_source) and path.suffix not in {'.tsx', '.jsx'}):
                    result.add('mainframe-typescript-backend')
                elif path.suffix in {'.tsx', '.jsx'} and 'react' in deps and deps & {'react-dom', 'next'} and 'react-native' not in deps and _web_app(manifest[0], project, deps):
                    result.add('mainframe-frontend')
        yaml = path.suffix.lower() in {'.yaml', '.yml'}
        kube = yaml and re.search(r'(?m)^apiVersion:\s*\S+', source) and re.search(
            r'(?m)^kind:\s*(?:Deployment|StatefulSet|DaemonSet|Service|Ingress|Job|CronJob|ConfigMap|Secret|Namespace|PersistentVolumeClaim)\s*$', source)
        compose = yaml and path.name.lower() in {'compose.yml', 'compose.yaml', 'docker-compose.yml', 'docker-compose.yaml'} and re.search(r'(?m)^services:\s*$', source)
        docker = (path.name == 'Dockerfile' or path.name.startswith('Dockerfile.')) and re.search(r'(?im)^FROM\s+\S+', source)
        terraform = path.suffix == '.tf' and re.search(r'(?m)^\s*(?:resource|provider|module)\s+"[^"\n]+"', source)
        if kube or compose or docker or terraform:
            result.add('mainframe-infrastructure')
        return result
    except (OSError, ValueError, TypeError, SyntaxError, RecursionError):
        return set()
