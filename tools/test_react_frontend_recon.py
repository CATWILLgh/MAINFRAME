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
    / "react-frontend-patterns"
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


class ReactFrontendReconTests(unittest.TestCase):
    def test_reports_vite_pwa_and_realtime_without_network_discovery(self):
        report = run_recon(
            {
                "name": "operator",
                "dependencies": {
                    "react": "^19.2.0",
                    "react-router-dom": "^7.0.0",
                    "dexie": "^4.0.0",
                    "socket.io-client": "^4.0.0",
                },
                "devDependencies": {
                    "vite": "^7.0.0",
                    "vite-plugin-pwa": "^1.0.0",
                    "vitest": "^4.0.0",
                    "typescript": "^5.9.0",
                },
            },
            {
                "components.json": "{}",
                "tsconfig.json": '{"compilerOptions":{"strict":false}}',
            },
        )
        self.assertIn("vite", report["frameworks"])
        self.assertIsNone(report["next_router"])
        self.assertIn("dexie", report["offline"])
        self.assertIn("vite-plugin-pwa", report["offline"])
        self.assertIn("socket.io-client", report["realtime"])
        self.assertTrue(report["ui"]["components_json"])
        self.assertFalse(
            report["runtime"]["typescript_configs"][0]["strictness"]["strict"]
        )
        self.assertEqual(
            report["dependency_values"],
            "declared package.json specifiers; verify installed resolutions",
        )

    def test_reports_next_client_content_and_visualization_stack(self):
        report = run_recon(
            {
                "name": "web",
                "dependencies": {
                    "next": "16.3.0",
                    "react": "^19.2.0",
                    "@base-ui/react": "^1.5.0",
                    "@tiptap/react": "^3.0.0",
                    "react-markdown": "^9.0.0",
                    "recharts": "^3.0.0",
                    "@dnd-kit/core": "^6.0.0",
                    "@xyflow/react": "^12.0.0",
                    "@tanstack/react-virtual": "^3.0.0",
                    "@tanstack/react-query-persist-client": "^5.0.0",
                    "zod": "^4.0.0",
                },
                "devDependencies": {
                    "@playwright/test": "^1.60.0",
                    "@testing-library/react": "^16.0.0",
                    "vitest": "^4.0.0",
                    "typescript": "^6.0.0",
                },
            },
            {
                "src/app/layout.tsx": "export default function Layout() {}",
                "tsconfig.json": '{"compilerOptions":{"strict":true,"noUncheckedIndexedAccess":true}}',
            },
        )
        self.assertEqual(report["next_router"], "app")
        self.assertIn("next", report["frameworks"])
        self.assertIn("@base-ui/react", report["ui"])
        self.assertIn("@tiptap/react", report["content"])
        self.assertIn("react-markdown", report["content"])
        self.assertIn("recharts", report["data_ui"])
        self.assertIn("@dnd-kit/core", report["interaction_ui"])
        self.assertIn("@xyflow/react", report["interaction_ui"])
        self.assertIn("@tanstack/react-virtual", report["interaction_ui"])
        self.assertIn("@tanstack/react-query-persist-client", report["offline"])
        strictness = report["runtime"]["typescript_configs"][0]["strictness"]
        self.assertTrue(strictness["strict"])
        self.assertTrue(strictness["noUncheckedIndexedAccess"])

    def test_reports_referenced_configs_without_false_strictness(self):
        report = run_recon(
            {
                "name": "client",
                "scripts": {
                    "pretest": "node prepare-test-db.mjs",
                    "test": "vitest run",
                    "db:generate": "drizzle-kit generate",
                    "db:test:setup": "node setup-test-db.mjs",
                    "db:seed:all": "node seed.mjs",
                },
                "devDependencies": {"typescript": "~5.9.3"},
            },
            {
                "tsconfig.json": '{"references":[{"path":"./tsconfig.app.json"}]}',
                "tsconfig.app.json": '{"compilerOptions":{"strict":true}}',
            },
        )

        configs = {
            config["file"]: config for config in report["runtime"]["typescript_configs"]
        }
        self.assertIsNone(configs["tsconfig.json"]["strictness"]["strict"])
        self.assertEqual(
            configs["tsconfig.json"]["references"], ["./tsconfig.app.json"]
        )
        self.assertTrue(configs["tsconfig.app.json"]["strictness"]["strict"])
        self.assertIn("pretest", report["scripts"])
        self.assertIn("test", report["scripts"])
        self.assertIn("db:test:setup", report["scripts"])
        self.assertNotIn("db:generate", report["scripts"])
        self.assertNotIn("db:seed:all", report["scripts"])

    def test_finds_workspace_lockfile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / ".git").mkdir()
            (workspace / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'")
            package_root = workspace / "apps" / "web"
            package_root.mkdir(parents=True)
            (package_root / "package.json").write_text(
                json.dumps({"dependencies": {"react": "^19"}}), encoding="utf-8"
            )
            result = subprocess.run(
                ["node", str(RECON), str(package_root)],
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(result.stdout)

        self.assertEqual(report["package_manager"], "pnpm")
        self.assertEqual(
            report["package_manager_lockfile"], str(workspace / "pnpm-lock.yaml")
        )


if __name__ == "__main__":
    unittest.main()
