package main

import (
	"path/filepath"
	"reflect"
	"runtime"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostcompatibility"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestBuildPreviewServiceDiscoversReleaseHostRequirements(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("CODEX_HOME", filepath.Join(home, ".codex"))
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, ".config"))
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{ID: domain.ComponentClaudeCode},
		{ID: domain.ComponentCodex},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
	})
	if err != nil {
		t.Fatal(err)
	}
	release := releasecontract.Release{
		ID: "test", Model: model,
		HostRequirements: []releasecontract.HostRequirement{{
			ComponentID:      domain.ComponentAntigravity2,
			Kind:             releasecontract.HostRequirementDarwinApplicationBundleV1,
			BundleIdentifier: "com.google.antigravity",
			ExactVersions:    []string{"2.2.1"},
		}},
	}
	var gotGOOS string
	var gotRoots []string
	discover := func(goos string, roots []string) hostcompatibility.ApplicationInventory {
		gotGOOS = goos
		gotRoots = append([]string(nil), roots...)
		return hostcompatibility.ApplicationInventory{
			Available: true, Complete: true,
			Applications: []hostcompatibility.Application{{
				BundleIdentifier: "com.google.antigravity", Version: "2.2.1",
			}},
		}
	}

	service, err := buildPreviewServiceFromContextWithHostDiscovery(
		t.TempDir(), release, "", nil, discover,
	)
	if err != nil {
		t.Fatalf("build preview service: %v", err)
	}
	if gotGOOS != runtime.GOOS {
		t.Fatalf("GOOS = %q, want %q", gotGOOS, runtime.GOOS)
	}
	wantRoots := []string{"/Applications", filepath.Join(home, "Applications")}
	if !reflect.DeepEqual(gotRoots, wantRoots) {
		t.Fatalf("roots = %#v, want %#v", gotRoots, wantRoots)
	}
	target := service.Targets()[3]
	if target.HostCompatibility == nil ||
		target.HostCompatibility.Status != hostcompatibility.StatusSatisfied {
		t.Fatalf("Antigravity target = %#v", target)
	}
}
