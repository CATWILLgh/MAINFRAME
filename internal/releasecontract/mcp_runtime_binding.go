package releasecontract

import (
	"encoding/json"
	"fmt"
	"regexp"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

var mcpSecretEnvironmentPattern = regexp.MustCompile(`^[A-Z_][A-Z0-9_]*$`)

const context7APIKeyHeader = "CONTEXT7_API_KEY"
const mcpDeferredSecretPlaceholder = "$MAINFRAME_DEFERRED_SECRET_VALUE"

func BindMCPProjectionProfile(
	projection MCPProjection,
	catalog mcpcatalog.Catalog,
	profileID mcpcatalog.ProfileID,
	secretEnvironmentVariable string,
) (MCPProjection, error) {
	if err := validateLoadedMCPProjection(projection, catalog); err != nil {
		return MCPProjection{}, fmt.Errorf("validate base MCP projection: %w", err)
	}
	if profileID == projection.ProfileID && secretEnvironmentVariable == "" {
		return projection, nil
	}
	if projection.ServerID != "context7" ||
		!credentialBindingCodecSupported(projection) {
		return MCPProjection{}, fmt.Errorf(
			"credential-bound MCP projection is unsupported for component %q",
			projection.ComponentID,
		)
	}
	server, exists := catalog.Server(projection.ServerID)
	if !exists {
		return MCPProjection{}, fmt.Errorf(
			"unknown MCP server %q",
			projection.ServerID,
		)
	}
	profile, exists := server.Profile(profileID)
	if !exists {
		return MCPProjection{}, fmt.Errorf(
			"unknown MCP profile %q",
			profileID,
		)
	}
	desired, err := encodeCredentialEntry(
		projection,
		profile,
		secretEnvironmentVariable,
	)
	if err != nil {
		return MCPProjection{}, err
	}
	bound := projection
	bound.ProfileID = profile.ID
	bound.DesiredEntry = desired
	return bound, nil
}

func credentialBindingCodecSupported(projection MCPProjection) bool {
	return projection.ComponentID == domain.ComponentOpenCode &&
		projection.Codec == MCPProjectionOpenCodeRemote ||
		projection.ComponentID == domain.ComponentAntigravity2 &&
			projection.Codec == MCPProjectionAntigravityGlobalHTTP
}

func encodeCredentialEntry(
	projection MCPProjection,
	profile mcpcatalog.Profile,
	secretEnvironmentVariable string,
) (string, error) {
	if projection.ComponentID == domain.ComponentOpenCode {
		if err := validateCredentialProfile(
			profile,
			domain.ComponentOpenCode,
			secretEnvironmentVariable,
		); err != nil {
			return "", err
		}
		return encodeOpenCodeCredentialEntry(profile, secretEnvironmentVariable)
	}
	if err := validateCredentialProfile(
		profile,
		domain.ComponentAntigravity2,
		secretEnvironmentVariable,
	); err != nil {
		return "", err
	}
	return encodeAntigravityCredentialEntry(profile)
}

func validateOpenCodeCredentialProfile(
	profile mcpcatalog.Profile,
	secretEnvironmentVariable string,
) error {
	return validateCredentialProfile(
		profile,
		domain.ComponentOpenCode,
		secretEnvironmentVariable,
	)
}

func validateCredentialProfile(
	profile mcpcatalog.Profile,
	component domain.ComponentID,
	secretEnvironmentVariable string,
) error {
	status, reason := profile.Support(component)
	if status != mcpcatalog.Supported {
		return fmt.Errorf("profile is unsupported: %s", reason)
	}
	authentication := profile.Authentication
	if profile.Transport != mcpcatalog.TransportStreamableHTTP ||
		profile.Endpoint == "" ||
		authentication.Kind != mcpcatalog.AuthenticationAPIKey ||
		authentication.Placement != mcpcatalog.PlacementHeader ||
		authentication.EnvironmentVariable != context7APIKeyHeader ||
		profile.ServiceCredential != nil {
		return fmt.Errorf(
			"profile is incompatible with %s credential binding",
			component,
		)
	}
	if !mcpSecretEnvironmentPattern.MatchString(secretEnvironmentVariable) {
		return fmt.Errorf("invalid secret environment-variable reference")
	}
	return nil
}

func encodeOpenCodeCredentialEntry(
	profile mcpcatalog.Profile,
	secretEnvironmentVariable string,
) (string, error) {
	contract, _ := mcpProjectionContract(
		domain.ComponentOpenCode,
		MCPProjectionOpenCodeRemote,
	)
	entry := struct {
		Headers map[string]string `json:"headers"`
		Type    string            `json:"type"`
		URL     string            `json:"url"`
	}{
		Headers: map[string]string{
			context7APIKeyHeader: "{file:" +
				string(contract.secretTarget.Path) + "}",
		},
		Type: "remote",
		URL:  profile.Endpoint,
	}
	payload, err := json.Marshal(entry)
	if err != nil {
		return "", fmt.Errorf("encode OpenCode credential-bound MCP entry: %w", err)
	}
	return string(payload), nil
}

func encodeAntigravityCredentialEntry(
	profile mcpcatalog.Profile,
) (string, error) {
	entry := struct {
		Headers   map[string]string `json:"headers"`
		ServerURL string            `json:"serverUrl"`
	}{
		Headers: map[string]string{
			context7APIKeyHeader: mcpDeferredSecretPlaceholder,
		},
		ServerURL: profile.Endpoint,
	}
	payload, err := json.Marshal(entry)
	if err != nil {
		return "", fmt.Errorf(
			"encode Antigravity credential-bound MCP entry: %w",
			err,
		)
	}
	return string(payload), nil
}
