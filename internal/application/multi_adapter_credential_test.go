package application

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestSemanticReviewSharesCredentialInstanceAcrossAdapterProjections(
	t *testing.T,
) {
	definitions := applicationCredentialDefinitions(t)
	existing := applicationCredentialInstances(t, definitions)
	credentials := applicationCredentialSnapshot(
		t,
		definitions,
		existing.All(),
	)
	snapshot := applicationMultiAdapterMCPSnapshot(t)
	snapshot.Credentials = &credentials
	reviewer, err := NewReviewer(
		&fakeSnapshotBuilder{snapshots: []Snapshot{snapshot}},
	)
	if err != nil {
		t.Fatalf("NewReviewer() error = %v", err)
	}
	adapters := []domain.ComponentID{
		domain.ComponentAntigravity2,
		domain.ComponentOpenCode,
	}
	bindings := make([]MCPCredentialBinding, len(adapters))
	for index, adapter := range adapters {
		bindings[index] = MCPCredentialBinding{
			ComponentID: adapter,
			ServerID:    "context7", ProfileID: "remote-api-key",
			InstanceID: "context7-home",
		}
	}

	preview, err := reviewer.Preview(Request{
		Components: adapters,
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-api-key",
			Adapters: adapters,
		}},
		MCPCredentials: bindings,
	})
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	if len(preview.MCP.Intents) != 2 {
		t.Fatalf("MCP intents = %#v", preview.MCP.Intents)
	}
	for _, intent := range preview.MCP.Intents {
		if intent.ServerID != "context7" ||
			intent.ProfileID != "remote-api-key" {
			t.Fatalf("MCP intent = %#v", intent)
		}
	}
}

func applicationMultiAdapterMCPSnapshot(t *testing.T) Snapshot {
	t.Helper()
	host := applicationCredentialHost{}
	base, err := configuration.Inspect(nil, host)
	if err != nil {
		t.Fatalf("configuration.Inspect() error = %v", err)
	}
	projections := []releasecontract.MCPProjection{
		applicationAntigravityProjection(),
		applicationOpenCodeProjection(),
	}
	mcp, err := mcpconfiguration.Inspect(
		projections,
		applicationMCPCatalog(t),
		host,
	)
	if err != nil {
		t.Fatalf("mcpconfiguration.Inspect() error = %v", err)
	}
	model, err := applicationMCPInstallModel()
	if err != nil {
		t.Fatalf("applicationMCPInstallModel() error = %v", err)
	}
	service, err := lifecycle.NewWithInspections(
		model,
		domain.ObservedState{},
		base,
		mcp,
	)
	if err != nil {
		t.Fatalf("lifecycle.NewWithInspections() error = %v", err)
	}
	return Snapshot{Release: testReleaseIdentity(), Lifecycle: service}
}
