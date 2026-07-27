package credentialcatalog

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
	"unicode"

	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

var identifierPattern = regexp.MustCompile(
	`^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`,
)

func validateDefinitions(
	services []ServiceDefinition,
	mcp mcpcatalog.Catalog,
) error {
	if len(services) == 0 {
		return fmt.Errorf("credential definitions must contain a service")
	}
	ids := make([]string, len(services))
	for index, service := range services {
		ids[index] = string(service.ID)
		if err := validateService(service, mcp); err != nil {
			return fmt.Errorf("service %q: %w", service.ID, err)
		}
	}
	if !sortedUnique(ids) {
		return fmt.Errorf("credential services must be sorted with unique ids")
	}
	return nil
}

func validateService(
	service ServiceDefinition,
	mcp mcpcatalog.Catalog,
) error {
	if !validIdentifier(string(service.ID)) ||
		!validText(service.Name, 80) ||
		!validText(service.Summary, 240) {
		return fmt.Errorf("invalid identity or description")
	}
	if err := validateSource(service.Source, mcp); err != nil {
		return err
	}
	if len(service.CredentialRoles) == 0 {
		return fmt.Errorf("service must define a credential role")
	}
	ids := make([]string, len(service.CredentialRoles))
	for index, role := range service.CredentialRoles {
		ids[index] = string(role.ID)
		if !validIdentifier(string(role.ID)) ||
			!validText(role.Name, 80) ||
			!validText(role.Purpose, 240) ||
			!validText(role.Acquisition, 240) {
			return fmt.Errorf("credential role %q is invalid", role.ID)
		}
	}
	if !sortedUnique(ids) {
		return fmt.Errorf("credential roles must be sorted with unique ids")
	}
	return nil
}

func validateSource(source SourceReference, mcp mcpcatalog.Catalog) error {
	switch source.Kind {
	case SourceStandalone:
		if source.ServerID != "" ||
			source.ProfileID != "" ||
			source.CredentialKind != "" {
			return fmt.Errorf("standalone source must not name an MCP profile")
		}
	case SourceMCPProfile:
		server, exists := mcp.Server(mcpcatalog.ServerID(source.ServerID))
		if !exists {
			return fmt.Errorf("MCP source server %q does not exist", source.ServerID)
		}
		profile, exists := server.Profile(mcpcatalog.ProfileID(source.ProfileID))
		if !exists {
			return fmt.Errorf("MCP source profile %q does not exist", source.ProfileID)
		}
		if !profileProvidesCredential(profile, source.CredentialKind) {
			return fmt.Errorf("MCP source profile credential kind does not match")
		}
	default:
		return fmt.Errorf("unsupported source kind %q", source.Kind)
	}
	return nil
}

func profileProvidesCredential(
	profile mcpcatalog.Profile,
	kind CredentialKind,
) bool {
	if kind != CredentialAPIKey {
		return false
	}
	if string(profile.Authentication.Kind) == string(kind) {
		return true
	}
	return profile.ServiceCredential != nil &&
		string(profile.ServiceCredential.Kind) == string(kind)
}

func validIdentifier(value string) bool {
	return identifierPattern.MatchString(value)
}

func validText(value string, maximum int) bool {
	return value == strings.TrimSpace(value) &&
		value != "" &&
		len(value) <= maximum &&
		!strings.ContainsFunc(value, unicode.IsControl)
}

func sortedUnique(values []string) bool {
	return sort.StringsAreSorted(values) && unique(values)
}

func unique(values []string) bool {
	for index := 1; index < len(values); index++ {
		if values[index-1] == values[index] {
			return false
		}
	}
	return true
}
