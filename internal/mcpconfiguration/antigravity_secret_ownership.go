package mcpconfiguration

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"regexp"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const antigravitySecretRegistryFormat = "antigravity-literal-secret-v1"
const antigravitySecretBackend = "environment"

var antigravitySecretReferencePattern = regexp.MustCompile(
	`^[A-Z_][A-Z0-9_]*$`,
)
var antigravitySecretDigestPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)

type antigravitySecretRegistryEntry struct {
	Format          string `json:"format"`
	Profile         string `json:"profile"`
	SecretBackend   string `json:"secret_backend"`
	SecretReference string `json:"secret_reference"`
	EntrySHA256     string `json:"entry_sha256"`
}

func encodeAntigravitySecretRegistryEntry(
	projection releasecontract.MCPProjection,
	binding CredentialBinding,
) (string, error) {
	entry := antigravitySecretRegistryEntry{
		Format:          antigravitySecretRegistryFormat,
		Profile:         string(projection.ProfileID),
		SecretBackend:   antigravitySecretBackend,
		SecretReference: binding.EnvironmentVariable,
		EntrySHA256:     configuration.DeferredSecretDigestPlaceholder,
	}
	if err := validateAntigravitySecretRegistryEntry(entry, true); err != nil {
		return "", err
	}
	payload, err := json.Marshal(entry)
	if err != nil {
		return "", fmt.Errorf("encode Antigravity MCP ownership metadata: %w", err)
	}
	return string(payload), nil
}

func decodeAntigravitySecretRegistryEntry(
	raw string,
	existing targetEntryObservation,
) (string, bool, bool, error) {
	var object map[string]json.RawMessage
	if err := json.Unmarshal([]byte(raw), &object); err != nil {
		return "", false, false, nil
	}
	format, exists := object["format"]
	if !exists || string(format) != `"`+antigravitySecretRegistryFormat+`"` {
		return "", false, false, nil
	}
	if len(object) != 5 {
		return "", false, true, fmt.Errorf(
			"Antigravity MCP ownership metadata is invalid",
		)
	}
	var entry antigravitySecretRegistryEntry
	if err := json.Unmarshal([]byte(raw), &entry); err != nil ||
		validateAntigravitySecretRegistryEntry(entry, false) != nil {
		return "", false, true, fmt.Errorf(
			"Antigravity MCP ownership metadata is invalid",
		)
	}
	if !existing.present || !existing.comparable {
		return raw, false, true, nil
	}
	digest := sha256.Sum256([]byte(existing.raw))
	if hex.EncodeToString(digest[:]) != entry.EntrySHA256 {
		return raw, false, true, nil
	}
	return existing.raw, true, true, nil
}

func validateAntigravitySecretRegistryEntry(
	entry antigravitySecretRegistryEntry,
	allowPlaceholder bool,
) error {
	digestValid := antigravitySecretDigestPattern.MatchString(entry.EntrySHA256)
	if allowPlaceholder {
		digestValid = entry.EntrySHA256 ==
			configuration.DeferredSecretDigestPlaceholder
	}
	if entry.Format != antigravitySecretRegistryFormat ||
		entry.Profile != "remote-api-key" ||
		entry.SecretBackend != antigravitySecretBackend ||
		!antigravitySecretReferencePattern.MatchString(entry.SecretReference) ||
		!digestValid {
		return fmt.Errorf("invalid Antigravity MCP ownership metadata")
	}
	return nil
}

func (builder *mcpPreparation) secretMaterializations(
	plan Plan,
) []configuration.SecretMaterializationRecipe {
	var result []configuration.SecretMaterializationRecipe
	for _, intent := range plan.Intents {
		if intent.ComponentID == domain.ComponentOpenCode &&
			intent.ProfileID == "remote-api-key" &&
			(intent.Kind == IntentAdd || intent.Kind == IntentUpdate) {
			projection, projectionExists := builder.inspection.projectionByID(
				intent.ProjectionID,
			)
			binding, bindingExists := builder.inspection.credentials[intent.ProjectionID]
			if projectionExists && bindingExists {
				result = append(result, configuration.SecretMaterializationRecipe{
					ResourceID:     projection.ID,
					FileTarget:     projection.SecretTarget(),
					RegistryTarget: projection.RegistryTarget,
					RegistryDigestPointer: projection.RegistryEntriesPointer +
						"/" + projection.EntryKey + "/secret_file_sha256",
					SecretReference: binding.EnvironmentVariable,
				})
			}
			continue
		}
		if intent.ComponentID != domain.ComponentAntigravity2 ||
			intent.ProfileID != "remote-api-key" ||
			(intent.Kind != IntentAdd && intent.Kind != IntentUpdate) {
			continue
		}
		projection, projectionExists := builder.inspection.projectionByID(
			intent.ProjectionID,
		)
		binding, bindingExists := builder.inspection.credentials[intent.ProjectionID]
		if !projectionExists || !bindingExists {
			continue
		}
		entryPointer := projection.MapPointer + "/" + projection.EntryKey
		result = append(result, configuration.SecretMaterializationRecipe{
			ResourceID:         projection.ID,
			ConfigTarget:       projection.Target,
			ConfigEntryPointer: entryPointer,
			ConfigValuePointer: entryPointer + "/headers/CONTEXT7_API_KEY",
			RegistryTarget:     projection.RegistryTarget,
			RegistryDigestPointer: projection.RegistryEntriesPointer +
				"/" + projection.EntryKey + "/entry_sha256",
			SecretReference: binding.EnvironmentVariable,
		})
	}
	return result
}
