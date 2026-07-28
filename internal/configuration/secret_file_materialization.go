package configuration

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

func parseSecretFileMaterialization(
	recipe SecretMaterializationRecipe,
) (parsedSecretMaterialization, error) {
	if recipe.ConfigTarget.Valid() || !recipe.RegistryTarget.Valid() ||
		!recipe.FileTarget.Path.Portable() ||
		recipe.FileTarget == recipe.RegistryTarget {
		return parsedSecretMaterialization{}, errors.New(
			"invalid deferred secret file materialization",
		)
	}
	digest, err := jsondocument.ParsePointer(recipe.RegistryDigestPointer)
	if err != nil {
		return parsedSecretMaterialization{}, errors.New(
			"invalid deferred secret file materialization pointer",
		)
	}
	return parsedSecretMaterialization{
		recipe:         recipe,
		registryDigest: digest,
	}, nil
}

func validateSecretFileConnection(
	transition Transition,
	parsed parsedSecretMaterialization,
) bool {
	file, found := transitionMutation(transition, parsed.recipe.FileTarget)
	registry, registryFound := transitionMutation(
		transition,
		parsed.recipe.RegistryTarget,
	)
	if !found || !file.After.Exists ||
		string(file.After.Content) != DeferredSecretFilePlaceholder ||
		!registryFound || !registry.After.Exists {
		return false
	}
	document, err := jsondocument.Parse(registry.After.Content)
	if err != nil {
		return false
	}
	digest, status := document.Lookup(parsed.registryDigest)
	encodedPlaceholder, _ := json.Marshal(DeferredSecretDigestPlaceholder)
	return status == jsondocument.Found &&
		digest == string(encodedPlaceholder)
}

func secretFileMaterializationsOverlap(
	left parsedSecretMaterialization,
	right parsedSecretMaterialization,
) bool {
	if left.recipe.FileTarget.Valid() && right.recipe.FileTarget.Valid() {
		return locationsOverlap(left.recipe.FileTarget, right.recipe.FileTarget) ||
			left.recipe.RegistryTarget == right.recipe.RegistryTarget &&
				jsondocument.Overlaps(left.registryDigest, right.registryDigest)
	}
	file, embedded := left, right
	if !file.recipe.FileTarget.Valid() {
		file, embedded = right, left
	}
	return file.recipe.FileTarget == embedded.recipe.ConfigTarget ||
		file.recipe.FileTarget == embedded.recipe.RegistryTarget ||
		file.recipe.RegistryTarget == embedded.recipe.ConfigTarget &&
			jsondocument.Overlaps(file.registryDigest, embedded.configEntry) ||
		file.recipe.RegistryTarget == embedded.recipe.RegistryTarget &&
			jsondocument.Overlaps(file.registryDigest, embedded.registryDigest)
}

func materializeSecretFile(
	transitions []Transition,
	recipe SecretMaterializationRecipe,
	secret string,
) error {
	if strings.ContainsAny(secret, "\x00\r\n") {
		return errors.New("resolved deferred secret contains invalid bytes")
	}
	sum := sha256.Sum256([]byte(secret))
	encodedDigest, _ := json.Marshal(hex.EncodeToString(sum[:]))
	for transitionIndex := range transitions {
		transition := &transitions[transitionIndex]
		if !containsString(transition.ResourceIDs, recipe.ResourceID) {
			continue
		}
		file, registry := materializationFileMutations(transition, recipe)
		if file == nil || registry == nil {
			break
		}
		document, err := jsondocument.Parse(registry.After.Content)
		if err != nil {
			break
		}
		parsed, _ := parseSecretMaterialization(recipe)
		document, err = document.Set(parsed.registryDigest, encodedDigest)
		if err != nil {
			break
		}
		file.After.Content = []byte(secret)
		registry.After.Content = document.Indented()
		return nil
	}
	return errors.New("deferred secret file target is unavailable")
}

func materializationFileMutations(
	transition *Transition,
	recipe SecretMaterializationRecipe,
) (*FileMutation, *FileMutation) {
	var file *FileMutation
	var registry *FileMutation
	for index := range transition.Mutations {
		mutation := &transition.Mutations[index]
		if mutation.Target == recipe.FileTarget {
			file = mutation
		}
		if mutation.Target == recipe.RegistryTarget {
			registry = mutation
		}
	}
	return file, registry
}
