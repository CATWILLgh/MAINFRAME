from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from installer.skill_profiles import candidates


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'project'
        self.root.mkdir()

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_go_internal_service_and_library_rejection(self):
        self.put('go.mod', 'module example.test/service\ngo 1.23\n')
        service = self.put('internal/app/store.go', 'package app\nimport "database/sql"\n')
        self.assertEqual(candidates(service, self.root), {'mainframe-go-backend'})
        library = self.put('internal/codec/json.go', 'package codec\nimport "encoding/json"\n')
        self.assertEqual(candidates(library, self.root), set())
        comment = self.put('internal/app/example.go', 'package app\n// import "database/sql"\n')
        self.assertEqual(candidates(comment, self.root), set())

    def test_python_service_and_cli_rejection(self):
        self.put('pyproject.toml', '[project]\ndependencies = ["fastapi>=0.1"]\n')
        path = self.put('backend/services/orders.py', 'def get_order(): pass\n')
        self.assertEqual(candidates(path, self.root), {'mainframe-python-backend'})
        cli = self.put('cli/format.py', 'import fastapi\n')
        self.assertEqual(candidates(cli, self.root), set())
        named = self.put('prodtrack-backend/services/orders.py', 'def get_order(): pass\n')
        self.assertEqual(candidates(named, self.root), {'mainframe-python-backend'})

    def test_ts_service_react_web_and_native(self):
        self.put('server/package.json', '{"dependencies":{"@nestjs/core":"1"}}')
        path = self.put('server/src/orders/service.ts', 'export class Orders {}')
        self.assertEqual(candidates(path, self.root), {'mainframe-typescript-backend'})
        self.put('proxy-wb/package.json', '{"dependencies":{"@nestjs/core":"1"}}')
        nested = self.put('proxy-wb/src/modules/orders/service.ts', 'export class Orders {}')
        self.assertEqual(candidates(nested, self.root), {'mainframe-typescript-backend'})
        self.put('web/package.json', '{"dependencies":{"react":"1","react-dom":"1"}}')
        self.put('web/src/main.tsx', "import {createRoot} from 'react-dom/client';\ncreateRoot(document.getElementById('root')).render(<App />);\n")
        page = self.put('web/src/Page.tsx', 'export const Page = () => <main />;')
        self.assertEqual(candidates(page, self.root), {'mainframe-frontend'})
        self.put('web/package.json', '{"dependencies":{"react":"1","react-native":"1"}}')
        self.assertEqual(candidates(page, self.root), set())

    def test_next_server_and_generic_typescript(self):
        self.put('package.json', '{"dependencies":{"next":"1","react":"1","react-dom":"1"}}')
        route = self.put('app/api/orders/route.ts', 'export async function GET() {}')
        self.assertEqual(candidates(route, self.root), {'mainframe-typescript-backend'})
        server = self.put('app/actions.tsx', '"use server";\nexport async function save() {}')
        self.assertEqual(candidates(server, self.root), {'mainframe-typescript-backend'})
        server.write_text('"use server"\nexport async function save() {}')
        self.assertEqual(candidates(server, self.root), {'mainframe-typescript-backend'})
        ordinary = self.put('src/utils.ts', 'export const one = 1;')
        self.assertEqual(candidates(ordinary, self.root), set())

    def test_infrastructure_requires_config_syntax(self):
        manifest = self.put('deploy/app.yaml', 'apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: demo\n')
        self.assertEqual(candidates(manifest, self.root), {'mainframe-infrastructure'})
        other = self.put('config/settings.yaml', 'kind: greeting\nmessage: hi\n')
        self.assertEqual(candidates(other, self.root), set())
        docker = self.put('Dockerfile', 'FROM python:3\nCOPY . /app\n')
        self.assertEqual(candidates(docker, self.root), {'mainframe-infrastructure'})

    def test_clickhouse_actual_import_and_sql(self):
        path = self.put('backend/analytics.py', 'import clickhouse_connect\nclient = clickhouse_connect.get_client()\n')
        self.assertIn('mainframe-clickhouse', candidates(path, self.root))
        prose = self.put('docs/example.py', '# import clickhouse_connect\n')
        self.assertEqual(candidates(prose, self.root), set())
        sql = self.put('migrations/001.sql', 'CREATE TABLE events (id UInt64) ENGINE = MergeTree ORDER BY id;')
        self.assertEqual(candidates(sql, self.root), {'mainframe-clickhouse'})
        self.put('package.json', '{"dependencies":{"@clickhouse/client":"1"}}')
        ts = self.put('backend/analytics.ts', "import {createClient} from '@clickhouse/client';\nconst c = createClient();")
        self.assertEqual(candidates(ts, self.root), {'mainframe-clickhouse'})
        ts.write_text("const docs = `\nimport {createClient} from '@clickhouse/client';\n`;\n")
        self.assertEqual(candidates(ts, self.root), set())
        go = self.put('internal/analytics/client.go', 'package analytics\nimport "github.com/ClickHouse/clickhouse-go/v2"\n')
        self.assertEqual(candidates(go, self.root), {'mainframe-clickhouse'})

    def test_excluded_unsafe_and_oversized(self):
        self.put('package.json', '{"dependencies":{"react":"1","react-dom":"1"}}')
        for folder in ('fixtures', 'vendor', 'generated', 'node_modules', 'dist', '__tests__'):
            path = self.put(folder + '/Page.tsx', 'export const Page = () => <main />;')
            self.assertEqual(candidates(path, self.root), set(), folder)
        outside = self.root.parent / 'Outside.tsx'
        outside.write_text('export const Page = () => <main />;')
        link = self.root / 'Link.tsx'
        link.symlink_to(outside)
        self.assertEqual(candidates(link, self.root), set())
        self.assertEqual(candidates(outside, self.root), set())
        huge = self.put('Page.tsx', 'x' * 65537)
        self.assertEqual(candidates(huge, self.root), set())
        self.put('package.json', '{' + ' ' * 65537)
        small = self.put('Small.tsx', 'export const Page = () => <main />;')
        self.assertEqual(candidates(small, self.root), set())

    def test_unusable_nearest_metadata_and_generated_source(self):
        self.put('package.json', '{"dependencies":{"react":"1","react-dom":"1"}}')
        page = self.put('web/Page.tsx', 'export const Page = () => <main />;')
        manifest = self.put('web/package.json', '{malformed')
        self.assertEqual(candidates(page, self.root), set())
        manifest.unlink()
        manifest.symlink_to(self.root / 'package.json')
        self.assertEqual(candidates(page, self.root), set())
        generated = self.put('Page.tsx', '// Code generated by tool. DO NOT EDIT.\nexport const Page = () => <main />;')
        self.assertEqual(candidates(generated, self.root), set())
        self.put('pyproject.toml', 'project = "invalid"\n')
        python = self.put('backend/orders.py', 'def order(): pass\n')
        self.assertEqual(candidates(python, self.root), set())
        example = self.put('migrations/string.sql', "CREATE TABLE example (note String DEFAULT 'ENGINE = MergeTree');")
        self.assertEqual(candidates(example, self.root), set())

    def test_opaque_and_secret_paths_do_not_read_content(self):
        for name in ('.env', '.env.local', 'server/private.pem', 'server/key.py',
                     'server/credentials.json', 'server/id_rsa', 'server/secret.yaml',
                     'server/archive.bin', 'server/.env.py'):
            target = self.put(name, 'opaque sensitive content')
            with patch('installer.skill_profiles._text') as read:
                self.assertEqual(candidates(target, self.root), set(), name)
                read.assert_not_called()

    def test_standalone_react_package_requires_app_entry(self):
        self.put('package.json', '{"dependencies":{"react":"1","react-dom":"1"}}')
        component = self.put('src/Button.tsx', 'export const Button = () => <button />;')
        self.assertEqual(candidates(component, self.root), set())
        self.put('src/main.tsx', "// createRoot(document.getElementById('root')).render(<App />);\n")
        self.assertEqual(candidates(component, self.root), set())
        self.put('src/main.tsx', "import {createRoot} from 'react-dom/client';\ncreateRoot(document.getElementById('root')).render(<App />);\n")
        self.assertEqual(candidates(component, self.root), {'mainframe-frontend'})


if __name__ == '__main__':
    unittest.main()
