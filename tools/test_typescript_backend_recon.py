#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECON = (
    ROOT
    / "adapters"
    / "claude-code"
    / "plugin"
    / "skills"
    / "typescript-backend-patterns"
    / "recon.js"
)


def run_recon(package: dict, files: dict[str, str] | None = None) -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "package.json").write_text(json.dumps(package), encoding="utf-8")
        for relative, content in (files or {}).items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        result = subprocess.run(
            ["node", str(RECON), str(root)],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)


class TypeScriptBackendReconTests(unittest.TestCase):
    def test_reports_coexisting_nest_stack_without_forcing_a_choice(self):
        report = run_recon(
            {
                "name": "api",
                "engines": {"node": ">=22"},
                "dependencies": {
                    "@nestjs/core": "^11.0.0",
                    "@nestjs/platform-express": "^11.0.0",
                    "typeorm": "^0.3.0",
                    "zod": "^4.0.0",
                    "class-validator": "^0.14.0",
                    "passport": "^0.7.0",
                    "@nestjs/swagger": "^11.0.0",
                    "@nestjs/axios": "^4.0.0",
                    "bullmq": "^5.0.0",
                    "socket.io": "^4.0.0",
                    "minio": "^8.0.0",
                },
                "devDependencies": {"jest": "^30.0.0", "typescript": "^5.9.0"},
            },
            {"tsconfig.json": '{"compilerOptions":{"strict":false}}'},
        )
        self.assertEqual(report["frameworks"]["@nestjs/core"], "^11.0.0")
        self.assertIn("class-validator", report["validation"])
        self.assertIn("zod", report["validation"])
        self.assertIn("bullmq", report["background"])
        self.assertIn("socket.io", report["realtime"])
        self.assertIn("@nestjs/swagger", report["contracts"])
        self.assertIn("@nestjs/axios", report["http_clients"])
        self.assertFalse(report["runtime"]["strictness"]["strict"])
        self.assertEqual(
            report["dependency_values"],
            "declared package.json specifiers; verify installed resolutions",
        )

    def test_reports_next_server_stack_and_router(self):
        report = run_recon(
            {
                "name": "web",
                "type": "module",
                "dependencies": {
                    "next": "^16.0.0",
                    "drizzle-orm": "^0.45.0",
                    "postgres": "^3.4.0",
                    "next-auth": "5.0.0-beta.30",
                    "pg-boss": "^12.0.0",
                    "pino": "^9.0.0",
                },
                "devDependencies": {"vitest": "^4.0.0", "@playwright/test": "^1.55.0"},
            },
            {
                "src/app/layout.tsx": "export default function Layout() {}",
                "tsconfig.json": '{"compilerOptions":{"strict":true}}',
                "pnpm-lock.yaml": "lockfileVersion: '9.0'",
            },
        )
        self.assertEqual(report["next_router"], "app")
        self.assertEqual(report["package_manager"], "pnpm")
        self.assertIn("drizzle-orm", report["data"])
        self.assertIn("next-auth", report["auth"])
        self.assertIn("pg-boss", report["background"])
        self.assertTrue(report["runtime"]["strictness"]["strict"])

    def test_does_not_infer_next_router_without_next(self):
        report = run_recon(
            {"name": "ordinary-node-service", "devDependencies": {"typescript": "^5"}},
            {"app/index.ts": "export {}"},
        )
        self.assertIsNone(report["next_router"])

    def test_reports_partial_or_inherited_strictness_without_false_precision(self):
        report = run_recon(
            {"name": "api", "devDependencies": {"typescript": "^5"}},
            {
                "tsconfig.json": (
                    '{"extends":"../tsconfig.base.json","compilerOptions":'
                    '{"strictNullChecks":true,"noImplicitAny":true}}'
                )
            },
        )
        self.assertEqual(
            report["runtime"]["tsconfig_extends"], "../tsconfig.base.json"
        )
        self.assertIsNone(report["runtime"]["strictness"]["strict"])
        self.assertTrue(report["runtime"]["strictness"]["strictNullChecks"])
        self.assertTrue(report["runtime"]["strictness"]["noImplicitAny"])

    def test_finds_workspace_lockfile_and_limits_script_noise(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / ".git").mkdir()
            (workspace / "package-lock.json").write_text("{}", encoding="utf-8")
            package_root = workspace / "packages" / "api"
            package_root.mkdir(parents=True)
            (package_root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "test": "vitest run",
                            "contracts:upstream:check": "node check.mjs",
                            "db:seed:all": "node seed.mjs",
                        }
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                ["node", str(RECON), str(package_root)],
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(result.stdout)

        self.assertEqual(report["package_manager"], "npm")
        self.assertEqual(
            report["package_manager_lockfile"], str(workspace / "package-lock.json")
        )
        self.assertIn("test", report["scripts"])
        self.assertIn("contracts:upstream:check", report["scripts"])
        self.assertNotIn("db:seed:all", report["scripts"])


if __name__ == "__main__":
    unittest.main()
