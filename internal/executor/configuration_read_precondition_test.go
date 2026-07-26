package executor

import (
	"errors"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestApplyChecksReadPreconditionsBeforeAnyWrite(t *testing.T) {
	preview := preparedExecutorPreview(t, `{"bash":"allow"}`)
	precondition := configuration.ReadPrecondition{
		Kind:               configuration.ReadPreconditionSymlink,
		Target:             testConfigurationLocation("legacy.json"),
		Device:             8,
		Inode:              13,
		ExpectedTargetPath: "/home/test/.config/opencode/opencode.json",
	}
	prepared, err := configuration.NewPreparedPlanWithPreconditions(
		preview.Configuration.Transitions(),
		[]configuration.ReadPrecondition{precondition},
	)
	if err != nil {
		t.Fatalf("NewPreparedPlanWithPreconditions() error = %v", err)
	}
	preview.Configuration = prepared
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	configurations.preconditionErr = errors.New("read precondition changed")

	_, err = fixture.configurationExecutor(configurations).Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "read precondition changed") {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.store.saveCalls != 0 || fixture.workspace.filesystemCalls() != 0 ||
		len(configurations.private) != 0 || len(configurations.payloads) != 0 ||
		len(configurations.public) != 0 || len(configurations.staged) != 0 {
		t.Fatalf(
			"precondition failure caused writes: saves=%d link=%d private=%#v payloads=%#v public=%#v staged=%#v",
			fixture.store.saveCalls,
			fixture.workspace.filesystemCalls(),
			configurations.private,
			configurations.payloads,
			configurations.public,
			configurations.staged,
		)
	}
	if got := configurations.preconditions[precondition.Target]; got != precondition {
		t.Fatalf("checked precondition = %#v, want %#v", got, precondition)
	}
}

func TestApplyRequiresWorkspaceForReadPreconditionBeforeWrites(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"credential-tools"})
	prepared, err := configuration.NewPreparedPlanWithPreconditions(
		nil,
		[]configuration.ReadPrecondition{{
			Kind:               configuration.ReadPreconditionSymlink,
			Target:             testConfigurationLocation("legacy.json"),
			Device:             8,
			Inode:              13,
			ExpectedTargetPath: "/home/test/.config/opencode/opencode.json",
		}},
	)
	if err != nil {
		t.Fatalf("NewPreparedPlanWithPreconditions() error = %v", err)
	}
	preview.Configuration = prepared
	fixture := newFixture(preview)

	_, err = fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "configuration workspace") {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.store.saveCalls != 0 || fixture.workspace.filesystemCalls() != 0 {
		t.Fatal("missing configuration workspace caused writes")
	}
}
