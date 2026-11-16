from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/mainframe-typescript-backend/scripts/recon.mjs"
MARKER = "SYNTHETIC_PRIVATE_MARKER"


class TypeScriptReconTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="typescript-recon-")
        self.root = Path(self.temporary.name)
        self.write_package({"name": "@example/service"})

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_package(self, value: object) -> None:
        (self.root / "package.json").write_text(json.dumps(value), encoding="utf-8")

    def run_recon(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["node", str(SCRIPT), str(self.root)], capture_output=True, text=True,
            timeout=5, check=False, cwd=self.root,
        )

    def successful_result(self) -> dict[str, object]:
        process = self.run_recon()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        return json.loads(process.stdout)

    def test_preserves_declarations_and_jsonc_without_running_project_code(self) -> None:
        self.write_package({
            "name": "@example/service", "type": "module", "packageManager": "pnpm@10.2.1",
            "engines": {"node": ">=22 <25"},
            "dependencies": {"next": "^15.0.0", "zod": "workspace:^"},
            "devDependencies": {"typescript": "~5.8.0"},
            "scripts": {"test:unit": f"touch {MARKER}", "lint": MARKER, "unrelated": MARKER},
            "main": "source-must-not-load.cjs",
        })
        (self.root / "source-must-not-load.cjs").write_text(f'throw Error("{MARKER}");', encoding="utf-8")
        (self.root / "pnpm-lock.yaml").touch()
        (self.root / "src/app").mkdir(parents=True)
        (self.root / "tsconfig.json").write_text('''{
            // A direct JSONC config; inherited values are not resolved.
            "extends": ["@tsconfig/node22/tsconfig.json", "./config/base.json",],
            "compilerOptions": {"module": "NodeNext", "moduleResolution": "Bundler",
                "strict": true, "strictNullChecks": false, "noImplicitAny": true,
                "useUnknownInCatchVariables": false,},
        }''', encoding="utf-8")
        before = {file.relative_to(self.root): file.read_bytes() for file in self.root.rglob("*") if file.is_file()}
        result = self.successful_result()
        self.assertEqual(result["package"], "@example/service")
        self.assertEqual(result["frameworks"], {"next": "^15.0.0"})
        self.assertEqual(result["validation"], {"zod": "workspace:^"})
        self.assertEqual(result["package_manager"]["declared"], "pnpm@10.2.1")
        self.assertEqual(result["package_manager"]["nearest_lockfile"]["manager"], "pnpm")
        self.assertEqual(result["next_router_hint"], "app")
        self.assertEqual(result["relevant_script_names"], ["lint", "test:unit"])
        runtime = result["runtime"]
        self.assertEqual(runtime["node_declared"], ">=22 <25")
        self.assertEqual(runtime["typescript_declared"], "~5.8.0")
        self.assertEqual(runtime["tsconfig_extends"], ["@tsconfig/node22/tsconfig.json", "./config/base.json"])
        self.assertEqual(runtime["direct_compiler_options"], {
            "module": "NodeNext", "moduleResolution": "Bundler", "strict": True,
            "strictNullChecks": False, "noImplicitAny": True, "useUnknownInCatchVariables": False,
        })
        self.assertEqual(result["metadata_omissions"], [])
        self.assertNotIn(MARKER, json.dumps(result))
        self.assertFalse((self.root / MARKER).exists())
        after = {file.relative_to(self.root): file.read_bytes() for file in self.root.rglob("*") if file.is_file()}
        self.assertEqual(after, before)
        self.assertTrue(any("inherited" in limit for limit in result["evidence_limits"]))

    def test_invalid_package_json_is_machine_readable_without_parser_excerpt(self) -> None:
        for source in (f"{MARKER} malformed", "[]", "null"):
            with self.subTest(source=source):
                (self.root / "package.json").write_text(source, encoding="utf-8")
                process = self.run_recon()
                self.assertEqual(process.returncode, 2)
                self.assertEqual(process.stdout, "")
                self.assertIn("package.json", json.loads(process.stderr)["error"])
                self.assertNotIn(MARKER, process.stderr)

    def test_unavailable_config_is_distinct_from_absent_or_valid_config(self) -> None:
        missing = self.successful_result()["runtime"]
        self.assertFalse(missing["tsconfig_present"])
        self.assertIsNone(missing["tsconfig_error"])
        for source in (f"{MARKER} malformed", "[]", "null"):
            with self.subTest(source=source):
                (self.root / "tsconfig.json").write_text(source, encoding="utf-8")
                result = self.successful_result()
                self.assertTrue(result["runtime"]["tsconfig_present"])
                self.assertIsNotNone(result["runtime"]["tsconfig_error"])
                self.assertNotIn(MARKER, json.dumps(result))

    def test_invalid_and_oversized_metadata_is_explicitly_omitted(self) -> None:
        self.write_package({
            "name": "x" * 10_000, "packageManager": "pnpm@" + "1" * 10_000,
            "dependencies": {"next": "1" * 10_000, "zod": {"source": MARKER},
                             "axios": f"https://user:{MARKER}@example.invalid/archive.tgz"},
            "scripts": {"test:" + "x" * 10_000: MARKER, "lint": MARKER, "test:invalid": {"source": MARKER}},
        })
        (self.root / "tsconfig.json").write_text(json.dumps({
            "extends": {"source": MARKER}, "compilerOptions": {
                "strict": {"source": MARKER}, "module": "x" * 10_000,
                "moduleResolution": [MARKER], "noImplicitAny": False,
            },
        }), encoding="utf-8")
        result = self.successful_result()
        self.assertIsNone(result["package"])
        self.assertIsNone(result["package_manager"]["declared"])
        self.assertIsNone(result["frameworks"]["next"])
        self.assertIsNone(result["validation"]["zod"])
        self.assertIsNone(result["http_clients"]["axios"])
        self.assertEqual(result["relevant_script_names"], ["lint"])
        self.assertIsNone(result["runtime"]["tsconfig_extends"])
        self.assertIsNone(result["runtime"]["direct_compiler_options"]["strict"])
        self.assertIsNone(result["runtime"]["direct_compiler_options"]["module"])
        self.assertIsNone(result["runtime"]["direct_compiler_options"]["moduleResolution"])
        self.assertIs(result["runtime"]["direct_compiler_options"]["noImplicitAny"], False)
        omissions = " ".join(result["metadata_omissions"])
        for field in ("package", "package_manager", "next", "zod", "axios", "script", "extends", "strict", "module"):
            self.assertIn(field, omissions)
        self.assertNotIn(MARKER, json.dumps(result))
        self.assertLess(len(json.dumps(result)), 16_000)

    def test_unfamiliar_module_declarations_are_preserved_with_evidence_limits(self) -> None:
        self.write_package({"name": "not a package", "type": MARKER, "dependencies": [], "engines": [], "scripts": []})
        (self.root / "tsconfig.json").write_text(json.dumps({
            "extends": ["./base.json", {"source": MARKER}],
            "compilerOptions": {"module": "madeup", "moduleResolution": "madeup", "strict": "true"},
        }), encoding="utf-8")
        result = self.successful_result()
        self.assertIsNone(result["package"])
        self.assertEqual(result["frameworks"], {})
        self.assertIsNone(result["runtime"]["package_type"])
        self.assertEqual(result["runtime"]["tsconfig_extends"], ["./base.json"])
        for name in ("module", "moduleResolution"):
            self.assertEqual(result["runtime"]["direct_compiler_options"][name], "madeup")
            self.assertNotIn(f"compilerOptions.{name}:", " ".join(result["metadata_omissions"]))
        self.assertTrue(any("not compiler-validated" in limit for limit in result["evidence_limits"]))
        self.assertIsNone(result["runtime"]["direct_compiler_options"]["strict"])
        self.assertIn("strict", " ".join(result["metadata_omissions"]))
        for field in ("package", "package_type", "dependencies", "engines", "scripts", "extends"):
            self.assertIn(field, " ".join(result["metadata_omissions"]))
        self.assertNotIn(MARKER, json.dumps(result))

    def test_total_declaration_and_collection_limits_are_reported(self) -> None:
        self.write_package({
            "name": "@example/service", "dependencies": {"next": "1" * 250},
            "scripts": {f"test:{index:04}:" + "x" * 100: MARKER for index in range(500)},
        })
        (self.root / "tsconfig.json").write_text(json.dumps({
            "extends": [f"./config/base-{index}.json" for index in range(100)],
        }), encoding="utf-8")
        result = self.successful_result()
        self.assertLessEqual(len(result["relevant_script_names"]), 48)
        self.assertLessEqual(len(result["runtime"]["tsconfig_extends"]), 16)
        declarations = [result["package"], result["frameworks"]["next"],
                        *result["runtime"]["tsconfig_extends"], *result["relevant_script_names"]]
        self.assertLessEqual(sum(len(value) for value in declarations if isinstance(value, str)), 4096)
        self.assertTrue(result["metadata_omissions"])
        self.assertIn("total declaration limit", " ".join(result["metadata_omissions"]))
        self.assertIn("reference count limit", " ".join(result["metadata_omissions"]))
        self.assertLess(len(json.dumps(result)), 16_000)
        self.write_package({"scripts": {f"test:{index:04}": MARKER for index in range(500)}})
        counted = self.successful_result()
        self.assertEqual(len(counted["relevant_script_names"]), 48)
        self.assertIn("name count limit", " ".join(counted["metadata_omissions"]))

    def test_oversized_and_nonregular_input_files_are_unavailable(self) -> None:
        package = self.root / "package.json"
        package.write_text(" " * (1024 * 1024 + 1), encoding="utf-8")
        oversized = self.run_recon()
        self.assertEqual(oversized.returncode, 2)
        self.assertIn("size", json.loads(oversized.stderr)["error"])
        package.unlink()
        package.mkdir()
        nonregular = self.run_recon()
        self.assertEqual(nonregular.returncode, 2)
        self.assertIn("regular", json.loads(nonregular.stderr)["error"])
        package.rmdir()
        self.write_package({})
        config = self.root / "tsconfig.json"
        config.write_text(" " * (1024 * 1024 + 1), encoding="utf-8")
        result = self.successful_result()["runtime"]
        self.assertTrue(result["tsconfig_present"])
        self.assertIn("size", result["tsconfig_error"])
        config.unlink()
        if hasattr(os, "mkfifo"):
            os.mkfifo(config)
            result = self.successful_result()["runtime"]
            self.assertTrue(result["tsconfig_present"])
            self.assertIn("regular", result["tsconfig_error"])


if __name__ == "__main__":
    unittest.main()
