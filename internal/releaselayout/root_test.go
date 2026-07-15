package releaselayout_test

import (
	"fmt"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/releaselayout"
)

func TestResolveUsesExplicitReleaseRoot(t *testing.T) {
	root, err := releaselayout.Resolve(
		"/opt/mainframe/test-release",
		true,
		func() (string, error) { return "", fmt.Errorf("must not run") },
		func(path string) (string, error) { return path, nil },
	)
	if err != nil || root != "/opt/mainframe/test-release" {
		t.Fatalf("root = %q, err = %v", root, err)
	}
}

func TestResolveFindsReleaseAboveResolvedExecutableBin(t *testing.T) {
	root, err := releaselayout.Resolve(
		"",
		false,
		func() (string, error) { return "/usr/local/bin/mainframe", nil },
		func(path string) (string, error) {
			if path != "/usr/local/bin/mainframe" {
				t.Fatalf("resolve path = %q", path)
			}
			return "/opt/mainframe/test-release/bin/mainframe", nil
		},
	)
	if err != nil || root != "/opt/mainframe/test-release" {
		t.Fatalf("root = %q, err = %v", root, err)
	}
}

func TestResolveRejectsEmptyExplicitRootAndUnexpectedLayout(t *testing.T) {
	if _, err := releaselayout.Resolve("", true, nil, nil); err == nil {
		t.Fatal("empty explicit root was accepted")
	}
	_, err := releaselayout.Resolve(
		"",
		false,
		func() (string, error) { return "/tmp/mainframe", nil },
		func(path string) (string, error) { return path, nil },
	)
	if err == nil {
		t.Fatal("unexpected executable layout was accepted")
	}
}
