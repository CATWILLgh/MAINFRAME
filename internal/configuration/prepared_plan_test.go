package configuration_test

import (
	"crypto/sha256"
	"fmt"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestNewPreparedPlanNormalizesAndClonesTransitions(t *testing.T) {
	first := preparedTransition("z-resource", "z.json", 21)
	second := preparedTransition("a-resource", "a.json", 22)
	input := []configuration.Transition{first, second}

	plan, err := configuration.NewPreparedPlan(input)
	if err != nil {
		t.Fatalf("NewPreparedPlan() error = %v", err)
	}
	input[0].ResourceIDs[0] = "forged"
	input[0].Mutations[0].After[0] = 'x'

	got := plan.Transitions()
	if len(got) != 2 || got[0].ResourceIDs[0] != "a-resource" ||
		got[1].ResourceIDs[0] != "z-resource" {
		t.Fatalf("normalized transitions = %#v", got)
	}
	got[0].Mutations[0].After[0] = 'x'
	if reflect.DeepEqual(got, plan.Transitions()) {
		t.Fatal("Transitions() exposed mutable plan storage")
	}
}

func TestCombinePreparedPlansRevalidatesTheCombinedBoundary(t *testing.T) {
	first, err := configuration.NewPreparedPlan([]configuration.Transition{
		preparedTransition("first", "first.json", 31),
	})
	if err != nil {
		t.Fatal(err)
	}
	second, err := configuration.NewPreparedPlan([]configuration.Transition{
		preparedTransition("second", "second.json", 32),
	})
	if err != nil {
		t.Fatal(err)
	}

	combined, err := configuration.CombinePreparedPlans(first, second)
	if err != nil || len(combined.Transitions()) != 2 {
		t.Fatalf("CombinePreparedPlans() = %#v, %v", combined, err)
	}

	duplicate := preparedTransition("third", "first.json", 33)
	unsafe, err := configuration.NewPreparedPlan([]configuration.Transition{duplicate})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := configuration.CombinePreparedPlans(first, unsafe); err == nil {
		t.Fatal("CombinePreparedPlans() accepted a duplicate target")
	}

	aliasTransition := preparedTransition("alias", "alias.json", 31)
	alias, err := configuration.NewPreparedPlan([]configuration.Transition{aliasTransition})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := configuration.CombinePreparedPlans(first, alias); err == nil {
		t.Fatal("CombinePreparedPlans() accepted a cross-plan physical alias")
	}
}

func TestNewPreparedPlanRejectsMalformedTransitions(t *testing.T) {
	valid := preparedTransition("resource", "config.toml", 41)
	tests := map[string]func() []configuration.Transition{
		"empty transition": func() []configuration.Transition {
			return []configuration.Transition{{ResourceIDs: []string{"resource"}}}
		},
		"invalid resource id": func() []configuration.Transition {
			input := clonePreparedTransitions(valid)
			input[0].ResourceIDs[0] = "Invalid ID"
			return input
		},
		"invalid target": func() []configuration.Transition {
			input := clonePreparedTransitions(valid)
			input[0].Mutations[0].Target.Path = "../config.toml"
			return input
		},
		"missing digest": func() []configuration.Transition {
			input := clonePreparedTransitions(valid)
			input[0].Mutations[0].Before.SHA256 = ""
			return input
		},
		"missing identity": func() []configuration.Transition {
			input := clonePreparedTransitions(valid)
			input[0].Mutations[0].Before.Inode = 0
			return input
		},
		"unsafe mode": func() []configuration.Transition {
			input := clonePreparedTransitions(valid)
			input[0].Mutations[0].Mode = 0o666
			return input
		},
		"duplicate resource": func() []configuration.Transition {
			first := clonePreparedTransitions(valid)[0]
			second := preparedTransition("resource", "other.toml", 42)
			return []configuration.Transition{first, second}
		},
		"duplicate target": func() []configuration.Transition {
			first := clonePreparedTransitions(valid)[0]
			second := preparedTransition("other", "config.toml", 42)
			return []configuration.Transition{first, second}
		},
		"overlapping target": func() []configuration.Transition {
			first := clonePreparedTransitions(valid)[0]
			second := preparedTransition("other", "config.toml/child", 42)
			return []configuration.Transition{first, second}
		},
		"physical alias": func() []configuration.Transition {
			first := clonePreparedTransitions(valid)[0]
			second := preparedTransition("other", "other.toml", 41)
			return []configuration.Transition{first, second}
		},
	}
	for name, makeInput := range tests {
		t.Run(name, func(t *testing.T) {
			if plan, err := configuration.NewPreparedPlan(makeInput()); err == nil || len(plan.Transitions()) != 0 {
				t.Fatalf("NewPreparedPlan() = %#v, %v", plan, err)
			}
		})
	}
}

func TestNewPreparedPlanAllowsAnEmptyAfterImage(t *testing.T) {
	transition := preparedTransition("resource", "config.toml", 51)
	transition.Mutations[0].After = []byte{}
	if _, err := configuration.NewPreparedPlan([]configuration.Transition{transition}); err != nil {
		t.Fatalf("NewPreparedPlan() rejected an empty file image: %v", err)
	}
}

func preparedTransition(resource, path string, inode uint64) configuration.Transition {
	before := []byte("before")
	digest := sha256.Sum256(before)
	return configuration.Transition{
		ResourceIDs: []string{resource},
		Mutations: []configuration.FileMutation{{
			Target: domain.Location{Root: domain.RootCodexConfig, Path: domain.ArtifactPath(path)},
			Before: configuration.BeforeImage{
				Exists: true, SHA256: fmt.Sprintf("%x", digest), Mode: 0o600,
				Device: 7, Inode: inode,
			},
			After: []byte("after"), Mode: 0o600,
		}},
	}
}

func clonePreparedTransitions(input configuration.Transition) []configuration.Transition {
	return []configuration.Transition{{
		ResourceIDs: append([]string(nil), input.ResourceIDs...),
		Mutations: []configuration.FileMutation{{
			Target: input.Mutations[0].Target,
			Before: input.Mutations[0].Before,
			After:  append([]byte(nil), input.Mutations[0].After...),
			Mode:   input.Mutations[0].Mode,
		}},
	}}
}
