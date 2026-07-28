package releasecontract_test

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestBundleSchemaV6LoadsManagedFileOwnership(t *testing.T) {
	root := writeFixture(t)
	manifestPath, manifest := credentialStoreManifest(t, root)
	writeCredentialStoreFixture(t, root, manifestPath, manifest)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("Load(): %v", err)
	}
	ownership := release.Resources[0].FileOwnership
	if ownership == nil ||
		ownership.RegistryTarget.Path != "mainframe/file-ownership.json" ||
		ownership.RegistrySchemaVersion != 1 {
		t.Fatalf("file ownership = %#v", ownership)
	}
}

func TestManagedFileOwnershipFailsClosed(t *testing.T) {
	tests := map[string]func(map[string]any){
		"schema v5": func(manifest map[string]any) {
			manifest["schema_version"] = 5
		},
		"unknown kind": func(manifest map[string]any) {
			resource := manifest["resources"].([]any)[0].(map[string]any)
			resource["file_ownership"].(map[string]any)["kind"] = "unknown"
		},
		"unknown descriptor field": func(manifest map[string]any) {
			resource := manifest["resources"].([]any)[0].(map[string]any)
			resource["file_ownership"].(map[string]any)["unknown"] = true
		},
		"unimplemented apply": func(manifest map[string]any) {
			resource := manifest["resources"].([]any)[0].(map[string]any)
			resource["apply"] = "unimplemented"
		},
		"foreign registry root": func(manifest map[string]any) {
			resource := manifest["resources"].([]any)[0].(map[string]any)
			registry := resource["file_ownership"].(map[string]any)["registry"].(map[string]any)
			registry["target"].(map[string]any)["root"] = "credentials-config"
		},
		"overlapping registry": func(manifest map[string]any) {
			resource := manifest["resources"].([]any)[0].(map[string]any)
			registry := resource["file_ownership"].(map[string]any)["registry"].(map[string]any)
			registry["target"].(map[string]any)["path"] = "config.json/claims.json"
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			manifest["schema_version"] = 6
			resource := manifest["resources"].([]any)[0].(map[string]any)
			resource["strategy"] = "seed-if-absent"
			resource["observation"] = "supported"
			resource["apply"] = "supported"
			resource["file_ownership"] = managedFileOwnershipRecord(
				"codex-config",
				"mainframe/file-ownership.json",
			)
			mutate(manifest)
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)

			_, err := releasecontract.Load(root)
			if err == nil {
				t.Fatal("Load() accepted invalid managed file ownership")
			}
		})
	}
}

func TestBundleSchemaV6RejectsManagedFileApplyOutsideCredentialStore(
	t *testing.T,
) {
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["schema_version"] = 6
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["strategy"] = "seed-if-absent"
	resource["observation"] = "supported"
	resource["apply"] = "supported"
	delete(resource, "legacy_source_suffixes")
	resource["file_ownership"] = managedFileOwnershipRecord(
		"codex-config",
		"mainframe/file-ownership.json",
	)
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	if _, err := releasecontract.Load(root); err == nil ||
		!strings.Contains(err.Error(), "overstates lifecycle support") {
		t.Fatalf("Load() error = %v", err)
	}
}

func TestBundleSchemaV6RejectsManagedFileRegistryCollision(t *testing.T) {
	root := writeFixture(t)
	manifestPath, manifest := credentialStoreManifest(t, root)
	unit := manifest["install_units"].([]any)[0].(map[string]any)
	unit["target"].(map[string]any)["path"] =
		"mainframe/file-ownership.json"
	writeCredentialStoreFixture(t, root, manifestPath, manifest)

	if _, err := releasecontract.Load(root); err == nil ||
		!strings.Contains(err.Error(), "overlaps") {
		t.Fatalf("Load() error = %v", err)
	}
}

func credentialStoreManifest(
	t *testing.T,
	root string,
) (string, map[string]any) {
	t.Helper()
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["schema_version"] = 6
	manifest["component"] = "credential-tools"
	for _, collection := range []string{"install_units", "legacy_artifacts"} {
		for _, raw := range manifest[collection].([]any) {
			raw.(map[string]any)["target"].(map[string]any)["root"] =
				"credentials-config"
		}
	}
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["id"] = "credential-tools.secrets-store"
	resource["strategy"] = "seed-if-absent"
	resource["target"] = map[string]any{
		"root": "credentials-config", "path": "secrets.env",
	}
	resource["observation"] = "supported"
	resource["apply"] = "supported"
	delete(resource, "legacy_source_suffixes")
	resource["file_ownership"] = managedFileOwnershipRecord(
		"credentials-config",
		"mainframe/file-ownership.json",
	)
	return manifestPath, manifest
}

func writeCredentialStoreFixture(
	t *testing.T,
	root string,
	manifestPath string,
	manifest map[string]any,
) {
	t.Helper()
	writeJSON(t, manifestPath, manifest, 0o644)
	indexPath := filepath.Join(root, "release.json")
	index := readObject(t, indexPath)
	entry := index["manifests"].([]any)[0].(map[string]any)
	entry["component"] = "credential-tools"
	entry["sha256"] = digest(t, manifestPath)
	writeJSON(t, indexPath, index, 0o644)
}

func managedFileOwnershipRecord(root, path string) map[string]any {
	return map[string]any{
		"kind": "managed-file-registry-v1",
		"registry": map[string]any{
			"target":         map[string]any{"root": root, "path": path},
			"schema_version": 1,
		},
	}
}
