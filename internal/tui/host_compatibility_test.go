package tui

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostcompatibility"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func TestSelectionExplainsAndExcludesUnavailableEnvironment(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: []lifecycle.Target{
		{ID: domain.ComponentClaudeCode, Status: lifecycle.StatusManaged, Selected: true},
		{
			ID: domain.ComponentAntigravity2, Status: lifecycle.StatusManaged, Selected: true,
			HostCompatibility: &hostcompatibility.Assessment{
				ComponentID:      domain.ComponentAntigravity2,
				Status:           hostcompatibility.StatusIncompatible,
				DetectedVersions: []string{"2.1.0"},
				ExpectedVersions: []string{"2.2.1"},
			},
		},
	}})
	model.Init()

	view := model.View().Content
	for _, text := range []string{
		"Unavailable environments",
		"Antigravity 2.x — installed version 2.1.0 is not supported; supported: 2.2.1",
	} {
		if !strings.Contains(view, text) {
			t.Fatalf("view does not contain %q:\n%s", text, view)
		}
	}
	if strings.Count(view, "Antigravity 2.x") != 1 {
		t.Fatalf("Antigravity appeared as a selectable option:\n%s", view)
	}
	if !reflect.DeepEqual(model.selected, []domain.ComponentID{domain.ComponentClaudeCode}) {
		t.Fatalf("selected = %#v", model.selected)
	}
}

func TestSelectionSanitizesStaleUnavailableSelectionOnRebuild(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: []lifecycle.Target{
		{ID: domain.ComponentClaudeCode, Status: lifecycle.StatusAbsent},
		{
			ID: domain.ComponentAntigravity2,
			HostCompatibility: &hostcompatibility.Assessment{
				ComponentID: domain.ComponentAntigravity2,
				Status:      hostcompatibility.StatusMissing,
			},
		},
	}})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentAntigravity2}
	model.backToSelection()
	if !reflect.DeepEqual(model.selected, []domain.ComponentID{domain.ComponentClaudeCode}) {
		t.Fatalf("selected = %#v", model.selected)
	}
}

func TestCompatibilityMessagesDoNotExposeDiscoveryDetails(t *testing.T) {
	statuses := map[hostcompatibility.Status]string{
		hostcompatibility.StatusMissing:     "required application is not installed",
		hostcompatibility.StatusUnavailable: "application could not be checked safely",
	}
	for status, message := range statuses {
		model := newTestModel(t, &fakePreviewer{targets: []lifecycle.Target{{
			ID: domain.ComponentAntigravity2,
			HostCompatibility: &hostcompatibility.Assessment{
				ComponentID: domain.ComponentAntigravity2, Status: status,
			},
		}}})
		view := model.View().Content
		if !strings.Contains(view, message) {
			t.Fatalf("status %q view:\n%s", status, view)
		}
	}
}

func TestCompatibilityMessageSanitizesVersionText(t *testing.T) {
	target := lifecycle.Target{
		ID: domain.ComponentAntigravity2,
		HostCompatibility: &hostcompatibility.Assessment{
			ComponentID:      domain.ComponentAntigravity2,
			Status:           hostcompatibility.StatusIncompatible,
			DetectedVersions: []string{"2.1.0\x1b]8;;malicious\a"},
			ExpectedVersions: []string{"2.2.1\nforged"},
		},
	}
	got := compatibilityMessage(target)
	if strings.ContainsAny(got, "\x1b\a\n\r") || !strings.Contains(got, "unrecognized") {
		t.Fatalf("message contains unsafe version text: %q", got)
	}
}
