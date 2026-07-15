//go:build darwin || linux

package releasecontract

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReadVerifiedPayloadAuthenticatesTheOpenedBytes(t *testing.T) {
	root := t.TempDir()
	path := filepath.Join(root, "bundle", "config.json")
	if err := os.Mkdir(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir bundle: %v", err)
	}
	original := []byte(`{"permissions":[]}`)
	if err := os.WriteFile(path, original, 0o644); err != nil {
		t.Fatalf("write original: %v", err)
	}
	expected := payloadFile{
		Path: "config.json", Mode: "0644", Size: int64(len(original)), SHA256: digestBytes(original),
	}
	if err := os.WriteFile(path, []byte(`{"permissions":{}}`), 0o644); err != nil {
		t.Fatalf("replace payload: %v", err)
	}
	if _, err := readVerifiedPayload(root, "bundle/config.json", expected); err == nil {
		t.Fatal("changed payload bytes passed integrity verification")
	}
}

func TestReadVerifiedPayloadDoesNotFollowFinalSymlink(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "bundle"), 0o755); err != nil {
		t.Fatalf("mkdir bundle: %v", err)
	}
	target := filepath.Join(root, "target.json")
	payload := []byte(`{"permissions":[]}`)
	if err := os.WriteFile(target, payload, 0o644); err != nil {
		t.Fatalf("write target: %v", err)
	}
	if err := os.Symlink(target, filepath.Join(root, "bundle/config.json")); err != nil {
		t.Fatalf("symlink payload: %v", err)
	}
	expected := payloadFile{
		Path: "config.json", Mode: "0644", Size: int64(len(payload)), SHA256: digestBytes(payload),
	}
	if _, err := readVerifiedPayload(root, "bundle/config.json", expected); err == nil {
		t.Fatal("verified payload reader followed a symbolic link")
	}
}
