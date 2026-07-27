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
	if projection.ComponentID != domain.ComponentOpenCode ||
		projection.Codec != MCPProjectionOpenCodeRemote ||
		projection.ServerID != "context7" {
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
	if err := validateOpenCodeCredentialProfile(
		profile,
		secretEnvironmentVariable,
	); err != nil {
		return MCPProjection{}, err
	}
	desired, err := encodeOpenCodeCredentialEntry(
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

func validateOpenCodeCredentialProfile(
	profile mcpcatalog.Profile,
	secretEnvironmentVariable string,
) error {
	status, reason := profile.Support(domain.ComponentOpenCode)
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
		return fmt.Errorf("profile is incompatible with OpenCode credential binding")
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
	entry := struct {
		Headers map[string]string `json:"headers"`
		Type    string            `json:"type"`
		URL     string            `json:"url"`
	}{
		Headers: map[string]string{
			context7APIKeyHeader: "{env:" + secretEnvironmentVariable + "}",
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
