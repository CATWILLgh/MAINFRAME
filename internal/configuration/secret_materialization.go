package configuration

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"regexp"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

const (
	DeferredSecretJSONPlaceholder   = `"$MAINFRAME_DEFERRED_SECRET_VALUE"`
	DeferredSecretDigestPlaceholder = "$MAINFRAME_DEFERRED_SECRET_DIGEST"
	DeferredSecretFilePlaceholder   = "$MAINFRAME_DEFERRED_SECRET_FILE"
)

var deferredSecretReferencePattern = regexp.MustCompile(
	`^[A-Z_][A-Z0-9_]*$`,
)

type SecretMaterializationRecipe struct {
	ResourceID            string
	FileTarget            domain.Location
	ConfigTarget          domain.Location
	ConfigEntryPointer    string
	ConfigValuePointer    string
	RegistryTarget        domain.Location
	RegistryDigestPointer string
	SecretReference       string
}

type SecretResolver interface {
	ResolveSecret(string) (string, error)
}

func cloneSecretMaterializations(
	source []SecretMaterializationRecipe,
) []SecretMaterializationRecipe {
	result := append([]SecretMaterializationRecipe(nil), source...)
	sort.Slice(result, func(left, right int) bool {
		return secretMaterializationLess(result[left], result[right])
	})
	return result
}

func secretMaterializationLess(
	left SecretMaterializationRecipe,
	right SecretMaterializationRecipe,
) bool {
	switch {
	case left.ConfigTarget != right.ConfigTarget:
		return locationLess(left.ConfigTarget, right.ConfigTarget)
	case left.ConfigEntryPointer != right.ConfigEntryPointer:
		return left.ConfigEntryPointer < right.ConfigEntryPointer
	case left.RegistryTarget != right.RegistryTarget:
		return locationLess(left.RegistryTarget, right.RegistryTarget)
	case left.RegistryDigestPointer != right.RegistryDigestPointer:
		return left.RegistryDigestPointer < right.RegistryDigestPointer
	default:
		return left.ResourceID < right.ResourceID
	}
}

func validateSecretMaterializations(
	transitions []Transition,
	recipes []SecretMaterializationRecipe,
) error {
	seenResources := make(map[string]bool)
	parsed := make([]parsedSecretMaterialization, 0, len(recipes))
	for _, recipe := range recipes {
		current, err := parseSecretMaterialization(recipe)
		if err != nil {
			return err
		}
		if seenResources[recipe.ResourceID] {
			return errors.New("duplicate deferred secret resource")
		}
		if err := validateMaterializationConnection(
			transitions,
			current,
		); err != nil {
			return err
		}
		for _, previous := range parsed {
			if materializationsOverlap(previous, current) {
				return errors.New("deferred secret materializations overlap")
			}
		}
		seenResources[recipe.ResourceID] = true
		parsed = append(parsed, current)
	}
	return nil
}

type parsedSecretMaterialization struct {
	recipe         SecretMaterializationRecipe
	configEntry    jsondocument.Pointer
	configValue    jsondocument.Pointer
	registryDigest jsondocument.Pointer
}

func parseSecretMaterialization(
	recipe SecretMaterializationRecipe,
) (parsedSecretMaterialization, error) {
	if !preparedResourceIDPattern.MatchString(recipe.ResourceID) ||
		!deferredSecretReferencePattern.MatchString(recipe.SecretReference) {
		return parsedSecretMaterialization{}, errors.New(
			"invalid deferred secret materialization",
		)
	}
	if recipe.FileTarget.Valid() {
		return parseSecretFileMaterialization(recipe)
	}
	if recipe.ConfigTarget == recipe.RegistryTarget {
		return parsedSecretMaterialization{}, errors.New(
			"invalid deferred secret materialization",
		)
	}
	entry, entryErr := jsondocument.ParsePointer(recipe.ConfigEntryPointer)
	value, valueErr := jsondocument.ParsePointer(recipe.ConfigValuePointer)
	digest, digestErr := jsondocument.ParsePointer(recipe.RegistryDigestPointer)
	if entryErr != nil || valueErr != nil || digestErr != nil ||
		!pointerStrictlyContains(entry, value) {
		return parsedSecretMaterialization{}, errors.New(
			"invalid deferred secret materialization pointer",
		)
	}
	return parsedSecretMaterialization{
		recipe:         recipe,
		configEntry:    entry,
		configValue:    value,
		registryDigest: digest,
	}, nil
}

func pointerStrictlyContains(
	parent jsondocument.Pointer,
	child jsondocument.Pointer,
) bool {
	parentTokens := parent.Tokens()
	childTokens := child.Tokens()
	if len(parentTokens) >= len(childTokens) {
		return false
	}
	for index := range parentTokens {
		if parentTokens[index] != childTokens[index] {
			return false
		}
	}
	return true
}

func validateMaterializationConnection(
	transitions []Transition,
	parsed parsedSecretMaterialization,
) error {
	for _, transition := range transitions {
		if !containsString(transition.ResourceIDs, parsed.recipe.ResourceID) {
			continue
		}
		if parsed.recipe.FileTarget.Valid() {
			if validateSecretFileConnection(transition, parsed) {
				return nil
			}
			break
		}
		config, configFound := transitionMutation(
			transition,
			parsed.recipe.ConfigTarget,
		)
		registry, registryFound := transitionMutation(
			transition,
			parsed.recipe.RegistryTarget,
		)
		if !configFound || !registryFound {
			break
		}
		return validateMaterializationPlaceholders(config, registry, parsed)
	}
	return errors.New("deferred secret materialization is disconnected")
}

func transitionMutation(
	transition Transition,
	target domain.Location,
) (FileMutation, bool) {
	for _, mutation := range transition.Mutations {
		if mutation.Target == target {
			return mutation, true
		}
	}
	return FileMutation{}, false
}

func validateMaterializationPlaceholders(
	config FileMutation,
	registry FileMutation,
	parsed parsedSecretMaterialization,
) error {
	if !config.After.Exists || !registry.After.Exists {
		return errors.New("deferred secret target is absent")
	}
	configDocument, configErr := jsondocument.Parse(config.After.Content)
	registryDocument, registryErr := jsondocument.Parse(registry.After.Content)
	if configErr != nil || registryErr != nil {
		return errors.New("deferred secret target is not valid JSON")
	}
	value, valueStatus := configDocument.Lookup(parsed.configValue)
	digest, digestStatus := registryDocument.Lookup(parsed.registryDigest)
	encodedDigest, _ := json.Marshal(DeferredSecretDigestPlaceholder)
	if valueStatus != jsondocument.Found ||
		value != DeferredSecretJSONPlaceholder ||
		digestStatus != jsondocument.Found ||
		digest != string(encodedDigest) {
		return errors.New("deferred secret placeholder is missing")
	}
	if _, status := configDocument.Lookup(parsed.configEntry); status != jsondocument.Found {
		return errors.New("deferred secret managed entry is missing")
	}
	return nil
}

func materializationsOverlap(
	left parsedSecretMaterialization,
	right parsedSecretMaterialization,
) bool {
	if left.recipe.FileTarget.Valid() || right.recipe.FileTarget.Valid() {
		return secretFileMaterializationsOverlap(left, right)
	}
	if left.recipe.ConfigTarget == right.recipe.ConfigTarget &&
		(jsondocument.Overlaps(left.configEntry, right.configEntry) ||
			jsondocument.Overlaps(left.configValue, right.configValue)) {
		return true
	}
	if left.recipe.RegistryTarget == right.recipe.RegistryTarget &&
		jsondocument.Overlaps(left.registryDigest, right.registryDigest) {
		return true
	}
	if left.recipe.ConfigTarget == right.recipe.RegistryTarget &&
		jsondocument.Overlaps(left.configEntry, right.registryDigest) {
		return true
	}
	return right.recipe.ConfigTarget == left.recipe.RegistryTarget &&
		jsondocument.Overlaps(right.configEntry, left.registryDigest)
}

func containsString(values []string, expected string) bool {
	for _, value := range values {
		if value == expected {
			return true
		}
	}
	return false
}

func (plan PreparedPlan) MaterializeSecrets(
	resolver SecretResolver,
) (PreparedPlan, error) {
	if len(plan.materializations) == 0 {
		return NewPreparedPlanWithMaterializations(
			plan.Transitions(),
			plan.Preconditions(),
			nil,
		)
	}
	if resolver == nil {
		return PreparedPlan{}, errors.New("deferred secret resolver is unavailable")
	}
	transitions := plan.Transitions()
	for _, recipe := range plan.materializations {
		if err := materializeSecret(transitions, recipe, resolver); err != nil {
			return PreparedPlan{}, err
		}
	}
	return NewPreparedPlanWithMaterializations(
		transitions,
		plan.Preconditions(),
		nil,
	)
}

func materializeSecret(
	transitions []Transition,
	recipe SecretMaterializationRecipe,
	resolver SecretResolver,
) error {
	secret, err := resolver.ResolveSecret(recipe.SecretReference)
	if err != nil {
		return errors.New("resolve deferred secret failed")
	}
	if secret == "" {
		return errors.New("resolved deferred secret is empty")
	}
	if recipe.FileTarget.Valid() {
		return materializeSecretFile(transitions, recipe, secret)
	}
	parsed, _ := parseSecretMaterialization(recipe)
	config, registry := materializationMutations(transitions, recipe)
	configDocument, _ := jsondocument.Parse(config.After.Content)
	encodedSecret, _ := json.Marshal(secret)
	configDocument, err = configDocument.Set(parsed.configValue, encodedSecret)
	if err != nil {
		return errors.New("materialize deferred secret value failed")
	}
	entry, status := configDocument.Lookup(parsed.configEntry)
	if status != jsondocument.Found {
		return errors.New("materialize deferred secret entry failed")
	}
	sum := sha256.Sum256([]byte(entry))
	registryDocument, _ := jsondocument.Parse(registry.After.Content)
	encodedDigest, _ := json.Marshal(hex.EncodeToString(sum[:]))
	registryDocument, err = registryDocument.Set(
		parsed.registryDigest,
		encodedDigest,
	)
	if err != nil {
		return errors.New("materialize deferred secret digest failed")
	}
	if !materializationReplaced(configDocument, registryDocument, parsed) {
		return errors.New("deferred secret placeholders remain")
	}
	config.After.Content = configDocument.Indented()
	registry.After.Content = registryDocument.Indented()
	return nil
}

func materializationMutations(
	transitions []Transition,
	recipe SecretMaterializationRecipe,
) (*FileMutation, *FileMutation) {
	for transitionIndex := range transitions {
		transition := &transitions[transitionIndex]
		if !containsString(transition.ResourceIDs, recipe.ResourceID) {
			continue
		}
		var config *FileMutation
		var registry *FileMutation
		for mutationIndex := range transition.Mutations {
			mutation := &transition.Mutations[mutationIndex]
			if mutation.Target == recipe.ConfigTarget {
				config = mutation
			}
			if mutation.Target == recipe.RegistryTarget {
				registry = mutation
			}
		}
		return config, registry
	}
	return nil, nil
}

func materializationReplaced(
	config jsondocument.Document,
	registry jsondocument.Document,
	parsed parsedSecretMaterialization,
) bool {
	value, valueStatus := config.Lookup(parsed.configValue)
	digest, digestStatus := registry.Lookup(parsed.registryDigest)
	encodedDigest, _ := json.Marshal(DeferredSecretDigestPlaceholder)
	return valueStatus == jsondocument.Found &&
		value != DeferredSecretJSONPlaceholder &&
		digestStatus == jsondocument.Found &&
		digest != string(encodedDigest)
}
