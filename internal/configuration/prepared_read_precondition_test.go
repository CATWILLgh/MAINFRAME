package configuration_test

import (
	"path/filepath"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestNewPreparedPlanWithPreconditionsNormalizesAndClones(t *testing.T) {
	input := []configuration.ReadPrecondition{
		preparedReadPrecondition("z.json", 61, "/tmp/z.json"),
		preparedReadPrecondition("a.json", 62, "/tmp/a.json"),
	}

	plan, err := configuration.NewPreparedPlanWithPreconditions(nil, input)
	if err != nil {
		t.Fatalf("NewPreparedPlanWithPreconditions() error = %v", err)
	}
	input[0].ExpectedTargetPath = "/tmp/forged.json"

	got := plan.Preconditions()
	if len(got) != 2 || got[0].Target.Path != "a.json" ||
		got[1].Target.Path != "z.json" {
		t.Fatalf("normalized preconditions = %#v", got)
	}
	got[0].ExpectedTargetPath = "/tmp/changed.json"
	if reflect.DeepEqual(got, plan.Preconditions()) {
		t.Fatal("Preconditions() exposed mutable plan storage")
	}
}

func TestNewPreparedPlanWithPreconditionsRejectsMalformedInput(t *testing.T) {
	valid := preparedReadPrecondition("legacy.json", 71, "/tmp/current.json")
	tests := map[string]func() []configuration.ReadPrecondition{
		"invalid kind": func() []configuration.ReadPrecondition {
			input := []configuration.ReadPrecondition{valid}
			input[0].Kind = "other"
			return input
		},
		"invalid target": func() []configuration.ReadPrecondition {
			input := []configuration.ReadPrecondition{valid}
			input[0].Target.Path = "../legacy.json"
			return input
		},
		"nonportable target": func() []configuration.ReadPrecondition {
			input := []configuration.ReadPrecondition{valid}
			input[0].Target.Path = "настройки.json"
			return input
		},
		"missing device": func() []configuration.ReadPrecondition {
			input := []configuration.ReadPrecondition{valid}
			input[0].Device = 0
			return input
		},
		"missing inode": func() []configuration.ReadPrecondition {
			input := []configuration.ReadPrecondition{valid}
			input[0].Inode = 0
			return input
		},
		"relative expected target": func() []configuration.ReadPrecondition {
			input := []configuration.ReadPrecondition{valid}
			input[0].ExpectedTargetPath = "current.json"
			return input
		},
		"unclean expected target": func() []configuration.ReadPrecondition {
			input := []configuration.ReadPrecondition{valid}
			input[0].ExpectedTargetPath = string(filepath.Separator) +
				filepath.Join("tmp", "nested") +
				string(filepath.Separator) + ".." +
				string(filepath.Separator) + "current.json"
			return input
		},
		"duplicate target": func() []configuration.ReadPrecondition {
			return []configuration.ReadPrecondition{
				valid,
				preparedReadPrecondition("legacy.json", 72, "/tmp/other.json"),
			}
		},
	}
	for name, makeInput := range tests {
		t.Run(name, func(t *testing.T) {
			plan, err := configuration.NewPreparedPlanWithPreconditions(
				nil,
				makeInput(),
			)
			if err == nil || len(plan.Preconditions()) != 0 {
				t.Fatalf(
					"NewPreparedPlanWithPreconditions() = %#v, %v",
					plan,
					err,
				)
			}
		})
	}
}

func TestNewPreparedPlanWithPreconditionsRejectsMutationOverlap(t *testing.T) {
	transition := preparedTransition("resource", "config/current.json", 81)
	precondition := preparedReadPrecondition(
		"config",
		82,
		"/tmp/current.json",
	)
	precondition.Target.Root = domain.RootCodexConfig

	if _, err := configuration.NewPreparedPlanWithPreconditions(
		[]configuration.Transition{transition},
		[]configuration.ReadPrecondition{precondition},
	); err == nil {
		t.Fatal("NewPreparedPlanWithPreconditions() accepted logical overlap")
	}
}

func TestCombinePreparedPlansCombinesPreconditions(t *testing.T) {
	first, err := configuration.NewPreparedPlanWithPreconditions(
		nil,
		[]configuration.ReadPrecondition{
			preparedReadPrecondition("z.json", 91, "/tmp/z.json"),
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	second, err := configuration.NewPreparedPlanWithPreconditions(
		nil,
		[]configuration.ReadPrecondition{
			preparedReadPrecondition("a.json", 92, "/tmp/a.json"),
		},
	)
	if err != nil {
		t.Fatal(err)
	}

	combined, err := configuration.CombinePreparedPlans(first, second)
	if err != nil {
		t.Fatalf("CombinePreparedPlans() error = %v", err)
	}
	got := combined.Preconditions()
	if len(got) != 2 || got[0].Target.Path != "a.json" ||
		got[1].Target.Path != "z.json" {
		t.Fatalf("combined preconditions = %#v", got)
	}

	duplicate, err := configuration.NewPreparedPlanWithPreconditions(
		nil,
		[]configuration.ReadPrecondition{
			preparedReadPrecondition("z.json", 93, "/tmp/other.json"),
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := configuration.CombinePreparedPlans(
		first,
		duplicate,
	); err == nil {
		t.Fatal("CombinePreparedPlans() accepted duplicate preconditions")
	}
}

func preparedReadPrecondition(
	path string,
	inode uint64,
	expectedTargetPath string,
) configuration.ReadPrecondition {
	return configuration.ReadPrecondition{
		Kind: configuration.ReadPreconditionSymlink,
		Target: domain.Location{
			Root: domain.RootAntigravityData,
			Path: domain.ArtifactPath(path),
		},
		Device:             7,
		Inode:              inode,
		ExpectedTargetPath: expectedTargetPath,
	}
}
