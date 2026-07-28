package configuration

import (
	"errors"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

func TestPreparedPlanClonesAndCombinesSecretMaterializations(t *testing.T) {
	transition, recipe := secretMaterializationFixture()
	recipes := []SecretMaterializationRecipe{recipe}
	plan, err := NewPreparedPlanWithMaterializations(
		[]Transition{transition},
		nil,
		recipes,
	)
	if err != nil {
		t.Fatalf("NewPreparedPlanWithMaterializations() error = %v", err)
	}
	recipes[0].SecretReference = "MUTATED"
	exposed := plan.Materializations()
	exposed[0].SecretReference = "EXPOSED"

	combined, err := CombinePreparedPlans(PreparedPlan{}, plan)
	if err != nil {
		t.Fatalf("CombinePreparedPlans() error = %v", err)
	}
	got := combined.Materializations()
	if len(got) != 1 || got[0].SecretReference != recipe.SecretReference {
		t.Fatalf("combined materializations = %#v", got)
	}
}

func TestPreparedPlanRejectsInvalidSecretMaterializationBindings(t *testing.T) {
	transition, valid := secretMaterializationFixture()
	tests := map[string]func(*SecretMaterializationRecipe, *[]Transition){
		"invalid pointer": func(recipe *SecretMaterializationRecipe, _ *[]Transition) {
			recipe.ConfigValuePointer = "not-a-pointer"
		},
		"missing placeholder": func(_ *SecretMaterializationRecipe, transitions *[]Transition) {
			(*transitions)[0].Mutations[0].After.Content = []byte(`{"mcp":{"context7":{"apiKey":"wrong"}}}`)
		},
		"disconnected resource": func(recipe *SecretMaterializationRecipe, _ *[]Transition) {
			recipe.ResourceID = "antigravity2.mcp.other"
		},
		"disconnected target": func(recipe *SecretMaterializationRecipe, _ *[]Transition) {
			recipe.RegistryTarget.Path = "other-registry.json"
		},
		"invalid secret reference": func(recipe *SecretMaterializationRecipe, _ *[]Transition) {
			recipe.SecretReference = "not shell safe"
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			transitions := cloneTransitions([]Transition{transition})
			recipe := valid
			mutate(&recipe, &transitions)
			if _, err := NewPreparedPlanWithMaterializations(
				transitions,
				nil,
				[]SecretMaterializationRecipe{recipe},
			); err == nil {
				t.Fatal("constructor accepted invalid materialization")
			}
		})
	}
}

func TestMaterializeSecretFileRejectsHeaderBreakingValues(t *testing.T) {
	plan := secretFileMaterializationPlan(t)
	for _, value := range []string{"line\nbreak", "line\rbreak", "nul\x00byte"} {
		if _, err := plan.MaterializeSecrets(staticResolver(value)); err == nil {
			t.Fatalf("MaterializeSecrets() accepted %q", value)
		}
	}
}

type staticResolver string

func (resolver staticResolver) ResolveSecret(string) (string, error) {
	return string(resolver), nil
}

func secretFileMaterializationPlan(t *testing.T) PreparedPlan {
	t.Helper()
	fileTarget := domain.Location{
		Root: domain.RootOpenCodeConfig,
		Path: "mainframe/secrets/context7-api-key",
	}
	registryTarget := domain.Location{
		Root: domain.RootOpenCodeConfig,
		Path: "opencode.json.mainframe-mcp.json",
	}
	plan, err := NewPreparedPlanWithMaterializations(
		[]Transition{{
			ResourceIDs: []string{"opencode.mcp.context7"},
			Mutations: []FileMutation{
				secretMutation(
					fileTarget,
					[]byte(DeferredSecretFilePlaceholder),
				),
				secretMutation(
					registryTarget,
					[]byte(`{"servers":{"context7":{"digest":"`+
						DeferredSecretDigestPlaceholder+`"}}}`),
				),
			},
		}},
		nil,
		[]SecretMaterializationRecipe{{
			ResourceID:            "opencode.mcp.context7",
			FileTarget:            fileTarget,
			RegistryTarget:        registryTarget,
			RegistryDigestPointer: "/servers/context7/digest",
			SecretReference:       "CONTEXT7_KEY",
		}},
	)
	if err != nil {
		t.Fatal(err)
	}
	return plan
}

func TestPreparedPlanRejectsDuplicateAndOverlappingSecretMaterializations(t *testing.T) {
	transition, recipe := secretMaterializationFixture()
	duplicate := recipe
	if _, err := NewPreparedPlanWithMaterializations(
		[]Transition{transition},
		nil,
		[]SecretMaterializationRecipe{recipe, duplicate},
	); err == nil {
		t.Fatal("constructor accepted duplicate materialization")
	}

	overlap := recipe
	overlap.ResourceID = "antigravity2.mcp.other"
	overlap.ConfigEntryPointer = "/mcp"
	overlap.SecretReference = "OTHER_KEY"
	transition.ResourceIDs = append(transition.ResourceIDs, overlap.ResourceID)
	if _, err := NewPreparedPlanWithMaterializations(
		[]Transition{transition},
		nil,
		[]SecretMaterializationRecipe{recipe, overlap},
	); err == nil {
		t.Fatal("constructor accepted overlapping materialization")
	}
}

func TestPreparedPlanRejectsCrossRoleSecretMaterializationOverlap(t *testing.T) {
	leftTarget := domain.Location{
		Root: domain.RootAntigravityData,
		Path: "left.json",
	}
	rightTarget := domain.Location{
		Root: domain.RootAntigravityData,
		Path: "right.json",
	}
	transition := Transition{
		ResourceIDs: []string{"antigravity2.mcp.left", "antigravity2.mcp.right"},
		Mutations: []FileMutation{
			secretMutation(leftTarget, crossRoleDocument("left")),
			secretMutation(rightTarget, crossRoleDocument("right")),
		},
	}
	recipes := []SecretMaterializationRecipe{
		crossRoleRecipe("left", leftTarget, rightTarget),
		crossRoleRecipe("right", rightTarget, leftTarget),
	}

	if _, err := NewPreparedPlanWithMaterializations(
		[]Transition{transition},
		nil,
		recipes,
	); err == nil {
		t.Fatal("constructor accepted cross-role pointer overlap")
	}
}

func TestMaterializeSecretsEscapesValueHashesCanonicalEntryAndConsumesRecipe(t *testing.T) {
	transition, recipe := secretMaterializationFixture()
	plan, err := NewPreparedPlanWithMaterializations(
		[]Transition{transition},
		nil,
		[]SecretMaterializationRecipe{recipe},
	)
	if err != nil {
		t.Fatalf("NewPreparedPlanWithMaterializations() error = %v", err)
	}
	resolver := &fakeSecretResolver{value: "quote\" slash\\ newline\n"}

	materialized, err := plan.MaterializeSecrets(resolver)
	if err != nil {
		t.Fatalf("MaterializeSecrets() error = %v", err)
	}
	if resolver.calls != 1 || len(materialized.Materializations()) != 0 {
		t.Fatalf("resolver calls = %d, recipes = %#v", resolver.calls, materialized.Materializations())
	}
	mutations := materialized.Transitions()[0].Mutations
	configMutation := mutationForTarget(t, mutations, recipe.ConfigTarget)
	config := parseTestDocument(t, configMutation.After.Content)
	valuePointer, _ := jsondocument.ParsePointer(recipe.ConfigValuePointer)
	if value, status := config.Lookup(valuePointer); status != jsondocument.Found ||
		value != `"quote\" slash\\ newline\n"` {
		t.Fatalf("materialized value = %q, status = %q", value, status)
	}
	registryMutation := mutationForTarget(t, mutations, recipe.RegistryTarget)
	registry := parseTestDocument(t, registryMutation.After.Content)
	digestPointer, _ := jsondocument.ParsePointer(recipe.RegistryDigestPointer)
	digest, status := registry.Lookup(digestPointer)
	if status != jsondocument.Found ||
		digest != `"947d10ac2ff10f2087ff89317b18456e16eec76d5f2654017b201a5e92b22f49"` {
		t.Fatalf("registry digest = %q, status = %q", digest, status)
	}
}

func TestMaterializeSecretsRedactsEmptyAndResolverFailures(t *testing.T) {
	transition, recipe := secretMaterializationFixture()
	plan, err := NewPreparedPlanWithMaterializations(
		[]Transition{transition}, nil, []SecretMaterializationRecipe{recipe},
	)
	if err != nil {
		t.Fatalf("NewPreparedPlanWithMaterializations() error = %v", err)
	}
	distinctive := "FAKE_SECRET_MUST_NOT_APPEAR"
	tests := []*fakeSecretResolver{
		{value: ""},
		{err: errors.New(distinctive)},
	}
	for _, resolver := range tests {
		_, err := plan.MaterializeSecrets(resolver)
		if err == nil || strings.Contains(err.Error(), distinctive) {
			t.Fatalf("MaterializeSecrets() error = %v", err)
		}
	}
}

type fakeSecretResolver struct {
	value string
	err   error
	calls int
}

func (resolver *fakeSecretResolver) ResolveSecret(string) (string, error) {
	resolver.calls++
	return resolver.value, resolver.err
}

func secretMaterializationFixture() (Transition, SecretMaterializationRecipe) {
	configTarget := domain.Location{
		Root: domain.RootAntigravityData,
		Path: "mcp_config.json",
	}
	registryTarget := domain.Location{
		Root: domain.RootAntigravityData,
		Path: "mainframe/mcp-ownership.json",
	}
	resourceID := "antigravity2.mcp.context7"
	transition := Transition{
		ResourceIDs: []string{resourceID},
		Mutations: []FileMutation{
			secretMutation(configTarget, []byte(
				`{"mcp":{"context7":{"apiKey":`+DeferredSecretJSONPlaceholder+`}}}`,
			)),
			secretMutation(registryTarget, []byte(
				`{"servers":{"context7":{"digest":"`+
					DeferredSecretDigestPlaceholder+`"}}}`,
			)),
		},
	}
	return transition, SecretMaterializationRecipe{
		ResourceID:            resourceID,
		ConfigTarget:          configTarget,
		ConfigEntryPointer:    "/mcp/context7",
		ConfigValuePointer:    "/mcp/context7/apiKey",
		RegistryTarget:        registryTarget,
		RegistryDigestPointer: "/servers/context7/digest",
		SecretReference:       "CONTEXT7_FAKE_KEY",
	}
}

func secretMutation(target domain.Location, content []byte) FileMutation {
	return FileMutation{
		Disposition: MutationPresent,
		Target:      target,
		After: AfterImage{
			Exists:  true,
			Content: content,
			Mode:    privateConfigurationMode,
		},
	}
}

func crossRoleDocument(name string) []byte {
	return []byte(
		`{"entries":{"` + name + `":{"secret":` +
			DeferredSecretJSONPlaceholder + `,"digest":"` +
			DeferredSecretDigestPlaceholder + `"}}}`,
	)
}

func crossRoleRecipe(
	name string,
	configTarget domain.Location,
	registryTarget domain.Location,
) SecretMaterializationRecipe {
	return SecretMaterializationRecipe{
		ResourceID:            "antigravity2.mcp." + name,
		ConfigTarget:          configTarget,
		ConfigEntryPointer:    "/entries/" + name,
		ConfigValuePointer:    "/entries/" + name + "/secret",
		RegistryTarget:        registryTarget,
		RegistryDigestPointer: "/entries/" + oppositeName(name) + "/digest",
		SecretReference:       strings.ToUpper(name) + "_KEY",
	}
}

func oppositeName(name string) string {
	if name == "left" {
		return "right"
	}
	return "left"
}

func parseTestDocument(t *testing.T, raw []byte) jsondocument.Document {
	t.Helper()
	document, err := jsondocument.Parse(raw)
	if err != nil {
		t.Fatalf("parse JSON: %v", err)
	}
	return document
}

func mutationForTarget(
	t *testing.T,
	mutations []FileMutation,
	target domain.Location,
) FileMutation {
	t.Helper()
	for _, mutation := range mutations {
		if mutation.Target == target {
			return mutation
		}
	}
	t.Fatalf("mutation for %v is missing", target)
	return FileMutation{}
}
