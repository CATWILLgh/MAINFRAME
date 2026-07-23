package diagnostics

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestBuildReturnsEmptyNonExecutablePlanWhenUnconfigured(t *testing.T) {
	got, err := Build(nil, Desired{})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if len(got.Intents) != 0 || got.Executable {
		t.Fatalf("Build() = %#v, want empty non-executable plan", got)
	}
}

func TestBuildCreatesStableEnableAndDisableIntents(t *testing.T) {
	got, err := Build(
		[]domain.ComponentID{
			domain.ComponentAntigravity2,
			domain.ComponentOpenCode,
			domain.ComponentClaudeCode,
			domain.ComponentCodex,
			domain.ComponentOpenCode,
			"internal-component",
		},
		Desired{Configured: true, Events: true},
	)
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	want := Plan{Intents: []Intent{
		{ComponentID: domain.ComponentClaudeCode, Events: true, Feedback: false},
		{ComponentID: domain.ComponentCodex, Events: true, Feedback: false},
		{ComponentID: domain.ComponentOpenCode, Events: true, Feedback: false},
		{ComponentID: domain.ComponentAntigravity2, Events: true, Feedback: false},
	}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("Build() = %#v, want %#v", got, want)
	}
}

func TestBuildRepresentsExplicitDisableForEverySelectedAdapter(t *testing.T) {
	got, err := Build(
		[]domain.ComponentID{domain.ComponentCodex, domain.ComponentClaudeCode},
		Desired{Configured: true},
	)
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	want := Plan{Intents: []Intent{
		{ComponentID: domain.ComponentClaudeCode},
		{ComponentID: domain.ComponentCodex},
	}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("Build() = %#v, want explicit disable %#v", got, want)
	}
}

func TestBuildRejectsContradictoryDesiredState(t *testing.T) {
	for _, desired := range []Desired{
		{Events: true},
		{Feedback: true},
		{Events: true, Feedback: true},
	} {
		if _, err := Build(nil, desired); err == nil ||
			!strings.Contains(err.Error(), "features require diagnostics to be configured") {
			t.Fatalf("Build(%#v) error = %v", desired, err)
		}
	}
}

func TestBuildRequiresDEVForHarnessFeedback(t *testing.T) {
	_, err := Build(
		[]domain.ComponentID{domain.ComponentClaudeCode},
		Desired{Configured: true, Feedback: true},
	)
	if err == nil || !strings.Contains(err.Error(), "feedback requires DEV mode") {
		t.Fatalf("Build() error = %v", err)
	}
}

func TestBuildRequiresAVisibleAdapterWhenConfigured(t *testing.T) {
	if _, err := Build(
		[]domain.ComponentID{"internal-component"},
		Desired{Configured: true},
	); err == nil || !strings.Contains(err.Error(), "at least one supported environment") {
		t.Fatalf("Build() error = %v", err)
	}
}
