package releasecontract

import (
	"strings"
	"testing"
)

func TestValidateGlobalRejectsCrossRuntimeDependency(t *testing.T) {
	manifests := []bundleManifest{
		{Component: "claude-code", Dependencies: []string{}},
		{Component: "opencode", Dependencies: []string{"claude-code"}},
	}

	err := validateGlobal(manifests)
	if err == nil || !strings.Contains(err.Error(), "cannot depend") {
		t.Fatalf("cross-runtime dependency result = %v", err)
	}
}

func TestValidateGlobalAcceptsAdapterNeutralDependencies(t *testing.T) {
	manifests := []bundleManifest{
		{Component: "credential-tools", Dependencies: []string{}},
		{Component: "mainframe-cli", Dependencies: []string{}},
		{
			Component:    "opencode",
			Dependencies: []string{"credential-tools", "mainframe-cli"},
		},
	}

	if err := validateGlobal(manifests); err != nil {
		t.Fatalf("neutral dependencies: %v", err)
	}
}
